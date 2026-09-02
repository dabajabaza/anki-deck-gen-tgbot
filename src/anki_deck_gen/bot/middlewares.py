"""С кем бот разговаривает вообще.

Две внешние мидлвари на ``update``, до любого фильтра: сообщение Постороннего
не должно даже сопоставляться с обработчиками, не то что получать ответ.

Список доступа — в SQLite (Админы — из окружения, Гости — по инвайту или
``/allow``), поэтому проверка ходит в базу на каждом апдейте. Она делается
READONLY-соединением: в WAL читатель не берёт блокировку записи, и поток чужих
апдейтов ничего не стоит тем, кто допущен. Единственная запись на этом пути —
погашение инвайта по ``/start <код>``, редкое событие в своей короткой сессии.
"""

import logging
from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.enums import ChatType
from aiogram.types import Message, TelegramObject, Update, User
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from anki_deck_gen.services import access

logger = logging.getLogger(__name__)

Handler = Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]]

# Ключ в data, по которому /start понимает, что человек только что вошёл по инвайту.
INVITE_REDEEMED = "invite_redeemed"

# Больше стольких разных посторонних лог отказов своё дело сделал и только ест
# память; бот, чьё имя перебирают, даёт ровно такую картину.
_MAX_TRACKED_STRANGERS = 256


class PrivateChatOnlyMiddleware(BaseMiddleware):
    """Игнорирует групповой трафик: бот личный, каждый ответ — в ЛС."""

    async def __call__(self, handler: Handler, event: TelegramObject, data: dict[str, Any]) -> Any:
        chat = data.get("event_chat")
        if chat is not None and chat.type != ChatType.PRIVATE:
            return None
        return await handler(event, data)


def invite_code_from_start(event: TelegramObject) -> str | None:
    """Код из deep-link ``/start <код>``, если он там есть.

    Принимает Update: мидлварь висит на ``dp.update``. Версия, умевшая только
    Message, в lesson-tracker всегда возвращала None — единственный
    самостоятельный вход для приглашённого был мёртв, а тесты этого не видели.
    """
    if isinstance(event, Update):
        message = event.message
    elif isinstance(event, Message):
        message = event
    else:
        return None
    if message is None or not message.text or not message.text.startswith("/start"):
        return None
    parts = message.text.split(maxsplit=1)
    return parts[1].strip() if len(parts) > 1 else None


class AuthMiddleware(BaseMiddleware):
    """Молча отбрасывает апдейты всех, кто не Админ и не Гость.

    Молчание, а не отказ: имена ботов перебирают, и ответ любого вида
    подтверждает, что бот существует и жив.
    """

    def __init__(
        self,
        *,
        admin_ids: frozenset[int],
        engine: AsyncEngine,
        sessionmaker: async_sessionmaker[AsyncSession],
    ) -> None:
        self._admin_ids = admin_ids
        self._engine = engine
        self._sessionmaker = sessionmaker
        self._denied_seen: set[int] = set()

    async def __call__(self, handler: Handler, event: TelegramObject, data: dict[str, Any]) -> Any:
        user: User | None = data.get("event_from_user")
        if user is None:
            logger.debug("update without a user rejected")
            return None
        if await access.is_allowed_readonly(self._engine, self._admin_ids, user.id):
            return await handler(event, data)

        code = invite_code_from_start(event)
        if code is not None and await self._redeem(code, user):
            data[INVITE_REDEEMED] = True
            return await handler(event, data)

        self._log_denial(user, invite_attempted=code is not None)
        return None

    async def _redeem(self, code: str, user: User) -> bool:
        async with self._sessionmaker() as session:
            ok = await access.redeem_invite(session, code, user.id, user.username)
            if ok:
                await session.commit()
                logger.info("invite redeemed: user_id=%s username=%s", user.id, user.username)
            else:
                await session.rollback()
        return ok

    def _log_denial(self, user: User, *, invite_attempted: bool) -> None:
        if user.id in self._denied_seen:
            # Повторные — в debug: один настырный посторонний не должен
            # заваливать лог, который владелец читает ради настоящих проблем.
            logger.debug("stranger %s rejected again", user.id)
            return
        if len(self._denied_seen) >= _MAX_TRACKED_STRANGERS:
            self._denied_seen.clear()
        self._denied_seen.add(user.id)
        logger.warning(
            "stranger rejected: id=%s username=%s invite=%s",
            user.id,
            user.username,
            invite_attempted,
        )
