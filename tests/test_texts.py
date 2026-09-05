"""Строки бота: непустые, без разметки (кроме HELP), плейсхолдеры кто-то подставляет."""

import re
import string

from anki_deck_gen.bot import texts
from anki_deck_gen.domain import AudioSide, DeckSettings, Summary, Theme

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
    "name",
    "options",
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


# Единственные тексты с HTML: идут с parse_mode=HTML из handlers/start.py (A11).
# Тексты с разметкой: справка и экраны Настроек. Их шлют с parse_mode=HTML
# (A11); всё, что в них подставляется, экранируется вызывающим helper'ом.
HTML_TEXTS = {
    "HELP",
    "HELP_EXAMPLE",
    "CHOOSE_LANGUAGES",
    "CHOOSE_PAIR",
    "CHOOSE_AUDIO",
    "CHOOSE_THEME",
}
_ALLOWED_TAGS = re.compile(r"</?b>|<a href=\"[^\"<>]*\">|</a>")


def test_no_markup_sneaks_in() -> None:
    # Бот шлёт простой текст без parse_mode: «<b>» показался бы буквально.
    for name, value in _constants().items():
        if name in HTML_TEXTS:
            continue
        assert "<" not in value and ">" not in value, name
        assert "**" not in value and "__" not in value, name


def test_the_list_of_marked_up_texts_matches_reality() -> None:
    """Разметка в новом тексте — решение, а не случайность: объявите его здесь."""
    with_tags = {name for name, value in _constants().items() if "<" in value or ">" in value}
    assert with_tags == HTML_TEXTS


def test_marked_up_texts_use_only_bold_and_links_and_close_them() -> None:
    for name in HTML_TEXTS:
        value = getattr(texts, name)
        stripped = _ALLOWED_TAGS.sub("", value)
        assert "<" not in stripped and ">" not in stripped and "&" not in stripped, name
        assert value.count("<b>") == value.count("</b>"), name
        assert value.count("<a href") == value.count("</a>"), name


def test_settings_screens_escape_what_they_interpolate() -> None:
    """Подписи типов сегодня безобидны, но экранирование не должно зависеть от этого."""
    assert "&lt;b&gt;" in texts.choose_pair("<b>злой тип</b>")
    assert "&lt;" in texts.choose_audio("<", "English → Русский")
    assert "&amp;" in texts.choose_theme("A & B", "English → Русский, озвучен English")
    screen = texts.choose_theme("Простая", "English → Русский")
    assert "<b>Оформление карточек:</b>" in screen
    assert "▫️ Карточка — светлая карточка на сером фоне" in screen


def test_help_message_escapes_the_example_url() -> None:
    url = 'https://example.com/?a=1&b="x"'
    message = texts.help_message(url)
    assert 'href="https://example.com/?a=1&amp;b=&quot;x&quot;"' in message
    assert "▫️ /template" in message
    assert "Пример готовой таблицы" not in texts.help_message(None)


def test_placeholders_are_known() -> None:
    formatter = string.Formatter()
    for name, value in _constants().items():
        for _, field, _, _ in formatter.parse(value):
            if field:
                assert field in KNOWN_PLACEHOLDERS, f"{name}: {{{field}}}"


def _button_width(label: str) -> float:
    """Грубая мера ширины подписи: кириллица заметно шире латиницы.

    Telegram режет подпись кнопки по ширине экрана и без многоточия. Точной
    границы у нас нет, порог откалиброван по двум замерам на телефоне 6":
    «English → Русский, озвучен English» помещается, «Простая (с обратной
    карточкой)» — уже нет.
    """
    cyrillic = sum(1 for char in label if "а" <= char.lower() <= "я" or char.lower() == "ё")
    return len(label) + 0.6 * cyrillic


def test_button_labels_fit_a_phone_screen() -> None:
    labels = {
        name: value
        for name, value in _constants().items()
        if name.startswith("BTN_") and "{" not in value
    }
    assert labels, "подписи кнопок разъехались по другим именам"
    for name, value in labels.items():
        assert _button_width(value) <= 44, f"{name}: {value}"
    # Единственная подпись с подстановкой: коды языков, самый длинный — три буквы.
    longest = DeckSettings(note_type_id="basic", lang_q="vie", lang_a="rus", audio=AudioSide.BOTH)
    assert _button_width(texts.last_button(longest)) <= 44, texts.last_button(longest)


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


def test_settings_description_names_the_voiced_side_and_the_theme() -> None:
    both = DeckSettings(note_type_id="basic", lang_q="en", lang_a="ru", audio=AudioSide.BOTH)
    assert texts.audio_description(both) == "English → Русский, озвучены обе стороны"
    assert texts.settings_description(both) == "English → Русский, озвучены обе стороны · Карточка"
    answer = DeckSettings(
        note_type_id="basic", lang_q="en", lang_a="ru", audio=AudioSide.ANSWER, theme=Theme.BOOK
    )
    assert texts.settings_description(answer) == "English → Русский, озвучен Русский · Учебник"
