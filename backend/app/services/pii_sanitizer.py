"""Data Sanitization Layer, run on RawItem.text before it ever reaches an
AI provider (see app/services/lead_pipeline.py process_raw_item).

RAW MESSAGE -> PERSONAL DATA DETECTION -> REDACTION -> AI REQUEST

Best-effort, regex-based: phone numbers and email addresses are matched
reliably; street addresses are far harder to detect generically and are
only caught for a few common Russian patterns ("ул. X, д. Y") — this is
explicitly a "по возможности" (best-effort) layer per the spec, not a
guarantee that no PII ever reaches the AI provider. The lead-qualifying
signal in these messages is almost never the phone number/email itself
(it's the ask — "нужен сайt", budget, timeline), so redacting them costs
the analysis nothing.
"""
import re

#  Deliberately anchored to a leading +, a parenthesized area code, or a
#  bare "8"/"7" country prefix — NOT a bare digit-group regex, which would
#  false-positive-redact budget figures like "100 200 300 руб." A message
#  that's just a run of digits with no phone-like prefix/parens is left
#  alone; the qualifying signal (budget, timeline) matters more here than
#  catching every possible phone format.
_PHONE_RE = re.compile(
    r"(?:\+7|\b[78])[\s.-]?\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{2}[\s.-]?\d{2}\b"
    r"|\(\d{3,4}\)[\s.-]?\d{2,3}[\s.-]?\d{2}[\s.-]?\d{2}\b"
)
_EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")
# "ул. Ленина 12", "ул Ленина, д 12", "проспект Мира д. 5" — common
# Russian street-address shorthand. Deliberately narrow: a broad address
# regex produces far more false positives (redacting normal sentences)
# than it's worth.
_ADDRESS_RE = re.compile(
    r"(?:ул\.?|улица|пр-?кт\.?|проспект|пер\.?|переулок)\s+[А-ЯЁа-яё\-\s]{2,30}"
    r"(?:,?\s*д\.?\s*\d+[а-яА-Я]?)?",
    re.IGNORECASE,
)

PHONE_PLACEHOLDER = "[номер телефона скрыт]"
EMAIL_PLACEHOLDER = "[email скрыт]"
ADDRESS_PLACEHOLDER = "[адрес скрыт]"


def sanitize_message_text(text: str) -> str:
    if not text:
        return text
    text = _EMAIL_RE.sub(EMAIL_PLACEHOLDER, text)
    text = _PHONE_RE.sub(PHONE_PLACEHOLDER, text)
    text = _ADDRESS_RE.sub(ADDRESS_PLACEHOLDER, text)
    return text
