# Data Retention Policy

Not legal advice. States what this codebase actually does today, plus
where a number was chosen by engineering default rather than a
legally-mandated period — those are flagged explicitly for the owner to
confirm or change.

## Raw Messages

- **Retention**: `RAW_ITEM_RETENTION_DAYS` (default: 90 days), set per row
  at collection time as `RawItem.retention_until`
  (`app/services/telegram_collector.py`).
- **Rationale for the default**: long enough to cover a normal sales-cycle
  analytics window, short enough that third-party message text doesn't
  accumulate indefinitely. **This is an engineering default, not a
  reviewed legal figure — the owner should confirm or change
  `RAW_ITEM_RETENTION_DAYS` in `.env` before public launch.**
- **Enforcement**: the column is tracked and populated on every new
  RawItem going forward. **No automated purge/anonymization job exists
  yet** — `retention_until` being in the past does not currently delete
  or anonymize anything by itself. Building that job (a scheduled task
  that purges/anonymizes rows past `retention_until`) is listed as an
  open item in `LEGAL_LAUNCH_CHECKLIST.md`.
- Rows collected before this column existed (migration `0009_add_legal_audit`)
  have `retention_until = NULL`, meaning "no retention policy has run
  against this row's era" — not "keep forever" as a deliberate choice.

## AI Analysis (Lead rows)

- **Retention**: tied to the owning SearchProfile/user. Deleting a
  SearchProfile or the account itself cascades to delete its Leads
  (`app/models/search_profile.py` `cascade="all, delete-orphan"`,
  confirmed working since Stage 1's per-profile delete endpoint).
- No independent shorter retention period for Lead rows — they live as
  long as the profile that owns them.

## Security Logs (AuditLog)

- **Current behavior**: `AuditLog` rows (`app/models/audit_log.py`) are
  never automatically purged. `user_id` is set to `NULL` on account
  deletion (`ondelete="SET NULL"`), anonymizing the row without deleting
  the security record of the action.
- **Open item**: no fixed retention window (e.g. "12 months") is
  enforced. The owner should decide a concrete period appropriate for
  incident investigation needs and implement a purge job — flagged in
  `LEGAL_LAUNCH_CHECKLIST.md`.

## User Data

- **Retention**: until the user deletes their account
  (`POST /api/auth/delete-account`) or requests deletion via
  `/support`/`/delete-account`. No automatic expiry of active accounts.
- Deletion is immediate and cascading (see `DATA_FLOW_MAP.md` §3), not a
  soft-delete/grace-period flow — there is currently no "restore my
  account within N days" option.

## Legal/consent records (UserLegalAcceptance)

- Never auto-deleted, including after account deletion — the FK is
  `ondelete="CASCADE"` from `users`, so acceptance rows **are** deleted
  with the account today. **This is worth the owner's explicit attention**:
  if consent records need to survive account deletion for legal
  defensibility, this cascade should change to anonymize-and-keep instead
  of delete. Flagged in `LEGAL_LAUNCH_CHECKLIST.md`.

## What is explicitly NOT done

"Хранить навсегда" (retain forever) is not used as a policy anywhere in
this codebase by design — every category above either has an active
expiry mechanism or is flagged as an open item needing one.
