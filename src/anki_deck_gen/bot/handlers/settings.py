"""Выбор Настроек колоды кнопками и постановка Задания в очередь.

Состояния нет: тип записи, пара языков и сторона озвучки едут в callback_data
(bot/callbacks.py), а Таблица лежит в Pending. Последний шаг собирает
BuildRequest целиком из Pending и отдаёт воркеру — тот в Pending не смотрит.
"""

import asyncio
import logging
from dataclasses import replace

from aiogram import Bot, F, Router
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from anki_deck_gen import notetypes
from anki_deck_gen.bot import callbacks, keyboards, texts
from anki_deck_gen.bot.pending import Pending, PendingStore
from anki_deck_gen.bot.progress import ProgressReporter
from anki_deck_gen.bot.views import edit_status, render_summary
from anki_deck_gen.config import BotSettings
from anki_deck_gen.domain import BuildRequest, DeckSettings
from anki_deck_gen.errors import UnknownNoteType
from anki_deck_gen.runtime.worker import Request, RequestQueue
from anki_deck_gen.services import prefs

logger = logging.getLogger(__name__)

router = Router(name="settings")


@router.callback_query(F.data.startswith(("nt:", "last:", "cfg:", "lp:", "s:")))
async def on_settings_step(
    callback: CallbackQuery,
    bot: Bot,
    pending: PendingStore,
    settings: BotSettings,
    sessionmaker: async_sessionmaker[AsyncSession],
    queue: RequestQueue,
) -> None:
    parsed = callbacks.parse(callback.data or "")
    if parsed is None:
        await callback.answer(texts.ERR_UNKNOWN_BUTTON, show_alert=True)
        return
    user_id = callback.from_user.id
    item = pending.touch(user_id)
    message = callback.message if isinstance(callback.message, Message) else None
    if item is None:
        await callback.answer()
        if message is not None:
            await _edit(message, texts.ERR_EXPIRED.format(minutes=settings.pending_ttl_s // 60))
        return
    if item.unresolved():
        # Кнопки настроек появляются только после решения проблем; сюда можно
        # попасть лишь старой кнопкой — вернуть человека к актуальной сводке.
        await callback.answer()
        await render_summary(bot, item)
        return
    assert parsed.note_type_id is not None
    try:
        note_type = notetypes.get(parsed.note_type_id)
    except UnknownNoteType:
        await callback.answer(texts.ERR_UNKNOWN_BUTTON, show_alert=True)
        return

    await callback.answer()
    if parsed.action == "nt":
        async with sessionmaker() as session:
            last = await prefs.get_last(session, user_id)
        await edit_status(
            bot,
            item,
            texts.CHOOSE_LANGUAGES.format(label=note_type.label),
            keyboards.languages(note_type.id, last),
        )
        return
    if parsed.action == "cfg":
        await edit_status(
            bot,
            item,
            texts.CHOOSE_PAIR.format(label=note_type.label),
            keyboards.language_pairs(note_type.id),
        )
        return
    if parsed.action == "lp":
        assert parsed.lang_q and parsed.lang_a
        await edit_status(
            bot,
            item,
            texts.CHOOSE_AUDIO.format(
                label=note_type.label, pair=texts.pair_label(parsed.lang_q, parsed.lang_a)
            ),
            keyboards.audio_sides(note_type.id, parsed.lang_q, parsed.lang_a),
        )
        return
    if parsed.action == "last":
        async with sessionmaker() as session:
            last = await prefs.get_last(session, user_id)
        if last is None:
            await edit_status(
                bot,
                item,
                texts.CHOOSE_PAIR.format(label=note_type.label),
                keyboards.language_pairs(note_type.id),
            )
            return
        chosen = replace(last, note_type_id=note_type.id)
    else:
        chosen = parsed.deck_settings()

    await enqueue(
        bot=bot,
        item=item,
        user_id=user_id,
        chosen=chosen,
        pending=pending,
        queue=queue,
        settings=settings,
        sessionmaker=sessionmaker,
    )


async def enqueue(
    *,
    bot: Bot,
    item: Pending,
    user_id: int,
    chosen: DeckSettings,
    pending: PendingStore,
    queue: RequestQueue,
    settings: BotSettings,
    sessionmaker: async_sessionmaker[AsyncSession],
) -> None:
    """Собрать Задание из Pending и поставить в очередь. Pending при этом заканчивается."""
    note_type = notetypes.get(chosen.note_type_id)
    missing = note_type.required_columns - item.table.columns
    if missing:
        await edit_status(
            bot,
            item,
            texts.ERR_MISSING_COLUMNS.format(
                label=note_type.label, columns=", ".join(sorted(missing))
            ),
        )
        return

    pending.pop(user_id)
    reporter = ProgressReporter(bot, chat_id=item.chat_id, message_id=item.status_message_id)
    request = Request(
        build=BuildRequest(
            table=item.table,
            settings=chosen,
            deck_name=item.deck_name,
            fixes=dict(item.fixes),
            skips=frozenset(item.skips),
        ),
        chat_id=item.chat_id,
        user_id=user_id,
        reporter=reporter,
    )
    try:
        position = queue.submit(request)
    except asyncio.QueueFull:
        await reporter.finish(texts.QUEUE_FULL.format(limit=settings.queue_limit))
        return
    logger.info(
        "queued deck for %s at position %s: type=%s langs=%s-%s audio=%s notes=%s",
        user_id,
        position,
        chosen.note_type_id,
        chosen.lang_q,
        chosen.lang_a,
        chosen.audio.value,
        item.notes,
    )
    await reporter.set(
        texts.QUEUED if position == 1 else texts.QUEUED_POSITION.format(position=position)
    )
    async with sessionmaker() as session:
        await prefs.save_last(session, user_id, chosen)
        await session.commit()


async def _edit(message: Message, text: str) -> None:
    try:
        await message.edit_text(text)
    except Exception as exc:
        logger.debug("status edit failed: %s", exc)
