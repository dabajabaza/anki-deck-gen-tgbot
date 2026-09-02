"""Строки бота: непустые, без разметки, с плейсхолдерами, которые кто-то подставляет."""

import string

from anki_deck_gen.bot import texts
from anki_deck_gen.domain import AudioSide, DeckSettings, Summary

# Каждому плейсхолдеру — хоть один вызывающий. Новый {name} без строки здесь
# означает, что либо текст, либо вызов написан с опечаткой.
KNOWN_PLACEHOLDERS = {
    "example",
    "url",
    "hours",
    "link",
    "user_id",
    "count",
    "ids",
    "rows",
    "username",
    "deck",
    "names",
    "number",
    "sheet",
    "reason",
    "question",
    "answer",
    "line",
    "needs",
    "label",
    "columns",
    "pair",
    "description",
    "lang",
    "position",
    "limit",
    "done",
    "total",
    "parts",
    "size",
    "detail",
    "minutes",
}


def _constants() -> dict[str, str]:
    return {
        name: value
        for name, value in vars(texts).items()
        if name.isupper() and isinstance(value, str)
    }


def test_every_string_is_non_empty() -> None:
    for name, value in _constants().items():
        assert value.strip(), name


def test_no_markup_sneaks_in() -> None:
    # Бот шлёт простой текст без parse_mode: «<b>» показался бы буквально.
    for name, value in _constants().items():
        assert "<" not in value and ">" not in value, name
        assert "**" not in value and "__" not in value, name


def test_placeholders_are_known() -> None:
    formatter = string.Formatter()
    for name, value in _constants().items():
        for _, field, _, _ in formatter.parse(value):
            if field:
                assert field in KNOWN_PLACEHOLDERS, f"{name}: {{{field}}}"


def test_plural_forms() -> None:
    assert texts.notes_word(1) == "1 запись"
    assert texts.notes_word(2) == "2 записи"
    assert texts.notes_word(5) == "5 записей"
    assert texts.notes_word(11) == "11 записей"
    assert texts.notes_word(21) == "21 запись"
    assert texts.cards_word(180) == "180 карточек"


def test_verdict_reads_well() -> None:
    summary = Summary(
        deck_name="At the appointment",
        subdecks=tuple(f"At the appointment::{i}" for i in range(9)),
        notes=90,
        cards=180,
        media_files=90,
        skipped=1,
        duplicates=1,
    )
    text = texts.verdict(summary)
    assert text.startswith("Колода «At the appointment»: 9 подколод, 90 записей, 180 карточек")
    assert "90 аудиофайлов" in text and "пропущено строк: 1" in text


def test_settings_description_names_the_voiced_side() -> None:
    both = DeckSettings(note_type_id="basic", lang_q="en", lang_a="ru", audio=AudioSide.BOTH)
    assert texts.settings_description(both) == "English → Русский, озвучены обе стороны"
    answer = DeckSettings(note_type_id="basic", lang_q="en", lang_a="ru", audio=AudioSide.ANSWER)
    assert texts.settings_description(answer) == "English → Русский, озвучен Русский"
