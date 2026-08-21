"""Builds the "Скачать мои данные" export bundle (see
app/api/auth.py export_data). Deliberately simple: a same-request
authenticated JSON download, not a separately-issued expiring signed
link — see SECURITY_REVIEW.md for that gap and why it was accepted for
this pass rather than building a temp-storage/signed-URL system.
"""
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.repositories.lead_feedback_repository import LeadFeedbackRepository
from app.repositories.lead_repository import LeadRepository
from app.repositories.search_profile_keyword_repository import SearchProfileKeywordRepository
from app.repositories.search_profile_repository import SearchProfileRepository
from app.repositories.search_profile_source_repository import SearchProfileSourceRepository

# A user's own export, not a paginated API response — cap high enough
# that it's effectively "everything" for any real account without an
# unbounded query.
_EXPORT_LEAD_LIMIT = 5000


async def build_user_export(session: AsyncSession, user: User) -> dict[str, Any]:
    profile_repo = SearchProfileRepository(session)
    keyword_repo = SearchProfileKeywordRepository(session)
    source_repo = SearchProfileSourceRepository(session)
    lead_repo = LeadRepository(session)
    feedback_repo = LeadFeedbackRepository(session)

    search_profiles = await profile_repo.list_for_user(user.id)

    profiles_export = []
    for profile in search_profiles:
        keywords = await keyword_repo.list_for_profile(profile.id)
        sources = await source_repo.list_for_profile(profile.id)
        leads = await lead_repo.search(search_profile_id=profile.id, limit=_EXPORT_LEAD_LIMIT)

        leads_export = []
        for lead in leads:
            feedback = await feedback_repo.list_for_lead(lead.id)
            leads_export.append(
                {
                    "id": lead.id,
                    "lead_score": lead.lead_score,
                    "intent_score": lead.intent_score,
                    "is_lead": lead.is_lead,
                    "status": lead.status,
                    "business_niche": lead.business_niche,
                    "services": lead.services,
                    "summary": lead.summary,
                    "reasoning": lead.reasoning,
                    "budget_min": lead.budget_min,
                    "budget_max": lead.budget_max,
                    "currency": lead.currency,
                    "created_at": lead.created_at,
                    "feedback": [
                        {
                            "feedback_type": f.feedback_type,
                            "action": f.action,
                            "created_at": f.created_at,
                        }
                        for f in feedback
                    ],
                }
            )

        profiles_export.append(
            {
                "id": profile.id,
                "name": profile.name,
                "profession": profile.profession,
                "profession_description": profile.profession_description,
                "services": profile.services,
                "preferred_niches": profile.preferred_niches,
                "excluded_niches": profile.excluded_niches,
                "min_budget": profile.min_budget,
                "max_budget": profile.max_budget,
                "geography": profile.geography,
                "languages": profile.languages,
                "notification_threshold": profile.notification_threshold,
                "is_active": profile.is_active,
                "ai_profile_context": profile.ai_profile_context,
                "created_at": profile.created_at,
                "keywords": [
                    {"text": k.text, "category": k.category, "enabled": k.enabled} for k in keywords
                ],
                "sources": [
                    {"source_id": s.source_id, "enabled": s.enabled} for s in sources
                ],
                "leads": leads_export,
            }
        )

    return {
        "account": {
            "id": user.id,
            "email": user.email,
            "telegram_username": user.telegram_username,
            "name": user.name,
            "created_at": user.created_at,
        },
        "search_profiles": profiles_export,
    }
