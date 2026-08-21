"""UsageCounter: one row per user per billing period, tracking consumption
against the user's plan limits (currently just AI analyses — the only
metered operation that costs real money today, via the AI provider API).

Nothing increments or enforces this yet (Этап 11 is architecture-only —
see IMPLEMENTATION_PLAN.md §10); wiring `LeadPipelineService` to call
`UsageService.increment_ai_analyses` is future work once limits actually
need enforcing.
"""
import datetime as dt

from sqlalchemy import DateTime, ForeignKey, Integer, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.mixins import TimestampMixin, UpdatedAtMixin


class UsageCounter(Base, TimestampMixin, UpdatedAtMixin):
    __tablename__ = "usage_counters"
    __table_args__ = (UniqueConstraint("user_id", "period_start", name="uq_usage_user_period"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    period_start: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    ai_analyses_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    user: Mapped["User"] = relationship()  # noqa: F821

    def __repr__(self) -> str:  # pragma: no cover
        return f"<UsageCounter id={self.id} user_id={self.user_id} period_start={self.period_start}>"
