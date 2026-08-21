# Security Review — Этап 12 (Telegram login + legal/privacy layer)

Not legal advice. Covers what was checked during this implementation
pass, what was found, what was fixed, and what genuinely needs the
owner's (and where noted, legal counsel's) attention before public launch.

## 1. Authentication

- Two independent paths now exist: email+password (bcrypt via
  `app/services/auth_service.py`, unchanged from Stage 1) and Telegram
  bot-initiated login (`app/services/telegram_login_service.py`, new).
  Both issue the same JWT-in-httpOnly-cookie session
  (`app/api/auth.py _set_session_cookie`).
- `User.password_hash`/`User.email` are now nullable (Telegram-only
  accounts have neither) — every code path that previously assumed both
  were always set was audited and guarded: `login`, `change_password`,
  `UserRead` serialization (`app/schemas/auth_schemas.py`
  `_derive_auth_flags`), the admin user list (`AdminUserRead`), and the
  frontend nav/admin display. Confirmed via the full test suite (232
  tests) plus new tests specifically for the null-password/null-email
  paths (`tests/test_api_telegram_auth.py`).
- **Finding, fixed**: `change_password`/`login` would have raised an
  unhandled `AttributeError` calling `.encode()` on a `None`
  `password_hash` for a Telegram-only account under specific conditions.
  Explicit `is not None` guards added.

## 2. Authorization

- Server-side ownership checks unchanged from Stage 1/Этап 2-11 — every
  user-data endpoint resolves the caller's own resources, never trusts a
  client-supplied user/profile id alone. Re-verified, not re-built, in
  this pass.
- Admin endpoints (`get_current_admin_user`) unchanged. New admin-only
  surface (`/api/admin/legal/*`) uses the same dependency, confirmed via
  `test_non_admin_cannot_manage_legal_documents`.

## 3. Multi-tenant isolation

- Unchanged from prior stages; not re-derived here. The new tables
  (`telegram_login_tokens`, `legal_documents`, `user_legal_acceptances`,
  `audit_logs`) each scope correctly: tokens by `user_id` (LINK) or
  telegram_id (LOGIN), acceptances by `user_id`, legal documents are
  global (not per-tenant, deliberately — one policy per type, not one
  per user), audit logs by `user_id` with `SET NULL` on deletion.

## 4. Telegram Login

- Uses the bot-deep-link pattern, not the official Telegram Login
  Widget — the Widget requires a registered HTTPS domain
  (`/setdomain` in @BotFather), which this deployment doesn't have yet
  (see `PROJECT_AUDIT.md`). This was an explicit, discussed decision
  with the owner, not a silent substitution.
