"""Bill database model."""

from datetime import datetime, date
from typing import Optional

from sqlalchemy import String, Text, DateTime, Date, Integer, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Bill(Base):
    """Cached bill data from Congress.gov."""

    __tablename__ = "bills"

    id: Mapped[int] = mapped_column(primary_key=True)
    congress: Mapped[int] = mapped_column(Integer)
    bill_type: Mapped[str] = mapped_column(String(10))
    bill_number: Mapped[int] = mapped_column(Integer)
    title: Mapped[str] = mapped_column(Text)
    short_title: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    introduced_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    latest_action_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    latest_action_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    policy_area: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    sponsor_bioguide_id: Mapped[Optional[str]] = mapped_column(
        String(10), ForeignKey("legislators.bioguide_id"), nullable=True
    )
    is_cosponsored: Mapped[bool] = mapped_column(default=False)

    cached_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relationships
    sponsor: Mapped[Optional["Legislator"]] = relationship(back_populates="bills", lazy="selectin")

    @property
    def bill_id(self) -> str:
        """Return formatted bill ID like 'H.R. 123'."""
        type_map = {
            "hr": "H.R.",
            "s": "S.",
            "hjres": "H.J.Res.",
            "sjres": "S.J.Res.",
            "hconres": "H.Con.Res.",
            "sconres": "S.Con.Res.",
            "hres": "H.Res.",
            "sres": "S.Res.",
        }
        formatted_type = type_map.get(self.bill_type.lower(), self.bill_type.upper())
        return f"{formatted_type} {self.bill_number}"


from app.models.legislator import Legislator
