"""News article database model."""

from datetime import datetime
from typing import Optional

from sqlalchemy import String, Text, DateTime
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class NewsArticle(Base):
    """Cached news article from NewsAPI."""

    __tablename__ = "news_articles"

    id: Mapped[int] = mapped_column(primary_key=True)
    legislator_bioguide_id: Mapped[str] = mapped_column(String(10), index=True)

    title: Mapped[str] = mapped_column(Text)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    url: Mapped[str] = mapped_column(Text)
    source_name: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    author: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    image_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    published_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    cached_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
