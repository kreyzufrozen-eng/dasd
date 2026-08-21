# ReadHunter

Automated lead-discovery system for web development / web design services.
Monitors allowed public Telegram sources via Telethon (with a pluggable
adapter interface for future API-based sources), filters and analyzes
messages with an AI provider, scores them, and pushes qualified leads to a
Telegram bot and a Next.js dashboard.

**Status: MVP complete — all 12 build stages implemented.**

```
SOURCE -> COLLECT RAW ITEM -> DEDUPLICATION -> KEYWORD FILTER
       -> AI ANALYSIS -> LEAD SCORING -> DATABASE
       -> TELEGRAM NOTIFICATION -> DASHBOARD
```

## Project structure

```
lead-hunter/
  backend/
    app/
      api/           FastAPI routers: health, leads, sources, keywords, analytics
      core/           config (env vars), logging, scoring weights
      db/             async SQLAlchemy engine/session, declarative base, seed script
      models/         ORM models: Source, RawItem, Lead, LeadFeedback, Keyword
      schemas/        Pydantic v2 request/response schemas + AI response schema
      repositories/   DB access per entity (CRUD + queries), no business logic
      services/       KeywordFilter, LeadScoringService, DuplicateDetectionService,
                       LeadPipelineService, TelegramCollectorService, LeadStatsService
      sources/        BaseSourceAdapter, TelegramSourceAdapter (Telethon),
                       ApiSourceAdapter / FreelanceSourceAdapter interfaces
      ai/             AIProvider abstraction: MockAIProvider (default, no key needed),
                       OpenAICompatibleProvider (retry + JSON repair on invalid output)
      bot/             aiogram bot: /start /leads /hot /stats, inline action buttons
      workers/         IntervalScheduler + pipeline_worker entrypoint (collect + analyze)
      main.py         FastAPI app factory
    alembic/           migrations (hand-written initial schema + one add-column revision)
    tests/             pytest suite — 133 tests, no Docker/Postgres required to run
    Dockerfile
    requirements.txt / requirements-dev.txt
  frontend/
    app/               Next.js App Router pages: /, /leads, /sources, /keywords
    components/        shadcn-style UI primitives + lead-card, nav, stat-card, chart
    lib/               typed API client (api.ts), types.ts, utils.ts
    Dockerfile
  docker-compose.yml   postgres, migrate, backend, worker, bot, frontend
  .env.example
```

Backend runs as **one codebase, three processes** (`backend`/API, `worker`,
`bot` in docker-compose) — same image, different container command — so
there's nothing to keep in sync between them.

## Quick start (Docker — recommended)

