"""Черновик текстом: две кнопки, которыми он заканчивается.

Сами строки принимает `handlers/source.py` — здесь только «Готово» и «Отменить».
«Готово» ничего не пересобирает: Таблица уже лежит в Pending, пересчитанная на
каждом сообщении. Оно лишь закрывает приём строк (``draft = None``) и передаёт
человека в обычный поток — имя колоды, сводка, Тип записи.
"""

import logging

from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery

from anki_deck_gen.bot import callbacks, texts
from anki_deck_gen.bot.pending import PendingStore
from anki_deck_gen.bot.states import Rename
from anki_deck_gen.bot.views import edit_status, message_of, render_summary, resolve_pending
from anki_deck_gen.config import BotSettings

logger = logging.getLogger(__name__)

router = Router(name="draft")


@router.callback_query(F.data == callbacks.DRAFT_DONE)
async def finish(
    callback: CallbackQuery,
    bot: Bot,
    state: FSMContext,
    pending: PendingStore,
    settings: BotSettings,
) -> None:
    item = await resolve_pending(callback, pending, settings, state)
    if item is None:
        return
    if item.draft is None:
        # Кнопка с уже завершённого черновика: показать, где человек сейчас.
        await callback.answer()
        await render_summary(bot, item)
        return
    logger.info("draft from %s finished: %s note(s)", callback.from_user.id, item.validation.notes)
    item.draft = None
    await callback.answer()
    # Имя у текста взять негде — спрашиваем до сводки, как и у безымянного файла.
    await state.set_state(Rename.waiting)
    message = message_of(callback)
    if message is not None:
        await message.answer(texts.ASK_DECK_NAME)


@router.callback_query(F.data == callbacks.DRAFT_CANCEL)
async def cancel(
    callback: CallbackQuery,
    bot: Bot,
    state: FSMContext,
    pending: PendingStore,
    settings: BotSettings,
) -> None:
    item = await resolve_pending(callback, pending, settings, state)
    if item is None:
        return
    pending.pop(callback.from_user.id)
    await state.clear()
    await callback.answer()
    await edit_status(bot, item, texts.DRAFT_CANCELLED)
