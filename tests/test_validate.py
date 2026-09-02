"""Проблемные строки, дубли, потолок и применение правок из диалога."""

import pytest

from anki_deck_gen.domain import Fix, Problem
from anki_deck_gen.errors import TooManyRows
from anki_deck_gen.tables.parse import NO_SEPARATOR_MARK, parse_text
from anki_deck_gen.tables.validate import apply, validate
from tests.helpers.tables import make_row, make_table


def test_empty_question_and_answer_are_problems() -> None:
    table = make_table(make_row(2, "", "b"), make_row(3, "c", "  "), make_row(4, "e", "f"))
    result = validate(table, max_notes=100)
    assert [(p.row.number, p.problem) for p in result.problems] == [
        (2, Problem.EMPTY_QUESTION),
        (3, Problem.EMPTY_ANSWER),
    ]
    assert result.notes == 1
    assert not result.ok


def test_no_separator_marker_wins_over_empty_answer() -> None:
    table = parse_text("a — b\nno separator")
    result = validate(table, max_notes=100)
    assert result.problems[0].problem is Problem.NO_SEPARATOR


def test_duplicates_are_reported_in_first_seen_order_and_are_not_problems() -> None:
    table = make_table(
        make_row(2, "same", "1"),
        make_row(3, "other", "2"),
        make_row(4, "same", "3"),
        make_row(5, "other", "4"),
        make_row(6, "unique", "5"),
    )
    result = validate(table, max_notes=100)
    assert result.ok
    assert result.duplicates == ("same", "other")
    assert result.notes == 5


def test_too_many_rows_is_raised_against_the_note_count() -> None:
    table = make_table(*(make_row(i, f"q{i}", "a") for i in range(2, 13)))
    with pytest.raises(TooManyRows) as info:
        validate(table, max_notes=10)
    assert info.value.count == 11
    assert info.value.limit == 10


def test_apply_replaces_fixed_rows_and_drops_skipped_ones() -> None:
    table = parse_text("a — b\nbroken line\nc — \n\nd — e")
    broken, empty = (row.key for row in table.rows[1:3])
    fixed = apply(
        table,
        fixes={broken: Fix(question="broken", answer="line")},
        skips=frozenset({empty}),
    )
    rows = fixed.rows
    assert [(r.question, r.answer) for r in rows] == [("a", "b"), ("broken", "line"), ("d", "e")]
    assert NO_SEPARATOR_MARK not in rows[1].extra
    assert validate(fixed, max_notes=100).ok
