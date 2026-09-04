"""Прогон настоящего диспетчера через сфабрикованные апдейты, без сети.

Перенос из clipivore. Добавлены документы (входящие и исходящие), удаление
сообщений, ответы на кнопки — то, чем этот бот пользуется, а тот нет.
"""

import asyncio
from collections.abc import AsyncGenerator
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, TypeVar

from aiogram import Bot, Dispatcher
from aiogram.client.session.base import BaseSession
from aiogram.methods import (
    AnswerCallbackQuery,
    DeleteMessage,
    EditMessageText,
    SendDocument,
    SendMessage,
    TelegramMethod,
)
from aiogram.methods.get_me import GetMe
from aiogram.types import CallbackQuery, Chat, Document, Message, Update
from aiogram.types import User as TgUser
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from anki_deck_gen.bot.loader import Source, TableLoader
from anki_deck_gen.bot.pending import PendingStore
from anki_deck_gen.domain import Table
from anki_deck_gen.runtime.worker import Request, RequestQueue

M = TypeVar("M", bound=TelegramMethod[Any])


class RecordingSession(BaseSession):
    """Двойник сессии aiogram: записывает каждый исходящий вызов и возвращает
    сфабрикованные результаты, проходящие валидацию ответов самого aiogram.

    Наследует BaseSession, а не утка: так ``Bot.session`` его принимает и
    ``Bot.__call__`` работает без изменений. ``fail_on`` программирует отказ
    по имени класса метода.
    """

    def __init__(self) -> None:
        super().__init__()
        self.calls: list[TelegramMethod[Any]] = []
        self.timeouts: list[int | None] = []
        self.fail_on: dict[str, Exception] = {}
        self._next_message_id = 5000

    def _next_message(self, chat_id: int, text: str | None) -> Message:
        self._next_message_id += 1
        return Message(
            message_id=self._next_message_id,
            date=datetime.now(UTC),
            chat=Chat(id=chat_id, type="private"),
            text=text,
        )

    async def make_request(
        self, bot: Bot, method: TelegramMethod[Any], timeout: int | None = None
    ) -> Any:
        self.calls.append(method)
        self.timeouts.append(timeout)
        # Настоящий вызов API всегда уступает циклу событий. Без этого двойник
        # атомарен, и гонки в проверяемом коде — устаревшая правка прогресса
        # после вердикта, две правки одного сообщения — становятся структурно
        # невоспроизводимы.
        await asyncio.sleep(0)
        name = type(method).__name__
        if name in self.fail_on:
            raise self.fail_on[name]

        if isinstance(method, SendMessage | EditMessageText | SendDocument):
            assert isinstance(method.chat_id, int)
            return self._next_message(method.chat_id, getattr(method, "text", None))
        if isinstance(method, GetMe):
            return TgUser(id=1, is_bot=True, first_name="Bot", username="testbot")
        return True

    async def close(self) -> None:
        pass

    async def stream_content(
        self,
        url: str,
        headers: dict[str, Any] | None = None,
        timeout: int = 30,
        chunk_size: int = 65536,
        raise_for_status: bool = True,
    ) -> AsyncGenerator[bytes, None]:
        yield b""

    def timeout_of(self, method_type: type[M]) -> int | None:
        for method, timeout in zip(self.calls, self.timeouts, strict=True):
            if isinstance(method, method_type):
                return timeout
        raise AssertionError(f"{method_type.__name__} was never called")

    def calls_of(self, method_type: type[M]) -> list[M]:
        return [method for method in self.calls if isinstance(method, method_type)]

    def sent_texts(self) -> list[str]:
        return [
            text for method in self.calls if (text := getattr(method, "text", None)) is not None
        ]

    def last_text(self) -> str:
        texts = self.sent_texts()
        assert texts, "the bot said nothing"
        return texts[-1]

    def last_labels(self) -> list[str]:
        """Подписи кнопок на последнем ОТПРАВЛЕННОМ сообщении; пусто, если их нет."""
        sent = [method for method in self.calls if getattr(method, "text", None) is not None]
        assert sent, "the bot said nothing"
        markup = getattr(sent[-1], "reply_markup", None)
        if markup is None or not hasattr(markup, "inline_keyboard"):
            return []
        return [button.text for row in markup.inline_keyboard for button in row]

    def edit_texts(self) -> list[str]:
        """Тексты всех правок статус-сообщений, по порядку."""
        return [m.text for m in self.calls_of(EditMessageText) if m.text is not None]

    def last_edit(self) -> EditMessageText:
        edits = self.calls_of(EditMessageText)
        assert edits, "the bot edited nothing"
        return edits[-1]

    def last_edit_text(self) -> str:
        text = self.last_edit().text
        assert text is not None
        return text

    def last_edit_labels(self) -> list[str]:
        """Подписи кнопок на последней правке; пусто, если клавиатуры нет."""
        markup = self.last_edit().reply_markup
        if markup is None:
            return []
        return [button.text for row in markup.inline_keyboard for button in row]

    def answered_callbacks(self) -> list[AnswerCallbackQuery]:
        return self.calls_of(AnswerCallbackQuery)

    def deleted(self) -> list[DeleteMessage]:
        return self.calls_of(DeleteMessage)

    def clear(self) -> None:
        self.calls.clear()
        self.timeouts.clear()


