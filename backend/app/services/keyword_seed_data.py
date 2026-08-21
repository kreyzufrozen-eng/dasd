"""Seed keywords for the pre-filter, per category.

Weights are a relative signal strength within a category (used later by
services that want a finer-grained score than plain match count — the
KeywordFilter itself does not decide lead/not-lead, see keyword_filter.py).
"""
from app.models.enums import KeywordCategory

SeedKeyword = tuple[str, KeywordCategory, float]

SEED_KEYWORDS: list[SeedKeyword] = [
    # direct_intent — explicit "I need X" / "I'm looking for X" phrasing
    ("нужен сайт", KeywordCategory.DIRECT_INTENT, 2.0),
    ("ищу разработчика", KeywordCategory.DIRECT_INTENT, 2.0),
    ("ищу веб разработчика", KeywordCategory.DIRECT_INTENT, 2.0),
    ("нужен веб дизайнер", KeywordCategory.DIRECT_INTENT, 2.0),
    ("нужен дизайнер", KeywordCategory.DIRECT_INTENT, 1.5),
    ("сделать сайт", KeywordCategory.DIRECT_INTENT, 2.0),
    ("разработать сайт", KeywordCategory.DIRECT_INTENT, 2.0),
    ("заказать сайт", KeywordCategory.DIRECT_INTENT, 2.0),
    ("ищу фрилансера", KeywordCategory.DIRECT_INTENT, 1.5),
    ("нужен фрилансер", KeywordCategory.DIRECT_INTENT, 1.5),

    # service — services this studio offers
    ("веб-дизайн", KeywordCategory.SERVICE, 1.5),
    ("веб дизайн", KeywordCategory.SERVICE, 1.5),
    ("frontend разработка", KeywordCategory.SERVICE, 1.5),
    ("вёрстка сайта", KeywordCategory.SERVICE, 1.2),
    ("верстка сайта", KeywordCategory.SERVICE, 1.2),
    ("редизайн сайта", KeywordCategory.SERVICE, 1.8),
    ("доработка сайта", KeywordCategory.SERVICE, 1.5),
    ("поддержка сайта", KeywordCategory.SERVICE, 1.0),

    # project_type — kinds of projects
    ("лендинг", KeywordCategory.PROJECT_TYPE, 1.5),
    ("корпоративный сайт", KeywordCategory.PROJECT_TYPE, 1.5),
    ("интернет магазин", KeywordCategory.PROJECT_TYPE, 1.5),
    ("интернет-магазин", KeywordCategory.PROJECT_TYPE, 1.5),
    ("веб приложение", KeywordCategory.PROJECT_TYPE, 1.3),
    ("веб-приложение", KeywordCategory.PROJECT_TYPE, 1.3),
    ("одностраничный сайт", KeywordCategory.PROJECT_TYPE, 1.2),
    ("сайт визитка", KeywordCategory.PROJECT_TYPE, 1.2),

    # problem — signals of an unmet need with an existing site/presence
    ("сайт устарел", KeywordCategory.PROBLEM, 1.8),
    ("нужно обновить сайт", KeywordCategory.PROBLEM, 1.8),
    ("сайт не работает", KeywordCategory.PROBLEM, 1.5),
    ("сайт плохо выглядит", KeywordCategory.PROBLEM, 1.5),
    ("нет сайта", KeywordCategory.PROBLEM, 1.5),
    ("медленный сайт", KeywordCategory.PROBLEM, 1.2),
    ("сайт не адаптивный", KeywordCategory.PROBLEM, 1.2),

    # hidden_intent — business situations that predict a website need
    # soon, without the author asking for one yet (see Lead.intent_score)
    ("сайт устарел", KeywordCategory.HIDDEN_INTENT, 1.5),
    ("старый сайт", KeywordCategory.HIDDEN_INTENT, 1.5),
    ("нужно что-то делать с сайтом", KeywordCategory.HIDDEN_INTENT, 1.8),
    ("работаем только через инстаграм", KeywordCategory.HIDDEN_INTENT, 1.5),
    ("работаем через инстаграм", KeywordCategory.HIDDEN_INTENT, 1.3),
    ("продвигаемся через инстаграм", KeywordCategory.HIDDEN_INTENT, 1.3),
    ("пока без сайта", KeywordCategory.HIDDEN_INTENT, 1.8),
    ("открываем клинику", KeywordCategory.HIDDEN_INTENT, 1.5),
    ("открываем магазин", KeywordCategory.HIDDEN_INTENT, 1.3),
    ("открываем салон", KeywordCategory.HIDDEN_INTENT, 1.3),
    ("открываем шоурум", KeywordCategory.HIDDEN_INTENT, 1.3),
    ("запускаем новый проект", KeywordCategory.HIDDEN_INTENT, 1.3),
    ("запускаем производство", KeywordCategory.HIDDEN_INTENT, 1.3),
    ("запустили производство", KeywordCategory.HIDDEN_INTENT, 1.3),
    ("думаем над сайтом", KeywordCategory.HIDDEN_INTENT, 1.8),
    ("рассматриваем создание сайта", KeywordCategory.HIDDEN_INTENT, 1.8),
    ("нет заявок", KeywordCategory.HIDDEN_INTENT, 1.5),
    ("мало заявок", KeywordCategory.HIDDEN_INTENT, 1.5),
    ("способы получать заявки", KeywordCategory.HIDDEN_INTENT, 1.5),
    ("источники заявок", KeywordCategory.HIDDEN_INTENT, 1.3),
    ("новое направление бизнеса", KeywordCategory.HIDDEN_INTENT, 1.2),

    # technology — tools/stacks that indicate a web project
    ("React", KeywordCategory.TECHNOLOGY, 1.0),
    ("Next.js", KeywordCategory.TECHNOLOGY, 1.0),
    ("WordPress", KeywordCategory.TECHNOLOGY, 1.0),
    ("Webflow", KeywordCategory.TECHNOLOGY, 1.0),
    ("Tilda", KeywordCategory.TECHNOLOGY, 1.0),
    ("Figma", KeywordCategory.TECHNOLOGY, 0.8),

    # exclusion — reduces relevance rather than raising it (see the ТЗ's
    # own "Что не показывать" examples). Deliberately narrow, multi-word
    # phrases here, not bare words like "вакансия" alone — the source mix
    # includes a lot of hiring-channel noise, and a single broad word
    # would flood the pre-filter with messages the AI would just reject
    # anyway, burning AI calls for no benefit. KeywordFilter does not yet
    # treat this category specially (should_pass_to_ai passes on ANY
    # match) — making exclusion matches actually suppress rather than
    # trigger AI analysis is part of Этап 3's pipeline personalization,
    # not this seed data.
    ("работа за отзыв", KeywordCategory.EXCLUSION, 1.0),
    ("оплата отзывом", KeywordCategory.EXCLUSION, 1.0),
    ("ищу работу", KeywordCategory.EXCLUSION, 1.0),
    ("ищу вакансию", KeywordCategory.EXCLUSION, 1.0),
    ("возьмите в штат", KeywordCategory.EXCLUSION, 1.0),
    ("рассмотрю стажировку", KeywordCategory.EXCLUSION, 1.0),
    ("ищу стажировку", KeywordCategory.EXCLUSION, 1.0),
]
