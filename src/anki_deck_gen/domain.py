"""Словарь, на котором говорит весь остальной код.

Намеренно без aiogram, genanki и gTTS: разбор таблиц, реестр типов записей и
сборка колоды описываются этими типами, поэтому их можно собрать и проверить без
чата и без Anki. Что означают слова — в CONTEXT.md.
"""

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path

# Канонические имена колонок Таблицы. Заголовок в файле может быть и русским
# (`Вопрос`/`Ответ`/`Колода`/`Метки`), tables/headers.py приводит его к этим.
COL_Q = "Q"
COL_A = "A"
COL_DECK = "Deck"
COL_TAGS = "Tags"


class AudioSide(StrEnum):
    """Какая сторона озвучена. Значения — коды для CLI и callback_data."""

    NONE = "none"
    QUESTION = "q"
    ANSWER = "a"
    BOTH = "both"

    @property
    def question(self) -> bool:
        return self in (AudioSide.QUESTION, AudioSide.BOTH)

    @property
    def answer(self) -> bool:
        return self in (AudioSide.ANSWER, AudioSide.BOTH)


# Адрес строки внутри Таблицы: имя листа (None у csv и текста) и номер строки,
# как его видит человек в редакторе (1-based, заголовок — строка 1).
RowKey = tuple[str | None, int]


@dataclass(frozen=True)
class Row:
    """Одна строка Таблицы, уже приведённая к каноническим колонкам."""

    number: int
    sheet: str | None
    question: str
    answer: str
    deck: str | None = None
    tags: tuple[str, ...] = ()
    # Прочие колонки по каноническому имени заголовка — для кастомных Типов записи
    # (вьетнамскому нужны Tips/Dialect/Note/Example).
    extra: Mapping[str, str] = field(default_factory=dict)

    @property
    def key(self) -> RowKey:
        return (self.sheet, self.number)


@dataclass(frozen=True)
class Sheet:
    """Лист Таблицы: у xlsx — вкладка, у csv и текста — единственный безымянный."""

    name: str | None
    columns: frozenset[str]  # канонические имена присутствующих колонок
    rows: tuple[Row, ...]


@dataclass(frozen=True)
class Table:
    """То, из чего делается колода. ``title`` — имя файла без расширения или
    заголовок Google-таблицы; None, если взять негде (вставленный текст)."""

    sheets: tuple[Sheet, ...]
    title: str | None = None

    @property
    def rows(self) -> tuple[Row, ...]:
        return tuple(row for sheet in self.sheets for row in sheet.rows)

    @property
    def columns(self) -> frozenset[str]:
        """Колонки, которые есть на КАЖДОМ листе: только на них может опираться Тип записи."""
        if not self.sheets:
            return frozenset()
        common = set(self.sheets[0].columns)
        for sheet in self.sheets[1:]:
            common &= sheet.columns
        return frozenset(common)

    @property
    def multi_sheet(self) -> bool:
        return len(self.sheets) > 1


class Problem(StrEnum):
    """Почему из строки нельзя сделать Запись."""

    EMPTY_QUESTION = "empty_question"
    EMPTY_ANSWER = "empty_answer"
    NO_SEPARATOR = "no_separator"  # только у вставленного текста


@dataclass(frozen=True)
class ProblemRow:
    row: Row
    problem: Problem


@dataclass(frozen=True)
class Validation:
    """Итог проверки Таблицы: что чинить и о чём предупредить."""

    problems: tuple[ProblemRow, ...]
    duplicates: tuple[str, ...]  # вопросы, встретившиеся больше одного раза
    notes: int  # сколько Записей выйдет, если проблемные строки убрать

    @property
    def ok(self) -> bool:
        return not self.problems


@dataclass(frozen=True)
class Fix:
    """Исправление Проблемной строки, присланное в диалоге."""

    question: str
    answer: str


@dataclass(frozen=True)
class DeckSettings:
    """Всё, что бот спрашивает перед сборкой: Тип записи, Языки, Озвучка."""

    note_type_id: str
    lang_q: str  # код языка вопроса для gTTS, напр. "en"
    lang_a: str  # код языка ответа, напр. "ru"
    audio: AudioSide


@dataclass(frozen=True)
class BuildRequest:
    """Заказ на сборку, полностью самодостаточный: воркеру больше ничего не нужно."""

    table: Table
    settings: DeckSettings
    deck_name: str
    fixes: Mapping[RowKey, Fix] = field(default_factory=dict)
    skips: frozenset[RowKey] = frozenset()
    # Каталог с картинками для `<img src>` в полях — только CLI.
    media_dir: Path | None = None


@dataclass(frozen=True)
class Summary:
    """Вердикт словами: что собрали."""

    deck_name: str
    subdecks: tuple[str, ...]  # полные имена подколод, в порядке появления
    notes: int
    cards: int
    media_files: int
    skipped: int  # Проблемных строк пропущено
    duplicates: int  # вопросов-дублей (предупреждение, не ошибка)


@dataclass(frozen=True)
class BuildResult:
    path: Path  # готовый .apkg
    summary: Summary


# Прогресс сборки для статус-сообщения: «озвучено 120/900». Вызывается из
# рабочего потока — получатель обязан сам перебросить вызов в event loop.
ProgressCallback = Callable[[int, int], None]
