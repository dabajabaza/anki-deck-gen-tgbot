"""Сборка тестовых таблиц: xlsx-книги в памяти и готовые объекты домена."""

import io
from collections.abc import Sequence

from openpyxl import Workbook

from anki_deck_gen.domain import Row, Sheet, Table


def workbook_bytes(
    sheets: dict[str, Sequence[Sequence[object]]], *, hidden: Sequence[str] = ()
) -> bytes:
    """Книга xlsx: имя листа → строки (первая — заголовок). Листы из `hidden` скрыты."""
    workbook = Workbook()
    default = workbook.active
    assert default is not None
    workbook.remove(default)
    for name, rows in sheets.items():
        worksheet = workbook.create_sheet(name)
        for row in rows:
            worksheet.append(list(row))
        if name in hidden:
            worksheet.sheet_state = "hidden"
    buffer = io.BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()


def make_row(
    number: int,
    question: str,
    answer: str,
    *,
    sheet: str | None = None,
    deck: str | None = None,
    tags: tuple[str, ...] = (),
    extra: dict[str, str] | None = None,
) -> Row:
    return Row(
        number=number,
        sheet=sheet,
        question=question,
        answer=answer,
        deck=deck,
        tags=tags,
        extra=extra or {},
    )


def make_table(
    *rows: Row, title: str | None = None, columns: frozenset[str] | None = None
) -> Table:
    """Одно-листовая таблица из готовых строк."""
    return Table(
        sheets=(Sheet(name=None, columns=columns or frozenset({"Q", "A"}), rows=tuple(rows)),),
        title=title,
    )