def _user(user_id: int) -> TgUser:
    return TgUser(id=user_id, is_bot=False, first_name="Test", username=f"user{user_id}")


def make_update_message(
    text: str | None,
    *,
    user_id: int,
    chat_id: int | None = None,
    chat_type: str = "private",
    update_id: int = 1,
    document: Document | None = None,
) -> Update:
    chat = Chat(id=chat_id if chat_id is not None else user_id, type=chat_type)
    message = Message(
        message_id=update_id,
        date=datetime.now(UTC),
        chat=chat,
        from_user=_user(user_id),
        text=text,
        document=document,
    )
    return Update(update_id=update_id, message=message)


def make_document(file_name: str, *, size: int = 1024) -> Document:
    return Document(
        file_id=f"file-{file_name}",
        file_unique_id=f"uniq-{file_name}",
        file_name=file_name,
        file_size=size,
    )


def make_callback_update(
    data: str,
    *,
    user_id: int,
    message_id: int,
    chat_id: int | None = None,
    update_id: int = 1,
) -> Update:
    chat = Chat(id=chat_id if chat_id is not None else user_id, type="private")
    message = Message(
        message_id=message_id,
        date=datetime.now(UTC),
        chat=chat,
        from_user=TgUser(id=1, is_bot=True, first_name="Bot", username="testbot"),
        text="status",
    )
    callback = CallbackQuery(
        id=f"callback-{update_id}",
        from_user=_user(user_id),
        chat_instance="test",
        message=message,
        data=data,
    )
    return Update(update_id=update_id, callback_query=callback)


class FakeLoader(TableLoader):
    """Загрузчик без Telegram и без Google: отдаёт заранее подготовленные Таблицы.

    Ключ — имя файла, URL или сам текст; значение — Таблица или исключение,
    которое надо бросить.
    """

    def __init__(self) -> None:
        super().__init__(max_file_bytes=5 * 1024 * 1024)
        self.tables: dict[str, Table | Exception] = {}
        self.loaded: list[Source] = []

    def _key(self, source: Source) -> str:
        if source.kind == "document":
            assert source.document is not None
            return source.document.file_name or ""
        if source.kind == "sheets":
            assert source.url is not None
            return source.url
        assert source.text is not None
        return source.text

    async def load(self, bot: Bot, source: Source) -> Table:
        self.loaded.append(source)
        key = self._key(source)
        if key not in self.tables:
            # Текст без заготовки разбираем по-настоящему — там сети нет.
            if source.kind == "text":
                assert source.text is not None
                return self.from_text(source.text)
            raise AssertionError(f"FakeLoader has no table for {key!r}")
        prepared = self.tables[key]
        if isinstance(prepared, Exception):
            raise prepared
        return prepared


@dataclass
class BotHarness:
    """Настоящий Dispatcher — тот, что собирает ``build_dispatcher`` для прода, —
    на сфабрикованных апдейтах, с записью всего, что бот попытался отправить."""

    bot: Bot
    dp: Dispatcher
    session: RecordingSession
    queue: RequestQueue
    pending: PendingStore
    loader: FakeLoader
    sessionmaker: async_sessionmaker[AsyncSession]
    _next_update_id: int = field(default=1)

    def _update_id(self) -> int:
        self._next_update_id += 1
        return self._next_update_id

    async def take(self, timeout: float = 2.0) -> Request:
        """Следующее Задание из очереди — или быстрый провал, если ничего не поставили."""
        async with asyncio.timeout(timeout):
            return await self.queue.take()

    async def send(self, text: str, *, user_id: int = 1, chat_type: str = "private") -> None:
        update = make_update_message(
            text, user_id=user_id, chat_type=chat_type, update_id=self._update_id()
        )
        await self.dp.feed_update(self.bot, update)

    async def send_document(self, file_name: str, *, user_id: int = 1, size: int = 1024) -> None:
        update = make_update_message(
            None,
            user_id=user_id,
            update_id=self._update_id(),
            document=make_document(file_name, size=size),
        )
        await self.dp.feed_update(self.bot, update)

    async def press(self, data: str, *, user_id: int = 1, message_id: int | None = None) -> None:
        """Нажать кнопку на статус-сообщении пользователя (по умолчанию — текущем)."""
        if message_id is None:
            item = self.pending.get(user_id)
            message_id = item.status_message_id if item is not None else 7000
        update = make_callback_update(
            data, user_id=user_id, message_id=message_id, update_id=self._update_id()
        )
        await self.dp.feed_update(self.bot, update)
