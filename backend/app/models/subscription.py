"""Subscription: one user's link to a SubscriptionPlan.

Every user gets one on registration (the free plan — see
app/services/subscription_service.py), so this is a 1:1 in practice
today, but modeled as a FK relationship (not a column on User) so a
future upgrade/downgrade/cancel flow is a row update, not a schema
change.
"""
import datetime as dt
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.enums import SubscriptionStatus
from app.models.mixins import TimestampMixin


class Subscription(Base, TimestampMixin):
    __tablename__ = "subscriptions"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True, unique=True
    )
    plan_id: Mapped[int] = mapped_column(
        ForeignKey("subscription_plans.id", ondelete="RESTRICT"), nullable=False
    )

    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default=SubscriptionStatus.ACTIVE.value
    )
    current_period_start: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    current_period_end: Mapped[Optional[dt.datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    user: Mapped["User"] = relationship()  # noqa: F821
    plan: Mapped["SubscriptionPlan"] = relationship(back_populates="subscriptions")

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Subscription id={self.id} user_id={self.user_id} plan_id={self.plan_id}>"
