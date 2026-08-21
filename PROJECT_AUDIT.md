# PROJECT_AUDIT.md — LeadHunter (Этап 0)

Аудит перед миграцией single-user личного инструмента в multi-tenant SaaS.
Ничего в коде на этом этапе не менялось — только анализ.

---

## 1. Стек

| Слой | Технология |
|---|---|
| Backend | Python 3.12, FastAPI 0.115, SQLAlchemy 2.0 (async), asyncpg |
| Миграции | Alembic (3 ревизии, вручную написаны) |
| БД | PostgreSQL 16 |
| AI | OpenAI-совместимый chat/completions API (сейчас — реальный GPT-4o-mini), + `MockAIProvider` для dev без ключа |
| Telegram-сбор | Telethon (user-account, не Bot API) |
| Telegram-бот | aiogram 3.15, long polling |
| Frontend | Next.js 14 (App Router), React 18, TypeScript, Tailwind, ручные shadcn-подобные примитивы (без Radix) |
| Инфраструктура | Docker Compose, 5 сервисов: postgres, migrate, backend, worker, bot, frontend |
| Тесты | pytest, 134 теста, SQLite in-memory — без Docker |
| Продакшн | 1 VPS (HOSTKEY, Ubuntu 22.04, Финляндия), IP `222.167.212.158`, без домена/TLS |

## 2. Архитектура пайплайна (как есть)

```
Source (Telegram / Kwork / FL.ru)
   → TelegramCollectorService.collect_from_source()   [сбор + дедуп]
   → RawItem (в БД, без анализа)
   → KeywordFilter.should_pass_to_ai()                [дешёвый прескрин]
   → AIProvider.analyze_lead()                        [GPT-4o-mini]
   → LeadScoringService.calculate_score()              [lead_score 0-100]
   → Lead (в БД)
   → LeadNotifier (Telegram, если score/intent ≥ порога)
```

Воркер (`pipeline_worker.py`) — единственный процесс, который всё это гоняет по таймеру (60 сек номинально, по факту цикл длиннее из-за 433 Telegram-источников). Три сервиса (`backend`, `worker`, `bot`) — **один и тот же Docker-образ**, разные команды запуска.

## 3. Модели БД (что уже есть)

```
Source        — id, name, type(telegram/website/api/freelance), url,
                 external_identifier, is_active, last_checked_at,
                 last_external_id (watermark для докачки)

RawItem        — id, source_id→Source, external_id, author_name/username,
                 text, url, published_at, content_hash, metadata(JSON)
                 UNIQUE(source_id, external_id) — дедуп #1
                 index(content_hash) — дедуп #2

Lead           — id, raw_item_id→RawItem (1:1, UNIQUE),
                 is_lead, lead_probability, lead_score,
                 lead_type, services(JSON), business_niche,
                 project_description, budget_min/max, currency,
                 urgency, complexity, estimated_value,
                 summary, positive_signals(JSON), negative_signals(JSON),
                 intent_score, intent_signals(JSON)   ← добавлено недавно
                 status (new/viewed/contacted/.../archived)

LeadFeedback   — id, lead_id→Lead, feedback_type(good/not_interesting/
                 client/archived), comment

Keyword        — id, keyword, category(direct_intent/service/project_type/
                 problem/technology/hidden_intent), weight, is_active
                 UNIQUE(keyword, category)
```

**Важно: нет ни одной таблицы `users`.** Всё в системе — глобальное, на весь инстанс сразу. Ключевые слова, источники, лиды — общие для всех, кто зайдёт в дашборд.

## 4. API-эндпоинты (что уже есть)

```
GET    /health                      — без авторизации (нужен для Docker healthcheck)

GET    /api/leads                   — фильтры: score_min/max, intent_score_min,
                                       status, source_id, lead_type, is_lead,
                                       date_from/to, sort(newest/score/intent)
GET    /api/leads/{id}
PATCH  /api/leads/{id}               — только status

GET    /api/sources
POST   /api/sources
PATCH  /api/sources/{id}
DELETE /api/sources/{id}

GET    /api/keywords                — фильтр category
POST   /api/keywords
PATCH  /api/keywords/{id}
DELETE /api/keywords/{id}

GET    /api/analytics/overview      — total/today/hot/converted + 7/30-дневные ряды
```

Авторизация: **один общий `X-API-Key`** на весь backend (не per-user — это единственный уровень защиты, добавлен в этой же сессии вместо полного отсутствия auth). CORS ограничен одним origin из `.env`.

## 5. Frontend (что уже есть)

