from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    anthropic_api_key: str = ""
    anthropic_model: str = "claude-3-5-sonnet-20241022"
    mock_mode: bool = True

    session_duration_seconds: int = 180
    transcript_dir: Path = Field(default=Path("transcripts"))


settings = Settings()
