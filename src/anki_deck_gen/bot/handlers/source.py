"""Приём Таблицы: файл, ссылка на Google Таблицу или текст.

Команды запоминать не нужно — Таблица и есть команда. Разбор происходит прямо
здесь (ввод-вывод, async), результат ложится в Pending, человек видит сводку и
кнопки. Новый файл или ссылка сбрасывают предыдущий диалог: FixRows держит
номера строк уже другой таблицы.

Текст — особый случай (A10): он копится черновиком. Первая строка «вопрос /
ответ» открывает черновик, каждое следующее сообщение дописывает свои строки, и
только «Готово» превращает накопленное в Таблицу. Поэтому строку можно прислать
одну, можно десять, можно добавлять их по мере того, как они приходят в голову.
"""

import logging
from typing import Any

from aiogram import Bot, Router
from aiogram.filters import Filter
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from anki_deck_gen.bot import keyboards, texts
from anki_deck_gen.bot.loader import Source, TableLoader, describe
from anki_deck_gen.bot.pending import Pending, PendingStore
from anki_deck_gen.bot.states import Rename
from anki_deck_gen.bot.views import draft_text, error_text, render_summary
from anki_deck_gen.config import BotSettings
from anki_deck_gen.errors import AnkiDeckGenError
from anki_deck_gen.tables.parse import parse_text
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

    Пока открыт черновик, годится ЛЮБОЙ текст, а не только похожий на таблицу:
    человек уже сказал, что набирает колоду, и строка без разделителя — не повод
    молчать, а Проблемная строка, которую он поправит после «Готово». Команды
    (`/skip`, `/cancel`) сюда не попадают: их разбирают свои обработчики.
    """

    async def __call__(
        self, message: Message, state: FSMContext, pending: PendingStore
    ) -> bool | dict[str, Any]:
        source = describe(message)
        if source is not None and source.kind != "text":
            # Файл и ссылка не двусмысленны: это всегда новая Таблица, чем бы ни
            # был занят человек — правкой строк, именем колоды или черновиком.
            return {"source": source}
        if await state.get_state() is not None:
            return False
        text = message.text or ""
        item = pending.get(message.from_user.id) if message.from_user else None
        if item is not None and item.draft is not None and text and not text.startswith("/"):
            return {"source": Source(kind="text", text=text)}
        return {"source": source} if source is not None else False


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
    if source.kind == "text":
        await _collect(message, source, bot, state, pending, settings)
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
        # Имя взять негде — спрашиваем до сводки.
        await state.set_state(Rename.waiting)
        await message.answer(texts.ASK_DECK_NAME)
        return
    await render_summary(bot, item)


async def _collect(
    message: Message,
    source: Source,
    bot: Bot,
    state: FSMContext,
    pending: PendingStore,
    settings: BotSettings,
) -> None:
    """Дописать строки в черновик — или начать новый (A10)."""
    user = message.from_user
    assert user is not None
    current = pending.get(user.id)
    started = current is not None and current.draft is not None
    lines = list(current.draft or []) if started and current is not None else []
    lines += [line for line in (source.text or "").splitlines() if line.strip()]

    table = parse_text("\n".join(lines))
    try:
        validation = validate(table, max_notes=settings.max_notes)
    except AnkiDeckGenError as exc:
        # Потолок записей: черновик остаётся прежним, лишние строки не приняты.
        logger.info("draft from %s refused: %s: %s", user.id, type(exc).__name__, exc)
        await message.answer(error_text(exc, settings))
        return

    if started and current is not None:
        current.table, current.validation, current.draft = table, validation, lines
        item = current
    else:
        await state.clear()
        pending.pop(user.id)
        item = Pending(
            table=table,
            validation=validation,
            deck_name="",
            chat_id=message.chat.id,
            status_message_id=0,
            draft=lines,
        )
        pending.put(user.id, item)

    # Клавиатура черновика всегда должна быть последним сообщением в чате: строки
    # человек шлёт одну за другой, и правка старого сообщения уехала бы вверх.
    status = await message.answer(draft_text(item), reply_markup=keyboards.draft())
    if started:
        await _delete(bot, item.chat_id, item.status_message_id)
    item.chat_id, item.status_message_id = status.chat.id, status.message_id
    pending.touch(user.id)


async def _delete(bot: Bot, chat_id: int, message_id: int) -> None:
    try:
        await bot.delete_message(chat_id=chat_id, message_id=message_id)
    except Exception as exc:  # сообщение старше 48 часов или уже удалено
        logger.debug("could not remove the previous draft message: %s", exc)


async def _edit(bot: Bot, chat_id: int, message_id: int, text: str) -> None:
    try:
        await bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=text)
    except Exception as exc:
        logger.warning("status edit failed: %s: %s", type(exc).__name__, exc)
