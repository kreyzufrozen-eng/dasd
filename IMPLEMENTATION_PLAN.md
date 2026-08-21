# LeadHunter — Implementation Plan: Multi-Search-Profile SaaS

Written per the user's ТЗ (2026-08-18): turn LeadHunter into a self-serve,
multi-профиль SaaS where each user describes their business in plain text
and gets a personalized, independently-configurable search ("Search
Profile") — potentially several per user — instead of one hardcoded
web-dev persona for everyone.

This document is Этап 1 only: analysis + plan. No refactoring has started.

---

## 1. Current architecture (verified by reading the code, not assumed)

### Stack
FastAPI 0.115 + SQLAlchemy 2.0 async + asyncpg + Alembic + PostgreSQL 16 /
Telethon (Telegram) + aiogram 3.15 (bot) / Next.js 14 App Router + React 18
+ TypeScript + Tailwind + hand-rolled shadcn-style UI. Auth: JWT in an
httpOnly cookie (Stage 1, already shipped). Multi-tenant foundation
(User + SearchProfile + per-profile Lead isolation) is already live in
production — this ТЗ is the next layer on top of that, not a restart.

### Entities that exist today

| Entity | Ownership today | Notes |
|---|---|---|
| `User` | — | email/password, `is_admin`. Shipped. |
| `SearchProfile` | `user_id` FK | **Already supports multiple profiles per user at the data/API layer** — `SearchProfileRepository.list_for_user()` and the `/api/search-profiles` CRUD return/accept any number of profiles. Already has: name, profession, profession_description, services[], skills[], technologies[], target_clients, preferred_niches[], excluded_niches[], min/max_budget, currency, geography, languages[], lead_types[], notification_threshold, is_active, ai_profile_context. This is ~90% of the ТЗ's requested SearchProfile shape already. |
| `Source` | **none — fully global** | telegram/api/freelance/website type. No per-user link at all. Admin-only CRUD (`/api/sources`, gated by `get_current_admin_user`). |
| `Keyword` | **none — fully global** | category (direct_intent/service/project_type/problem/technology/hidden_intent) + weight + is_active. Admin-only CRUD (`/api/keywords`). |
| `RawItem` | via `Source` | Deduplicated raw message (source_id, external_id, content_hash, text, author, published_at). |
| `Lead` | `search_profile_id` FK, N:1 with `RawItem` | **This is the key existing piece that makes per-profile personalization possible without a schema change**: one `RawItem` can already have many `Lead` rows, one per `SearchProfile`, via `UniqueConstraint(raw_item_id, search_profile_id)`. `lead_score` (0-100) is *already scoped to one profile's Lead row* — it can directly become "Match Score" once the AI call that produces it is profile-aware. No new `match_score` column needed. |
| `LeadFeedback` | via `Lead` | Currently just `lead_id` + `feedback_type` (good/not_interesting/client/archived) + optional comment. No `user_id`/`search_profile_id`/generic `action` yet. |

### How parsing/pipeline works today (SOURCE → ... → NOTIFICATION)

```
TelegramSourceAdapter / KworkProjectsAdapter / FlRuProjectsAdapter
  → TelegramCollectorService (dedup by source+external_id, then content_hash)
  → RawItem persisted
  → [worker cycle, every ~60s via IntervalScheduler]
  → RawItemRepository.list_without_lead(search_profile_id, limit=1000, max_age_days=5)
  → KeywordFilter.should_pass_to_ai(text)   — cheap pre-filter, ANY active keyword match passes
  → AIProvider.analyze_lead(text) → LeadAnalysis (Pydantic-validated JSON)
  → LeadScoringService.calculate_score(...) → 0-100 lead_score
  → Lead row created (search_profile_id attached)
  → LeadNotifier → Telegram bot message if score/intent ≥ threshold
```

**The critical gap**: `run_lead_pipeline()` in `pipeline_worker.py` resolves
exactly **one** "primary" `SearchProfile` (`SearchProfileRepository.
get_primary()` = oldest active profile system-wide) and runs the *entire*
pipeline — keyword filter, AI call, scoring — against that single profile
only. Every other registered user's profile gets zero leads. This was an
explicit, documented Stage-1 shortcut (see `PROJECT_AUDIT.md` and the
docstring on `get_primary()`) specifically deferred to "Stage 3". This ТЗ
*is* Stage 3, plus multi-profile-per-user, plus onboarding, plus a rebuilt
UI around it.

The AI prompt itself (`app/ai/prompts.py`) is a **hardcoded, single-persona
system prompt** ("ты анализируешь сообщения... для студии, которая
предоставляет разработку сайтов...") with a hardcoded `OFFERED_SERVICES`
set in `lead_pipeline.py` used for scoring. Zero parameterization by
profile today.

### API inventory (all under JWT auth except register/login)

- `/api/auth/*` — register, login, logout, me, change-password
- `/api/search-profiles` — full CRUD, already user-scoped, already multi-profile-capable
- `/api/leads` — list/detail/patch status; resolves "the user's first profile" via `SearchProfileRepository.get_first_id_for_user()` (a Stage-1 single-profile assumption baked into 3 call sites: `leads.py` ×3, `analytics.py` ×1)
- `/api/analytics/overview` — per-profile-scoped (same "first profile" assumption)
- `/api/sources`, `/api/keywords` — global, admin-only
- `/api/admin/*` — overview + user management, admin-only
- Bot commands (`/leads`, `/hot`, `/stats`) — resolve the system-wide "primary" profile, same Stage-1 shortcut

### Frontend inventory

- `/` Dashboard, `/leads`, `/filtered` (AI-rejected items), `/sources`,
  `/keywords`, `/admin`, `/login`, `/register` — all `'use client'`
  components, manual fetch+state (no data-fetching library), shared
  `Card`/`Button`/`Input`/`Select`/`Dialog`/`Table`/`Badge` primitives in
  `components/ui/*`, dark theme via Tailwind CSS variables. `AuthProvider`
  + `AuthGate` (React context) already handle session/redirect.
- `/leads` and `/filtered` both call `getSources()` for their filter
  dropdown — **this will 403 for any non-admin user today**, an existing
  bug this work will fix as a side effect of making sources per-profile.
- No profile switcher, no onboarding, no "Мои поиски" page — none of this
  exists yet.

---

## 2. What gets reused as-is (no changes)

- Auth system (JWT cookie, register/login/admin gating) — untouched.
- `RawItem` + `TelegramCollectorService` + dedup logic — untouched.
- `AIProvider` interface / `get_ai_provider` factory / mock+openai_compatible
  providers — untouched interface; only the *prompt content* becomes
  profile-parameterized.
- `KeywordFilter` matching engine (regex word-boundary matcher) — untouched;
  only *which keyword rows* get fed into it changes (per-profile query
  instead of "all active keywords").
- `LeadScoringService` formula/weights engine — untouched; only the
  *inputs* (`matches_offered_services` etc.) become profile-aware instead
  of reading a hardcoded `OFFERED_SERVICES` set.
- `Lead`/`LeadWithContextRead` schema, `LeadRepository.search()`, the
  `LeadCard`/`FilteredItemCard` components, `Dashboard`'s stat cards/chart,
  the whole `components/ui/*` design system, `AuthProvider`/`AuthGate`/`Nav`
  shell.
- Bot notification plumbing (`LeadNotifier`, aiogram handlers/keyboards) —
  reused, just re-pointed at per-profile data instead of the single global
  profile.
- Admin panel — untouched (still a global system view; sources/keywords
  management moves *into* it as the global catalog, see §4).

## 3. What has to change, and why

1. **Source/Keyword ownership model** → junction tables (`SearchProfileSource`,
   `SearchProfileKeyword`), *not* per-user duplicate rows. A `Source` (e.g.
   a public Telegram channel) is a real-world object shared by every user
   who wants to watch it; duplicating it per user would break dedup
   (`RawItem` dedups by `source_id` + `external_id`) and multiply parsing
   work per channel by however many users add it. This exactly matches
   what the ТЗ itself asks for ("Source существует один раз, но имеет
   связь с несколькими SearchProfiles").
2. **Keywords become two-tier**: a global/admin-curated catalog (today's
   `Keyword` table, kept as-is) that seeds new profiles, plus a
   `SearchProfileKeyword` junction that lets each profile enable/disable/
   reweight/recategorize a keyword independently, or add profile-private
   keywords. This is the ТЗ's own "GLOBAL_KEYWORDS vs USER_KEYWORDS" split.
3. **Pipeline becomes fan-out, not single-profile**: `run_lead_pipeline()`
   must iterate *all active SearchProfiles* (not just the "primary" one),
   pre-filter each `RawItem` against each profile's own keyword set, and
   only call the AI once per (RawItem, candidate profile) pair that
   survives pre-filtering. One `RawItem` can and will produce Lead rows
   for multiple profiles — the schema already supports this (§1). Cost
   control matters here: with N active profiles this is O(N) pre-filter
   checks (cheap, local, no I/O) but still O(matches) AI calls — acceptable
   for MVP scale, revisit with a shared-candidate-set optimization only if
   profile count grows large enough to matter.
4. **AI prompt becomes profile-parameterized**: replace the hardcoded
   `SYSTEM_PROMPT` with a template built from `SearchProfile` fields
   (profession, services, desired/excluded orders, ai_profile_context) at
   call time. Keep the existing strict JSON-schema contract and
   `is_self_advertising` deterministic backstop — both are provider-
   agnostic, profession-agnostic mechanisms, nothing to change there.
5. **`lead_score` becomes "Match Score"** — no new column. Since `Lead` is
   already N:1 per profile, the existing 0-100 `lead_score` produced by
   `LeadScoringService` *is* the per-profile match score once step 3/4
   land. `lead_type` (already a free-text column) becomes the
   hot/potential/hidden_demand classification the ТЗ wants, derived from
   `lead_score` + `intent_score` bands (thresholds documented in §5).
6. **Onboarding**: new "describe yourself in plain text" → AI extracts a
   structured `SearchProfile` draft → user reviews/edits → keywords
   auto-generated → sources selected from a catalog → profile created and
   activated. All net-new frontend + one new backend endpoint
   (`POST /api/search-profiles/generate-draft`, AI call, no DB write) plus
   reusing the existing `POST /api/search-profiles` to actually create it.
7. **"Мои поиски" (My Searches) page + profile switcher** in the nav —
   net-new frontend, backed by the already-existing `GET /api/search-profiles`.
8. **`/api/leads`, `/api/analytics/overview` need an explicit `search_profile_id`
   param** instead of silently picking "the user's first profile" — this
   is the one true breaking change to an existing endpoint contract (still
   ownership-checked, still 404s on a profile that isn't the caller's).
9. **LeadFeedback gets a generic `action` field** (relevant/irrelevant/
   saved/contacted) alongside the existing `feedback_type` enum, plus
   `search_profile_id` for future signal use — additive, not a rewrite of
   the existing bot feedback flow.
10. **Subscriptions/Plans/Usage** — net-new, additive tables. Nothing
    currently enforces limits, so this is pure preparation (no existing
    behavior to preserve/break).

## 4. Database changes (new Alembic migration `0005_*`)

New tables:

```
search_profile_sources (search_profile_id FK, source_id FK, enabled bool,
                         created_at)  — UNIQUE(search_profile_id, source_id)

search_profile_keywords (search_profile_id FK, keyword_id FK NULLABLE,
                          -- NULL keyword_id = profile-private keyword,
                          -- text/category/weight below are then authoritative
                          text, category, weight, enabled, created_at)
                          — UNIQUE(search_profile_id, keyword_id) when keyword_id set

lead_feedback: ADD COLUMN action VARCHAR(32) NULL,
               ADD COLUMN search_profile_id INT NULL FK  (backfilled from
               lead.search_profile_id for existing rows)

keywords: ADD COLUMN is_global BOOLEAN DEFAULT true NOT NULL
          (existing 60 seed rows stay is_global=true — the shared catalog
          new profiles get seeded from; profile-private rows go through
          search_profile_keywords.text instead, not this table, so this
          flag is mostly documentation/future-proofing)

sources: ADD COLUMN category VARCHAR(64) NULL   (for catalog grouping —
         🔥 Фриланс / 🎨 Дизайн / 💻 Разработка / etc., per ТЗ §"Каталог источников")
         ADD COLUMN added_by_user_id INT NULL FK  (who first added a
         custom source — for "your own vs catalog" distinction in UI)

subscription_plans (id, name, max_search_profiles, max_sources_per_profile,
                     max_ai_analyses_per_month, price, created_at)
subscriptions (id, user_id FK, plan_id FK, status, current_period_start,
               current_period_end, created_at)
usage_counters (id, user_id FK, period_start, ai_analyses_count,
                created_at, updated_at)
```

No destructive changes to any existing table/column. `leads.lead_score`,
`leads.lead_type` are reinterpreted at the application layer (§3.5), not
altered in the DB.

## 5. Match Score / lead_type bands (reusing existing columns)

```
lead_score 0-39   → lead_type = "irrelevant"      (not shown by default)
lead_score 40-59  → lead_type = "weak"             (shown, low priority)
lead_score 60-74  → lead_type = "potential_lead"
lead_score 75-89  → lead_type = "hot_lead"  wait — see below
lead_score 90-100 → lead_type = "hot_lead"
intent_score ≥ 60 AND lead_score < 60 → lead_type = "hidden_opportunity"
  (independent axis, already how intent_score works today — no change to
  that mechanic, just a display/classification label on top of it)
```
(Exact cut points configurable via `app/core/scoring_config.py`, already
the pattern used for the scoring weights — no new config mechanism
needed.)

## 6. New/changed API surface

```
POST   /api/search-profiles/generate-draft      NEW — AI text→profile draft, no DB write
GET    /api/leads?search_profile_id=..          CHANGED — explicit param, was implicit
GET    /api/analytics/overview?search_profile_id=..  CHANGED — same
GET    /api/search-profiles/{id}/keywords        NEW
POST   /api/search-profiles/{id}/keywords        NEW
PATCH  /api/search-profiles/{id}/keywords/{kwid}  NEW
DELETE /api/search-profiles/{id}/keywords/{kwid}  NEW
POST   /api/search-profiles/{id}/keywords/generate NEW — AI keyword suggestion
GET    /api/search-profiles/{id}/sources          NEW
POST   /api/search-profiles/{id}/sources          NEW (attach existing or create+attach new Source)
PATCH  /api/search-profiles/{id}/sources/{srcid}   NEW (enable/disable)
DELETE /api/search-profiles/{id}/sources/{srcid}   NEW (detach, not delete Source)
GET    /api/sources/catalog                       NEW — browsable catalog, grouped by category, JWT-only (not admin-only, read access for all users)
POST   /api/leads/{id}/feedback                    NEW — writes LeadFeedback with action
GET    /api/search-profiles/{id}/analytics         NEW — funnel/conversion (processed→candidates→leads→hot)
```

`/api/sources`, `/api/keywords` (the flat admin ones) stay exactly as they
are — the global catalog management surface, admin-only, unchanged.

## 7. Frontend changes

New pages: `/onboarding` (multi-step wizard), `/searches` ("Мои поиски"),
`/searches/[id]/*` (tabbed settings: Общее / Что искать / Ключевые слова /
Источники / Исключения / AI-настройка / Уведомления).

Changed: `Nav` gains a profile switcher + "Мои поиски" + updates its route
list; `AuthGate` gains a redirect-to-`/onboarding` rule when the logged-in
user has zero SearchProfiles (mirrors the existing "redirect to /login
when unauthenticated" pattern already in `components/auth-gate.tsx`);
Dashboard, `/leads`, `/filtered` all become profile-scoped (read the active
profile from a new lightweight `ActiveProfileProvider` context, sibling to
the existing `AuthProvider`); `LeadCard` gains the Match Score badge +
"why it matched" reasons list + feedback buttons.

All new UI reuses the existing `components/ui/*` primitives — no new
design-system components planned except a `ProfileSwitcher` dropdown and a
`StepIndicator` for the onboarding wizard (both thin wrappers over
existing `Button`/`Card`).

## 8. Order of implementation (Этапы 2–11, per the ТЗ's own staging)

1. **Этап 2 — Backend foundation**: migration 0005, `SearchProfileSource`/
   `SearchProfileKeyword` models+repos, per-profile keyword/source APIs,
   `search_profile_id` explicit param on leads/analytics, sources catalog
   endpoint. Verify: existing single-profile flow (today's one real
   profile) keeps working unchanged.
2. **Этап 3 — Pipeline personalization**: fan-out pipeline across active
   profiles, profile-parameterized AI prompt, profile-aware scoring
   inputs. This is the highest-risk stage (touches the live production
   pipeline) — will be built and tested against a copy of prod data before
   deploying, same process as the Stage 1 migration.
3. **Этап 4 — Onboarding wizard** (frontend + generate-draft endpoint +
   AI keyword generation endpoint).
4. **Этап 5 — Dashboard** rebuild: profile switcher, Match Score—aware
   stat cards.
5. **Этап 6 — Источники**: catalog UI, per-profile enable/disable, add-custom-source flow.
6. **Этап 7 — Ключевые слова**: per-profile keyword management UI + AI generation button.
7. **Этап 8 — Отфильтровано AI**: rejection-reason display + 👍/👎 feedback wired to the new feedback endpoint.
8. **Этап 9 — Мои поиски** page + create-new-search entry point (re-runs onboarding).
9. **Этап 10 — Аналитика**: per-profile funnel view.
10. **Этап 11 — Подписки**: `SubscriptionPlan`/`Subscription`/`Usage` tables + a read-only "your plan/usage" panel; no payment integration (none exists to integrate with).

Freelance-exchange source adapters, AI outreach generation, and
email/push notification channels are explicitly out of scope for full
implementation per the ТЗ itself ("архитектуру подготовь, полную
реализацию не обязательно") — this plan prepares the `SourceConnector`-
style interface and the `LeadFeedback`/outreach data shapes so they slot
in later without another schema migration, but does not build working
freelance-exchange scraping or an outreach-sending integration.

## 9. Risk notes

- The pipeline fan-out (Этап 3) is the one change that touches the live,
  currently-working single-profile flow. It will be built so that with
  exactly one active profile (today's real-world state) behavior is
  byte-for-byte identical to today — the fan-out loop with N=1 profile
  degenerates to exactly the current code path.
- Migration 0005 is purely additive (new tables + nullable columns) —
  no data migration risk comparable to 0004's Lead 1:1→N:1 change.
