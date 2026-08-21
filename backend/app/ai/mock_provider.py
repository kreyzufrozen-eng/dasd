"""MockAIProvider: deterministic, offline analyzer for dev/testing.

Not a real ML model — rule-based on the raw text, so the rest of the
pipeline (scoring, notifications, dashboard) has realistic-looking data to
work with before AI_API_KEY / AI_BASE_URL are configured. This is what
lets `docker compose up` produce a working end-to-end demo with zero
external credentials (AI_PROVIDER=mock is the default in .env.example).
"""
from typing import Any, Optional

from app.ai.base import AIProvider
from app.models.enums import KeywordCategory
from app.schemas.ai_analysis import BudgetInfo, LeadAnalysis
from app.schemas.profile_draft import ProfileDraft, SuggestedKeyword

LEAD_INDICATORS = [
    "нужен сайт", "ищу разработчика", "ищу веб разработчика", "нужен веб дизайнер",
    "нужен дизайнер", "сделать сайт", "разработать сайт", "заказать сайт",
    "редизайн сайта", "доработка сайта", "сайт устарел", "нужно обновить сайт",
    "лендинг", "корпоративный сайт", "интернет магазин", "интернет-магазин",
]
JOB_SEEKER_INDICATORS = ["ищу работу", "ищу вакансию", "резюме", "готов работать удалённо"]
AD_INDICATORS = ["предлагаю услуги", "делаю сайты на заказ", "разрабатываю сайты", "мои услуги", "выполню заказ"]
BUDGET_HINTS = ["бюджет", "руб", "₽", "$", "usd", "тыс"]
URGENCY_HINTS = ["срочно", "сегодня", "как можно скорее", "asap"]
HIDDEN_INTENT_INDICATORS = [
    "сайт устарел", "старый сайт", "нужно что-то делать с сайтом",
    "работаем только через инстаграм", "работаем через инстаграм",
    "продвигаемся через инстаграм", "пока без сайта",
    "открываем клинику", "открываем магазин", "открываем салон", "открываем шоурум",
    "запускаем новый проект", "запускаем производство", "запустили производство",
    "думаем над сайтом", "рассматриваем создание сайта",
    "нет заявок", "мало заявок", "способы получать заявки", "источники заявок",
    "новое направление бизнеса",
]


class MockAIProvider(AIProvider):
    """Rule-based on the raw text only — deliberately ignores
    `system_prompt` (unlike the real provider). Its job is proving the
    pipeline works end-to-end with zero external credentials, not
    demonstrating multi-profession intelligence; real personalization only
    happens once a real AI provider is configured."""

    async def analyze_lead(
        self, text: str, system_prompt: str, context: Optional[dict[str, Any]] = None
    ) -> LeadAnalysis:
        lowered = text.lower()

        if any(p in lowered for p in JOB_SEEKER_INDICATORS):
            return LeadAnalysis(
                is_lead=False,
                lead_probability=0.05,
                intent="unrelated",
                summary="Похоже, автор ищет работу, а не заказывает услугу.",
                reasoning_short="Обнаружены индикаторы поиска работы соискателем.",
                negative_signals=["author appears to be job-seeking"],
                confidence=0.6,
            )

        if any(p in lowered for p in AD_INDICATORS):
            return LeadAnalysis(
                is_lead=False,
                lead_probability=0.05,
                intent="unrelated",
                is_self_advertising=True,
                summary="Похоже на рекламу собственных услуг автора, а не запрос.",
                reasoning_short="Обнаружены индикаторы саморекламы.",
                negative_signals=["looks like self-advertising"],
                confidence=0.55,
            )

        hidden_matched = [p for p in HIDDEN_INTENT_INDICATORS if p in lowered]

        matched = [p for p in LEAD_INDICATORS if p in lowered]
        if not matched:
            if hidden_matched:
                return LeadAnalysis(
                    is_lead=False,
                    lead_probability=0.1,
                    intent="unrelated",
                    intent_score=min(90, 40 + 25 * len(hidden_matched)),
                    intent_signals=hidden_matched,
                    summary="Явного запроса нет, но есть признаки скорой потребности в сайте.",
                    reasoning_short="Обнаружены индикаторы скрытого спроса (mock-эвристика).",
                    confidence=0.5,
                )
            return LeadAnalysis(
                is_lead=False,
                lead_probability=0.1,
                intent="unrelated",
                summary="Явных признаков коммерческого запроса на веб-услуги не найдено.",
                reasoning_short="Нет совпадений с индикаторами лида (mock-эвристика).",
                confidence=0.4,
            )

        has_budget = any(p in lowered for p in BUDGET_HINTS)
        is_urgent = any(p in lowered for p in URGENCY_HINTS)

        return LeadAnalysis(
            is_lead=True,
            lead_probability=0.8 if len(matched) > 1 else 0.65,
            lead_type="website_development",
            services=["website_development", "web_design"],
            project_description=text[:300],
            business_niche=None,
            budget=BudgetInfo(mentioned=has_budget),
            urgency="high" if is_urgent else "medium",
            project_complexity="medium",
            intent="looking_for_contractor",
            intent_score=min(90, 40 + 25 * len(hidden_matched)) if hidden_matched else 0,
            intent_signals=hidden_matched,
            estimated_value="medium",
            summary=f"Возможный запрос на веб-разработку (совпадение: «{matched[0]}»).",
            reasoning_short="Найдены прямые индикаторы намерения заказать сайт/дизайн (mock-эвристика).",
            positive_signals=[f"keyword match: {m}" for m in matched],
            negative_signals=[],
            confidence=0.7,
        )

    async def generate_profile_draft(self, description: str) -> ProfileDraft:
        """Naive heuristic — first sentence as the profession label, a
        generic starter keyword set. Good enough to let onboarding be
        tested end-to-end with zero AI credentials; not meant to look
        smart the way the real provider's output does."""
        first_sentence = description.strip().split(".")[0].strip() or description.strip()[:80]
        profession = first_sentence[:120] or "Специалист"

        return ProfileDraft(
            profession=profession,
            services=["услуги по описанию"],
            suggested_orders=[f"Нужен специалист: {profession.lower()}"],
            suggested_exclusions=["вакансия в штат", "стажировка", "работа за отзыв"],
            suggested_keywords=[
                SuggestedKeyword(text="нужен специалист", category=KeywordCategory.DIRECT_INTENT.value, weight=1.5),
                SuggestedKeyword(text="ищу исполнителя", category=KeywordCategory.DIRECT_INTENT.value, weight=1.5),
                SuggestedKeyword(text="вакансия", category=KeywordCategory.EXCLUSION.value, weight=1.0),
                SuggestedKeyword(text="стажировка", category=KeywordCategory.EXCLUSION.value, weight=1.0),
            ],
            ai_profile_context=f"Пользователь: {description.strip()[:500]} (mock-эвристика, без реального AI).",
            summary_direct=f"Прямые запросы на услуги: {profession}.",
            summary_potential="Сообщения с подходящей задачей без прямого запроса.",
            summary_hidden="Ситуации, предвещающие будущий заказ.",
            summary_excluded="Вакансии, стажировки, работа за отзыв.",
        )
