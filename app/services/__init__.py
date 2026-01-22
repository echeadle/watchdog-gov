"""Service clients for external APIs and AI agent."""

from app.services.congress_api import congress_client
from app.services.fec_api import fec_client
from app.services.news_api import news_client

__all__ = [
    "congress_client",
    "fec_client",
    "news_client",
]