```
/           Dashboard — 4 stat-карточки + 7/30-дневный bar-chart (SVG, без библиотек)
/leads      Список лидов — фильтры (score, intent_score, status, source, service,
            даты), сортировка (newest/score/intent), карточки с inline сменой статуса
/filtered   "Отфильтровано ИИ" — is_lead=false с summary/negative_signals/intent_signals
/sources    CRUD источников (без статистики по эффективности)
/keywords   CRUD ключевых слов, фильтр по категории
```

Компоненты: `lead-card`, `filtered-item-card`, `nav`, `stat-card`, `simple-bar-chart` +
ручные `ui/*` примитивы (button, card, badge, input, select, dialog, table).
Тёмная тема — единственная (нет переключателя, но и светлой темы просто нет — весь CSS писан под тёмный фон).

**Аутентификации на фронте нет вообще.** `NEXT_PUBLIC_API_KEY` вшит в билд и одинаков для всех, кто откроет сайт — по сути "кто знает URL, тот и админ".

## 6. AI-логика — ключевые детали

- **Промпт** (`app/ai/prompts.py`) жёстко зашит под одну профессию: "студия, которая предоставляет разработку сайтов / веб-дизайн / лендинги / интернет-магазины". Это **прямо противоречит** цели SaaS — промпт нужно параметризовать под `SearchProfile` каждого пользователя.
- Два независимых скора: `lead_score` (годится ли сообщение вообще для кого-то в этой нише) и `intent_score` (скрытый спрос — понадобится ли сайт скоро). **Пока нет ничего похожего на персональный Match Score** — это придётся строить с нуля (п.9 ТЗ).
- `is_self_advertising` — защита от того, что исполнители сами себя рекламируют, ловится отдельным полем схемы, а не эвристикой по `negative_signals` (была реальная проблема с этим, исправлено).
- Retry/repair-логика на невалидный JSON от модели уже есть (`openai_compatible_provider.py`, до 3 попыток).
- **AI usage tracking отсутствует полностью** — нет ни подсчёта токенов, ни стоимости, ни лимитов. Для SaaS с биллингом это блокер (п.45 ТЗ).

## 7. Источники — архитектура адаптеров (уже готова к расширению)

```python
BaseSourceAdapter (ABC)
  ├── TelegramSourceAdapter   — Telethon, min_id watermark, 5-дневный cutoff
  ├── KworkProjectsAdapter    — парсинг встроенного JSON-состояния страницы
  ├── FlRuProjectsAdapter     — HTML-парсинг (BeautifulSoup), т.к. нет встроенного JSON
  └── ApiSourceAdapter / FreelanceSourceAdapter — задел на будущее, не реализованы
```

Это ровно то, что просит п.21 ТЗ ("Не создавать дублирующую архитектуру") — **уже сделано правильно**, расширять новыми адаптерами тривиально.

Сейчас подключено: **433 Telegram-канала**, kwork.ru, FL.ru. Все источники — глобальные (общие на всю систему), привязки к пользователю нет.

## 8. Что уже работает и это подтверждено вживую на проде

- Сбор + дедуп + AI-анализ + скоринг — гоняется на реальном сервере, реальные лиды приходят в Telegram
- kwork.ru / FL.ru парсеры — проверены на реальных данных
- intent_score (скрытый спрос) — проверен на 4 примерах пользователя, работает
- Docker-хардненинг (non-root), CORS, security headers, `.env` не течёт — проверено security-аудитом
- 104 из 134 тестов проходят

## 9. Проблемы, которые аудит обязан зафиксировать честно

### Критично для SaaS-миграции
1. **Нет модели `User` вообще.** Это не "доработать", а добавить с нуля — самая большая часть Этапа 1.
2. **Нет изоляции данных.** Все `Lead`, `Source`, `Keyword` — на всю систему разом. Придётся добавлять `user_id`/`search_profile_id` практически везде и переписывать все `WHERE`-условия в репозиториях.
3. **Промпт AI — не персонализирован.** Один и тот же хардкоженный промпт про веб-студию. Нужен `PersonalizedAIContext` per `SearchProfile` (п.44 ТЗ) — по сути новый слой над существующим `AIProvider`.
4. **AI cost control отсутствует.** Для платного SaaS нужен трекинг расхода до первого релиза с реальными пользователями, иначе можно легко улететь в минус на AI-счетах.

