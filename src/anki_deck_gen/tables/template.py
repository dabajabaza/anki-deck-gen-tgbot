"""Шаблон таблицы для пользователя: заполнил — прислал обратно.

Генерируется кодом, а не лежит файлом в репозитории: бинарник в git нечем
ревьюить, а два листа с шестью строками проще держать здесь, рядом с правилами
разбора, которым шаблон обязан соответствовать.
"""

import io

from openpyxl import Workbook
from openpyxl.styles import Font

from anki_deck_gen.domain import COL_A, COL_Q, COL_TAGS

TEMPLATE_FILENAME = "anki-deck-template.xlsx"

_SHEETS: dict[str, list[tuple[str, str, str]]] = {
    "1. Приветствие": [
        ("How are you today?", "Как вы сегодня?", "greeting"),
        ("Nice to see you.", "Рада вас видеть.", "greeting"),
        ("Please have a seat.", "Пожалуйста, присаживайтесь.", ""),
    ],
    "2. Прощание": [
        ("See you in two weeks.", "Увидимся через две недели.", "farewell"),
        ("Take care.", "Берегите себя.", "farewell"),
        ("Call me if anything bothers you.", "Звоните, если что-то будет беспокоить.", ""),
    ],
}


def build_template_xlsx() -> bytes:
    """Книга с двумя листами-примерами (лист = подколода) и заголовком Q | A | Tags."""
    workbook = Workbook()
    first = True
    for sheet_name, rows in _SHEETS.items():
        if first:
            worksheet = workbook.active
            assert worksheet is not None
            worksheet.title = sheet_name
            first = False
        else:
            worksheet = workbook.create_sheet(sheet_name)
        worksheet.append([COL_Q, COL_A, COL_TAGS])
        for cell in worksheet[1]:
            cell.font = Font(bold=True)
        for row in rows:
            worksheet.append(list(row))
        worksheet.column_dimensions["A"].width = 40
        worksheet.column_dimensions["B"].width = 40
        worksheet.column_dimensions["C"].width = 16
    buffer = io.BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()
