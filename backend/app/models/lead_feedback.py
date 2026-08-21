"""LeadFeedback: human feedback on a Lead (from bot inline buttons or API)."""
from typing import Optional

from sqlalchemy import ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.mixins import TimestampMixin


class LeadFeedback(Base, TimestampMixin):
    __tablename__ = "lead_feedback"
    __table_args__ = (Index("ix_lead_feedback_lead_id", "lead_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    lead_id: Mapped[int] = mapped_column(ForeignKey("leads.id", ondelete="CASCADE"))
    feedback_type: Mapped[str] = mapped_column(String(32), nullable=False)
    comment: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # Generic signal alongside feedback_type (bot-only: good/not_interesting/
    # client/archived) — this is what the web "Отфильтровано AI" page's
    # 👍/👎 buttons write (relevant/irrelevant), plus saved/contacted for
    # future use. Both columns coexist rather than merging into one enum:
    # feedback_type already has real production data and bot callback
    # wiring; action is the new, broader vocabulary the ТЗ asks for.
    action: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    # Denormalized from lead.search_profile_id at write time — lets future
    # per-profile learning queries filter feedback without a join back to
    # leads for every row.
    search_profile_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("search_profiles.id", ondelete="CASCADE"), nullable=True
    )

    lead: Mapped["Lead"] = relationship(back_populates="feedback_entries")  # noqa: F821

    def __repr__(self) -> str:  # pragma: no cover
        return f"<LeadFeedback id={self.id} lead_id={self.lead_id} type={self.feedback_type}>"
