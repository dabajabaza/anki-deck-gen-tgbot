"""Админские команды: выдача приглашений и ручной допуск.

Отвечаем только Админам (ADMIN_IDS). Гость на эти команды получает молчание, а
не «недостаточно прав»: существование админки незачем светить.

Роутер подключать раньше остальных — там есть catch-all, который иначе
перехватит команду.
"""

import logging
from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware, Router
from aiogram.filters import Command, CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, TelegramObject
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from anki_deck_gen.bot import texts
from anki_deck_gen.config import BotSettings
from anki_deck_gen.db.limits import fits_in_db
from anki_deck_gen.services import access

logger = logging.getLogger(__name__)

router = Router(name="admin")


class _DialogInterrupt(BaseMiddleware):
    """Любая админская команда прерывает начатый ввод — как /start."""

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        state: FSMContext | None = data.get("state")
        if state is not None:
            await state.clear()
        return await handler(event, data)


router.message.middleware(_DialogInterrupt())


def _is_admin(message: Message, settings: BotSettings) -> bool:
    return message.from_user is not None and message.from_user.id in settings.admin_ids


@router.message(Command("invite"))
async def invite(
    message: Message,
    settings: BotSettings,
    sessionmaker: async_sessionmaker[AsyncSession],
) -> None:
    if not _is_admin(message, settings):
        return
    assert message.from_user is not None and message.bot is not None
    async with sessionmaker() as session:
        created = await access.create_invite(session, message.from_user.id)
        code = created.code
        await session.commit()
    # me(), не get_me(): результат закэширован на старте, сети здесь нет.
    me = await message.bot.me()
    link = f"https://t.me/{me.username}?start={code}"
    await message.answer(
        texts.INVITE_LINK.format(hours=access.INVITE_TTL_SECONDS // 3600, link=link)
    )
    # Код — bearer-секрет на 48 часов; в лог идёт только факт и автор.
    logger.info(
        "invite issued: admin=%s ttl=%sh", message.from_user.id, access.INVITE_TTL_SECONDS // 3600
    )


@router.message(Command("allow"))
async def allow(
    message: Message,
    command: CommandObject,
    settings: BotSettings,
    sessionmaker: async_sessionmaker[AsyncSession],
) -> None:
    if not _is_admin(message, settings):
        return
    assert message.from_user is not None
    args = (command.args or "").strip()
    # isdecimal, а не isdigit: последний истинен для «³», на котором int() падает.
    if not args.isdecimal() or not fits_in_db(int(args)):
        await message.answer(texts.ALLOW_USAGE)
        return
    user_id = int(args)
    async with sessionmaker() as session:
        await access.allow_user(session, user_id, invited_by=message.from_user.id)
        await session.commit()
    await message.answer(texts.ALLOWED.format(user_id=user_id))
    logger.info("access granted manually: admin=%s user_id=%s", message.from_user.id, user_id)


@router.message(Command("access"))
async def who_has_access(
    message: Message,
    settings: BotSettings,
    sessionmaker: async_sessionmaker[AsyncSession],
) -> None:
    if not _is_admin(message, settings):
        return
    async with sessionmaker() as session:
        guests = await access.list_allowed(session)
        invites = await access.live_invites(session)
    lines = [
        texts.ACCESS_ADMINS.format(
            count=len(settings.admin_ids), ids=", ".join(str(i) for i in sorted(settings.admin_ids))
        )
    ]
    if guests:
        rows = "\n".join(
            texts.ACCESS_GUEST_ROW.format(
                user_id=g.user_id, username=f" @{g.username}" if g.username else ""
            )
            for g in guests
        )
        lines.append(texts.ACCESS_GUESTS.format(count=len(guests), rows=rows))
    else:
        lines.append(texts.ACCESS_NO_GUESTS)
    lines.append(texts.ACCESS_INVITES.format(count=len(invites)))
    await message.answer("\n".join(lines))
