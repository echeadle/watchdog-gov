"""Favorite model for user bookmarks (PWA offline support)."""

from datetime import datetime
from typing import Optional

from sqlalchemy import String, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Favorite(Base):
    """User bookmark for a legislator.

    Since there are no user accounts in MVP, favorites are tied to a
    session ID (stored in browser cookie). This allows users to bookmark
    legislators and have them cached for offline PWA viewing.
    """

    __tablename__ = "favorites"

    # Ensure each session can only favorite a legislator once
    __table_args__ = (
        UniqueConstraint("session_id", "legislator_bioguide_id", name="uq_session_legislator"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[str] = mapped_column(String(64), index=True)
    legislator_bioguide_id: Mapped[str] = mapped_column(
        String(10), ForeignKey("legislators.bioguide_id"), index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Optional note/label for the bookmark
    note: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)

    # Relationship to legislator
    legislator: Mapped["Legislator"] = relationship(lazy="selectin")


# Import at bottom to avoid circular imports
from app.models.legislator import Legislator
