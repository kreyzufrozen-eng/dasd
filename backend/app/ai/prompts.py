"""System prompt for the AI lead analyzer, and the JSON contract it must follow.

Этап 3: the prompt is built per-SearchProfile instead of hardcoded to one
web-dev persona — build_system_prompt() below fills in the same template
every profile shares (the mechanics: context-over-keywords, the
is_self_advertising backstop, the intent_score hidden-demand axis, the
strict JSON schema) with that profile's own profession/services/desired-
orders/exclusions. The `services` field's vocabulary is now literally the
profile's own service list — the AI is instructed to echo terms from it
verbatim rather than invent English category slugs, which is what makes
LeadPipelineService's profile-aware scoring match reliably (see
_map_analysis_to_scoring_input in app/services/lead_pipeline.py)."""
from typing import Optional

_JSON_CONTRACT = """Возвращай ТОЛЬКО валидный JSON, без markdown, без пояснений вне JSON, ровно со
следующими полями:
{
  "is_lead": true,
  "lead_probability": 0.94,
  "lead_type": "website_development",
  "services": ["услуга из списка выше, дословно"],
  "project_description": "string",
  "business_niche": "string or null",
  "budget": {"mentioned": false, "min": null, "max": null, "currency": null},
  "urgency": "low | medium | high",
  "project_complexity": "low | medium | high",
  "intent": "looking_for_contractor | problem_statement | recommendation_request | unrelated",
  "is_self_advertising": false,
  "intent_score": 0,
  "intent_signals": [],
  "estimated_value": "low | medium | high",
  "summary": "Короткое описание на русском",
  "reasoning_short": "Короткое объяснение без длинных рассуждений",
  "positive_signals": [],
  "negative_signals": [],
  "confidence": 0.0
}"""


def _format_list(items: list[str], empty: str = "не указано") -> str:
    return ", ".join(items) if items else empty


