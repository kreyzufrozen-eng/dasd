"""LeadPipelineService: RawItem -> KEYWORD FILTER -> AI ANALYSIS -> LEAD
SCORING -> DATABASE (the second half of the pipeline diagram; the first
half — SOURCE -> COLLECT RAW ITEM -> DEDUPLICATION — is
TelegramCollectorService, Stage 6).

One call processes one already-persisted RawItem against one SearchProfile
into (at most) one Lead row for that profile. Never raises for "expected"
failure modes (AI provider down, invalid AI JSON) — those are logged and
the RawItem is simply left without a Lead, so a single bad item/profile
can't take down the whole worker loop.

Этап 3: both the keyword pre-filter and the AI analysis are now scoped to
the SearchProfile doing the analysis (see app/ai/prompts.py
build_system_prompt and app/services/profile_keyword_seeder.py) — the same
RawItem can produce a Lead for one profile and nothing for another,
exactly as the Lead schema has supported since Stage 1.
"""
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.base import AIProvider
from app.ai.exceptions import AIProviderError, AIResponseValidationError
from app.ai.prompts import build_system_prompt
from app.core.config import Settings
from app.core.logging import get_logger
from app.models.lead import Lead
from app.models.raw_item import RawItem
from app.models.search_profile import SearchProfile
from app.repositories.lead_repository import LeadRepository
from app.services.pii_sanitizer import sanitize_message_text
from app.repositories.search_profile_keyword_repository import SearchProfileKeywordRepository
from app.schemas.ai_analysis import LeadAnalysis
from app.services.keyword_filter import KeywordFilter
from app.services.lead_scoring import LeadScoringInput, LeadScoringResult, LeadScoringService

logger = get_logger(__name__)


def _matches_profile_services(analysis_services: list[str], profile_services: list[str]) -> bool:
    """Case-insensitive membership check. The AI is instructed (see
    build_system_prompt) to echo services verbatim from the profile's own
    list rather than invent a fixed English vocabulary, so this is a
    straightforward set intersection once case is normalized — not a fuzzy
    match, deliberately: a loose substring match here would make almost
    anything "match" and defeat the point of the signal."""
    if not analysis_services or not profile_services:
        return False
    profile_set = {s.strip().lower() for s in profile_services}
    return any(s.strip().lower() in profile_set for s in analysis_services)


def _map_analysis_to_scoring_input(
    analysis: LeadAnalysis, raw_item: RawItem, profile: SearchProfile
) -> LeadScoringInput:
    has_concrete_description = bool(
        analysis.project_description and len(analysis.project_description.strip()) >= 15
    )
    matches_services = _matches_profile_services(analysis.services, profile.services)
    has_contact = bool(raw_item.author_username)

    return LeadScoringInput(
        direct_search=analysis.intent == "looking_for_contractor",
        has_concrete_description=has_concrete_description,
        business_niche=analysis.business_niche,
        budget_mentioned=analysis.budget.mentioned,
        high_urgency=analysis.urgency == "high",
        matches_offered_services=matches_services,
        has_contact_method=has_contact,
        published_at=raw_item.published_at,
        author_seeking_job="unrelated" == analysis.intent and not analysis.is_lead and any(
            "job" in s.lower() or "работ" in s.lower() for s in analysis.negative_signals
        ),
        advertising_own_services=analysis.is_self_advertising or any(
            "advertis" in s.lower() or "реклам" in s.lower() for s in analysis.negative_signals
        ),
        site_recommendation=analysis.intent == "recommendation_request",
        not_commercial_need=(not analysis.is_lead) and analysis.intent == "unrelated",
    )


class PipelineResult:
    def __init__(
        self,
        raw_item: RawItem,
        passed_keyword_filter: bool,
        analysis: Optional[LeadAnalysis] = None,
        scoring: Optional[LeadScoringResult] = None,
        lead: Optional[Lead] = None,
        ai_error: Optional[str] = None,
        is_new: bool = False,
    ) -> None:
        self.raw_item = raw_item
        self.passed_keyword_filter = passed_keyword_filter
        self.analysis = analysis
        self.scoring = scoring
        self.lead = lead
        self.ai_error = ai_error
        # True only when this call actually inserted a new Lead row — lets
        # callers (e.g. the notification step) avoid re-notifying for a
        # RawItem that already had a Lead from a previous cycle.
        self.is_new = is_new


