# LeadHunter — Multi-Search-Profile SaaS: Final Implementation Report

Этапы 2–11 of the multi-search-profile ТЗ, executed in full-autopilot mode
per the user's selection at the planning stage (see `IMPLEMENTATION_PLAN.md`
§8 for the original staged plan this report closes out). Built, tested,
and deployed to production on 2026-08-18.

## 1. What changed, end to end

The core shift: a `User` now legitimately owns **multiple independent
`SearchProfile`s** ("Веб-разработка", "Дизайн карточек", ...), each with
its own AI persona, keyword list, source list, notification threshold,
and analytics — instead of Stage 1's one-profile-per-user simplification.
Onboarding turns a plain-text description into a structured profile via
AI; the pipeline fans out across every active profile system-wide,
analyzing each RawItem once per profile with that profile's own AI
system prompt.

## 2. New backend entities

| Table | Purpose |
|---|---|
| `search_profile_sources` | Per-profile link to the shared `Source` catalog (enabled flag) — a Source stays one shared row, profiles just link to it |
| `search_profile_keywords` | Per-profile keyword list (`keyword_id` nullable — set when linked to the global catalog, null for AI-generated/private keywords) |
| `subscription_plans` | Plan catalog (limits + price) — one "Free" row seeded |
| `subscriptions` | 1:1 user→plan link, auto-created on registration |
| `usage_counters` | Per-user-per-month AI-analysis counter (tracked, not yet enforced) |

Extended existing tables (additive only): `sources.category` /
`added_by_user_id`, `keywords.is_global`, `lead_feedback.action` /
`search_profile_id`, `leads.reasoning`.

Three Alembic migrations, all purely additive, all verified against a
restored copy of production data before being applied for real:
- `0005_add_search_profile_links`
- `0006_add_lead_reasoning`
- `0007_add_subscriptions`

## 3. New/changed API surface

```
POST   /api/search-profiles/generate-draft        AI text→profile draft (onboarding step 1)
GET    /api/search-profiles/{id}/analytics         Per-profile funnel/breakdown
GET    /api/search-profiles/{id}/keywords          } per-profile keyword CRUD
POST/PATCH/DELETE  .../keywords/{kwid}              }
GET/POST/PATCH/DELETE /api/search-profiles/{id}/sources/*   per-profile source management
GET    /api/sources/catalog                        Browsable shared source catalog
POST   /api/leads/{id}/feedback                     👍/👎 feedback (relevant/irrelevant/saved/contacted)
GET    /api/subscription                            Read-only plan/usage panel
GET    /api/leads, /api/analytics/overview          now take explicit search_profile_id
```

`/api/sources`, `/api/keywords` (flat, admin-only, global-catalog
management) are unchanged.

## 4. New frontend pages

`/onboarding` (7-step wizard) · `/searches` ("Мои поиски") ·
`/searches/[id]` (tabbed settings) · `/searches/[id]/analytics` ·
`/settings` (plan/usage panel). `Nav` now exposes Дашборд / Мои поиски /
Лиды / Отфильтровано AI / Источники / Ключевые слова / Настройки, with
only Админка staying admin-gated. Dashboard, Leads, and Filtered are all
profile-scoped via a new `ActiveProfileProvider`.

## 5. Two real bugs found and fixed via live testing (not caught by unit tests)

1. **Onboarding→dashboard redirect loop**: `AuthGate` bounced a
   freshly-onboarded user back into `/onboarding` because the profile
   list context hadn't been refreshed after profile creation. Fixed with
   an explicit `refreshProfiles()` before navigating away.
2. **False redirect-to-onboarding for existing users**: a one-frame race
   where `ActiveProfileProvider`'s loading state resolved to `false`
   before auth had settled, causing `AuthGate` to misfire on hard page
   loads. Fixed by gating the profile fetch on `authLoading` first.

Both were only reproducible through actual browser navigation, not
component-level tests — confirms the value of the live-verification step
that ran after every stage.

