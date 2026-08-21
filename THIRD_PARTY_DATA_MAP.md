# Third-Party Data Map

Not legal advice. Technical inventory of every external service LeadHunter's
backend talks to, for the owner's own legal review before public launch —
see `LEGAL_LAUNCH_CHECKLIST.md`.

| service_name | purpose | data_categories | personal_data_possible | country | data_transfer_type | legal_review_required |
|---|---|---|---|---|---|---|
| Telegram Bot API (`aiogram`, `BOT_TOKEN`) | Sends lead notifications to users' own linked chats; "Войти через Telegram" login/link handshake (`app/services/telegram_login_service.py`) | telegram_id, telegram_username, first_name, message content sent to the user | Yes — telegram_id/username are personal data | Telegram LLC — global infrastructure, no published fixed jurisdiction | Cross-border | Yes |
| Telegram (Telethon monitoring, `app/sources/telegram_client.py`) | Reads public channel/group messages to find leads | Message text, author_username/display name (public, source-side), publish timestamp | Yes, for the message author (a third party, not a LeadHunter user) | Telegram LLC | Cross-border | Yes |
| AI provider (`AI_PROVIDER=openai_compatible`, `AI_BASE_URL`) | Analyzes message text for lead relevance (`app/ai/openai_compatible_provider.py`) | Sanitized message text (see `app/services/pii_sanitizer.py`), profile context the user wrote about themselves | Possible — sanitization is best-effort, not a guarantee (phone/email/some addresses redacted; other PII forms may pass through) | Depends on configured `AI_BASE_URL` — provider-specific, not fixed by this codebase | Cross-border unless a Russian-hosted OpenAI-compatible endpoint is configured | **Yes — flagged explicitly per the owner's decision to defer this (see below)** |
| Hosting (HOSTKEY VPS) | Runs Postgres, backend, worker, bot, frontend | All application data — the entire database | Yes — this is where all personal data physically lives | **Finland** (see `PROJECT_AUDIT.md`) | N/A (this IS the primary storage location) | **Yes — see below** |

## Open items the owner explicitly deferred (not fixed by this pass)

- **Hosting is in Finland, not the Russian Federation.** If LeadHunter is
  offered to RF citizens and 152-ФЗ localization requirements apply, the
  primary personal-data database needs to move to RF-compliant
  infrastructure. This was raised during this implementation pass and the
  owner chose to document it rather than migrate now — see
  `LEGAL_LAUNCH_CHECKLIST.md`.
- **AI provider country/jurisdiction is whatever `AI_BASE_URL` points at
  in the deployed `.env`** — this file can't state a fixed answer; check
  the actual configured endpoint before relying on this map.

## Not currently used

No analytics, advertising, or marketing third-party scripts exist in this
codebase (see `app/cookies` page in the frontend and
`components/cookie-consent-banner.tsx`) — the analytics/marketing cookie
categories are prepared architecture, not live integrations.