class LeadPipelineService:
    def __init__(
        self,
        session: AsyncSession,
        ai_provider: AIProvider,
        settings: Settings,
        scoring_service: Optional[LeadScoringService] = None,
    ) -> None:
        self.session = session
        self.ai_provider = ai_provider
        self.settings = settings
        self.scoring_service = scoring_service or LeadScoringService()
        self.lead_repo = LeadRepository(session)
        self.profile_keyword_repo = SearchProfileKeywordRepository(session)

    async def build_keyword_filter(self, search_profile_id: int) -> KeywordFilter:
        """Snapshot a profile's own enabled keywords into a KeywordFilter.
        Build once per processing batch (per profile) and pass it into
        process_raw_item() — rebuilding per item would mean one DB query
        per RawItem for no benefit. Callers must have already ensured the
        profile has keyword rows (see profile_keyword_seeder.ensure_
        keywords_seeded) — an unseeded profile legitimately has zero
        keywords and this returns an always-empty filter for it."""
        enabled_keywords = await self.profile_keyword_repo.list_enabled_for_profile(
            search_profile_id
        )
        return KeywordFilter(enabled_keywords)

    async def process_raw_item(
        self,
        raw_item: RawItem,
        search_profile: SearchProfile,
        keyword_filter: Optional[KeywordFilter] = None,
    ) -> PipelineResult:
        search_profile_id = search_profile.id

        # A Lead already exists for this (RawItem, SearchProfile) pair
        # (e.g. reprocessing) — skip. DuplicateDetectionService already
        # prevents duplicate RawItems; this guards the RawItem -> Lead step
        # specifically, per profile (Stage 1: N:1, see models/lead.py).
        existing = await self.lead_repo.get_by_raw_item_and_profile(raw_item.id, search_profile_id)
        if existing is not None:
            logger.info("RawItem id=%s already has a Lead (id=%s), skipping", raw_item.id, existing.id)
            return PipelineResult(raw_item, passed_keyword_filter=True, lead=existing)

        keyword_filter = keyword_filter or await self.build_keyword_filter(search_profile_id)

        if not keyword_filter.should_pass_to_ai(raw_item.text):
            logger.debug(
                "RawItem id=%s filtered out by keywords for profile id=%s, skipping AI",
                raw_item.id,
                search_profile_id,
            )
            return PipelineResult(raw_item, passed_keyword_filter=False)

        try:
            # Data Sanitization Layer: redact phone/email/address patterns
            # from the message text before it leaves the system — see
            # app/services/pii_sanitizer.py. The stored RawItem.text (this
            # user's own dashboard) stays the original, unredacted copy;
            # only the AI-bound copy is sanitized.
            analysis = await self.ai_provider.analyze_lead(
                sanitize_message_text(raw_item.text),
                system_prompt=build_system_prompt(search_profile),
                context={"author": raw_item.author_username},
            )
        except (AIProviderError, AIResponseValidationError) as exc:
            # Per spec: don't crash the worker, save the error and move on.
            logger.error("AI analysis failed for RawItem id=%s: %s", raw_item.id, exc)
            return PipelineResult(raw_item, passed_keyword_filter=True, ai_error=str(exc))

        scoring_input = _map_analysis_to_scoring_input(analysis, raw_item, search_profile)
        scoring = self.scoring_service.calculate_score(scoring_input)

        # Never trust the model's raw is_lead in isolation — it has been
        # observed to say is_lead=true for a message its own summary
        # describes as self-advertising (gpt-4o-mini is inconsistent about
        # keeping is_lead and is_self_advertising in sync). This is the
        # deterministic backstop: is_self_advertising always wins.
        is_lead = analysis.is_lead and not analysis.is_self_advertising

        status = "new"
        lead = await self.lead_repo.create(
            raw_item_id=raw_item.id,
            search_profile_id=search_profile_id,
            is_lead=is_lead,
            lead_probability=analysis.lead_probability,
            lead_score=scoring.score,
            lead_type=analysis.lead_type,
            services=analysis.services,
            business_niche=analysis.business_niche,
            project_description=analysis.project_description,
            budget_min=analysis.budget.min,
            budget_max=analysis.budget.max,
            currency=analysis.budget.currency,
            urgency=analysis.urgency,
            complexity=analysis.project_complexity,
            estimated_value=analysis.estimated_value,
            summary=analysis.summary,
            reasoning=analysis.reasoning_short,
            positive_signals=analysis.positive_signals,
            negative_signals=analysis.negative_signals,
            intent_score=analysis.intent_score,
            intent_signals=analysis.intent_signals,
            status=status,
        )

        logger.info(
            "Lead created: id=%s raw_item_id=%s profile_id=%s score=%s is_lead=%s",
            lead.id,
            raw_item.id,
            search_profile_id,
            scoring.score,
            is_lead,
        )

        return PipelineResult(
            raw_item,
            passed_keyword_filter=True,
            analysis=analysis,
            scoring=scoring,
            lead=lead,
            is_new=True,
        )
