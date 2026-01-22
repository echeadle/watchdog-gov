"""Vote database models."""

from datetime import datetime, date
from typing import Optional

from sqlalchemy import String, Text, DateTime, Date, Integer, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Vote(Base):
    """Roll call vote record."""

    __tablename__ = "votes"

    id: Mapped[int] = mapped_column(primary_key=True)
    congress: Mapped[int] = mapped_column(Integer)
    chamber: Mapped[str] = mapped_column(String(20))
    session: Mapped[int] = mapped_column(Integer)
    roll_number: Mapped[int] = mapped_column(Integer)

    vote_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    question: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    result: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    bill_congress: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    bill_type: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    bill_number: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    yea_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    nay_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    not_voting_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    cached_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relationships
    positions: Mapped[list["VotePosition"]] = relationship(back_populates="vote", lazy="selectin")


class VotePosition(Base):
    """How a specific legislator voted on a roll call."""

    __tablename__ = "vote_positions"

    id: Mapped[int] = mapped_column(primary_key=True)
    vote_id: Mapped[int] = mapped_column(Integer, ForeignKey("votes.id"))
    legislator_bioguide_id: Mapped[str] = mapped_column(
        String(10), ForeignKey("legislators.bioguide_id")
    )
    position: Mapped[str] = mapped_column(String(20))

    cached_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relationships
    vote: Mapped["Vote"] = relationship(back_populates="positions", lazy="selectin")
    legislator: Mapped["Legislator"] = relationship(back_populates="vote_positions", lazy="selectin")


from app.models.legislator import Legislator
