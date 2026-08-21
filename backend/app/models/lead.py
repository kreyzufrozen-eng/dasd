"""Lead: the AI-analyzed, scored outcome for a RawItem."""
import datetime as dt
from typing import Any, Optional

from sqlalchemy import (
    Boolean,
    Float,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.enums import LeadStatus
from app.models.mixins import TimestampMixin, UpdatedAtMixin


class Lead(Base, TimestampMixin, UpdatedAtMixin):
    """A Lead is now scoped to one SearchProfile, not just one RawItem: the
    same message can be a lead for one user's profile and not another's
    (see migration 0004_add_users_and_search_profiles and PROJECT_AUDIT.md
    §"Lead 1:1 vs N:1"). A RawItem can therefore have many Leads — at most
    one per SearchProfile, enforced by the unique constraint below."""

    __tablename__ = "leads"
    __table_args__ = (
        Index("ix_leads_score_status", "lead_score", "status"),
        Index("ix_leads_created_at", "created_at"),
        UniqueConstraint(
            "raw_item_id", "search_profile_id", name="uq_leads_raw_item_search_profile"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    raw_item_id: Mapped[int] = mapped_column(
        ForeignKey("raw_items.id", ondelete="CASCADE"), nullable=False, index=True
    )
    search_profile_id: Mapped[int] = mapped_column(
        ForeignKey("search_profiles.id", ondelete="CASCADE"), nullable=False, index=True
    )

    is_lead: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    lead_probability: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    lead_score: Mapped[int] = mapped_column(Integer, nullable=False, default=0, index=True)

    lead_type: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    services: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    business_niche: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    project_description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    budget_min: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    budget_max: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    currency: Mapped[Optional[str]] = mapped_column(String(8), nullable=True)

    urgency: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)
    complexity: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)
    estimated_value: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)

    summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # AI's own short explanation of its is_lead verdict (LeadAnalysis.
    # reasoning_short) — separate from `summary` (what the message IS)
    # since this is specifically WHY it was or wasn't judged a lead. Этап
    # 8: the "Отфильтровано AI" page shows this so a rejection isn't just
    # a bare score with no explanation.
    reasoning: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    positive_signals: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    negative_signals: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)

    # How likely this author will need a website SOON even though they
    # aren't asking for one right now — e.g. "launching a new project,
    # only on Instagram for now" or "opening a clinic, thinking about a
    # site". Deliberately independent from lead_score/is_lead: a message
    # can be intent_score=80 while is_lead=false (no request today), or
    # intent_score=20 while is_lead=true (asking today, but a one-off with
    # no ongoing potential). See app/ai/prompts.py for the AI-side rules.
    intent_score: Mapped[int] = mapped_column(Integer, nullable=False, default=0, index=True)
    intent_signals: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)

    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default=LeadStatus.NEW.value, index=True
    )

    raw_item: Mapped["RawItem"] = relationship(back_populates="leads")  # noqa: F821
    search_profile: Mapped["SearchProfile"] = relationship(back_populates="leads")  # noqa: F821
    feedback_entries: Mapped[list["LeadFeedback"]] = relationship(  # noqa: F821
        back_populates="lead", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Lead id={self.id} score={self.lead_score} status={self.status}>"
