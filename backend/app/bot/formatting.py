"""Message formatting for Telegram notifications and bot replies.

Kept free of any aiogram/DB imports so it's trivially unit-testable —
pure functions from plain data to a message string.
"""
from typing import Optional, Sequence

from app.models.lead import Lead
from app.models.raw_item import RawItem
from app.models.source import Source

VERY_HOT_THRESHOLD = 90


def format_budget(lead: Lead) -> str:
    if lead.budget_min is None and lead.budget_max is None:
        return "не указан"
    currency = lead.currency or ""
    if lead.budget_min is not None and lead.budget_max is not None:
        return f"{lead.budget_min:g}–{lead.budget_max:g} {currency}".strip()
    value = lead.budget_min if lead.budget_min is not None else lead.budget_max
    return f"{value:g} {currency}".strip()


def format_services(services: Sequence[str]) -> str:
    return ", ".join(services) if services else "не указаны"


def format_signals(signals: Sequence[str]) -> str:
    if not signals:
        return "—"
    return "\n".join(f"• {s}" for s in signals)


def format_lead_notification(lead: Lead, raw_item: RawItem, source: Optional[Source]) -> str:
    """Matches the required notification layout exactly, plus a
    🔥🔥 VERY HOT marker for score >= 90 per the spec's threshold rules.

    A message can qualify for notification purely on intent_score (hidden
    demand — no explicit request today, see Lead.intent_score) with
    is_lead=False and lead_score=0; that gets its own 🌱 header instead of
    being mislabeled "НОВЫЙ ЛИД" for a request that doesn't exist yet.
    """
    if lead.is_lead:
        header = "🔥🔥 ОЧЕНЬ ГОРЯЧИЙ ЛИД" if lead.lead_score >= VERY_HOT_THRESHOLD else "🔥 НОВЫЙ ЛИД"
    else:
        header = "🌱 СКРЫТЫЙ СПРОС"
    source_name = source.name if source else "неизвестен"

    score_line = f"Score: {lead.lead_score}/100"
    if lead.intent_score > 0:
        score_line += f"\nIntent Score: {lead.intent_score}/100 (вероятность, что сайт скоро понадобится)"

    signals = lead.positive_signals if lead.is_lead else lead.intent_signals
    why_label = "Почему подходит" if lead.is_lead else "Признаки скорой потребности"

    return (
        f"{header}\n"
        f"{score_line}\n\n"
        f"Услуги:\n{format_services(lead.services)}\n\n"
        f"Описание:\n{lead.summary or lead.project_description or '—'}\n\n"
        f"Ниша:\n{lead.business_niche or 'не указана'}\n\n"
        f"Бюджет:\n{format_budget(lead)}\n\n"
        f"Срочность:\n{lead.urgency or 'не указана'}\n\n"
        f"Источник:\n{source_name}\n\n"
        f"{why_label}:\n{format_signals(signals)}"
    )


def format_lead_summary_line(lead: Lead) -> str:
    """One-line summary used in /leads and /hot listings."""
    desc = (lead.summary or lead.project_description or "—").strip()
    if len(desc) > 80:
        desc = desc[:77] + "..."
    return f"#{lead.id} · {lead.lead_score}/100 · {desc}"


def format_stats_message(
    total: int, today: int, hot: int, converted: int
) -> str:
    return (
        "📊 Статистика ReadHunter\n\n"
        f"Всего лидов: {total}\n"
        f"Сегодня найдено: {today}\n"
        f"Горячих (60+): {hot}\n"
        f"Конвертировано: {converted}"
    )
