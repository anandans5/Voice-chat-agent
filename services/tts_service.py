import asyncio
import base64
import logging
import aiohttp
from typing import AsyncGenerator, Optional
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from config import settings, get_settings

logger = logging.getLogger("tts_service")

class ElevenLabsTTSService:
    """
    Manages text-to-speech streaming via ElevenLabs API.
    Streams back audio byte chunks for each input text sentence/clause.
    """
    def __init__(self):
        self.session: Optional[aiohttp.ClientSession] = None

    async def _get_session(self) -> aiohttp.ClientSession:
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession()
        return self.session

    async def stream_sentence_tts(self, text: str) -> AsyncGenerator[bytes, None]:
        """
        Sends a single sentence/clause to ElevenLabs streaming endpoint
        and yields raw audio byte chunks (mp3) as they stream back.
        """
        if not text.strip():
            return

        cfg = get_settings()
        if not cfg.elevenlabs_api_key or cfg.elevenlabs_api_key.startswith("your_"):
            logger.warning("ELEVENLABS_API_KEY is missing or using placeholder.")
            return

        url = f"https://api.elevenlabs.io/v1/text-to-speech/{cfg.elevenlabs_voice_id}/stream"
        headers = {
            "xi-api-key": cfg.elevenlabs_api_key,
            "Content-Type": "application/json",
            "Accept": "audio/mpeg",
        }
        payload = {
            "text": text,
            "model_id": cfg.elevenlabs_model_id,
            "voice_settings": {
                "stability": 0.85,
                "similarity_boost": 0.90,
                "style": 0.0,
                "use_speaker_boost": True,
                "speed": 0.70
            }
        }

        session = await self._get_session()

        try:
            async with session.post(url, json=payload, headers=headers) as response:
                if response.status != 200:
                    error_text = await response.text()
                    logger.error(f"ElevenLabs TTS Error ({response.status}): {error_text}")
                    return

                # Stream audio bytes in 1KB-4KB chunks
                async for chunk in response.content.iter_chunked(2048):
                    if chunk:
                        yield chunk

        except asyncio.CancelledError:
            logger.info("ElevenLabs TTS streaming task was cancelled due to barge-in.")
            raise
        except Exception as e:
            logger.error(f"Failed to stream TTS from ElevenLabs: {e}")

    async def close(self):
        """Closes the HTTP client session."""
        if self.session and not self.session.closed:
            await self.session.close()
            self.session = None
