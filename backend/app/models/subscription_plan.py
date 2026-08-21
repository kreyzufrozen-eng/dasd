"""SubscriptionPlan: a catalog entry describing tier limits/price.

Этап 11 (see IMPLEMENTATION_PLAN.md §10) is architecture-only — nothing
enforces these limits yet, and there is no payment provider to integrate
with. This table exists so the "your plan/usage" panel has real, non-fake
numbers to display and so limit enforcement is a pure application-layer
change later, not another migration.
"""
import datetime as dt
from typing import Optional

from sqlalchemy import Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.mixins import TimestampMixin


class SubscriptionPlan(Base, TimestampMixin):
    __tablename__ = "subscription_plans"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)

    max_search_profiles: Mapped[int] = mapped_column(Integer, nullable=False)
    max_sources_per_profile: Mapped[int] = mapped_column(Integer, nullable=False)
    max_ai_analyses_per_month: Mapped[int] = mapped_column(Integer, nullable=False)

    # NULL price = not for sale outside the free default (avoids a
    # separate is_purchasable flag for the MVP's single free tier).
    price: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    currency: Mapped[str] = mapped_column(String(8), nullable=False, default="RUB")

    subscriptions: Mapped[list["Subscription"]] = relationship(  # noqa: F821
        back_populates="plan"
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<SubscriptionPlan id={self.id} name={self.name!r}>"