def build_system_prompt(profile) -> str:  # profile: app.models.search_profile.SearchProfile
    """`profile` needs: profession, profession_description, services,
    target_clients, preferred_niches, excluded_niches, ai_profile_context.
    Every field is optional at the model level — this degrades gracefully
    to a generic-but-still-useful prompt when a profile has only the bare
    minimum (e.g. one created via the API without onboarding)."""
    profession = profile.profession or "услуги, которые предоставляет пользователь"
    services = profile.services or []
    services_line = _format_list(services, empty="не указаны — ориентируйся на специализацию ниже")

    context_parts = []
    if profile.profession_description:
        context_parts.append(profile.profession_description.strip())
    if profile.ai_profile_context:
        context_parts.append(profile.ai_profile_context.strip())
    context_block = "\n".join(context_parts) if context_parts else (
        f"Пользователь предоставляет услуги: {services_line}."
    )

    exclusions = list(profile.excluded_niches or [])
    exclusions_block = (
        "\nДополнительно НЕ считай лидом, если сообщение относится к: "
        + _format_list(exclusions) + "."
        if exclusions
        else ""
    )

    niches_block = (
        f"\nПриоритетные ниши клиентов: {_format_list(profile.preferred_niches or [])}."
        if profile.preferred_niches
        else ""
    )
    clients_block = (
        f"\nЖелаемые клиенты: {profile.target_clients}." if profile.target_clients else ""
    )

    return f"""Ты анализируешь сообщения из Telegram и других источников.
Твоя задача — определить, является ли сообщение потенциальным коммерческим лидом
для специалиста в сфере: {profession}.

Он предоставляет следующие услуги: {services_line}.

Контекст о том, какие заказы нужны пользователю:
{context_block}{niches_block}{clients_block}

Сообщение является лидом, если:
1. Автор прямо ищет исполнителя для одной из перечисленных выше услуг.
2. Автор сообщает о потребности, которую решает одна из этих услуг.
3. Автор хочет улучшить/переделать/обновить что-то, что входит в эти услуги.
4. У автора есть проблема, которую можно решить одной из этих услуг.
5. Есть косвенная, но достаточно явная потребность в соответствующих услугах.

Сообщение НЕ является лидом, если:
1. Автор упоминает что-то по теме услуг, но не как ресурс/предмет, а мимоходом.
2. Автор обсуждает чужой проект/сайт/работу, а не свою потребность.
3. Автор ищет работу/вакансию в этой сфере (он специалист, а не заказчик).
4. Автор рекламирует собственные аналогичные услуги.
5. Автор задаёт вопрос, не предполагающий заказ услуг.
6. Сообщение не связано ни с одной из перечисленных выше услуг.{exclusions_block}

Не ориентируйся только на ключевые слова. Анализируй контекст и намерение автора.

КРИТИЧЕСКИ ВАЖНО — направление сделки (частая ошибка): нужны лиды, где автору
нужна услуга пользователя (он ЗАКАЗЧИК), а не сообщения, где автор сам ПРЕДЛАГАЕТ
такую же услугу (он ИСПОЛНИТЕЛЬ/конкурент). Сообщение вида "Я делаю [услугу] на
заказ, вот мои работы, пишите в ЛС" упоминает те же ключевые слова, но это НЕ
лид — это саморазмещение исполнителя. Типичные маркеры того, что автор —
ИСПОЛНИТЕЛЬ, а не заказчик:
- "предлагаю", "выполню", "делаю на заказ";
- "мои услуги", "портфолио", "работаю в сфере ... лет";
- "ищу клиентов/заказы", "беру проекты", "стоимость от", "цены:";
- перечисление своих услуг списком ("✅ ... ✅ ... ✅ ...").
Если увидел такие маркеры — ОБЯЗАТЕЛЬНО поставь "is_self_advertising": true И
"is_lead": false, даже если по остальным признакам текст похож на лид. Оба поля
должны быть согласованы: is_self_advertising=true всегда означает is_lead=false.

СКРЫТЫЙ СПРОС (отдельная, независимая оценка — "intent_score"):
Помимо is_lead (явный запрос ПРЯМО СЕЙЧАС), оцени вероятность, что автору
одна из перечисленных выше услуг понадобится В БЛИЖАЙШЕЕ ВРЕМЯ, даже если сейчас
он её не просит. Это отдельный показатель — сообщение может быть is_lead=false
(это не заказ прямо сейчас), но иметь высокий intent_score (услуга скоро
понадобится). Общие признаки скрытого спроса: упоминание устаревшего/
заброшенного текущего решения; запуск нового бизнеса/проекта/направления без
этой услуги; жалобы на нехватку заявок/клиентов/продаж без указания
конкретного решения; открытие нового объекта/направления. Если такого сигнала
нет вообще — ставь intent_score: 0, не выдумывай. Перечисли найденные сигналы в
"intent_signals" (короткие фразы на русском). Поле "intent" остаётся строго
одним из 4 значений схемы (looking_for_contractor | problem_statement |
recommendation_request | unrelated) — для скрытого спроса без прямого запроса
используй "unrelated" или "problem_statement", НЕ придумывай новые значения.

В поле "services" верни ТОЛЬКО те услуги из списка выше (дословно, как они там
написаны), которые упоминаются или подразумеваются в сообщении. Если ни одна не
подходит — верни пустой список.

{_JSON_CONTRACT}"""


def build_user_prompt(text: str, context: Optional[dict] = None) -> str:
    context = context or {}
    parts = [f"Сообщение:\n{text}"]
    if context:
        parts.append(f"\nДополнительный контекст: {context}")
    parts.append("\nВерни только JSON по описанной выше схеме.")
    return "\n".join(parts)


def build_repair_prompt(previous_error: str) -> str:
    return (
        "Твой предыдущий ответ не прошёл валидацию как JSON по заданной схеме. "
        f"Ошибка: {previous_error}. "
        "Верни ИСПРАВЛЕННЫЙ ответ — строго валидный JSON, без markdown-обёртки, "
        "без комментариев, точно соответствующий описанной схеме полей."
    )
