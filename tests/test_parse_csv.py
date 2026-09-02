"""csv: BOM от Excel, `;` русской локали, кавычки — и реальные колоды из local/, если лежат."""

from pathlib import Path

import pytest

from anki_deck_gen.errors import TableUnreadable
from anki_deck_gen.tables.parse import parse_csv

LOCAL = Path(__file__).resolve().parents[1] / "local"


def test_plain_comma_csv() -> None:
    table = parse_csv(b"Q,A,Tags\nHow are you?,\xd0\x9a\xd0\xb0\xd0\xba?,greeting\n")
    (row,) = table.rows
    assert row.question == "How are you?"
    assert row.answer == "Как?"
    assert row.tags == ("greeting",)
    assert row.number == 2
    assert table.sheets[0].name is None


def test_a_bom_from_excel_does_not_break_the_header() -> None:
    table = parse_csv("﻿Q,A\na,b\n".encode())
    assert table.columns == frozenset({"Q", "A"})


def test_semicolon_delimiter_is_sniffed() -> None:
    table = parse_csv("Вопрос;Ответ\nHow are you;Как дела\nBye;Пока\n".encode())
    assert [row.answer for row in table.rows] == ["Как дела", "Пока"]


def test_quoted_fields_with_commas_stay_whole() -> None:
    table = parse_csv(b'Q,A\ndifferent,"other, various"\n')
    assert table.rows[0].answer == "other, various"


def test_missing_header_is_reported_with_what_was_seen() -> None:
    with pytest.raises(TableUnreadable) as info:
        parse_csv(b"How are you,Kak dela\nBye,Poka\n")
    assert "How are you | Kak dela" in info.value.detail


def test_non_utf8_bytes_are_reported_as_encoding_problem() -> None:
    with pytest.raises(TableUnreadable) as info:
        parse_csv("Q,A\nпривет,hi\n".encode("cp1251"))
    assert "UTF-8" in info.value.detail


def test_empty_file_is_unreadable() -> None:
    with pytest.raises(TableUnreadable):
        parse_csv(b"")


def test_elena_fixture_has_ninety_rows_in_nine_decks() -> None:
    path = LOCAL / "elena_starter_at_the_appointment.csv"
    if not path.exists():
        pytest.skip("local fixture not present")
    table = parse_csv(path.read_bytes(), title=path.stem)
    assert len(table.rows) == 90
    assert len({row.deck for row in table.rows}) == 9
    assert table.title == "elena_starter_at_the_appointment"


def test_tus_fixture_with_quoted_html_cells_parses() -> None:
    path = LOCAL / "tus_kontrolnye_voprosy.csv"
    if not path.exists():
        pytest.skip("local fixture not present")
    table = parse_csv(path.read_bytes())
    # wc -l показывает 353 строки, но ячейки в кавычках многострочные: записей 122.
    assert len(table.rows) == 122
    assert table.rows[0].question.startswith("<b>1.</b>")
    assert "тус" in table.rows[0].tags
