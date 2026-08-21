"""SearchProfileSource: many-to-many link between a SearchProfile and a
Source, with per-profile enable/disable.

A Source is a real-world object (a Telegram channel, a freelance board)
shared by every profile that watches it — this junction is what lets many
profiles watch the same Source without duplicating it (duplicating would
break RawItem dedup, which keys on source_id, and would multiply parsing
work per channel by however many profiles added it).
"""
from sqlalchemy import Boolean, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.mixins import TimestampMixin


class SearchProfileSource(Base, TimestampMixin):
    __tablename__ = "search_profile_sources"
    __table_args__ = (
        UniqueConstraint("search_profile_id", "source_id", name="uq_sps_profile_source"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    search_profile_id: Mapped[int] = mapped_column(
        ForeignKey("search_profiles.id", ondelete="CASCADE"), nullable=False, index=True
    )
    source_id: Mapped[int] = mapped_column(
        ForeignKey("sources.id", ondelete="CASCADE"), nullable=False, index=True
    )
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    search_profile: Mapped["SearchProfile"] = relationship(  # noqa: F821
        back_populates="source_links"
    )
    source: Mapped["Source"] = relationship(back_populates="profile_links")  # noqa: F821

    def __repr__(self) -> str:  # pragma: no cover
        return (
            f"<SearchProfileSource profile_id={self.search_profile_id} "
            f"source_id={self.source_id} enabled={self.enabled}>"
        )
