"""Заголовок: строгий по составу, снисходительный к регистру, BOM и русскому."""

import pytest

from anki_deck_gen.errors import TableUnreadable
from anki_deck_gen.tables.headers import normalize_header, require_qa


@pytest.mark.parametrize(
    ("raw", "canonical"),
    [
        ("Q", "Q"),
        ("q", "Q"),
        ("Вопрос", "Q"),
        ("ВОПРОС", "Q"),
        ("  a ", "A"),
        ("Ответ", "A"),
        ("deck", "Deck"),
        ("Колода", "Deck"),
        ("Tags", "Tags"),
        ("метки", "Tags"),
    ],
)
def test_known_headers_normalize_to_canonical_names(raw: str, canonical: str) -> None:
    assert normalize_header(raw) == canonical


def test_a_bom_before_the_first_header_is_stripped() -> None:
    assert normalize_header("﻿Q") == "Q"


def test_unknown_headers_keep_their_name_for_custom_note_types() -> None:
    assert normalize_header(" Tips ") == "Tips"
    assert normalize_header("Dialect") == "Dialect"


def test_require_qa_passes_when_both_columns_present() -> None:
    require_qa(frozenset({"Q", "A", "Tips"}), sheet=None, first_row=["Q", "A", "Tips"])


def test_require_qa_names_the_sheet_and_echoes_the_first_row() -> None:
    with pytest.raises(TableUnreadable) as info:
        require_qa(frozenset({"Q"}), sheet="Examine", first_row=["Q", "Перевод"])
    assert "Лист «Examine»" in info.value.detail
    assert "Q | Перевод" in info.value.detail
    assert "Вопрос и Ответ" in info.value.detail


def test_require_qa_without_a_sheet_does_not_mention_one() -> None:
    with pytest.raises(TableUnreadable) as info:
        require_qa(frozenset(), sheet=None, first_row=["How are you", "Как дела"])
    assert "Лист" not in info.value.detail
    assert info.value.detail.startswith("Первая строка")