Requires Docker + Docker Compose (this repo was built in a sandbox without
either installed — see [Verification notes](#verification-notes) below for
exactly what was and wasn't runnable during development).

```bash
cp .env.example .env
docker compose up --build
```

- API: http://localhost:8000 (interactive docs at `/docs`, healthcheck at `/health`)
- Frontend: http://localhost:3000
- Postgres: localhost:5432

Startup order: `postgres` → `migrate` (runs `alembic upgrade head` then
seeds the keyword list, idempotently) → `backend` / `worker` / `bot` (wait
on `migrate` via `depends_on: service_completed_successfully`) → `frontend`.

By default `AI_PROVIDER=mock`, so the **entire pipeline runs end-to-end
without any AI API key** using a deterministic rule-based analyzer.
Telegram monitoring and the notification bot stay inert (logged, not
crashing) until `TELEGRAM_*` / `BOT_TOKEN` are configured — see below.

### Enabling Telegram monitoring

1. Get `TELEGRAM_API_ID` / `TELEGRAM_API_HASH` from https://my.telegram.org
2. Set them in `.env`, plus `TELEGRAM_ALLOWED_SOURCES` (comma-separated
   public channel usernames you're allowed to monitor).
3. Add matching `Source` rows via the API/dashboard (`type: "telegram"`,
   `external_identifier` = the channel username).
4. Authenticate once, interactively (Telethon needs a login code the first
   time — the recurring worker never blocks on stdin, so this is a
   separate one-off step):
   ```bash
   docker compose run --rm worker python -m app.workers.telegram_login
   ```
   The resulting session is stored in the `telegram_sessions` volume and
   persists across restarts.
5. `docker compose up -d worker` (or restart the stack) — it will now poll
   every `TELEGRAM_POLL_INTERVAL_SECONDS`.

### Enabling the notification bot

Set `BOT_TOKEN` (from @BotFather) and `NOTIFICATION_CHAT_ID` (the chat/user
id to receive notifications) in `.env`, then restart the `bot` and `worker`
services. Leads scoring ≥ `NOTIFICATION_THRESHOLD` (default 60) get pushed
automatically with inline action buttons; the bot also answers
`/start`, `/leads`, `/hot`, `/stats`.

### Enabling real AI analysis

Set `AI_PROVIDER=openai_compatible`, `AI_BASE_URL`, `AI_API_KEY`, `AI_MODEL`
in `.env` and restart `worker`. Works with OpenAI itself or any
OpenAI-compatible `/chat/completions` endpoint.

## Local backend development (without Docker)

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
cp ../.env.example ../.env   # edit DATABASE_URL to point at a local Postgres (or leave as-is to see graceful DB-down behavior)
uvicorn app.main:app --reload
```

Without a running Postgres, `/health` reports `"database": "error"` but the
process still starts and serves requests — it never crashes on DB
unavailability, per the project's error-handling rules.

To run the worker/bot locally the same way:
```bash
python -m app.workers.pipeline_worker
python -m app.bot.run_bot
```

## Local frontend development

```bash
cd frontend
npm install
npm run dev
```

Reads the backend URL from `NEXT_PUBLIC_API_URL` (defaults to
`http://localhost:8000`).

## Running tests

```bash
cd backend
source .venv/bin/activate
pytest
```

**133 tests, all runnable without Docker/Postgres** — repository/model
tests use in-memory SQLite (`aiosqlite`), API tests use FastAPI's
dependency-override mechanism against the same, and pure business-logic
tests (scoring, keyword filter, dedup, AI schema validation, Telegram
adapter, scheduler, bot formatting/handlers) have no external dependencies
at all. Covers, per the spec's testing requirements: `LeadScoringService`,
`DuplicateDetectionService`, `KeywordFilter`, and AI response validation —
plus the full pipeline, repositories, REST API, and bot.

## Environment variables

See [.env.example](.env.example) for the full list with comments. Nothing
is hardcoded — every secret/endpoint is env-driven; `.env` is git-ignored.

## Verification notes

This project was built in a sandbox with **no Docker and no Node.js/npm
installed** (only a Python 3.9 interpreter). Given that constraint,
verification split into what was actually runnable vs. what could only be
reviewed statically:

**Actually executed and verified:**
- Full backend test suite (133 tests) in a local Python 3.9 venv
- The literal `migrate` service command end-to-end
  (`alembic upgrade head && python -m app.db.seed`, including the
  idempotency of the seed step) against a real database file
- `uvicorn app.main:app` booting and serving `/health` and all REST routes
- Every backend module/entrypoint import-checked and `py_compile`-checked

**Not executable in this sandbox — review only, verify yourself:**
- `docker compose up --build` (no Docker available)
- The frontend build (`npm install && npm run build`/`next build`) — no
  Node.js available. Frontend code was hand-written to match Next.js/shadcn
  conventions, statically reviewed for import/type/prop consistency, and
  two real bugs were caught and fixed this way (a `string`/`number` type
  mismatch on `estimated_value`, and a missing Docker build-arg for
  `NEXT_PUBLIC_API_URL`) — but an actual `next build` has not run.
- Real Telegram/Postgres connectivity (Telethon auth, asyncpg against a
  live Postgres) — the code paths are covered by tests using fakes/SQLite,
  but not against the real services.

Before relying on this in production, run `docker compose up --build`
yourself and confirm the frontend actually compiles and renders.

## Known simplifications (documented in code, listed here for visibility)

- `KeywordFilter` is a pre-filter only (word-boundary regex matching) — it
  never makes the final is-a-lead decision, per spec.
- `DuplicateDetectionService` implements the two required checks
  (source+external_id, content_hash); fuzzy text-similarity dedup is
  explicitly out of scope for this MVP (spec marks it optional).
- The background scheduler is a plain `asyncio` interval loop
  (`app/workers/scheduler.py`), not Celery/Arq — deliberately, so it's easy
  to see how business logic (plain async functions) would plug into either.
- `frontend/components/ui/dialog.tsx` and `select.tsx` are hand-rolled
  (no Radix UI) since npm wasn't available to add that dependency — no
  focus trap/portal on the dialog, native `<select>` under the hood.
- The dashboard's 7/30-day chart is a small hand-rolled SVG bar chart, not
  a charting library dependency.
- `Source.last_external_id` was added beyond the original spec's field
  list — required to persist "last processed message" and recover cleanly
  after a worker restart, which the spec's Telegram-monitoring section
  explicitly asks for but the original Source field list didn't include a
  column for.
