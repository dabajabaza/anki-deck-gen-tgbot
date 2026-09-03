"""Меню команд Telegram: всем — помощь и шаблон, Админам — ещё и раздача доступа.

Меню Админа вешается на скоуп конкретного чата (`BotCommandScopeChat`), и здесь есть
ловушка: пока Админ ни разу не написал боту, чата с ним не существует, и Telegram
отвечает «chat not found». Первый запуск на сервере на этом упал и ушёл в
crash-loop — второй Админ ещё не открывал бота. Поэтому регистрация меню Админа
никогда не роняет старт, а `/start` от Админа регистрирует меню повторно: к тому
моменту чат уже есть.
"""

import logging

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError
from aiogram.types import BotCommand, BotCommandScopeChat, BotCommandScopeDefault

from anki_deck_gen.bot import texts

logger = logging.getLogger(__name__)

COMMON = [
    BotCommand(command="help", description=texts.CMD_HELP),
    BotCommand(command="template", description=texts.CMD_TEMPLATE),
]
ADMIN_ONLY = [
    BotCommand(command="invite", description=texts.CMD_INVITE),
    BotCommand(command="allow", description=texts.CMD_ALLOW),
    BotCommand(command="access", description=texts.CMD_ACCESS),
]


async def set_default_commands(bot: Bot) -> None:
    """Меню по умолчанию. Ошибка здесь — настоящая (сеть, токен), и её не глотаем."""
    await bot.set_my_commands(COMMON, scope=BotCommandScopeDefault())


async def set_admin_commands(bot: Bot, chat_id: int) -> bool:
    """Меню Админа для одного чата. False — чата ещё нет или Telegram отказал.

    Меню — косметика: команды работают и без него. Ронять из-за него процесс,
    когда всё остальное готово, было бы худшим из исходов.
    """
    try:
        await bot.set_my_commands(COMMON + ADMIN_ONLY, scope=BotCommandScopeChat(chat_id=chat_id))
    except TelegramAPIError as exc:
        logger.info(
            "admin menu not set for %s (%s) — will retry when they send /start", chat_id, exc
        )
        return False
    return True


async def set_all_commands(bot: Bot, *, admin_ids: frozenset[int]) -> None:
    """Старт бота: общее меню обязательно, админские — по возможности."""
    await set_default_commands(bot)
    for admin_id in sorted(admin_ids):
        await set_admin_commands(bot, admin_id)
