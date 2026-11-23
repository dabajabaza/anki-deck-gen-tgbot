"""Китайский тип: слоги пиньиня, цвета тонов, звук отдельно от иероглифов, две карточки."""

import unicodedata
from pathlib import Path

import pytest

from anki_deck_gen import notetypes
from anki_deck_gen.build.package import build_package
from anki_deck_gen.domain import AudioSide, BuildRequest, DeckSettings, Theme
from anki_deck_gen.notetypes.chinese import colour_hanzi, colour_pinyin, syllables
from tests.helpers.apkg import read_apkg
from tests.helpers.tables import make_row, make_table
from tests.test_build import FakeAudioCache

COLUMNS = frozenset({"Q", "A", "Pinyin"})


def tones(pinyin: str) -> list[tuple[str, int]]:
    pinyin = unicodedata.normalize("NFC", pinyin)  # позиции слогов — в форме NFC
    return [(pinyin[start:end], tone) for start, end, tone in syllables(pinyin)]


@pytest.mark.parametrize(
    ("pinyin", "expected"),
    [
        ("nǐ hǎo", [("nǐ", 3), ("hǎo", 3)]),
        ("māma", [("mā", 1), ("ma", 5)]),
        ("Zhōngguó", [("Zhōng", 1), ("guó", 2)]),
        # Кода не уходит к слогу, если за ней гласная.
        ("dàngāo", [("dàn", 4), ("gāo", 1)]),
        ("kěnéng", [("kě", 3), ("néng", 2)]),
        ("wǎnshang", [("wǎn", 3), ("shang", 5)]),
        ("nǚ'ér", [("nǚ", 3), ("ér", 2)]),
        ("Xī'ān", [("Xī", 1), ("ān", 1)]),
        ("yìdiǎnr", [("yì", 4), ("diǎnr", 3)]),
    ],
)
def test_pinyin_splits_into_syllables_with_their_tones(
    pinyin: str, expected: list[tuple[str, int]]
) -> None:
    assert tones(pinyin) == expected


def test_a_whole_phrase_keeps_spaces_and_punctuation_uncoloured() -> None:
    assert colour_pinyin("nǐ jiào shénme míngzi?") == (
        '<span class="tone3">nǐ</span> <span class="tone4">jiào</span> '
        '<span class="tone2">shén</span><span class="tone5">me</span> '
        '<span class="tone2">míng</span><span class="tone5">zi</span>?'
    )


def test_decomposed_tone_marks_are_read_too() -> None:
    """Пиньинь, набранный комбинирующими знаками (n + U+030C + i), — тот же пиньинь."""
    assert tones("nǐ") == [("nǐ", 3)]


def test_hanzi_take_the_tone_of_their_syllable_and_punctuation_stays() -> None:
    assert colour_hanzi("你叫什么名字？", "nǐ jiào shénme míngzi?") == (
        '<span class="tone3">你</span><span class="tone4">叫</span>'
        '<span class="tone2">什</span><span class="tone5">么</span>'
        '<span class="tone2">名</span><span class="tone5">字</span>？'
    )


def test_erhua_gives_er_its_own_neutral_colour() -> None:
    assert colour_hanzi("一点儿", "yìdiǎnr") == (
        '<span class="tone4">一</span><span class="tone3">点</span><span class="tone5">儿</span>'
    )


def test_hanzi_stay_plain_when_the_counts_disagree_or_pinyin_is_empty() -> None:
    assert colour_hanzi("你好", "nǐ") == "你好"
    assert colour_hanzi("你好", "") == "你好"


def test_html_in_a_field_is_left_alone() -> None:
    assert colour_pinyin("<b>nǐ</b>") == "<b>nǐ</b>"
    assert colour_hanzi('<img src="a.png">', "nǐ") == '<img src="a.png">'


def test_note_fields_keep_the_audio_out_of_the_hanzi_field() -> None:
    chinese = notetypes.get("chinese")
    row = make_row(2, "妈妈", "мама", extra={"Pinyin": "māma", "Example": "e", "Note": "n"})
    fields = dict(
        zip(
            chinese.fields(),
            chinese.note_fields(row, audio_q="[sound:q.mp3]", audio_a=""),
            strict=True,
        )
    )
    assert fields["Hanzi"] == "妈妈"
    assert fields["Audio"] == "[sound:q.mp3]"
    assert fields["Pinyin"] == '<span class="tone1">mā</span><span class="tone5">ma</span>'
    assert fields["Example"] == "e" and fields["Note"] == "n"


def test_reading_card_shows_only_plain_hanzi_and_listening_card_only_sound() -> None:
    reading, listening = notetypes.get("chinese").templates()
    assert reading["name"] == "Чтение" and listening["name"] == "На слух"
    # Звук и цвет тонов на лице «Чтения» подсказали бы ответ.
    assert "{{Hanzi}}" in reading["qfmt"]
    assert "Audio" not in reading["qfmt"] and "Coloured" not in reading["qfmt"]
    assert "{{Audio}}" in reading["afmt"]
    assert "{{Audio}}" in listening["qfmt"] and "Hanzi" not in listening["qfmt"]
    assert "{{Hanzi Coloured}}" in listening["afmt"]
    for card in (reading, listening):
        assert "{{Pinyin}}" in card["afmt"] and "{{Meaning}}" in card["afmt"]
        assert "Pinyin" not in card["qfmt"] and "Meaning" not in card["qfmt"]


def test_tone_colours_sit_on_top_of_the_chosen_theme_and_night_mode() -> None:
    chinese = notetypes.get("chinese")
    assert chinese.themed
    assert chinese.css(Theme.CARD) != chinese.css(Theme.BOOK)
    for theme in Theme:
        css = chinese.css(theme)
        for tone in range(1, 6):
            assert f".tone{tone} {{" in css
            assert f".nightMode .tone{tone} {{" in css


def build(tmp_path: Path, audio: AudioSide) -> tuple[Path, int]:
    table = make_table(
        make_row(2, "妈妈", "мама", extra={"Pinyin": "māma"}),
        make_row(
            3, "你叫什么名字？", "Как тебя зовут?", extra={"Pinyin": "nǐ jiào shénme míngzi?"}
        ),
        make_row(4, "好", "хорошо", extra={"Pinyin": ""}),
        columns=COLUMNS,
    )
    settings = DeckSettings(note_type_id="chinese", lang_q="zh", lang_a="ru", audio=audio)
    result = build_package(
        BuildRequest(table=table, settings=settings, deck_name="zh"),
        out_dir=tmp_path / "out",
        media_cache_dir=tmp_path / "media",
        audio_cache=FakeAudioCache(tmp_path / "media"),
    )
    return result.path, result.summary.cards


def test_with_audio_every_note_gets_both_cards(tmp_path: Path) -> None:
    path, summary_cards = build(tmp_path, AudioSide.QUESTION)
    contents = read_apkg(path)
    assert contents.notes == 3
    assert contents.cards == summary_cards == 6
    assert len(contents.media) == 3


def test_without_audio_there_is_no_listening_card_and_the_summary_says_so(tmp_path: Path) -> None:
    """Пустое лицо «На слух» Anki не заводит — и итог считает только то, что есть."""
    path, summary_cards = build(tmp_path, AudioSide.NONE)
    assert read_apkg(path).cards == summary_cards == 3
