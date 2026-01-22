"""Application configuration loaded from environment variables."""

import os
from functools import lru_cache

from dotenv import load_dotenv

load_dotenv()


class Settings:
    """Application settings loaded from environment."""

    def __init__(self):
        self.congress_api_key: str = os.getenv("CONGRESS_API_KEY", "")
        self.fec_api_key: str = os.getenv("FEC_API_KEY", "DEMO_KEY")
        self.news_api_key: str = os.getenv("NEWS_API_KEY", "")
        self.anthropic_api_key: str = os.getenv("ANTHROPIC_API_KEY", "")
        self.secret_key: str = os.getenv("SECRET_KEY", "dev-secret-key")
        self.database_url: str = os.getenv(
            "DATABASE_URL", "sqlite+aiosqlite:///./watchdog.db"
        )

    @property
    def congress_api_base_url(self) -> str:
        return "https://api.congress.gov/v3"

    @property
    def fec_api_base_url(self) -> str:
        return "https://api.open.fec.gov/v1"

    @property
    def news_api_base_url(self) -> str:
        return "https://newsapi.org/v2"


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
