"""Keyword: a single weighted keyword used by the pre-filter stage."""
from sqlalchemy import Boolean, Float, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.mixins import TimestampMixin


class Keyword(Base, TimestampMixin):
    __tablename__ = "keywords"
    __table_args__ = (
        UniqueConstraint("keyword", "category", name="uq_keywords_keyword_category"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    keyword: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    category: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    weight: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)
    # True for the shared, admin-curated catalog (today's rows, seeded via
    # app/services/keyword_seed_data.py) that new SearchProfiles get
    # seeded from. Profile-private keywords live in SearchProfileKeyword
    # instead of this table, so in practice every row here stays
    # is_global=true — the column exists so that invariant is explicit
    # rather than implied.
    is_global: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Keyword id={self.id} keyword={self.keyword!r} category={self.category}>"
