"""REST API: /api/leads — scoped to the authenticated user's SearchProfile."""
import datetime as dt
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import resolve_profile_id
from app.core.exceptions import NotFoundError
from app.core.security import get_current_user
from app.db.session import get_db_session
from app.models.lead import Lead
from app.models.raw_item import RawItem
from app.models.source import Source
from app.models.user import User
from app.repositories.lead_feedback_repository import LeadFeedbackRepository
from app.repositories.lead_repository import LeadRepository
from app.repositories.raw_item_repository import RawItemRepository
from app.repositories.search_profile_repository import SearchProfileRepository
from app.repositories.source_repository import SourceRepository
from app.schemas.lead_feedback_schemas import LeadFeedbackCreate, LeadFeedbackRead
from app.schemas.lead_schemas import LeadRead, LeadUpdate, LeadWithContextRead

router = APIRouter(prefix="/api/leads", tags=["leads"])

# LeadFeedback.feedback_type predates the broader `action` vocabulary (see
# app/models/lead_feedback.py) and is NOT NULL — every web feedback write
# needs some value there too, so map the new action onto the closest
# existing bucket rather than adding a second enum with overlapping
# meaning.
_ACTION_TO_FEEDBACK_TYPE = {
    "relevant": "good",
    "irrelevant": "not_interesting",
    "saved": "good",
    "contacted": "client",
}


def _to_lead_with_context(
    lead: Lead, raw_item: Optional[RawItem], source: Optional[Source]
) -> LeadWithContextRead:
    base = LeadRead.model_validate(lead).model_dump()
    return LeadWithContextRead(
        **base,
        raw_text=raw_item.text if raw_item else "",
        raw_url=raw_item.url if raw_item else None,
        author_name=raw_item.author_name if raw_item else None,
        author_username=raw_item.author_username if raw_item else None,
        source_id=source.id if source else None,
        source_name=source.name if source else None,
    )


@router.get("", response_model=list[LeadWithContextRead])
async def list_leads(
    search_profile_id: Optional[int] = Query(
        default=None, description="Defaults to the caller's first profile if omitted"
    ),
    score_min: Optional[int] = None,
    score_max: Optional[int] = None,
    intent_score_min: Optional[int] = None,
    status: Optional[str] = None,
    source_id: Optional[int] = None,
    lead_type: Optional[str] = None,
    is_lead: Optional[bool] = None,
    date_from: Optional[dt.datetime] = None,
    date_to: Optional[dt.datetime] = None,
    sort: str = Query("newest", pattern="^(newest|score|intent)$"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> list[LeadWithContextRead]:
    profile_id = await resolve_profile_id(db, user, search_profile_id)
    if profile_id is None:
        # No SearchProfile yet (onboarding not completed) — nothing to
        # show. Not an error: the frontend renders this as an empty
        # state pointing at onboarding, same as "no leads found".
        return []

    lead_repo = LeadRepository(db)
    raw_repo = RawItemRepository(db)
    source_repo = SourceRepository(db)

    leads = await lead_repo.search(
        search_profile_id=profile_id,
        score_min=score_min,
        score_max=score_max,
        intent_score_min=intent_score_min,
        status=status,
        source_id=source_id,
        lead_type=lead_type,
        is_lead=is_lead,
        date_from=date_from,
        date_to=date_to,
        sort=sort,
        limit=limit,
        offset=offset,
    )

    results = []
    for lead in leads:
        raw_item = await raw_repo.get(lead.raw_item_id)
        source = await source_repo.get(raw_item.source_id) if raw_item else None
        results.append(_to_lead_with_context(lead, raw_item, source))
    return results


@router.get("/{lead_id}", response_model=LeadWithContextRead)
async def get_lead(
    lead_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> LeadWithContextRead:
    lead_repo = LeadRepository(db)
    lead = await lead_repo.get(lead_id)
    owned_profile_ids = await SearchProfileRepository(db).list_ids_for_user(user.id)
    if lead is None or lead.search_profile_id not in owned_profile_ids:
        raise NotFoundError("Lead not found")

    raw_repo = RawItemRepository(db)
    source_repo = SourceRepository(db)
    raw_item = await raw_repo.get(lead.raw_item_id)
    source = await source_repo.get(raw_item.source_id) if raw_item else None
    return _to_lead_with_context(lead, raw_item, source)


@router.patch("/{lead_id}", response_model=LeadRead)
async def update_lead(
    lead_id: int,
    payload: LeadUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> Lead:
    lead_repo = LeadRepository(db)
    lead = await lead_repo.get(lead_id)
    owned_profile_ids = await SearchProfileRepository(db).list_ids_for_user(user.id)
    if lead is None or lead.search_profile_id not in owned_profile_ids:
        raise NotFoundError("Lead not found")

    # payload.status is already validated against LeadStatus by
    # LeadUpdate's field_validator — no need to re-check it here.
    update_data = payload.model_dump(exclude_unset=True)
    updated = await lead_repo.update(lead, **update_data)
    await db.commit()
    return updated


@router.post("/{lead_id}/feedback", response_model=LeadFeedbackRead, status_code=201)
async def create_lead_feedback(
    lead_id: int,
    payload: LeadFeedbackCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    """Records the 👍/👎 "Отфильтровано AI" feedback (and future saved/
    contacted actions). `relevant` also moves the item into the regular
    leads view by flipping is_lead — a "фактически лид" click means the
    keyword+AI pipeline got it wrong, not that the user wants a note filed
    away and forgotten."""
    lead_repo = LeadRepository(db)
    lead = await lead_repo.get(lead_id)
    owned_profile_ids = await SearchProfileRepository(db).list_ids_for_user(user.id)
    if lead is None or lead.search_profile_id not in owned_profile_ids:
        raise NotFoundError("Lead not found")

    if payload.action == "relevant" and not lead.is_lead:
        await lead_repo.update(lead, is_lead=True)

    feedback_repo = LeadFeedbackRepository(db)
    feedback = await feedback_repo.create(
        lead_id=lead.id,
        feedback_type=_ACTION_TO_FEEDBACK_TYPE[payload.action],
        action=payload.action,
        comment=payload.comment,
        search_profile_id=lead.search_profile_id,
    )
    await db.commit()
    return feedback
