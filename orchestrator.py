import asyncio
import base64
import json
import logging
import re
from typing import Optional
from fastapi import WebSocket

from services.asr_service import DeepgramASRService
from services.llm_service import OpenAILLMService
from services.tts_service import ElevenLabsTTSService

logger = logging.getLogger("orchestrator")

class PipelineOrchestrator:
    PUNCTUATION_SPLIT_REGEX = re.compile(r'(?<=[.!?;\n])\s+')

    def __init__(self, client_ws: WebSocket):
        self.client_ws = client_ws
        self.llm_service = OpenAILLMService()
        self.tts_service = ElevenLabsTTSService()
        self.asr_service: Optional[DeepgramASRService] = None

        self.active_pipeline_task: Optional[asyncio.Task] = None
        self.silence_timer_task: Optional[asyncio.Task] = None
        self.is_assistant_speaking = False
        self.latest_interim_text = ""
        self.turn_lock = asyncio.Lock()

    async def initialize(self):
        self.asr_service = DeepgramASRService(
            on_transcript=self.handle_transcript,
            on_speech_started=self.handle_speech_started,
            on_error=self.handle_asr_error,
        )
        await self.asr_service.start()

    async def send_client_json(self, data: dict):
        try:
            await self.client_ws.send_text(json.dumps(data))
        except Exception as e:
            logger.warning(f"Error sending JSON to browser client: {e}")

    async def handle_audio_chunk(self, chunk: bytes):
        if self.asr_service:
            await self.asr_service.send_audio(chunk)

    async def handle_speech_started(self):
        logger.debug("VAD SpeechStarted detected from Deepgram.")

    async def handle_transcript(self, transcript: str, is_final: bool, speech_final: bool):
        clean_text = transcript.strip()

        if is_final or speech_final:
            target_text = clean_text or self.latest_interim_text
            if target_text:
                await self.finalize_turn(target_text)
        else:
            if clean_text:
                self.latest_interim_text = clean_text
                await self.send_client_json({"type": "user_interim", "text": clean_text})

                if self.silence_timer_task and not self.silence_timer_task.done():
                    self.silence_timer_task.cancel()
                self.silence_timer_task = asyncio.create_task(self._silence_timer(1.0))

                if self.is_assistant_speaking and len(clean_text) >= 2:
                    logger.info(f"Barge-in triggered by interim transcript: '{clean_text}'")
                    await self.trigger_barge_in()

    async def _silence_timer(self, delay: float = 1.0):
        try:
            await asyncio.sleep(delay)
            if self.latest_interim_text:
                logger.info(f"Silence timer triggered turn completion for: '{self.latest_interim_text}'")
                await self.finalize_turn(self.latest_interim_text)
        except asyncio.CancelledError:
            pass

    async def finalize_turn(self, final_text: str):
        if not final_text.strip():
            return
        if self.silence_timer_task and not self.silence_timer_task.done():
            self.silence_timer_task.cancel()
            self.silence_timer_task = None

        self.latest_interim_text = ""
        logger.info(f"Finalized User Turn: '{final_text}'")
        await self.send_client_json({"type": "user_final", "text": final_text})
        await self.cancel_active_pipeline()
        self.active_pipeline_task = asyncio.create_task(self.run_llm_tts_pipeline(final_text))

    async def trigger_barge_in(self):
        logger.info("Barge-in triggered: Cancelling assistant response and clearing client audio buffer.")
        await self.cancel_active_pipeline()
        self.is_assistant_speaking = False
        await self.send_client_json({"type": "barge_in"})

    async def cancel_active_pipeline(self):
        if self.silence_timer_task and not self.silence_timer_task.done():
            self.silence_timer_task.cancel()
            self.silence_timer_task = None

        if self.active_pipeline_task and not self.active_pipeline_task.done():
            self.active_pipeline_task.cancel()
            try:
                await self.active_pipeline_task
            except asyncio.CancelledError:
                pass
            self.active_pipeline_task = None
        self.is_assistant_speaking = False

    async def handle_asr_error(self, error_msg: str):
        logger.error(f"ASR Error: {error_msg}")
        await self.send_client_json({"type": "error", "message": f"ASR Error: {error_msg}"})

    async def run_llm_tts_pipeline(self, user_text: str):
        async with self.turn_lock:
            self.is_assistant_speaking = True
            await self.send_client_json({"type": "assistant_start"})

            buffer = ""
            try:
                async for token in self.llm_service.stream_response(user_text):
                    await self.send_client_json({"type": "assistant_token", "text": token})
                    buffer += token

                    sentences, buffer = self._extract_sentences(buffer)
                    for sentence in sentences:
                        await self._process_and_stream_tts(sentence)

                if buffer.strip():
                    await self._process_and_stream_tts(buffer.strip())

            except asyncio.CancelledError:
                logger.info("Pipeline task cancelled due to barge-in.")
                await self.send_client_json({"type": "assistant_interrupted"})
                raise
            except Exception as e:
                logger.error(f"Error in LLM/TTS pipeline: {e}")
                await self.send_client_json({"type": "error", "message": f"Pipeline Error: {e}"})
            finally:
                self.is_assistant_speaking = False
                await self.send_client_json({"type": "assistant_end"})

    def _extract_sentences(self, text_buffer: str):
        sentences = []
        match = list(re.finditer(r'[.!?;\n]', text_buffer))
        if not match:
            return sentences, text_buffer

        last_end = 0
        for m in match:
            end = m.end()
            sentence = text_buffer[last_end:end].strip()
            if len(sentence) >= 15:
                sentences.append(sentence)
                last_end = end

        remaining = text_buffer[last_end:]
        return sentences, remaining

    async def _process_and_stream_tts(self, sentence: str):
        logger.info(f"Synthesizing TTS for sentence: '{sentence}'")
        async for audio_chunk in self.tts_service.stream_sentence_tts(sentence):
            if audio_chunk:
                b64_audio = base64.b64encode(audio_chunk).decode('utf-8')
                await self.send_client_json({
                    "type": "assistant_audio",
                    "audio": b64_audio,
                    "sentence": sentence
                })

    async def cleanup(self):
        logger.info("Cleaning up PipelineOrchestrator resources...")
        await self.cancel_active_pipeline()
        if self.asr_service:
            await self.asr_service.stop()
            self.asr_service = None
        await self.tts_service.close()
