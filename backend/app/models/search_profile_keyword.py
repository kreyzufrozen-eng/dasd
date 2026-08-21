"""SearchProfileKeyword: a profile's personal keyword list.

Two ways a row gets here:
1. Seeded/linked from the global `Keyword` catalog (`keyword_id` set) —
   the profile can still override `weight`/`enabled` independently of the
   global row, without affecting other profiles that also link to it.
2. Added directly by the user or AI-generated during onboarding
   (`keyword_id` NULL) — profile-private, never touches the shared catalog.

`text`/`category`/`weight` are stored directly on this row either way
(denormalized) so the hot pipeline path (KeywordFilter, run once per
message per active profile) never needs a join back to `keywords` — it
reads one row per profile-keyword-link exactly as it read one row per
global Keyword before this table existed.
"""
from typing import Optional

from sqlalchemy import Boolean, Float, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.mixins import TimestampMixin


class SearchProfileKeyword(Base, TimestampMixin):
    __tablename__ = "search_profile_keywords"
    __table_args__ = (
        UniqueConstraint("search_profile_id", "keyword_id", name="uq_spk_profile_keyword"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    search_profile_id: Mapped[int] = mapped_column(
        ForeignKey("search_profiles.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # NULL for a profile-private keyword never linked to the global catalog.
    keyword_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("keywords.id", ondelete="SET NULL"), nullable=True, index=True
    )

    text: Mapped[str] = mapped_column(String(255), nullable=False)
    category: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    weight: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)

    search_profile: Mapped["SearchProfile"] = relationship(  # noqa: F821
        back_populates="keyword_links"
    )

    # KeywordFilter (app/services/keyword_filter.py) was written against
    # the global Keyword model's attribute names and takes a plain
    # Sequence[Any] — these aliases let it accept SearchProfileKeyword rows
    # unchanged instead of duplicating the matcher or adding an adapter
    # layer for what's really the same "text + category + weight + active
    # flag" shape under different column names.
    @property
    def keyword(self) -> str:
        return self.text

    @property
    def is_active(self) -> bool:
        return self.enabled

    def __repr__(self) -> str:  # pragma: no cover
        return (
            f"<SearchProfileKeyword profile_id={self.search_profile_id} "
            f"text={self.text!r} category={self.category}>"
        )
