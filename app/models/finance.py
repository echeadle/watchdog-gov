"""Campaign finance database models."""

from datetime import datetime, date
from typing import Optional

from sqlalchemy import String, Text, DateTime, Date, Integer, Float, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class CampaignFinance(Base):
    """Campaign finance summary from FEC."""

    __tablename__ = "campaign_finance"

    id: Mapped[int] = mapped_column(primary_key=True)
    legislator_bioguide_id: Mapped[str] = mapped_column(
        String(10), ForeignKey("legislators.bioguide_id"), unique=True
    )
    fec_candidate_id: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    committee_id: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)

    cycle: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    total_receipts: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    total_disbursements: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    cash_on_hand: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    debt: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    individual_contributions: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    pac_contributions: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    party_contributions: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    cached_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relationships
    legislator: Mapped["Legislator"] = relationship(back_populates="campaign_finance", lazy="selectin")
    expenditures: Mapped[list["Expenditure"]] = relationship(back_populates="campaign_finance", lazy="selectin")


class Expenditure(Base):
    """Detailed campaign expenditure record."""

    __tablename__ = "expenditures"

    id: Mapped[int] = mapped_column(primary_key=True)
    campaign_finance_id: Mapped[int] = mapped_column(Integer, ForeignKey("campaign_finance.id"))

    payee_name: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    purpose: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    amount: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    expenditure_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    category: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    cached_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relationships
    campaign_finance: Mapped["CampaignFinance"] = relationship(back_populates="expenditures", lazy="selectin")


from app.models.legislator import Legislator
