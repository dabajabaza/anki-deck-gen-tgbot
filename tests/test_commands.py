"""Меню команд: «chat not found» для Админа, ещё не открывшего бота, не роняет старт."""

from typing import Any

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest
from aiogram.methods import SetMyCommands, TelegramMethod
from aiogram.types import BotCommandScopeChat

from anki_deck_gen.bot.commands import set_all_commands
from tests.helpers.bot_harness import BotHarness, RecordingSession
from tests.helpers.factories import ADMIN_ID, FAKE_BOT_TOKEN, SECOND_ADMIN_ID


class _NoChatForSecondAdmin(RecordingSession):
    """Как Telegram: у Админа, который не писал боту, чата нет."""

    async def make_request(
        self, bot: Bot, method: TelegramMethod[Any], timeout: int | None = None
    ) -> Any:
        if (
            isinstance(method, SetMyCommands)
            and isinstance(method.scope, BotCommandScopeChat)
            and method.scope.chat_id == SECOND_ADMIN_ID
        ):
            self.calls.append(method)
            raise TelegramBadRequest(method=method, message="Bad Request: chat not found")
        return await super().make_request(bot, method, timeout)


async def test_startup_menu_survives_an_admin_without_a_chat() -> None:
    session = _NoChatForSecondAdmin()
    bot = Bot(token=FAKE_BOT_TOKEN, session=session)
    await set_all_commands(bot, admin_ids=frozenset({ADMIN_ID, SECOND_ADMIN_ID}))
    scopes = [type(m.scope).__name__ for m in session.calls_of(SetMyCommands)]
    assert scopes.count("BotCommandScopeDefault") == 1
    assert scopes.count("BotCommandScopeChat") == 2, "both admins were attempted"


async def test_admin_start_registers_the_admin_menu(harness: BotHarness) -> None:
    await harness.send("/start", user_id=ADMIN_ID)
    chat_scopes = [
        m.scope
        for m in harness.session.calls_of(SetMyCommands)
        if isinstance(m.scope, BotCommandScopeChat)
    ]
    assert [s.chat_id for s in chat_scopes] == [ADMIN_ID]
    commands = harness.session.calls_of(SetMyCommands)[0].commands
    assert {c.command for c in commands} >= {"invite", "allow", "access", "help", "template"}


async def test_guest_start_does_not_touch_the_menu(harness: BotHarness) -> None:
    from anki_deck_gen.services import access
    from tests.helpers.factories import GUEST_ID

    async with harness.sessionmaker() as s:
        await access.allow_user(s, GUEST_ID, "guest")
        await s.commit()
    await harness.send("/start", user_id=GUEST_ID)
    assert harness.session.calls_of(SetMyCommands) == []
