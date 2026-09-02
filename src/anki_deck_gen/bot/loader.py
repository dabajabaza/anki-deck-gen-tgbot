"""Как из сообщения получается Таблица.

Три Источника — файл, ссылка на Google Таблицу, текст — и один класс, который
знает, как каждый из них скачать и разобрать. Вынесен из обработчика, чтобы
тесты подменяли его целиком (``dp["loader"]``) и гоняли диалог без Telegram и
без Google.
"""

import logging
from dataclasses import dataclass
from io import BytesIO
from typing import Literal

from aiogram import Bot
from aiogram.types import Document, Message

from anki_deck_gen.domain import Table
from anki_deck_gen.errors import FileTooLarge, UnsupportedSource
from anki_deck_gen.tables import parse, sources

logger = logging.getLogger(__name__)

SourceKind = Literal["document", "sheets", "text"]


@dataclass(frozen=True)
class Source:
    """Что именно прислали, ещё не скачанное."""

    kind: SourceKind
    document: Document | None = None
    url: str | None = None
    text: str | None = None


def describe(message: Message) -> Source | None:
    """Распознать Источник в сообщении. None — это не Таблица."""
    document = message.document
    if document is not None and _extension(document) in ("xlsx", "csv"):
        return Source(kind="document", document=document)
    text = message.text or message.caption
    url = sources.extract_sheets_url(text)
    if url:
        return Source(kind="sheets", url=url)
    if text and parse.looks_like_text_table(text):
        return Source(kind="text", text=text)
    return None


def _extension(document: Document) -> str:
    name = document.file_name or ""
    return name.rsplit(".", 1)[-1].lower() if "." in name else ""


class TableLoader:
    """Скачивает и разбирает Источник в Таблицу."""

    def __init__(self, *, max_file_bytes: int, sheets_timeout_s: float = 30.0) -> None:
        self._max_file_bytes = max_file_bytes
        self._sheets_timeout_s = sheets_timeout_s

    async def load(self, bot: Bot, source: Source) -> Table:
        if source.kind == "document":
            assert source.document is not None
            return await self.from_document(bot, source.document)
        if source.kind == "sheets":
            assert source.url is not None
            return await self.from_sheets(source.url)
        assert source.text is not None
        return self.from_text(source.text)

    async def from_document(self, bot: Bot, document: Document) -> Table:
        size = document.file_size or 0
        if size > self._max_file_bytes:
            raise FileTooLarge(size_bytes=size, limit_bytes=self._max_file_bytes)
        buffer = BytesIO()
        await bot.download(document, destination=buffer)
        data = buffer.getvalue()
        name = document.file_name or ""
        title = name.rsplit(".", 1)[0] if "." in name else name or None
        extension = _extension(document)
        if extension == "xlsx":
            return parse.parse_xlsx(data, title=title)
        if extension == "csv":
            return parse.parse_csv(data, title=title)
        raise UnsupportedSource(name)

    async def from_sheets(self, url: str) -> Table:
        data, title = await sources.fetch_google_sheet(url, timeout_s=self._sheets_timeout_s)
        return parse.parse_xlsx(data, title=title)

    def from_text(self, text: str) -> Table:
        return parse.parse_text(text)
