"""Всё от допущенного пользователя, что не оказалось Таблицей и не команда.

Регистрируется последним, так что видит только то, чего никто не захотел.
Кнопки без обработчика тоже сюда: иначе «часики» на кнопке крутятся вечно.
"""

from aiogram import Router
from aiogram.types import CallbackQuery, Message

from anki_deck_gen.bot import texts

router = Router(name="fallback")


@router.message()
async def not_a_table(message: Message) -> None:
    await message.answer(texts.ERR_UNSUPPORTED)


@router.callback_query()
async def dead_button(callback: CallbackQuery) -> None:
    await callback.answer(texts.ERR_UNKNOWN_BUTTON, show_alert=True)
