"""Инлайн-клавиатуры. Весь выбор едет в callback_data (см. bot/callbacks.py)."""

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from anki_deck_gen.bot import callbacks, texts
from anki_deck_gen.domain import AudioSide, DeckSettings, Theme
from anki_deck_gen.notetypes.base import NoteType


def _rows(*rows: list[InlineKeyboardButton]) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[row for row in rows if row])


def problems() -> InlineKeyboardMarkup:
    return _rows(
        [InlineKeyboardButton(text=texts.BTN_FIX, callback_data=callbacks.PROBLEMS_FIX)],
        [InlineKeyboardButton(text=texts.BTN_SKIP, callback_data=callbacks.PROBLEMS_SKIP)],
        [
            InlineKeyboardButton(text=texts.BTN_CANCEL, callback_data=callbacks.PROBLEMS_CANCEL),
            InlineKeyboardButton(text=texts.BTN_RENAME, callback_data=callbacks.RENAME),
        ],
    )


def draft() -> InlineKeyboardMarkup:
    """Черновик текстом: закончить или выбросить. Висит на последнем сообщении бота."""
    return _rows(
        [InlineKeyboardButton(text=texts.BTN_DRAFT_DONE, callback_data=callbacks.DRAFT_DONE)],
        [InlineKeyboardButton(text=texts.BTN_DRAFT_CANCEL, callback_data=callbacks.DRAFT_CANCEL)],
    )


def note_types(types: list[NoteType]) -> InlineKeyboardMarkup:
    return _rows(
        *(
            [
                InlineKeyboardButton(
                    text=texts.note_type_button(nt.label),
                    callback_data=callbacks.note_type(nt.id),
                )
            ]
            for nt in types
        ),
        [InlineKeyboardButton(text=texts.BTN_RENAME, callback_data=callbacks.RENAME)],
    )


def languages(note_type_id: str, last: DeckSettings | None) -> InlineKeyboardMarkup:
    lang_q, lang_a = texts.DEFAULT_SETTINGS_LANGS
    default = DeckSettings(
        note_type_id=note_type_id, lang_q=lang_q, lang_a=lang_a, audio=AudioSide.QUESTION
    )
    none = DeckSettings(
        note_type_id=note_type_id, lang_q=lang_q, lang_a=lang_a, audio=AudioSide.NONE
    )
    last_row = (
        [
            InlineKeyboardButton(
                text=texts.BTN_LANG_LAST.format(description=texts.settings_description(last)),
                callback_data=callbacks.last_used(note_type_id),
            )
        ]
        if last is not None
        else []
    )
    return _rows(
        [
            InlineKeyboardButton(
                text=texts.BTN_LANG_DEFAULT, callback_data=callbacks.settings(default)
            )
        ],
        [InlineKeyboardButton(text=texts.BTN_LANG_NONE, callback_data=callbacks.settings(none))],
        last_row,
        [
            InlineKeyboardButton(
                text=texts.BTN_LANG_CONFIGURE, callback_data=callbacks.configure(note_type_id)
            )
        ],
    )


def language_pairs(note_type_id: str) -> InlineKeyboardMarkup:
    return _rows(
        *(
            [
                InlineKeyboardButton(
                    text=texts.pair_label(lang_q, lang_a),
                    callback_data=callbacks.language_pair(note_type_id, lang_q, lang_a),
                )
            ]
            for lang_q, lang_a in texts.LANGUAGE_PAIRS
        ),
        [
            InlineKeyboardButton(
                text=texts.BTN_BACK, callback_data=callbacks.note_type(note_type_id)
            )
        ],
    )


def audio_sides(note_type_id: str, lang_q: str, lang_a: str) -> InlineKeyboardMarkup:
    def option(audio: AudioSide, label: str) -> InlineKeyboardButton:
        value = DeckSettings(note_type_id=note_type_id, lang_q=lang_q, lang_a=lang_a, audio=audio)
        return InlineKeyboardButton(text=label, callback_data=callbacks.settings(value))

    return _rows(
        [option(AudioSide.QUESTION, texts.BTN_AUDIO_Q.format(lang=texts.lang_name(lang_q)))],
        [option(AudioSide.ANSWER, texts.BTN_AUDIO_A.format(lang=texts.lang_name(lang_a)))],
        [option(AudioSide.BOTH, texts.BTN_AUDIO_BOTH)],
        [option(AudioSide.NONE, texts.BTN_AUDIO_NONE)],
        [
            InlineKeyboardButton(
                text=texts.BTN_BACK, callback_data=callbacks.configure(note_type_id)
            )
        ],
    )


def themes(note_type_id: str, lang_q: str, lang_a: str, audio: AudioSide) -> InlineKeyboardMarkup:
    """Последний шаг: Оформление. Кнопка несёт полный набор Настроек."""

    def option(theme: Theme) -> InlineKeyboardButton:
        value = DeckSettings(
            note_type_id=note_type_id, lang_q=lang_q, lang_a=lang_a, audio=audio, theme=theme
        )
        return InlineKeyboardButton(
            text=texts.theme_button(theme), callback_data=callbacks.build(value)
        )

    return _rows(
        *([option(theme)] for theme in Theme),
        [
            InlineKeyboardButton(
                text=texts.BTN_BACK,
                callback_data=callbacks.language_pair(note_type_id, lang_q, lang_a),
            )
        ],
    )
