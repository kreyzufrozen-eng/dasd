# Security Incident Response

Not legal advice — a technical starting point for the owner's own
incident-response process, not a substitute for one.

## 1. How an incident is detected

- `AuditLog` (`app/models/audit_log.py`) records login, logout,
  telegram_connect, account_deletion, register, data_export, and (once
  wired per-endpoint) profile/settings/subscription changes — an unusual
  pattern here (mass logins from one IP, repeated failed logins) is the
  first detection signal available today.
- Rate limiting (`app/core/rate_limit.py`) throttles login, register,
  Telegram start/link, account deletion, and data export per client IP —
  a spike in 429 responses in the backend logs is a secondary signal.
- No automated alerting exists yet (no SIEM, no anomaly-detection job)
  — detection today is manual log/AuditLog review. Building automated
  alerting is an open item.

## 2. Who gets notified

Not defined by this codebase — this is an organizational decision for
the owner (who is on call, what channel). Document this before public
launch.

## 3. What data is collected during investigation

- `AuditLog` rows for the affected time window (`action`, `user_id`,
  `ip_address`, `user_agent`, `target_type`/`target_id`, `extra`).
- Application logs (structured via `app/core/logging.py`).
- Database state as of the incident (Postgres, hosted per
  `THIRD_PARTY_DATA_MAP.md`).

`AuditLog` deliberately never stores passwords, tokens, secrets, or full
message content — see its docstring.

## 4. How access is restricted during an incident

- Admin panel access is already gated by `is_admin` +
  `get_current_admin_user` (`app/core/security.py`) — a compromised
  non-admin account cannot read other users' data (server-side ownership
  checks on every user-data endpoint) or admin endpoints.
- Immediate containment options available today: an admin can deactivate
  a user via `PATCH /api/admin/users/{id}` (`is_active: false`), which
  makes `get_current_user` reject that user's session on the next
  request.
- **No mechanism to revoke a single already-issued JWT exists** (the
  session cookie stays valid until it expires, `JWT_EXPIRE_MINUTES`,
  even after `is_active` flips to false the cookie itself isn't
  blocklisted — deactivation blocks future `get_current_user` lookups,
  but doesn't prove instant revocation without checking that flag on
  every single request path, which it currently does). Confirm this is
  sufficient for the owner's threat model before launch.

## 5. How evidence is preserved

Not automated. For a real incident: take a Postgres snapshot/backup
before any remediation writes, and export the relevant `AuditLog` rows.
No tooling for this exists in the codebase yet — a manual `pg_dump` of
the affected tables is the current option.

## 6. How analysis is performed

Manual: cross-reference `AuditLog` action sequences against expected
user behavior, check `ip_address`/`user_agent` consistency across a
session, review recent `AdminUserUpdate` calls.

## 7. How recovery is performed

- Rotate `JWT_SECRET`, `BOT_TOKEN`, `API_KEY`, `AI_API_KEY` as needed
  (all environment variables, never hardcoded — see `.env.example`).
- Force logout of all sessions by rotating `JWT_SECRET` (invalidates
  every existing token, including legitimate ones — a blunt but complete
  tool).
- Restore from the pre-incident Postgres snapshot if data integrity is
  in question.

## 8. What legal notifications may be required

Not something this codebase can determine automatically. Depending on
what data was affected and the applicable jurisdiction(s) — see
`THIRD_PARTY_DATA_MAP.md` for where data actually lives — a breach
affecting personal data may trigger notification obligations (e.g. to a
data protection authority and/or affected users). **This requires the
owner's own legal review at the time of an actual incident**; this
document does not and cannot make that determination in advance.
