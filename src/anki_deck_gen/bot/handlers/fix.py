"""Проблемные строки и имя колоды — два диалога, где бот ждёт текст.

Проблемы идут по одной: «первая нерешённая» вычисляется каждый раз заново из
Pending, поэтому в FSM нет ни индекса, ни копии списка — только факт «мы в
правке». /skip пропускает строку, /cancel прерывает правку (Pending остаётся,
человек может выбрать «Пропустить плохие»).
"""

import logging
import re

from aiogram import Bot, F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from anki_deck_gen.bot import callbacks, texts
from anki_deck_gen.bot.pending import Pending, PendingStore
from anki_deck_gen.bot.states import FixRows, Rename
from anki_deck_gen.bot.views import edit_status, is_stale, render_summary
from anki_deck_gen.config import BotSettings
from anki_deck_gen.domain import Fix, Problem, ProblemRow

logger = logging.getLogger(__name__)

router = Router(name="fix")

# Тот же разделитель, что у вставленного текста (tables/parse.py).
_SEPARATOR = re.compile(r"\s+[—–-]\s+|\t")


def _message_of(callback: CallbackQuery) -> Message | None:
    return callback.message if isinstance(callback.message, Message) else None


async def _current(
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
        await _expired(callback, settings)
        return None
    if is_stale(callback, item):
        await callback.answer(texts.ERR_UNKNOWN_BUTTON, show_alert=True)
        return None
    pending.touch(callback.from_user.id)
    return item


async def _expired(callback: CallbackQuery, settings: BotSettings) -> None:
    message = _message_of(callback)
    if message is not None:
        try:
            await message.edit_text(texts.ERR_EXPIRED.format(minutes=settings.pending_ttl_s // 60))
        except Exception as exc:  # правка косметическая
            logger.debug("could not mark expired: %s", exc)
    await callback.answer()


@router.callback_query(F.data == callbacks.PROBLEMS_FIX)
async def start_fixing(
    callback: CallbackQuery,
    bot: Bot,
    state: FSMContext,
    pending: PendingStore,
    settings: BotSettings,
) -> None:
    item = await _current(callback, pending, settings, state)
    if item is None:
        return
    unresolved = item.unresolved()
    await callback.answer()
    if not unresolved:
        await render_summary(bot, item)
        return
    await state.set_state(FixRows.fixing)
    message = _message_of(callback)
    if message is not None:
        await message.answer(texts.fix_prompt(unresolved[0]))


@router.callback_query(F.data == callbacks.PROBLEMS_SKIP)
async def skip_all(
    callback: CallbackQuery,
    bot: Bot,
    state: FSMContext,
    pending: PendingStore,
    settings: BotSettings,
) -> None:
    item = await _current(callback, pending, settings, state)
    if item is None:
        return
    for problem in item.unresolved():
        item.skips.add(problem.row.key)
    await state.clear()
    await callback.answer()
    await render_summary(bot, item)


@router.callback_query(F.data == callbacks.PROBLEMS_CANCEL)
async def cancel_table(
    callback: CallbackQuery,
    bot: Bot,
    state: FSMContext,
    pending: PendingStore,
    settings: BotSettings,
) -> None:
    item = await _current(callback, pending, settings, state)
    if item is None:
        return
    pending.pop(callback.from_user.id)
    await state.clear()
    await callback.answer()
    await edit_status(bot, item, texts.CANCELLED)


@router.callback_query(F.data == callbacks.RENAME)
async def ask_rename(
    callback: CallbackQuery,
    state: FSMContext,
    pending: PendingStore,
    settings: BotSettings,
) -> None:
    item = await _current(callback, pending, settings, state)
    if item is None:
        return
    await state.set_state(Rename.waiting)
    await callback.answer()
    message = _message_of(callback)
    if message is not None:
        await message.answer(texts.RENAME_PROMPT)


@router.message(Rename.waiting, F.text)
async def set_name(
    message: Message,
    bot: Bot,
    state: FSMContext,
    pending: PendingStore,
    settings: BotSettings,
) -> None:
    assert message.from_user is not None and message.text is not None
    item = pending.touch(message.from_user.id)
    if item is None:
        await state.clear()
        await message.answer(texts.ERR_EXPIRED.format(minutes=settings.pending_ttl_s // 60))
        return
    name = message.text.strip()
    if not name:
        await message.answer(texts.NAME_EMPTY)
        return
    item.deck_name = name
    await state.clear()
    await render_summary(bot, item)


@router.message(FixRows.fixing, Command("skip"))
async def skip_one(
    message: Message,
    bot: Bot,
    state: FSMContext,
    pending: PendingStore,
    settings: BotSettings,
) -> None:
    assert message.from_user is not None
    item = pending.touch(message.from_user.id)
    if item is None:
        await state.clear()
        await message.answer(texts.ERR_EXPIRED.format(minutes=settings.pending_ttl_s // 60))
        return
    unresolved = item.unresolved()
    if unresolved:
        item.skips.add(unresolved[0].row.key)
    await _advance(message, bot, state, item)


@router.message(FixRows.fixing, Command("cancel"))
async def cancel_fixing(
    message: Message,
    bot: Bot,
    state: FSMContext,
    pending: PendingStore,
) -> None:
    assert message.from_user is not None
    await state.clear()
    await message.answer(texts.FIX_CANCELLED)
    item = pending.touch(message.from_user.id)
    if item is not None:
        await render_summary(bot, item)


@router.message(FixRows.fixing, F.text)
async def fix_one(
    message: Message,
    bot: Bot,
    state: FSMContext,
    pending: PendingStore,
    settings: BotSettings,
) -> None:
    assert message.from_user is not None and message.text is not None
    item = pending.touch(message.from_user.id)
    if item is None:
        await state.clear()
        await message.answer(texts.ERR_EXPIRED.format(minutes=settings.pending_ttl_s // 60))
        return
    unresolved = item.unresolved()
    if not unresolved:
        await state.clear()
        await render_summary(bot, item)
        return
    fix = _fix_from(unresolved[0], message.text.strip())
    if fix is None:
        await message.answer(texts.FIX_STILL_NO_SEPARATOR)
        return
    item.fixes[unresolved[0].row.key] = fix
    await _advance(message, bot, state, item)


def _fix_from(problem: ProblemRow, text: str) -> Fix | None:
    """Собрать исправление из ответа человека; None — ответ не годится."""
    if not text:
        return None
    row = problem.row
    if problem.problem is Problem.EMPTY_ANSWER:
        return Fix(question=row.question, answer=text)
    if problem.problem is Problem.EMPTY_QUESTION:
        return Fix(question=text, answer=row.answer)
    parts = _SEPARATOR.split(text, maxsplit=1)
    if len(parts) != 2 or not parts[0].strip() or not parts[1].strip():
        return None
    return Fix(question=parts[0].strip(), answer=parts[1].strip())


async def _advance(message: Message, bot: Bot, state: FSMContext, item: Pending) -> None:
    """Следующая нерешённая строка — или конец правки и сводка."""
    unresolved = item.unresolved()
    if unresolved:
        await message.answer(texts.fix_prompt(unresolved[0]))
        return
    await state.clear()
    await message.answer(texts.FIX_DONE)
    await render_summary(bot, item)
