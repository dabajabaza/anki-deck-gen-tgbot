"""Типы записей: стоковые шаблоны Anki байт в байт, реестр и совместимость с колонками."""

from anki_deck_gen import notetypes
from anki_deck_gen.domain import Theme
from anki_deck_gen.errors import UnknownNoteType
from anki_deck_gen.notetypes import stock, theme
from anki_deck_gen.notetypes.base import ANKI_NAME_SUFFIX
from tests.helpers.tables import make_row

OLD_MODEL_IDS = {2163323615, 2163323616, 2163323618, 1759261800, 1762620000}


def test_registry_holds_the_stock_types_then_ours_then_the_vietnamese_one() -> None:
    assert list(notetypes.REGISTRY) == [
        "basic",
        "basic-reversed",
        "basic-typing",
        "basic-typing-reversed",
        "vietnamese",
    ]


def test_unknown_id_raises() -> None:
    import pytest

    with pytest.raises(UnknownNoteType):
        notetypes.get("cloze")


def test_basic_templates_are_stock_plus_audio_only() -> None:
    (card,) = notetypes.get("basic").templates()
    assert card["name"] == stock.CARD_1
    assert stock.strip_audio(card["qfmt"]) == stock.STOCK_QFMT
    assert stock.strip_audio(card["afmt"]) == stock.STOCK_AFMT


def test_reversed_templates_are_stock_plus_audio_only() -> None:
    first, second = notetypes.get("basic-reversed").templates()
    assert stock.strip_audio(first["qfmt"]) == stock.STOCK_QFMT
    assert stock.strip_audio(first["afmt"]) == stock.STOCK_AFMT
    assert second["name"] == stock.CARD_2
    assert stock.strip_audio(second["qfmt"]) == stock.STOCK_REVERSE_QFMT
    assert stock.strip_audio(second["afmt"]) == stock.STOCK_REVERSE_AFMT


def test_typing_templates_are_stock_plus_audio_only() -> None:
    (card,) = notetypes.get("basic-typing").templates()
    assert stock.strip_audio(card["qfmt"]) == stock.STOCK_TYPE_QFMT
    assert stock.strip_audio(card["afmt"]) == stock.STOCK_TYPE_AFMT


def test_the_typing_question_side_never_plays_the_answer_audio() -> None:
    (card,) = notetypes.get("basic-typing").templates()
    assert stock.AUDIO_BACK not in card["qfmt"]
    assert stock.AUDIO_FRONT in card["qfmt"]


def test_no_typing_template_uses_frontside() -> None:
    """{{FrontSide}} на обороте выводит разбор набранного второй раз (см. stock.py)."""
    for note_type_id in ("basic-typing", "basic-typing-reversed", "vietnamese"):
        for card in notetypes.get(note_type_id).templates():
            assert "{{FrontSide}}" not in card["afmt"], f"{note_type_id}: {card['name']}"


def test_the_two_way_typing_type_asks_both_directions_and_hides_the_answer_audio() -> None:
    two_way = notetypes.get("basic-typing-reversed")
    assert two_way.cards_per_note == 2
    assert two_way.fields() == notetypes.get("basic").fields(), "колонки Таблицы те же"
    forward, reverse = two_way.templates()
    assert "{{type:Back}}" in forward["qfmt"] and "{{type:Front}}" in reverse["qfmt"]
    # Озвучка стороны, которую набирают, на вопросе не звучит — иначе это подсказка.
    assert stock.AUDIO_BACK not in forward["qfmt"]
    assert stock.AUDIO_FRONT not in reverse["qfmt"]
    assert stock.AUDIO_BACK in forward["afmt"] and stock.AUDIO_FRONT in reverse["afmt"]


def test_stock_types_take_their_css_from_the_chosen_theme() -> None:
    for note_type_id in ("basic", "basic-reversed", "basic-typing"):
        note_type = notetypes.get(note_type_id)
        assert note_type.themed
        assert note_type.css(Theme.CARD) == theme.css_for(Theme.CARD)
        assert note_type.css(Theme.BOOK) == theme.css_for(Theme.BOOK)
        assert note_type.css(Theme.CARD) != note_type.css(Theme.BOOK)


def test_every_theme_styles_night_mode_the_answer_rule_and_the_audio_button() -> None:
    """Классы и элементы, которые Anki гарантирует: .card на body, nightMode, hr#answer, replay."""
    for value in Theme:
        css = theme.css_for(value)
        assert ".card {" in css and ".card.nightMode {" in css
        assert "hr#answer" in css
        assert ".replay-button svg" in css and ".replay-button span svg" in css, "AnkiDroid"
        assert "input#typeans" in css and "!important" in css


def test_the_vietnamese_type_keeps_its_own_css_regardless_of_theme() -> None:
    vietnamese = notetypes.get("vietnamese")
    assert not vietnamese.themed
    assert vietnamese.css(Theme.CARD) == vietnamese.css(Theme.BOOK)
    assert "ayuthaya" in vietnamese.css(Theme.CARD)


def test_stock_fields_are_front_back_plus_two_audio_fields() -> None:
    assert notetypes.get("basic").fields() == ["Front", "Back", "Audio Front", "Audio Back"]


def test_model_ids_are_distinct_and_none_of_the_old_generator_ids() -> None:
    ids = [nt.model_id for nt in notetypes.REGISTRY.values()]
    assert len(set(ids)) == len(ids)
    assert not set(ids) & OLD_MODEL_IDS


def test_anki_name_carries_the_suffix_so_it_cannot_shadow_the_stock_type() -> None:
    assert notetypes.get("basic").anki_name() == "Простая" + ANKI_NAME_SUFFIX


def test_compatible_filters_by_required_columns_and_visibility() -> None:
    with_qa = notetypes.compatible(frozenset({"Q", "A"}))
    assert [nt.id for nt in with_qa] == list(notetypes.REGISTRY)
    assert notetypes.compatible(frozenset({"Q"})) == []


def test_note_fields_of_stock_types_place_audio_after_front_and_back() -> None:
    row = make_row(2, "How are you?", "Как дела?")
    fields = notetypes.get("basic-reversed").note_fields(row, audio_q="[sound:q.mp3]", audio_a="")
    assert fields == ["How are you?", "Как дела?", "[sound:q.mp3]", ""]


def test_vietnamese_colours_tones_and_reads_optional_columns() -> None:
    vietnamese = notetypes.get("vietnamese")
    row = make_row(
        2,
        "cảm ơn",
        "thank you",
        extra={"Dialect": "North", "Note": "n", "Example": "e", "Tips": "t"},
    )
    fields = vietnamese.note_fields(row, audio_q="[sound:x.mp3]", audio_a="")
    assert fields[0] == '<font color="green">cảm</font> <font color="gray">ơn</font>'
    assert fields[2] == '<font color="blue">North</font>'
    assert fields[3:6] == ["n", "e", "t"]
    assert fields[6] == "[sound:x.mp3]"
    assert vietnamese.optional_columns == frozenset({"Tips", "Dialect", "Note", "Example"})
    assert len(vietnamese.templates()) == 2
    assert "{{Audio Front}}" in vietnamese.templates()[0]["afmt"]
    assert "{{Audio}}" not in vietnamese.templates()[0]["afmt"]
