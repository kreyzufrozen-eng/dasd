"""app/bot/public_handlers.py — the not-owner-gated router. Covers both
/start cases: bare (channel-subscription gate, then welcome + link to
the site, reachable for ANY sender, not just the bot owner — this is
the fix for the gap where a stranger's bare /start used to be silently
dropped) and with a "Войти через Telegram" deep-link payload (delegates
to telegram_login_service.confirm, exercised end-to-end already in
tests/test_api_telegram_auth.py; here we only check cmd_start dispatches
to it and answers appropriately).
"""
from types import SimpleNamespace
from typing import Optional
from unittest.mock import AsyncMock, patch

import pytest
from aiogram.exceptions import TelegramAPIError

from app.bot import public_handlers


def _fake_bot(subscribed: bool = True, raise_error: bool = False) -> SimpleNamespace:
    get_chat_member = AsyncMock()
    if raise_error:
        get_chat_member.side_effect = TelegramAPIError(method=None, message="bot is not a member")
    else:
        get_chat_member.return_value = SimpleNamespace(status="member" if subscribed else "left")
    return SimpleNamespace(get_chat_member=get_chat_member)


class FakeMessage:
    def __init__(
        self, user_id: int = 111, username: str = "someone", subscribed: bool = True
    ) -> None:
        self.answer = AsyncMock()
        self.from_user = SimpleNamespace(id=user_id, username=username, first_name="Some")
        self.bot = _fake_bot(subscribed=subscribed)


def _command(args: Optional[str]) -> SimpleNamespace:
    return SimpleNamespace(args=args)


@pytest.mark.asyncio
async def test_bare_start_sends_welcome_with_site_link():
    message = FakeMessage()
    await public_handlers.cmd_start(message, _command(None))

    message.answer.assert_awaited_once()
    text = message.answer.await_args.args[0]
    assert "ReadHunter" in text
    assert "http" in text  # PUBLIC_SITE_URL is inlined


@pytest.mark.asyncio
async def test_bare_start_works_for_any_sender_not_just_owner():
    # A random stranger (not the configured bot owner) still gets an
    # answer — this is the exact gap this handler fixes.
    message = FakeMessage(user_id=999999, username="a_random_stranger")
    await public_handlers.cmd_start(message, _command(None))
    message.answer.assert_awaited_once()


@pytest.mark.asyncio
async def test_bare_start_not_subscribed_prompts_to_join_channel_instead_of_welcome():
    message = FakeMessage(subscribed=False)
    await public_handlers.cmd_start(message, _command(None))

    message.answer.assert_awaited_once()
    text = message.answer.await_args.args[0]
    assert public_handlers.REQUIRED_CHANNEL in text
    assert "ReadHunter — ищу" not in text  # not the welcome text
    keyboard = message.answer.await_args.kwargs["reply_markup"]
    assert keyboard is not None


@pytest.mark.asyncio
async def test_bare_start_subscription_check_error_fails_open_to_welcome():
    # If the bot can't check membership (e.g. not yet an admin of the
    # channel), don't lock every user out of the bot over it.
    message = FakeMessage()
    message.bot = _fake_bot(raise_error=True)
    await public_handlers.cmd_start(message, _command(None))

    text = message.answer.await_args.args[0]
    assert "ReadHunter — ищу" in text


@pytest.mark.asyncio
async def test_check_subscription_callback_still_not_subscribed_shows_alert():
    callback = SimpleNamespace(
        from_user=SimpleNamespace(id=111),
        bot=_fake_bot(subscribed=False),
        message=SimpleNamespace(edit_text=AsyncMock()),
        answer=AsyncMock(),
    )
    await public_handlers.cb_check_subscription(callback)

    callback.answer.assert_awaited_once()
    assert callback.answer.await_args.kwargs.get("show_alert") is True
    callback.message.edit_text.assert_not_awaited()


@pytest.mark.asyncio
async def test_check_subscription_callback_now_subscribed_edits_to_welcome():
    callback = SimpleNamespace(
        from_user=SimpleNamespace(id=111),
        bot=_fake_bot(subscribed=True),
        message=SimpleNamespace(edit_text=AsyncMock()),
        answer=AsyncMock(),
    )
    await public_handlers.cb_check_subscription(callback)

    callback.message.edit_text.assert_awaited_once()
    text = callback.message.edit_text.await_args.args[0]
    assert "ReadHunter — ищу" in text
    callback.answer.assert_awaited_once()


@pytest.mark.asyncio
async def test_start_with_payload_confirms_and_replies_success():
    message = FakeMessage()
    with patch.object(public_handlers, "confirm", new=AsyncMock(return_value=True)) as mock_confirm:
        await public_handlers.cmd_start(message, _command("login-sometoken"))

    mock_confirm.assert_awaited_once()
    assert "подтверждён" in message.answer.await_args.args[0]


@pytest.mark.asyncio
async def test_start_with_payload_confirm_failure_replies_expired():
    message = FakeMessage()
    with patch.object(public_handlers, "confirm", new=AsyncMock(return_value=False)):
        await public_handlers.cmd_start(message, _command("login-badtoken"))

    assert "истёк" in message.answer.await_args.args[0] or "использована" in message.answer.await_args.args[0]
