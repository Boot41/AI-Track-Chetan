from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

APP_DIR = Path(__file__).resolve().parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=APP_DIR / ".env", extra="ignore")

    agent_model: str = "gemini-2.5-flash"
    google_api_key: str = ""
    google_genai_use_vertexai: bool = False


@lru_cache
def get_settings() -> Settings:
    return Settings()
