"""Проверка Таблицы перед сборкой и применение правок из диалога.

Проблемная строка — та, из которой нельзя сделать Запись. Дубль вопроса — не
проблема: Anki сам пометит его при импорте, бот лишь предупреждает (круг 3, Q14).
"""

from collections.abc import Mapping
from dataclasses import replace

from anki_deck_gen.domain import Fix, Problem, ProblemRow, Row, RowKey, Table, Validation
from anki_deck_gen.errors import TooManyRows
from anki_deck_gen.tables.parse import NO_SEPARATOR_MARK


def validate(table: Table, *, max_notes: int) -> Validation:
    """Что чинить, о чём предупредить и сколько Записей выйдет."""
    problems: list[ProblemRow] = []
    seen: dict[str, int] = {}
    notes = 0
    for row in table.rows:
        problem = problem_of(row)
        if problem is not None:
            problems.append(ProblemRow(row=row, problem=problem))
            continue
        notes += 1
        seen[row.question] = seen.get(row.question, 0) + 1
    # dict хранит порядок вставки — дубли перечисляются в порядке первого появления.
    duplicates = tuple(question for question, count in seen.items() if count > 1)
    if notes > max_notes:
        raise TooManyRows(count=notes, limit=max_notes)
    return Validation(problems=tuple(problems), duplicates=duplicates, notes=notes)


def problem_of(row: Row) -> Problem | None:
    """Почему строка не годится, или None."""
    if row.extra.get(NO_SEPARATOR_MARK):
        return Problem.NO_SEPARATOR
    if not row.question.strip():
        return Problem.EMPTY_QUESTION
    if not row.answer.strip():
        return Problem.EMPTY_ANSWER
    return None


def apply(table: Table, *, fixes: Mapping[RowKey, Fix], skips: frozenset[RowKey]) -> Table:
    """Новая Таблица: исправленные строки заменены, пропущенные убраны, порядок сохранён."""
    sheets = []
    for sheet in table.sheets:
        rows: list[Row] = []
        for row in sheet.rows:
            if row.key in skips:
                continue
            fix = fixes.get(row.key)
            if fix is not None:
                row = replace(
                    row,
                    question=fix.question.strip(),
                    answer=fix.answer.strip(),
                    extra={k: v for k, v in row.extra.items() if k != NO_SEPARATOR_MARK},
                )
            rows.append(row)
        sheets.append(replace(sheet, rows=tuple(rows)))
    return replace(table, sheets=tuple(sheets))
