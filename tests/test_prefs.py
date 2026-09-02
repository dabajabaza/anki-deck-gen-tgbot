"""«Как в прошлый раз»: последние Настройки колоды на пользователя."""

from sqlalchemy.ext.asyncio import AsyncSession

from anki_deck_gen.domain import AudioSide, DeckSettings
from anki_deck_gen.services import prefs

USER = 42


async def test_unknown_user_has_no_prefs(session: AsyncSession) -> None:
    assert await prefs.get_last(session, USER) is None


async def test_saved_settings_round_trip(session: AsyncSession) -> None:
    settings = DeckSettings(
        note_type_id="basic-reversed", lang_q="en", lang_a="ru", audio=AudioSide.QUESTION
    )
    await prefs.save_last(session, USER, settings)
    await session.commit()

    assert await prefs.get_last(session, USER) == settings


async def test_saving_again_overwrites_not_duplicates(session: AsyncSession) -> None:
    first = DeckSettings(note_type_id="basic", lang_q="en", lang_a="ru", audio=AudioSide.NONE)
    second = DeckSettings(note_type_id="vietnamese", lang_q="vi", lang_a="en", audio=AudioSide.BOTH)
    await prefs.save_last(session, USER, first)
    await prefs.save_last(session, USER, second)
    await session.commit()

    assert await prefs.get_last(session, USER) == second


async def test_prefs_are_per_user(session: AsyncSession) -> None:
    mine = DeckSettings(note_type_id="basic", lang_q="en", lang_a="ru", audio=AudioSide.ANSWER)
    await prefs.save_last(session, USER, mine)
    await session.commit()

    assert await prefs.get_last(session, USER + 1) is None