- Requests only `telegram_id` + `username`/`first_name` from Telegram
  (via `message.from_user` in the bot's `/start` handler) — no phone
  number, no additional OAuth scopes requested or stored.
  `telegram_username` is stored for display only; `telegram_id` is the
  only field ever used to look up an account
  (`UserRepository.get_by_telegram_id`).

## 5. Telegram Linking

- LINK-purpose tokens are bound to the initiating session's `user_id` at
  `start()` time and re-checked at `complete()` time
  (`current_user_id != row.user_id` rejects). Verified by
  `test_link_token_cannot_be_completed_by_a_different_session`.
- A `telegram_id` cannot be attached to two accounts —
  `test_telegram_id_cannot_be_linked_to_two_accounts` confirms the
  `existing.id != user.id` check in `telegram_login_service.complete()`.

## 6. Token security

- `TelegramLoginToken.token_hash` stores a SHA-256 hash, never the
  plaintext token (`_hash_token` in `telegram_login_service.py`) — a
  database read alone cannot be used to complete someone else's pending
  login.
- Tokens are single-use: `status` transitions PENDING → CONFIRMED →
  CONSUMED, and `complete()` only accepts CONFIRMED. Re-using a consumed
  token 422s (`test_token_is_single_use`).
- TTL: `TELEGRAM_LOGIN_TOKEN_TTL_SECONDS` (default 600s / 10 minutes),
  enforced on both `confirm()` and `complete()`.
- **Known gap**: the plaintext token is returned to the browser over
  plain HTTP (no TLS yet — see §9) and is visible in the deep-link URL
  shown to the user. Within its 10-minute window, anyone who intercepts
  that specific request/URL could complete that specific pending login.
  This is the same class of risk email/password login already has today
  (session cookie over HTTP) — not a new regression, but not fixed by
  this pass either. TLS is the actual fix; see §9.

## 7. API authorization

- New endpoints (`/api/auth/telegram/*`, `/api/auth/delete-account`,
  `/api/auth/export-data`, `/api/legal/*`, `/api/admin/legal/*`) all
  follow the existing `get_current_user`/`get_current_admin_user`
  pattern. `get_current_user_optional` (new) is used only where an
  endpoint genuinely needs to work both logged-in and logged-out
  (`/api/auth/logout`, `/api/auth/telegram/complete`) — never as a
  shortcut around a real auth requirement.

## 8. Rate limiting

- Extended to every new sensitive endpoint: telegram start/link/status/
  complete, delete-account, export-data — all via the existing
  `app/core/rate_limit.py` dependency, same per-IP in-process limiter
  used for login/register since Stage 1.

## 9. Secrets & transport

- No new secrets are hardcoded; `TELEGRAM_BOT_USERNAME`,
  `PUBLIC_SITE_URL`, `RAW_ITEM_RETENTION_DAYS`,
  `TELEGRAM_LOGIN_TOKEN_TTL_SECONDS` all follow the existing
  `.env`/`Settings` pattern (`app/core/config.py`), documented in
  `.env.example` with no real values committed.
- **Standing gap, not introduced by this pass**: the whole deployment is
  HTTP-only (no domain, no TLS — `PROJECT_AUDIT.md`). Every session
  cookie, password, and now every Telegram login token crosses the wire
  unencrypted. This was flagged as a "hard prerequisite" back in Stage 1
  planning and still hasn't been addressed. **This is the single highest
  -priority item before real public launch** — see
  `LEGAL_LAUNCH_CHECKLIST.md`.

## 10. Logs

- `AuditLog` (`app/models/audit_log.py`) never stores passwords, tokens,
  or secrets — confirmed by reading every `log_action()` call site added
  in this pass (register, login, logout, telegram_connect,
  account_deletion, data_export). `extra` (JSON) is unused so far; if a
  future call site adds structured context there, it should get the same
  scrutiny.

## 11. Data deletion

- `DELETE` cascades verified via FK `ondelete` behavior + the existing
  `SearchProfile` cascade (Stage 1) — confirmed end-to-end by
  `test_delete_account_succeeds_and_clears_session` (login after
  deletion correctly fails).
- **Finding, not fixed**: `UserLegalAcceptance` cascades on account
  deletion (`ondelete="CASCADE"`) — consent records are deleted along
  with the account rather than anonymized-and-kept. Flagged in
  `DATA_RETENTION_POLICY.md` and `LEGAL_LAUNCH_CHECKLIST.md` as an item
  the owner may want to change before this matters for real (legal
  defensibility of "this user did consent, here's proof, even though
  they later deleted their account").

## 12. Data export

- Functional and tested (`test_export_returns_account_and_profiles`),
  but simpler than the spec's "one-time signed link with short expiry":
  it's a same-request authenticated JSON download instead. Building a
  separate temp-storage + signed-URL system was judged out of proportion
  to the rest of this pass — flagged as a known simplification rather
  than silently built to spec and claimed complete.

## 13. Retention

- See `DATA_RETENTION_POLICY.md` in full. Summary: fields exist
  (`RawItem.retention_until`), no purge job runs yet.

## 14. Third-party data flows

- See `THIRD_PARTY_DATA_MAP.md`. Two explicit `LEGAL_REVIEW_REQUIRED`
  flags: the AI provider's jurisdiction (depends on deployed
  `AI_BASE_URL`) and the Finland-hosted database vs. RF localization
  requirements (owner's explicit decision to defer, recorded there).

## 15. No personal data/secrets in the frontend bundle

- Checked `NEXT_PUBLIC_*` build args added in this pass
  (`NEXT_PUBLIC_SUPPORT_EMAIL`) — a contact address, not a secret, safe
  to ship client-side, same category as the existing
  `NEXT_PUBLIC_API_KEY` (already documented in `docker-compose.yml` as
  visible-by-design, not a true secret, for this single-tenant-hosting
  deployment shape).
- No Telegram bot token, AI API key, database credentials, or JWT secret
  appear in any frontend file, `NEXT_PUBLIC_*` var, or client bundle —
  confirmed by grep across `frontend/` for each secret's env var name.

## Summary

Built and verified in this pass: dual-path auth with correct null-safety,
bound and single-use Telegram tokens, consent logging wired into both
signup paths, account deletion/export, an audit log, rate limiting on
every new sensitive route, and a best-effort PII sanitizer ahead of the
AI provider. The one standing, pre-existing, not-fixed-here blocker that
matters most is TLS — everything above is built assuming it will exist
soon, and several of the "known gap" notes above stop being real gaps
the moment it does.
