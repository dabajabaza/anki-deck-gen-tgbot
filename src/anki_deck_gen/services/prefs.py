"""Последние Настройки колоды пользователя — для кнопки «Как в прошлый раз».

Одна строка на человека. Пишется после постановки Задания в очередь, читается
при показе клавиатуры Языков: нет строки — нет кнопки. Сессию приносит
вызывающий и сам коммитит.
"""

from sqlalchemy.ext.asyncio import AsyncSession

from anki_deck_gen.db.models import UserPref
from anki_deck_gen.domain import AudioSide, DeckSettings, Theme
from anki_deck_gen.timeutils import now_ts


async def get_last(session: AsyncSession, user_id: int) -> DeckSettings | None:
    row = await session.get(UserPref, user_id)
    if row is None:
        return None
    return DeckSettings(
        note_type_id=row.note_type_id,
        lang_q=row.lang_q,
        lang_a=row.lang_a,
        audio=AudioSide(row.audio),
        theme=_theme(row.theme),
    )


def _theme(value: str) -> Theme:
    """Тема, снятая из репертуара (или битая), не должна ломать «Как в прошлый раз»."""
    try:
        return Theme(value)
    except ValueError:
        return Theme.CARD


async def save_last(session: AsyncSession, user_id: int, settings: DeckSettings) -> None:
    """Upsert: строка есть — обновить поля, нет — добавить."""
    row = await session.get(UserPref, user_id)
    if row is None:
        row = UserPref(user_id=user_id)
        session.add(row)
    row.note_type_id = settings.note_type_id
    row.lang_q = settings.lang_q
    row.lang_a = settings.lang_a
    row.audio = settings.audio.value
    row.theme = settings.theme.value
    row.updated_at = now_ts()
    await session.flush()
