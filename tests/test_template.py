"""Шаблон для /template должен сам проходить наш разбор — иначе он врёт пользователю."""

from anki_deck_gen.tables.parse import parse_xlsx
from anki_deck_gen.tables.template import build_template_xlsx
from anki_deck_gen.tables.validate import validate


def test_template_has_two_sheets_with_canonical_headers_and_examples() -> None:
    table = parse_xlsx(build_template_xlsx(), title="template")
    assert [sheet.name for sheet in table.sheets] == ["1. Приветствие", "2. Прощание"]
    assert table.columns == frozenset({"Q", "A", "Tags"})
    assert all(len(sheet.rows) == 3 for sheet in table.sheets)
    assert validate(table, max_notes=100).ok