### Технический долг, обнаруженный сейчас
5. **30 из 134 тестов красные** — сломаны правками этой сессии (X-API-Key auth не учтён в фикстурах, изменённая сигнатура `notify_if_qualifying`/`format_lead_notification` под intent_score не отражена в тестах). Нужно почистить перед тем, как наращивать новую функциональность поверх — иначе будет непонятно, что сломал новый код, а что было сломано уже.
6. **Уязвимые версии зависимостей** (задокументировано в прошлом аудите): `aiohttp`/`starlette` зажаты версиями `aiogram`/`fastapi`, `Next.js 14.2.15` с известными CVE. Не блокер для функциональности, но стоит держать в уме при апгрейде стека под Этап 1 (multi-user обычно тянет апгрейд auth-библиотек всё равно).
7. **Нет доменного имени и TLS.** Всё висит на голом IP по HTTP. Для регистрации/логина с паролями это неприемлемо — пароли и session-токены нельзя гонять в открытом виде. **TLS — жёсткая предпосылка Этапа 1**, не опция.
8. **Global API key вместо per-user auth.** Придётся полностью заменить на JWT/сессии — совместимо с тем, что просит п.5 ТЗ, но текущий механизм не переиспользуется, только сам паттерн `Depends()`-инъекции.

## 10. Что можно и нужно переиспользовать как есть

- Весь пайплайн `SOURCE → RAW_ITEM → FILTER → AI → SCORE → LEAD` — не трогаем, только добавляем `search_profile_id` контекст
- `BaseSourceAdapter` и все 3 адаптера — не трогаем
- `LeadScoringService` — остаётся как есть, это `lead_score` (глобальное качество), рядом достраивается отдельный `MatchScoreService`
- Структура репозиториев/схем/роутеров FastAPI — паттерн сохраняется, просто добавляется user-scoping
- UI-компоненты и тёмная тема — не трогаем визуально, только новые страницы в том же стиле
- `docker-compose.yml`, структура `app/{api,core,db,models,repositories,schemas,services,sources,ai,bot,workers}` — сохраняется без изменений

---

# Краткий план миграции в SaaS

Точка входа для Этапа 1 (после подтверждения этого аудита) —
**добавить `User`/`SearchProfile`, не трогая пайплайн**, всё остальное (onboarding UI,
Match Score, Opportunities-страница, CRM, биллинг, admin) — последующие этапы,
как и написано в ТЗ (п.49), по одному за раз с проверкой между ними.

### Этап 1 — фундамент (следующий шаг)
1. `User` (email, password_hash, created_at) + Alembic-миграция
2. JWT-аутентификация (`python-jose` + `passlib[bcrypt]`), эндпоинты `/api/auth/{register,login,logout,refresh}`
3. `SearchProfile` (модель из п.43 ТЗ) — пока один профиль на пользователя, поле `ai_profile_context` пустое (заполнится на Этапе 2/onboarding)
4. Добавить `user_id`/`search_profile_id` в `Lead` (через `RawItem`? нет — лид персонален, поэтому `Lead` должен стать `(raw_item_id, search_profile_id)`, не 1:1 с `RawItem` — **это меняет уникальный constraint** и требует отдельного продумывания: сейчас один `RawItem` = один `Lead`; в multi-user один `RawItem` может породить N лидов, по одному на каждый подходящий `SearchProfile`)
5. Domain-исключения + FastAPI dependency для "текущий пользователь", изоляция во всех репозиториях
6. TLS/домен — организационный шаг (нужен домен + Let's Encrypt/Caddy), делаю параллельно, т.к. без него небезопасно принимать пароли
7. Почистить 30 падающих тестов заодно (иначе непонятно, что ломает новый код)
8. Прогнать существующий single-user workflow (Kwork/FL.ru/Telegram сбор → лиды → Telegram-уведомление) и убедиться, что ничего не сломалось

**Оценка сложности:** пункт 4 (Lead становится не 1:1 с RawItem) — самое рискованное архитектурное решение во всём Этапе 1, трогает `lead_pipeline.py`, `pipeline_worker.py`, все репозитории и API leads.py. Хочу явно подтвердить этот момент с тобой перед стартом кода — см. вопрос ниже.

---

## Вопрос перед стартом Этапа 1

В текущей схеме `Lead.raw_item_id` — уникальный (1 сообщение = максимум 1 лид на всю систему). В multi-tenant мире **одно и то же сообщение может быть лидом для пользователя А и не быть лидом для пользователя Б** (п.2 ТЗ: "Один и тот же источник может выдавать разные лиды разным пользователям").

Это значит `Lead` должен перестать быть 1:1 с `RawItem` и стать N:1 (много лидов на одно сообщение — по одному на каждый подходящий профиль). Это самое важное архитектурное решение Этапа 1, и я хочу подтвердить его с тобой явно, а не тихо менять constraint в БД с реальными данными (646k+ `raw_items`, 400+ `leads` уже накоплено на проде).

Подтверди, пожалуйста, и я начинаю Этап 1.
