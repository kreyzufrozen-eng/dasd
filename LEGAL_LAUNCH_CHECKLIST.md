# Legal Launch Checklist

Not legal advice. Technical readiness checklist for the owner to work
through with actual legal counsel before public launch — items marked
`[x]` mean the *technical scaffolding* exists, not that legal review has
happened.

- [ ] Определён оператор персональных данных.
      _(Business/legal decision — not something code can determine.)_
- [x] Подготовлена архитектура для Privacy Policy — `LegalDocument` model +
      `/api/legal/privacy_policy` + `/privacy` page
      (`app/models/legal_document.py`, `frontend/app/privacy/page.tsx`).
      **Real reviewed text still needs to be written and published** via
      `POST /api/admin/legal` + `.../publish` — the page currently shows
      "not published yet" until an admin does this.
- [x] Подготовлена архитектура для Terms of Service — same mechanism,
      `frontend/app/terms/page.tsx`. **Real text still needed.**
- [x] Настроена страница Cookies — `frontend/app/cookies/page.tsx`,
      includes a live necessary/analytics/marketing preference control
      (`lib/cookie-consent.ts`) plus the same `LegalDocument`-backed text
      slot as privacy/terms. **Real text still needed if desired beyond
      the built-in "we only set one necessary cookie today" explanation.**
- [x] Настроено логирование принятия документов — `UserLegalAcceptance`
      (`app/models/user_legal_acceptance.py`), captured at both email
      registration and Telegram signup
      (`app/services/legal_acceptance_service.py`). Explicit checkbox,
      never pre-checked, on `/login` and `/register`.
- [ ] Проверена необходимость уведомления Роскомнадзора.
      _(Legal/regulatory decision — see THIRD_PARTY_DATA_MAP.md for the
      RU-localization question this depends on.)_
- [ ] При необходимости уведомление подано до запуска.
      _(Depends on the above.)_
- [ ] Проверена локализация персональных данных.
      **Known gap, explicitly deferred by the owner during this
      implementation pass**: production database is hosted in Finland
      (HOSTKEY VPS), not the Russian Federation. See
      `THIRD_PARTY_DATA_MAP.md` for the decision record.
- [x] Составлена карта потоков данных — `DATA_FLOW_MAP.md`.
- [x] Проверены внешние AI providers — classified in
      `THIRD_PARTY_DATA_MAP.md` as `LEGAL_REVIEW_REQUIRED`; actual
      jurisdiction depends on the deployed `AI_BASE_URL`.
- [x] Проверены Telegram integrations — classified in
      `THIRD_PARTY_DATA_MAP.md`; login flow only requests telegram_id
      (used as the identifier) + username/first_name (display only, never
      used as an identifier) — see `app/models/telegram_login_token.py`
      docstring for the minimization rationale.
- [ ] Проверены условия сторонних источников (freelance exchanges, etc.).
      _No freelance-exchange scraping was built in this codebase — see
      FINAL_IMPLEMENTATION_REPORT.md §8. Nothing to review yet because
      nothing exists yet; re-check if that work starts._
- [x] Настроено удаление аккаунта — `POST /api/auth/delete-account`
      (`app/api/auth.py`), Settings → Danger Zone
      (`frontend/app/settings/page.tsx`), `/delete-account` info page.
- [x] Настроен экспорт данных — `GET /api/auth/export-data`
      (`app/services/data_export_service.py`), Settings → "Скачать мои
      данные". **Simplification vs. the spec**: this is a same-request
      authenticated JSON download, not a separately-issued one-time
      expiring signed link — see `SECURITY_REVIEW.md`.
- [x] Настроена политика хранения — `DATA_RETENTION_POLICY.md`.
      **Enforcement gap**: `RawItem.retention_until` is tracked but no
      purge/anonymization job runs against it yet.
- [ ] Настроены резервные копии.
      _Manual `pg_dump` process used ad hoc during this implementation
      session (see FINAL_IMPLEMENTATION_REPORT.md) — no automated,
      scheduled backup job exists. Open item._
- [x] Настроен incident response — `SECURITY_INCIDENT_RESPONSE.md`.
- [x] Настроены роли и доступы — `is_admin` flag, `get_current_admin_user`,
      server-side ownership checks on every user-data endpoint (unchanged
      from Stage 1, re-verified during this pass).
- [x] Проведён security review перед production — `SECURITY_REVIEW.md`.

## Highest-priority open items before real public launch

1. **TLS/domain.** Everything above assumes HTTPS eventually exists;
   today the site is bare-IP HTTP (`PROJECT_AUDIT.md`). This is the
   single biggest blocker — passwords, session cookies, and the
   Telegram-login token all cross the wire unencrypted right now.
2. **RU data localization decision**, if the product targets RF citizens.
3. **Real legal text** for privacy policy / terms — the pipes exist, the
   words don't yet.
4. **Automated retention-purge job** and **automated backups** — both
   currently manual/nonexistent.
5. **UserLegalAcceptance cascade-on-delete** — currently deletes consent
   records along with the account; may need to anonymize-and-keep instead
   for legal defensibility (see `DATA_RETENTION_POLICY.md`).
