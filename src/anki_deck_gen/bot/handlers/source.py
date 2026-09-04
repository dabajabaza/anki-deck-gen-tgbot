"""Приём Таблицы: файл, ссылка на Google Таблицу или текст.

Команды запоминать не нужно — Таблица и есть команда. Разбор происходит прямо
здесь (ввод-вывод, async), результат ложится в Pending, человек видит сводку и
кнопки. Любой новый Источник сбрасывает предыдущий диалог: FixRows держит
номера строк уже другой таблицы.
"""

import logging
from typing import Any

from aiogram import Bot, Router
from aiogram.filters import Filter
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from anki_deck_gen.bot import texts
from anki_deck_gen.bot.loader import Source, TableLoader, describe
from anki_deck_gen.bot.pending import Pending, PendingStore
from anki_deck_gen.bot.states import Rename
from anki_deck_gen.bot.views import error_text, render_summary
from anki_deck_gen.config import BotSettings
from anki_deck_gen.errors import AnkiDeckGenError
from anki_deck_gen.tables.validate import validate

logger = logging.getLogger(__name__)

router = Router(name="source")


class IsTableSource(Filter):
    """Сообщение с файлом .xlsx/.csv, ссылкой на Google Таблицу или текстом-таблицей.

    Словарь из фильтра сливается в аргументы обработчика: распознавание
    происходит один раз здесь, а не второй раз внутри.

    Пока идёт диалог (правка строки, имя колоды), присланный текст — ответ на
    вопрос бота, а не новая Таблица: «bird / птица» подходит под оба описания
    сразу. Файл и ссылка не двусмысленны и диалог по-прежнему сбрасывают.
    """

    async def __call__(self, message: Message, state: FSMContext) -> bool | dict[str, Any]:
        source = describe(message)
        if source is None:
            return False
        if source.kind == "text" and await state.get_state() is not None:
            return False
        return {"source": source}


@router.message(IsTableSource())
async def accept_table(
    message: Message,
    source: Source,
    bot: Bot,
    state: FSMContext,
    pending: PendingStore,
    loader: TableLoader,
    settings: BotSettings,
) -> None:
    user = message.from_user
    if user is None:
        return
    await state.clear()
    pending.pop(user.id)

    status = await message.answer(texts.READING)
    try:
        table = await loader.load(bot, source)
        validation = validate(table, max_notes=settings.max_notes)
    except AnkiDeckGenError as exc:
        logger.info("table from %s rejected: %s: %s", user.id, type(exc).__name__, exc)
        await _edit(bot, status.chat.id, status.message_id, error_text(exc, settings))
        return
    except Exception:
        logger.exception("table from %s could not be read", user.id)
        await _edit(bot, status.chat.id, status.message_id, texts.ERR_BUILD_FAILED)
        return

    item = Pending(
        table=table,
        validation=validation,
        deck_name=table.title or "",
        chat_id=status.chat.id,
        status_message_id=status.message_id,
    )
    pending.put(user.id, item)
    logger.info(
        "table accepted from %s: %s sheet(s), %s notes, %s problem(s)",
        user.id,
        len(table.sheets),
        validation.notes,
        len(validation.problems),
    )
    if not item.deck_name:
        # У вставленного текста имени взять негде — спрашиваем до сводки.
        await state.set_state(Rename.waiting)
        await message.answer(texts.ASK_DECK_NAME)
        return
    await render_summary(bot, item)


async def _edit(bot: Bot, chat_id: int, message_id: int, text: str) -> None:
    try:
        await bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=text)
    except Exception as exc:
        logger.warning("status edit failed: %s: %s", type(exc).__name__, exc)
