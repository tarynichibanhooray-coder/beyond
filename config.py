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
    anthropic_model: str = "claude-sonnet-4-6"
    mock_mode: bool = True
    prompt_cache: bool = True
    app_base_url: str = "https://inthistimebefore.onrender.com"

    session_duration_seconds: int = 180
    transcript_dir: Path = Field(default=Path("transcripts"))
    # Daily token cap (UTC day).
    token_budget: int = 600_000
    # Comma-separated exactly 3 council member ids (arabi, blake, morrison, kierkegaard)
    council_roster: str = "arabi,morrison,kierkegaard"


settings = Settings()
