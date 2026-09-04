"""Экраны, которые рисуются из нескольких обработчиков.

Сводка после разбора нужна и приёму таблицы, и правке строк, и переименованию —
поэтому она здесь, а не в одном из них. Плюс перевод исключений в слова.
"""

import logging

from aiogram import Bot
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, Message

from anki_deck_gen import notetypes
from anki_deck_gen.bot import keyboards, texts
from anki_deck_gen.bot.pending import Pending, PendingStore
from anki_deck_gen.config import BotSettings
from anki_deck_gen.errors import (
    FileTooLarge,
    MissingColumns,
    SheetNotShared,
    SheetUnreachable,
    TableUnreadable,
    TooManyRows,
    TtsUnavailable,
    UnsupportedSource,
)

logger = logging.getLogger(__name__)


def message_of(callback: CallbackQuery) -> Message | None:
    return callback.message if isinstance(callback.message, Message) else None


async def resolve_pending(
    callback: CallbackQuery, pending: PendingStore, settings: BotSettings, state: FSMContext
) -> Pending | None:
    """Pending этого человека — если кнопка с его ТЕКУЩЕГО статус-сообщения.

    Порядок важен: сначала смотрим без побочных эффектов (`get`), продлеваем TTL
    только принятому нажатию — отклонённая кнопка мёртвой клавиатуры не шаг диалога.
    Истёкший Pending заодно закрывает диалог: иначе человек оставался бы в
    FixRows и получал «устарела» ещё и на следующий текст.
    """
    item = pending.get(callback.from_user.id)
    if item is None:
        await state.clear()
        await _mark_expired(callback, settings)
        return None
    if is_stale(callback, item):
        await callback.answer(texts.ERR_UNKNOWN_BUTTON, show_alert=True)
        return None
    pending.touch(callback.from_user.id)
    return item


async def _mark_expired(callback: CallbackQuery, settings: BotSettings) -> None:
    message = message_of(callback)
    if message is not None:
        try:
            await message.edit_text(texts.ERR_EXPIRED.format(minutes=settings.pending_ttl_s // 60))
        except Exception as exc:  # правка косметическая
            logger.debug("could not mark expired: %s", exc)
    await callback.answer()


def draft_text(pending: Pending) -> str:
    """Экран черновика: сколько строк набралось и что делать дальше."""
    return texts.draft(notes=pending.validation.notes, problems=len(pending.validation.problems))


def summary_text(pending: Pending) -> str:
    table = pending.table
    empty = [s.name for s in table.sheets if not s.rows and s.name]
    return texts.summary(
        deck_name=pending.deck_name,
        sheets=sum(1 for s in table.sheets if s.rows),
        notes=pending.notes,
        problems=pending.unresolved(),
        duplicates=len(pending.validation.duplicates),
        empty_sheets=empty,
    )


def summary_keyboard(pending: Pending) -> InlineKeyboardMarkup | None:
    """Проблемы не решены — кнопки про них; решены — выбор Типа записи."""
    if pending.unresolved():
        return keyboards.problems()
    compatible = notetypes.compatible(pending.table.columns)
    if not compatible:
        return None
    return keyboards.note_types(compatible)


def no_compatible_text() -> str:
    needs = "\n".join(
        texts.NOTE_TYPE_NEEDS.format(label=nt.label, columns=", ".join(sorted(nt.required_columns)))
        for nt in notetypes.REGISTRY.values()
        if nt.visible_in_bot
    )
    return texts.NO_COMPATIBLE_TYPES.format(needs=needs)


async def render_summary(bot: Bot, pending: Pending) -> None:
    """Перерисовать статус-сообщение в сводку с уместной клавиатурой."""
    text = summary_text(pending)
    keyboard = summary_keyboard(pending)
    if not pending.unresolved():
        if keyboard is None:
            text = f"{text}\n\n{no_compatible_text()}"
        else:
            text = f"{text}\n\n{texts.CHOOSE_NOTE_TYPE}"
    await edit_status(bot, pending, text, keyboard)


async def edit_status(
    bot: Bot, pending: Pending, text: str, keyboard: InlineKeyboardMarkup | None = None
) -> None:
    """Правка статус-сообщения, которая не роняет обработчик.

    Telegram отвечает «message is not modified» на правку тем же текстом и
    той же клавиатурой — это не ошибка, человек нажал кнопку второй раз.
    """
    try:
        await bot.edit_message_text(
            chat_id=pending.chat_id,
            message_id=pending.status_message_id,
            text=text,
            reply_markup=keyboard,
        )
    except Exception as exc:
        logger.warning("status edit failed: %s: %s", type(exc).__name__, exc)


def error_text(exc: Exception, settings: BotSettings) -> str:
    """Что сказать человеку о неудаче разбора Таблицы."""
    if isinstance(exc, UnsupportedSource):
        return texts.ERR_UNSUPPORTED
    if isinstance(exc, FileTooLarge):
        return texts.ERR_FILE_TOO_LARGE.format(
            size=texts.human_size(exc.size_bytes), limit=settings.max_file_mb
        )
    if isinstance(exc, TableUnreadable):
        return texts.ERR_TABLE_UNREADABLE.format(detail=exc.detail)
    if isinstance(exc, SheetNotShared):
        return texts.ERR_SHEET_NOT_SHARED
    if isinstance(exc, SheetUnreachable):
        return texts.ERR_SHEET_UNREACHABLE
    if isinstance(exc, TooManyRows):
        return texts.ERR_TOO_MANY_ROWS.format(count=exc.count, limit=exc.limit)
    if isinstance(exc, MissingColumns):
        label = (
            notetypes.REGISTRY[exc.note_type].label
            if exc.note_type in notetypes.REGISTRY
            else exc.note_type
        )
        return texts.ERR_MISSING_COLUMNS.format(label=label, columns=", ".join(sorted(exc.missing)))
    if isinstance(exc, TtsUnavailable):
        return texts.ERR_TTS
    return texts.ERR_BUILD_FAILED


def is_stale(callback: CallbackQuery, pending: Pending) -> bool:
    """Кнопка с прошлого статус-сообщения не должна управлять новой Таблицей (A3).

    Pending ищется по пользователю, и старая клавиатура иначе применила бы свои
    языки и озвучку к таблице, присланной позже.
    """
    message = callback.message
    if not isinstance(message, Message):
        return True
    # id сообщений уникальны только внутри чата — сравниваем и чат, хотя сегодня бот
    # только в личке (PrivateChatOnlyMiddleware): помощник не должен зависеть от этого.
    return message.chat.id != pending.chat_id or message.message_id != pending.status_message_id
