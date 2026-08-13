import asyncio
import logging
from typing import AsyncGenerator, List, Dict, Optional
from openai import AsyncOpenAI, APIConnectionError, RateLimitError
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from config import settings, get_settings

logger = logging.getLogger("llm_service")

class OpenAILLMService:
    def __init__(self):
        self.client: Optional[AsyncOpenAI] = None
        self.history: List[Dict[str, str]] = []
        self._init_client()

    def _init_client(self):
        current_settings = get_settings()
        if current_settings.openai_api_key and not current_settings.openai_api_key.startswith("your_"):
            kwargs = {"api_key": current_settings.openai_api_key}
            if current_settings.openai_base_url:
                kwargs["base_url"] = current_settings.openai_base_url
            self.client = AsyncOpenAI(**kwargs)
        else:
            self.client = None
            logger.warning("OPENAI_API_KEY is not set or using placeholder.")

        self.history = [{"role": "system", "content": current_settings.system_prompt}]

    def reset_history(self):
        current_settings = get_settings()
        self.history = [{"role": "system", "content": current_settings.system_prompt}]

    def update_system_prompt(self, new_prompt: str):
        if self.history and self.history[0]["role"] == "system":
            self.history[0]["content"] = new_prompt
        else:
            self.history.insert(0, {"role": "system", "content": new_prompt})

    async def stream_response(self, user_text: str) -> AsyncGenerator[str, None]:
        if not self.client:
            self._init_client()
            if not self.client:
                yield "[Error: OpenAI API Key is missing or invalid. Please configure .env file.]"
                return

        self.history.append({"role": "user", "content": user_text})
        full_assistant_reply = []

        try:
            stream = await self._create_completion_with_retry()

            async for chunk in stream:
                if chunk.choices and len(chunk.choices) > 0:
                    delta = chunk.choices[0].delta.content or ""
                    if delta:
                        full_assistant_reply.append(delta)
                        yield delta

            complete_text = "".join(full_assistant_reply).strip()
            if complete_text:
                self.history.append({"role": "assistant", "content": complete_text})

        except asyncio.CancelledError:
            logger.info("OpenAI LLM streaming task was cancelled due to barge-in/interruption.")
            partial_text = "".join(full_assistant_reply).strip()
            if partial_text:
                self.history.append({"role": "assistant", "content": f"{partial_text} [interrupted]"})
            raise

        except Exception as e:
            logger.error(f"Error during OpenAI streaming response: {e}")
            yield f" [Error generating response: {e}]"

    @retry(
        reraise=True,
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception_type((APIConnectionError, RateLimitError))
    )
    async def _create_completion_with_retry(self):
        current_settings = get_settings()
        return await self.client.chat.completions.create(
            model=current_settings.openai_model,
            messages=self.history,
            stream=True,
            temperature=0.7,
        )
