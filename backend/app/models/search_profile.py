"""SearchProfile: one user's "who am I / who are my clients" context.

This is what makes the leads personal — the pipeline currently analyzes
every RawItem once against a single hardcoded persona (see
app/ai/prompts.py); Stage 3 (personalized matching) is what teaches it to
analyze per-profile instead. For now, this model exists so Stage 1 can
attach every existing Lead to a real profile (see migration 0004) without
the AI/scoring pipeline needing to change yet.
"""
import datetime as dt
from typing import Any, Optional

from sqlalchemy import Boolean, Float, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.mixins import TimestampMixin, UpdatedAtMixin


class SearchProfile(Base, TimestampMixin, UpdatedAtMixin):
    __tablename__ = "search_profiles"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # User-facing label for this profile (relevant once multiple profiles
    # per user are supported — e.g. "Веб-разработка" vs "AI-автоматизация").
    name: Mapped[str] = mapped_column(String(255), nullable=False)

    profession: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    # Raw free-text the user typed during onboarding ("Я занимаюсь
    # настройкой таргетированной рекламы...") — kept verbatim so the AI
    # profile-generation step can be re-run/refined later.
    profession_description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    services: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    skills: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    technologies: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)

    target_clients: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    preferred_niches: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    excluded_niches: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)

    min_budget: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    max_budget: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    currency: Mapped[str] = mapped_column(String(8), nullable=False, default="RUB")

    # Free-form for MVP ("remote" | "russia" | "cis" | "world" | a city
    # name, ...) rather than an enum — geography preferences are too
    # open-ended to lock down before real users show what they actually
    # type here.
    geography: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    languages: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)

    # Subset of OpportunityType values (direct_lead/potential_lead/
    # hidden_opportunity) this profile wants surfaced — see
    # app/models/enums.py OpportunityType.
    lead_types: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)

    notification_threshold: Mapped[int] = mapped_column(Integer, nullable=False, default=60)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Auto-generated (see app/ai/profile_builder.py, Stage 2) system-prompt
    # fragment describing this profile to the AI — regenerated whenever the
    # user edits the profile. Analysis itself doesn't consume this yet
    # (Stage 3); stored now so onboarding has somewhere to write it.
    ai_profile_context: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    user: Mapped["User"] = relationship(back_populates="search_profiles")  # noqa: F821
    leads: Mapped[list["Lead"]] = relationship(  # noqa: F821
        back_populates="search_profile", cascade="all, delete-orphan"
    )
    source_links: Mapped[list["SearchProfileSource"]] = relationship(  # noqa: F821
        back_populates="search_profile", cascade="all, delete-orphan"
    )
    keyword_links: Mapped[list["SearchProfileKeyword"]] = relationship(  # noqa: F821
        back_populates="search_profile", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<SearchProfile id={self.id} user_id={self.user_id} name={self.name!r}>"
