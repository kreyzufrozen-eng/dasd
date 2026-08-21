"""Stage 3: KeywordFilter behavior + seed data sanity checks."""
import pytest

from app.models.enums import KeywordCategory
from app.models.keyword import Keyword
from app.services.keyword_filter import KeywordFilter
from app.services.keyword_seed_data import SEED_KEYWORDS


def make_keyword(id_: int, keyword: str, category: str, weight: float = 1.0, is_active: bool = True) -> Keyword:
    kw = Keyword(keyword=keyword, category=category, weight=weight, is_active=is_active)
    kw.id = id_
    return kw


@pytest.fixture
def sample_keywords() -> list[Keyword]:
    return [
        make_keyword(1, "нужен сайт", KeywordCategory.DIRECT_INTENT.value, weight=2.0),
        make_keyword(2, "лендинг", KeywordCategory.PROJECT_TYPE.value, weight=1.5),
        make_keyword(3, "React", KeywordCategory.TECHNOLOGY.value, weight=1.0),
        make_keyword(4, "inactive keyword", KeywordCategory.SERVICE.value, weight=1.0, is_active=False),
    ]


def test_matches_direct_intent_phrase(sample_keywords):
    kf = KeywordFilter(sample_keywords)
    result = kf.evaluate("Всем привет, нужен сайт для стоматологии, бюджет обсуждаем")
    assert result.matched is True
    assert any(m.keyword == "нужен сайт" for m in result.matches)
    assert KeywordCategory.DIRECT_INTENT.value in result.matched_categories


def test_no_match_returns_unmatched(sample_keywords):
    kf = KeywordFilter(sample_keywords)
    result = kf.evaluate("Продам б/у велосипед, торг уместен")
    assert result.matched is False
    assert result.matches == []
    assert result.total_weight == 0.0


def test_empty_text_does_not_match(sample_keywords):
    kf = KeywordFilter(sample_keywords)
    result = kf.evaluate("")
    assert result.matched is False


def test_inactive_keywords_are_ignored(sample_keywords):
    kf = KeywordFilter(sample_keywords)
    result = kf.evaluate("this text contains inactive keyword literally")
    assert result.matched is False


def test_word_boundary_avoids_false_positive_substring():
    # "React" should not match inside an unrelated longer word.
    kw = make_keyword(1, "React", KeywordCategory.TECHNOLOGY.value)
    kf = KeywordFilter([kw])
    result = kf.evaluate("У меня очень reactive характер, ищу психолога")
    assert result.matched is False


def test_word_boundary_matches_standalone_technology_term():
    kw = make_keyword(1, "React", KeywordCategory.TECHNOLOGY.value)
    kf = KeywordFilter([kw])
    result = kf.evaluate("Ищем разработчика, стек: React, Node.js")
    assert result.matched is True


def test_multiple_matches_sum_weight(sample_keywords):
    kf = KeywordFilter(sample_keywords)
    result = kf.evaluate("нужен сайт, желательно лендинг на React")
    assert result.matched is True
    assert len(result.matches) == 3
    assert result.total_weight == pytest.approx(2.0 + 1.5 + 1.0)
    assert result.matched_categories == {
        KeywordCategory.DIRECT_INTENT.value,
        KeywordCategory.PROJECT_TYPE.value,
        KeywordCategory.TECHNOLOGY.value,
    }


def test_should_pass_to_ai_is_permissive_gate(sample_keywords):
    kf = KeywordFilter(sample_keywords)
    assert kf.should_pass_to_ai("нужен сайт") is True
    assert kf.should_pass_to_ai("случайный текст ни о чём") is False


def test_case_insensitivity():
    kw = make_keyword(1, "WordPress", KeywordCategory.TECHNOLOGY.value)
    kf = KeywordFilter([kw])
    assert kf.evaluate("сайт на wordpress").matched is True
    assert kf.evaluate("сайт на WORDPRESS").matched is True


def test_seed_data_categories_are_valid_enum_values():
    valid_categories = {c.value for c in KeywordCategory}
    for keyword, category, weight in SEED_KEYWORDS:
        assert category in KeywordCategory
        assert category.value in valid_categories
        assert isinstance(keyword, str) and keyword.strip() != ""
        assert weight > 0


def test_seed_data_has_no_duplicate_keyword_category_pairs():
    pairs = [(keyword.lower(), category) for keyword, category, _ in SEED_KEYWORDS]
    assert len(pairs) == len(set(pairs))


def test_seed_data_covers_all_categories():
    categories_present = {category for _, category, _ in SEED_KEYWORDS}
    assert categories_present == set(KeywordCategory)


def test_multiword_keyword_matches_different_grammatical_form():
    # Real bug: a "дизайн карточек товаров" (genitive plural) keyword
    # never matched real messages phrased "Дизайн карточки товара"
    # (singular) because the old matcher required the exact literal
    # phrase. Words may now appear in any inflected form and any order.
    kw = make_keyword(1, "дизайн карточек товаров", KeywordCategory.SERVICE.value)
    kf = KeywordFilter([kw])
    assert kf.evaluate("Нужен дизайнер для создания слайдов карточки товара.").matched is True
    assert kf.evaluate("Дизайн серии карточек товара.").matched is True


def test_stemmed_word_still_respects_boundary():
    # "React" (<=5 chars, Latin) must stay an exact match even after
    # adding stemming for longer Cyrillic words.
    kw = make_keyword(1, "React", KeywordCategory.TECHNOLOGY.value)
    kf = KeywordFilter([kw])
    assert kf.evaluate("У меня очень reactive характер").matched is False


def test_short_cyrillic_word_does_not_over_stem():
    kw = make_keyword(1, "сайт", KeywordCategory.PROJECT_TYPE.value)
    kf = KeywordFilter([kw])
    assert kf.evaluate("нет сайта, работаем через инстаграм").matched is True
    assert kf.evaluate("ищу психолога").matched is False


def test_exclusion_only_match_is_suppressed_from_ai():
    kw = make_keyword(1, "вакансия", KeywordCategory.EXCLUSION.value)
    kf = KeywordFilter([kw])
    assert kf.evaluate("Вакансия: SMM-менеджер, удалённо").matched is True
    assert kf.should_pass_to_ai("Вакансия: SMM-менеджер, удалённо") is False


def test_exclusion_plus_other_category_still_passes():
    kws = [
        make_keyword(1, "вакансия", KeywordCategory.EXCLUSION.value),
        make_keyword(2, "нужен дизайнер", KeywordCategory.DIRECT_INTENT.value),
    ]
    kf = KeywordFilter(kws)
    assert kf.should_pass_to_ai("Вакансия дизайнера, но и нужен дизайнер на фрилансе") is True
