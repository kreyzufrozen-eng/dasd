"""KeywordFilter: a cheap PRE-FILTER over raw item text.

Important: this is only a pre-filter. It decides whether a message is
*worth sending to the AI analyzer* — it must never be treated as the final
is_lead decision (that's AIAnalyzer + LeadScoringService's job). A message
with zero keyword matches is skipped (saves AI calls); a match does not
guarantee it's actually a lead.
"""
import re
from dataclasses import dataclass, field
from typing import Sequence

from app.models.enums import KeywordCategory
from app.models.keyword import Keyword

_CYRILLIC_WORD_RE = re.compile(r"^[а-яёА-ЯЁ]+$")


def _stem(word: str) -> str:
    """Strip a short suffix off a Cyrillic word so common case/number
    endings match the same keyword instead of requiring the one exact
    grammatical form the keyword happened to be phrased in — e.g. a
    "service" keyword phrased as "дизайн карточек товаров" (genitive
    plural) previously never matched real text like "Дизайн карточки
    товара" (singular): different endings on every word meant the whole
    literal phrase never appeared verbatim. Left untouched for
    non-Cyrillic words and anything <=3 letters — tech terms like "React"
    must stay an exact match or they'd match inside "reactive" again (see
    test_word_boundary_avoids_false_positive_substring)."""
    n = len(word)
    if n <= 3 or not _CYRILLIC_WORD_RE.match(word):
        return word
    cut = 1 if n <= 5 else 2
    return word[: n - cut]


def _compile_word_pattern(word: str) -> re.Pattern:
    stem = _stem(word)
    if stem != word:
        return re.compile(rf"\b{re.escape(stem)}\w*", re.IGNORECASE | re.UNICODE)
    return re.compile(rf"\b{re.escape(stem)}\b", re.IGNORECASE | re.UNICODE)


@dataclass(frozen=True)
class KeywordMatch:
    keyword: str
    category: str
    weight: float


@dataclass(frozen=True)
class KeywordFilterResult:
    matched: bool
    matches: list[KeywordMatch] = field(default_factory=list)
    total_weight: float = 0.0
    matched_categories: frozenset = field(default_factory=frozenset)


class KeywordFilter:
    """Stateless matcher built from a snapshot of active Keyword rows.

    Rebuild (or re-instantiate) this whenever the Keyword table changes;
    it does not hit the DB itself so it stays easily unit-testable.

    A multi-word keyword ("дизайн карточек товаров") matches when every
    one of its words appears somewhere in the text (each independently
    stemmed, see _stem) rather than requiring the exact phrase verbatim
    and contiguous — real messages paraphrase and reorder ("Нужен
    дизайнер для карточки товара"), so a strict literal-phrase match was
    silently matching almost nothing for any keyword longer than one or
    two words.
    """

    def __init__(self, keywords: Sequence[Keyword]) -> None:
        self._entries: list[tuple[list[re.Pattern], str, str, float]] = [
            (
                [_compile_word_pattern(w) for w in kw.keyword.strip().split()],
                kw.keyword,
                kw.category,
                kw.weight,
            )
            for kw in keywords
            if kw.is_active
        ]

    def evaluate(self, text: str) -> KeywordFilterResult:
        if not text:
            return KeywordFilterResult(matched=False)

        matches: list[KeywordMatch] = []
        for word_patterns, keyword, category, weight in self._entries:
            if word_patterns and all(p.search(text) for p in word_patterns):
                matches.append(KeywordMatch(keyword=keyword, category=category, weight=weight))

        if not matches:
            return KeywordFilterResult(matched=False)

        total_weight = sum(m.weight for m in matches)
        categories = frozenset(m.category for m in matches)
        return KeywordFilterResult(
            matched=True,
            matches=matches,
            total_weight=total_weight,
            matched_categories=categories,
        )

    def should_pass_to_ai(self, text: str) -> bool:
        """Permissive gate: any non-exclusion keyword match is enough to
        forward to AI analysis. Precision beyond that is AI's job, not
        this filter's. A message matching ONLY exclusion-category
        keywords ("вакансия", "ищу работу", ...) is suppressed instead —
        see the EXCLUSION category comment in keyword_seed_data.py, this
        was the documented-but-never-wired-up behavior it describes.
        A message matching exclusion AND some other category still
        passes: those are still worth an AI call rather than a guess."""
        result = self.evaluate(text)
        if not result.matched:
            return False
        return bool(result.matched_categories - {KeywordCategory.EXCLUSION.value})
