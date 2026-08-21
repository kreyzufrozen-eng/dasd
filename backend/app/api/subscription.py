"""REST API: /api/subscription — read-only plan/usage panel (Этап 11).

No write endpoints: there is no payment provider to upgrade/downgrade
against yet (see IMPLEMENTATION_PLAN.md §10). Every account is on the
free plan; this exists so the frontend has real numbers to show instead
of faking a "your plan" screen.
"""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_current_user
from app.db.session import get_db_session
from app.models.user import User
from app.schemas.subscription_schemas import UsageSummaryRead
from app.services.subscription_service import get_usage_summary

router = APIRouter(prefix="/api/subscription", tags=["subscription"])


@router.get("", response_model=UsageSummaryRead)
async def get_my_subscription(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> UsageSummaryRead:
    summary = await get_usage_summary(db, user.id)
    await db.commit()
    return UsageSummaryRead(**summary.__dict__)
