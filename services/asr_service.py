import asyncio
import json
import logging
import websockets
from typing import Callable, Optional, Awaitable
from config import settings, get_settings

logger = logging.getLogger("asr_service")

class DeepgramASRService:
    """
    Manages live streaming transcription with Deepgram via WebSockets.
    Forwards audio chunks to Deepgram, sends KeepAlive frames, parses interim/final transcriptions,
    and supports speech_started VAD events for barge-in detection.
    """
    def __init__(
        self,
        on_transcript: Callable[[str, bool, bool], Awaitable[None]],
        on_speech_started: Optional[Callable[[], Awaitable[None]]] = None,
        on_error: Optional[Callable[[str], Awaitable[None]]] = None,
    ):
        self.on_transcript = on_transcript
        self.on_speech_started = on_speech_started
        self.on_error = on_error
        self.ws: Optional[websockets.WebSocketClientProtocol] = None
        self.listen_task: Optional[asyncio.Task] = None
        self.keepalive_task: Optional[asyncio.Task] = None
        self.is_running = False

    async def start(self):
        """Establishes WebSocket connection to Deepgram with exponential backoff retry."""
        cfg = get_settings()
        if not cfg.deepgram_api_key or cfg.deepgram_api_key.startswith("your_"):
            logger.warning("DEEPGRAM_API_KEY is not set or using placeholder.")
            if self.on_error:
                await self.on_error("Deepgram API Key is missing or invalid.")
            return

        self.is_running = True
        url = (
            f"wss://api.deepgram.com/v1/listen?"
            f"model={cfg.deepgram_model}&"
            f"smart_format=true&"
            f"interim_results=true&"
            f"endpointing=300&"
            f"vad_events=true"
        )
        headers = {"Authorization": f"Token {cfg.deepgram_api_key}"}

        max_retries = 5
        base_delay = 1.0

        for attempt in range(1, max_retries + 1):
            if not self.is_running:
                return
            try:
                logger.info(f"Connecting to Deepgram WebSocket (Attempt {attempt})...")
                try:
                    self.ws = await websockets.connect(url, additional_headers=headers)
                except TypeError:
                    self.ws = await websockets.connect(url, extra_headers=headers)
                logger.info("Connected to Deepgram ASR WebSocket.")
                self.listen_task = asyncio.create_task(self._listen_loop())
                self.keepalive_task = asyncio.create_task(self._keepalive_loop())
                return
            except Exception as e:
                logger.error(f"Failed to connect to Deepgram (attempt {attempt}): {e}")
                if attempt == max_retries:
                    if self.on_error:
                        await self.on_error(f"Deepgram connection failed after {max_retries} attempts: {e}")
                    return
                await asyncio.sleep(base_delay * (2 ** (attempt - 1)))

    async def send_audio(self, chunk: bytes):
        """Sends an audio byte chunk to Deepgram, reconnecting if needed."""
        if not self.is_running or not self.ws:
            await self.start()

        if self.ws:
            try:
                await self.ws.send(chunk)
            except websockets.ConnectionClosed:
                logger.warning("Deepgram WS closed unexpectedly while sending audio. Attempting reconnect...")
                await self.reconnect()
                if self.ws:
                    try:
                        await self.ws.send(chunk)
                    except Exception:
                        pass
            except Exception as e:
                logger.error(f"Error sending audio to Deepgram: {e}")

    async def _keepalive_loop(self):
        """Sends KeepAlive ping frames to Deepgram every 5 seconds to prevent stream timeout."""
        try:
            while self.is_running and self.ws:
                await asyncio.sleep(5)
                if self.ws and self.is_running:
                    try:
                        await self.ws.send(json.dumps({"type": "KeepAlive"}))
                    except websockets.ConnectionClosed:
                        break
                    except Exception as e:
                        logger.debug(f"Keepalive send warning: {e}")
        except asyncio.CancelledError:
            pass

    async def _listen_loop(self):
        """Receives and processes incoming WebSocket messages from Deepgram."""
        try:
            async for message in self.ws:
                if not self.is_running:
                    break
                data = json.loads(message)
                msg_type = data.get("type")

                if msg_type == "Results":
                    channel = data.get("channel", {})
                    alternatives = channel.get("alternatives", [])
                    if alternatives:
                        transcript = alternatives[0].get("transcript", "").strip()
                        is_final = data.get("is_final", False)
                        speech_final = data.get("speech_final", False)
                        logger.info(f"Deepgram Results: transcript='{transcript}', is_final={is_final}, speech_final={speech_final}")
                        if transcript or is_final or speech_final:
                            await self.on_transcript(transcript, is_final, speech_final)

                elif msg_type == "SpeechStarted":
                    logger.debug("VAD SpeechStarted event received from Deepgram.")
                    if self.on_speech_started:
                        await self.on_speech_started()

        except websockets.ConnectionClosedOK:
            logger.info("Deepgram WebSocket closed gracefully.")
        except websockets.ConnectionClosedError as e:
            logger.warning(f"Deepgram WebSocket closed with error: {e}")
            if self.is_running:
                await self.reconnect()
        except Exception as e:
            logger.error(f"Error in Deepgram listen loop: {e}")
            if self.on_error and self.is_running:
                await self.on_error(f"Deepgram stream error: {e}")

    async def reconnect(self):
        """Reconnects to Deepgram if stream was broken unexpectedly."""
        await self.stop()
        if self.is_running:
            await self.start()

    async def stop(self):
        """Gracefully closes Deepgram WebSocket connection."""
        self.is_running = False
        if self.keepalive_task:
            self.keepalive_task.cancel()
            self.keepalive_task = None

        if self.ws:
            try:
                await self.ws.send(json.dumps({"type": "CloseStream"}))
                await self.ws.close()
            except Exception:
                pass
            self.ws = None

        if self.listen_task:
            self.listen_task.cancel()
            self.listen_task = None
        logger.info("Deepgram ASR service stopped.")
