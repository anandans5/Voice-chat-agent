import os
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field

class Settings(BaseSettings):
    deepgram_api_key: str = Field(default="", env="DEEPGRAM_API_KEY")
    openai_api_key: str = Field(default="", env="OPENAI_API_KEY")
    elevenlabs_api_key: str = Field(default="", env="ELEVENLABS_API_KEY")

    elevenlabs_voice_id: str = Field(default="EXAVITQu4vr4xnSDxMaL", env="ELEVENLABS_VOICE_ID")
    elevenlabs_model_id: str = Field(default="eleven_multilingual_v2", env="ELEVENLABS_MODEL_ID")

    openai_model: str = Field(default="gpt-4o-mini", env="OPENAI_MODEL")
    openai_base_url: str = Field(default="", env="OPENAI_BASE_URL")
    system_prompt: str = Field(
        default="You are a helpful, concise, and conversational AI voice assistant. Keep your answers brief (1-3 sentences), warm, and engaging, optimized for natural spoken interaction.",
        env="SYSTEM_PROMPT"
    )

    deepgram_model: str = Field(default="nova-2", env="DEEPGRAM_MODEL")

    host: str = Field(default="0.0.0.0", env="HOST")
    port: int = Field(default=8050, env="PORT")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

def get_settings() -> Settings:
    return Settings()

settings = get_settings()
