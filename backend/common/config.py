from functools import lru_cache
from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


PROJECT_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    openai_api_key: str = ""
    openai_base_url: str | None = None
    openai_model_fast: str = ""
    openai_model_strong: str = ""
    deepgram_api_key: str = ""
    deepgram_stt_model: str = "nova-3"
    deepgram_tts_model: str = "aura-2-thalia-en"
    livekit_url: str = "ws://localhost:7880"
    livekit_api_key: str = "devkey"
    livekit_api_secret: str = "secret"
    agent_name: str = "interviewer"
    jwt_secret: str = "change-me"
    jwt_expire_days: int = 7
    internal_secret: str = "change-me-too"
    api_base_url: str = "http://localhost:8000"
    web_origin: str = "http://localhost:5173"
    database_url: str
    data_dir: Path = PROJECT_ROOT / "data"
    max_upload_mb: int = 5
    daily_minutes_limit: int = 60

    @field_validator("data_dir", mode="after")
    @classmethod
    def resolve_data_dir(cls, value: Path) -> Path:
        return value if value.is_absolute() else (PROJECT_ROOT / value).resolve()

    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
