"""Legislator database model."""

from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, String, Text, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Legislator(Base):
    """Cached legislator data from Congress.gov."""

    __tablename__ = "legislators"

    id: Mapped[int] = mapped_column(primary_key=True)
    bioguide_id: Mapped[str] = mapped_column(String(10), unique=True, index=True)
    first_name: Mapped[str] = mapped_column(String(100))
    last_name: Mapped[str] = mapped_column(String(100))
    full_name: Mapped[str] = mapped_column(String(200))
    party: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    state: Mapped[Optional[str]] = mapped_column(String(2), nullable=True)
    district: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    chamber: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    image_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    office_address: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    phone: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    # Member status
    is_current: Mapped[bool] = mapped_column(Boolean, default=True, index=True)

    cached_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relationships
    bills: Mapped[list["Bill"]] = relationship(back_populates="sponsor", lazy="selectin")
    vote_positions: Mapped[list["VotePosition"]] = relationship(back_populates="legislator", lazy="selectin")
    campaign_finance: Mapped[Optional["CampaignFinance"]] = relationship(back_populates="legislator", uselist=False, lazy="selectin")


# Import at bottom to avoid circular imports
from app.models.bill import Bill
from app.models.vote import VotePosition
from app.models.finance import CampaignFinance