## 6. Verification performed

- Full backend suite: **206/206 passing**, re-run after every stage and
  again immediately before the production deploy.
- Every stage frontend-built via `docker compose build frontend` (Next.js
  type-checking + build) before being considered done.
- Live browser verification after every stage against real Docker Compose
  dev services, including real (non-mock) AI provider calls — tested with
  three different professions (web dev, targeted advertising, interior
  design) to confirm the AI prompt is genuinely profile-personalized, not
  still hardcoded.
- **Production migration safety**: took a fresh `pg_dump` of production,
  restored it into an isolated local Postgres container, ran migrations
  0005→0007 against that copy, and diffed row counts before touching the
  real database.
- **Production deployment verified live**: registered a disposable test
  account on the real production URL, walked the entire onboarding wizard
  end to end (including two real AI calls — draft generation and keyword
  generation), reached the dashboard, checked `/settings` and
  `/searches/{id}/analytics`, then deleted the test account and its data.
  Confirmed the real pipeline worker picked up the pre-existing production
  profile ("Веб-разработка") on its normal cycle and wrote a new `Lead`
  row with a populated `reasoning` field — proof Этап 3's fan-out and
  Этап 8's reasoning column both work against the live pipeline, not just
  in tests.
- No new errors in backend/frontend logs since deploy (worker logs show
  only pre-existing, unrelated per-source Telegram fetch failures for a
  handful of stale/renamed channel usernames in the existing source
  catalog — present before this deploy, not a regression).

## 7. Production state after deploy

- Alembic at `0007_add_subscriptions`.
- 621 pre-existing leads, both existing users, and the original
  "Веб-разработка" profile all intact and unchanged.
- Both existing users backfilled with a `Subscription` to the seeded
  "Free" plan (3 search profiles / 10 sources per profile / 1000 AI
  analyses per month).
- All 5 containers (postgres, backend, worker, bot, frontend) healthy.

## 8. Explicitly out of scope (prepared, not fully built)

Per the ТЗ itself ("архитектуру подготовь, полную реализацию не
обязательно"):
- **AI outreach generation** — draft/copy response generation is not
  implemented; the `LeadFeedback` action vocabulary and per-lead context
  needed for it exist, but no send-to-platform automation was built.
- **Freelance-exchange source adapters** — the source catalog and
  `SourceConnector`-style interface support them; no scraper for a
  specific freelance exchange was written.
- **Per-user Telegram notification routing** — notifications still go to
  the single bot owner chat (`NOTIFICATION_CHAT_ID`); per-user delivery
  needs its own design.
- **Admin catalog-curation UI** — `sources.category` exists and the
  catalog groups by it, but most of the 435 existing sources have no
  category set yet (`NULL`) since no curation UI was built to set them.
- **Subscription billing** — `SubscriptionPlan`/`Subscription`/
  `UsageCounter` exist and are readable via `/api/subscription`, but there
  is no payment provider integration, no upgrade/downgrade flow, and
  nothing enforces the limits they describe yet.
- **"🧠 Что AI понял" insights block** — deliberately not built; it would
  need a new AI summarization call, and fabricating that text without one
  would violate the project's own "no fake data" rule.

## 9. What a future session picking this up should know

- `ensure_free_subscription` / `ensure_keywords_seeded` are the two
  "backfill on first touch" idempotent helpers — the pattern to follow if
  another per-profile or per-user resource needs the same
  works-for-old-and-new-data treatment.
- `KeywordFilter` works against both `Keyword` and `SearchProfileKeyword`
  via property aliases (`.keyword`/`.is_active`) on the latter — don't
  duplicate the matcher if a third keyword-like model shows up.
- The funnel intentionally starts at "Кандидаты" (Lead rows), not
  "Обработано сообщений" — messages rejected by the keyword pre-filter are
  never persisted, so there's no real count of them to show without
  adding a DB write per irrelevant message.
