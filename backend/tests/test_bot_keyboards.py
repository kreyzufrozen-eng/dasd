"""Stage 8: inline keyboard construction."""
from app.bot.keyboards import LeadAction, build_lead_keyboard
from app.models.raw_item import RawItem


def test_keyboard_includes_source_link_when_url_present():
    raw_item = RawItem(id=1, source_id=1, external_id="1", text="t", content_hash="h", url="https://t.me/x/1")
    markup = build_lead_keyboard(lead_id=42, raw_item=raw_item)

    all_buttons = [btn for row in markup.inline_keyboard for btn in row]
    labels = [btn.text for btn in all_buttons]

    assert "🔗 Открыть источник" in labels
    assert "👍 Хороший" in labels
    assert "👎 Неинтересно" in labels
    assert "💰 Клиент" in labels
    assert "🗂 Архив" in labels
    assert len(all_buttons) == 5


def test_keyboard_omits_source_link_without_url():
    raw_item = RawItem(id=1, source_id=1, external_id="1", text="t", content_hash="h", url=None)
    markup = build_lead_keyboard(lead_id=42, raw_item=raw_item)

    all_buttons = [btn for row in markup.inline_keyboard for btn in row]
    assert len(all_buttons) == 4
    assert all("Открыть источник" not in btn.text for btn in all_buttons)


def test_lead_action_callback_data_roundtrip():
    action = LeadAction(action="good", lead_id=42)
    packed = action.pack()
    unpacked = LeadAction.unpack(packed)
    assert unpacked.action == "good"
    assert unpacked.lead_id == 42
