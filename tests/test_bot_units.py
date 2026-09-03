"""Мелкие узлы бота: callback_data, Pending, ограниченное FSM-хранилище."""

from aiogram.fsm.storage.base import StorageKey

from anki_deck_gen.bot import callbacks
from anki_deck_gen.bot.pending import Pending, PendingStore
from anki_deck_gen.bot.storage import BoundedMemoryStorage
from anki_deck_gen.domain import (
    AudioSide,
    DeckSettings,
    Fix,
    Problem,
    ProblemRow,
    Theme,
    Validation,
)
from tests.helpers.factories import make_row, make_table

# ---------- callback_data ----------


def test_the_longest_callback_fits_telegram_limit() -> None:
    longest = DeckSettings(
        note_type_id="basic-reversed",
        lang_q="en",
        lang_a="ru",
        audio=AudioSide.BOTH,
        theme=Theme.BOOK,
    )
    assert len(callbacks.build(longest).encode()) <= callbacks.CALLBACK_DATA_LIMIT
    assert len(callbacks.build(longest).encode()) == 32


def test_build_roundtrip_keeps_the_theme() -> None:
    value = DeckSettings(
        note_type_id="vietnamese",
        lang_q="vi",
        lang_a="en",
        audio=AudioSide.QUESTION,
        theme=Theme.BOOK,
    )
    parsed = callbacks.parse(callbacks.build(value))
    assert parsed is not None and parsed.action == "t" and parsed.deck_settings() == value


def test_settings_step_carries_no_theme_and_defaults_to_card() -> None:
    value = DeckSettings(note_type_id="basic", lang_q="en", lang_a="ru", audio=AudioSide.NONE)
    parsed = callbacks.parse(callbacks.settings(value))
    assert parsed is not None and parsed.action == "s" and parsed.theme is None
    assert parsed.deck_settings() == value  # theme=Theme.CARD по умолчанию


def test_garbage_is_not_parsed() -> None:
    assert callbacks.parse("s:basic:en-ru:loud") is None
    assert callbacks.parse("t:basic:en-ru:both:neon") is None
    assert callbacks.parse("t:basic:en-ru:both") is None, "a build needs its theme"
    assert callbacks.parse("s:basic:en-ru:both:card") is None
    assert callbacks.parse("lp:basic") is None
    assert callbacks.parse("whatever") is None


# ---------- Pending ----------


def _pending() -> Pending:
    row_bad = make_row(3, "dog", "")
    return Pending(
        table=make_table(("a", "б")),
        validation=Validation(
            problems=(ProblemRow(row=row_bad, problem=Problem.EMPTY_ANSWER),),
            duplicates=(),
            notes=1,
        ),
        deck_name="x",
        chat_id=1,
        status_message_id=1,
    )


def test_pending_expires_and_touch_extends() -> None:
    store = PendingStore(ttl_s=0.05)
    store.put(1, _pending())
    assert store.get(1) is not None
    import time

    time.sleep(0.06)
    assert store.get(1) is None

    store = PendingStore(ttl_s=0.1)
    store.put(1, _pending())
    time.sleep(0.06)
    assert store.touch(1) is not None
    time.sleep(0.06)
    assert store.get(1) is not None, "touch must have extended the deadline"


def test_unresolved_respects_fixes_and_skips() -> None:
    item = _pending()
    assert len(item.unresolved()) == 1
    item.fixes[(None, 3)] = Fix("dog", "пёс")
    assert item.unresolved() == []
    assert item.notes == 2


# ---------- BoundedMemoryStorage ----------


def _key(user_id: int) -> StorageKey:
    return StorageKey(bot_id=1, chat_id=user_id, user_id=user_id)


async def test_storage_keeps_nothing_for_a_pure_reader() -> None:
    storage = BoundedMemoryStorage(max_keys=10)
    assert await storage.get_state(_key(1)) is None
    assert await storage.get_data(_key(1)) == {}
    assert len(storage) == 0


async def test_storage_evicts_the_oldest_beyond_the_cap() -> None:
    storage = BoundedMemoryStorage(max_keys=3)
    for i in range(1, 5):
        await storage.set_state(_key(i), "fixing")
    assert len(storage) == 3
    assert await storage.get_state(_key(1)) is None
    assert await storage.get_state(_key(4)) == "fixing"


async def test_clearing_state_and_data_drops_the_key() -> None:
    storage = BoundedMemoryStorage(max_keys=3)
    await storage.set_state(_key(1), "fixing")
    await storage.set_data(_key(1), {"a": 1})
    await storage.set_state(_key(1), None)
    assert len(storage) == 1, "data still there"
    await storage.set_data(_key(1), {})
    assert len(storage) == 0


async def test_reading_a_key_keeps_it_from_eviction() -> None:
    """Живой диалог (его читают) не вытесняется раньше давно забытого."""
    storage = BoundedMemoryStorage(max_keys=2)
    await storage.set_state(_key(1), "fixing")
    await storage.set_state(_key(2), "fixing")
    assert await storage.get_state(_key(1)) == "fixing"  # активность ключа 1
    await storage.set_state(_key(3), "fixing")
    assert await storage.get_state(_key(2)) is None, "the least recently USED key goes"
    assert await storage.get_state(_key(1)) == "fixing"


def test_is_stale_compares_chat_and_message() -> None:
    from datetime import UTC, datetime

    from aiogram.types import CallbackQuery, Chat, Message, User

    from anki_deck_gen.bot.views import is_stale

    item = _pending()  # chat_id=1, status_message_id=1

    def press(chat_id: int, message_id: int) -> CallbackQuery:
        message = Message(
            message_id=message_id,
            date=datetime.now(UTC),
            chat=Chat(id=chat_id, type="private"),
            text="status",
        )
        return CallbackQuery(
            id="c",
            from_user=User(id=1, is_bot=False, first_name="t"),
            chat_instance="i",
            message=message,
            data="nt:basic",
        )

    assert not is_stale(press(1, 1), item)
    assert is_stale(press(1, 2), item)
    assert is_stale(press(2, 1), item), "same message id in another chat is not ours"
