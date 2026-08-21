"""Source: a monitored origin of raw items (e.g. a public Telegram channel)."""
import datetime as dt
from typing import Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.mixins import TimestampMixin, UpdatedAtMixin


class Source(Base, TimestampMixin, UpdatedAtMixin):
    __tablename__ = "sources"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    url: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)
    # e.g. telegram channel username/id, freelance board id, api endpoint key
    external_identifier: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    last_checked_at: Mapped[Optional[dt.datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    # Not in the original spec field list — added in Stage 6 because Telegram
    # monitoring must "save the last processed message" and "recover
    # correctly after restart". Without persisting this, a worker restart
    # would have no way to know where it left off per source.
    last_external_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    # Catalog grouping for the source picker UI (e.g. "freelance",
    # "design", "development", "marketing", "marketplaces", "business",
    # "ai") — free-text rather than an enum since new categories are
    # expected as the catalog grows. NULL for sources predating the
    # catalog (existing 435 production sources) until someone categorizes
    # them.
    category: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    # Who first added this source, if it wasn't part of the original
    # system catalog — lets the UI distinguish "your own source" from
    # "catalog source" without a separate table.
    added_by_user_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    raw_items: Mapped[list["RawItem"]] = relationship(  # noqa: F821
        back_populates="source", cascade="all, delete-orphan"
    )
    profile_links: Mapped[list["SearchProfileSource"]] = relationship(  # noqa: F821
        back_populates="source", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<Source id={self.id} name={self.name!r} type={self.type}>"
