"""Заголовок Таблицы: строгий, но двуязычный.

Пользователь решил (круг 2, Q13): заголовок обязателен, колонки минимум `Q` и `A`.
Русские синонимы — единственная уступка: преподаватель пишет «Вопрос»/«Ответ», а
не выучивает латинские буквы. Регистр не важен — сознательное смягчение
«строгого», записано в ARCHITECTURE. Прочие колонки сохраняют своё имя как есть:
на них опираются кастомные Типы записи (вьетнамскому нужны Tips/Dialect/Note/Example).
"""

from anki_deck_gen.domain import COL_A, COL_DECK, COL_Q, COL_TAGS
from anki_deck_gen.errors import TableUnreadable

ALIASES: dict[str, str] = {
    "q": COL_Q,
    "вопрос": COL_Q,
    "a": COL_A,
    "ответ": COL_A,
    "deck": COL_DECK,
    "колода": COL_DECK,
    "tags": COL_TAGS,
    "метки": COL_TAGS,
}

# Excel пишет UTF-8 с BOM, и без этой зачистки первая колонка называлась бы
# «﻿Q» — то есть не Q, и файл отвергался бы с невнятным текстом.
_BOM = "﻿"


def normalize_header(raw: str) -> str:
    """Каноническое имя колонки: `Вопрос` → `Q`, `Tips` → `Tips`, `  a ` → `A`."""
    cleaned = raw.replace(_BOM, "").strip()
    return ALIASES.get(cleaned.casefold(), cleaned)


def require_qa(columns: frozenset[str], *, sheet: str | None, first_row: list[str]) -> None:
    """Проверить, что среди колонок есть Q и A; иначе — понятный человеку отказ.

    В тексте отказа — то, что реально стояло в первой строке: пользователь сразу
    видит, что бот прочитал данные вместо заголовка (или заголовок с опечаткой).
    """
    if COL_Q in columns and COL_A in columns:
        return
    seen = " | ".join(cell for cell in first_row if cell) or "(пусто)"
    where = f"Лист «{sheet}», первая строка" if sheet else "Первая строка"
    raise TableUnreadable(f"{where}: {seen}. Нужны колонки Q и A (или Вопрос и Ответ).")
