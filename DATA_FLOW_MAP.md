# Data Flow Map

Not legal advice. Traces where personal data actually moves through
LeadHunter, for the owner's pre-launch legal review.

## 1. Account creation / login

```
Пользователь
  ↓ (taps bot deep link, or submits email+password)
Telegram Bot API  ──или──  Browser (HTTPS not yet available — see note)
  ↓
LeadHunter Backend (FastAPI, app/api/auth.py + app/api/telegram_auth.py)
  ↓
Production Database (Postgres, hosted in Finland — see THIRD_PARTY_DATA_MAP.md)
```

| Transition | Data | Personal data? | Location | Internal/external | Review needed |
|---|---|---|---|---|---|
| Telegram → Backend | telegram_id, telegram_username, first_name | Yes | In transit via Telegram's infrastructure | External | Yes (see THIRD_PARTY_DATA_MAP.md) |
| Browser → Backend | email, password (hashed server-side, `app/services/auth_service.py`), IP, user-agent (for `UserLegalAcceptance`/`AuditLog`) | Yes | Currently plain HTTP — no domain/TLS (see PROJECT_AUDIT.md) | Internal | **Yes — HTTP-not-HTTPS is a real gap, see SECURITY_REVIEW.md** |
| Backend → DB | Full account record | Yes | Finland | Internal | Yes (localization question, see THIRD_PARTY_DATA_MAP.md) |

## 2. Source monitoring → lead

```
Telegram Sources (public channels/groups)
  ↓
Parser (Telethon, app/sources/telegram_client.py)
  ↓ (author_username, message text, published_at — all source-public)
Message Processing (app/services/telegram_collector.py — dedup, persist RawItem)
  ↓
AI Sanitization Layer (app/services/pii_sanitizer.py — best-effort phone/email/address redaction)
  ↓
AI Provider (external — see THIRD_PARTY_DATA_MAP.md)
  ↓
Lead Analysis (app/services/lead_pipeline.py — scoring, classification)
  ↓
LeadHunter Database (Lead row, tied to the owning user's SearchProfile)
  ↓
User Dashboard (own leads only — server-side ownership check on every read)
  ↓
Telegram Notifications (routed to the profile owner's own linked chat if
                         set, else the shared NOTIFICATION_CHAT_ID —
                         see app/workers/pipeline_worker.py
                         _resolve_notification_chat_id)
```

| Transition | Data | Personal data? | Location | Internal/external | Review needed |
|---|---|---|---|---|---|
| Source → Parser | Message text, author_username, publish time | Third-party personal data (message author, not a LeadHunter user) | In transit via Telegram | External | Yes |
| Parser → DB (RawItem) | Same, unredacted, plus `retention_until` | Yes | Finland | Internal | See DATA_RETENTION_POLICY.md |
| Sanitizer → AI provider | Redacted text only | Reduced but not eliminated (best-effort) | Cross-border, provider-dependent | External | Yes |
| Pipeline → DB (Lead) | AI's analysis output, score, reasoning | Derived data about the message, not directly about a person | Finland | Internal | Covered by hosting review above |
| Notifier → Telegram | Formatted lead card | No new personal data beyond what's already in the Lead | Cross-border | External | Covered by Telegram Bot API row above |

## 3. Account deletion / export

```
User → Settings (Danger Zone / "Скачать мои данные")
  ↓
Backend (app/api/auth.py delete_account / export_data)
  ↓
Database: cascading delete (SearchProfile, keywords, sources, leads,
          feedback, subscription, telegram link) OR JSON export response
  ↓
AuditLog row retained with user_id set to NULL (app/models/audit_log.py,
ondelete="SET NULL") — anonymized record that a deletion occurred,
not a way to reconstruct who it was
```

## Note on transport security

Every "Backend" node above is currently reached over plain HTTP (no
domain/TLS — see `PROJECT_AUDIT.md`). This is a pre-existing condition
from Stage 1, not something newly introduced, but it means every arrow
into "LeadHunter Backend" above is unencrypted in transit today. Fixing
this needs a registered domain + Let's Encrypt/Caddy — see
`SECURITY_REVIEW.md` and `LEGAL_LAUNCH_CHECKLIST.md`.
