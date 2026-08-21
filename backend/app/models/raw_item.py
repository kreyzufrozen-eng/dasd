"""RawItem: a single collected message/post, before any analysis."""
import datetime as dt
from typing import Any, Optional

from sqlalchemy import DateTime, ForeignKey, Index, String, Text, UniqueConstraint
from sqlalchemy import JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.mixins import TimestampMixin


class RawItem(Base, TimestampMixin):
    __tablename__ = "raw_items"
    __table_args__ = (
        # Dedup check #1: same source can never yield the same external_id twice.
        UniqueConstraint("source_id", "external_id", name="uq_raw_items_source_external_id"),
        Index("ix_raw_items_content_hash", "content_hash"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    source_id: Mapped[int] = mapped_column(ForeignKey("sources.id", ondelete="CASCADE"))
    external_id: Mapped[str] = mapped_column(String(255), nullable=False)
    author_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    author_username: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    url: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)
    published_at: Mapped[Optional[dt.datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    # Dedup check #2: hash of normalized text content, independent of source/external_id.
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    # Message Retention Policy (see DATA_RETENTION_POLICY.md): set at write
    # time to created_at + the configured retention window. NULL means "no
    # retention job has ever run against this row's era" (pre-migration
    # rows) rather than "keep forever" — a separate cleanup job is what
    # would actually purge/anonymize text past this date; none exists yet,
    # so today this column is tracked but not yet enforced.
    retention_until: Mapped[Optional[dt.datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    # Mapped as `metadata_` in Python (SQLAlchemy reserves `metadata` on Base),
    # stored as the `metadata` column in the DB.
    metadata_: Mapped[Optional[dict[str, Any]]] = mapped_column(
        "metadata", JSON, nullable=True
    )

    source: Mapped["Source"] = relationship(back_populates="raw_items")  # noqa: F821
    # One RawItem can now produce a Lead per matching SearchProfile — see
    # app/models/lead.py's docstring.
    leads: Mapped[list["Lead"]] = relationship(  # noqa: F821
        back_populates="raw_item", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<RawItem id={self.id} source_id={self.source_id} external_id={self.external_id!r}>"
