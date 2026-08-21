from app.services.pii_sanitizer import sanitize_message_text


def test_redacts_email():
    text = "Пишите на ivan@example.com по проекту"
    result = sanitize_message_text(text)
    assert "ivan@example.com" not in result
    assert "[email скрыт]" in result


def test_redacts_russian_mobile_with_plus7():
    text = "Звоните +7 916 123 45 67 в любое время"
    result = sanitize_message_text(text)
    assert "916 123 45 67" not in result
    assert "[номер телефона скрыт]" in result


def test_redacts_russian_mobile_with_leading_8():
    text = "Тел: 8(916)123-45-67"
    result = sanitize_message_text(text)
    assert "916" not in result or "[номер телефона скрыт]" in result


def test_does_not_redact_budget_figures():
    text = "Бюджет 100 000 - 150 000 рублей, сроки 2 недели"
    result = sanitize_message_text(text)
    assert "100 000" in result
    assert "150 000" in result


def test_does_not_redact_plain_sentence():
    text = "Нужен сайт для стоматологии, есть техзадание"
    assert sanitize_message_text(text) == text


def test_empty_text_returns_empty():
    assert sanitize_message_text("") == ""
