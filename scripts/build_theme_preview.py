"""Собрать `themes/preview.html` — как выглядят Карточки в каждом Оформлении.

Страница нужна, чтобы выбрать тему, не собирая колоду и не открывая Anki: четыре
состояния Карточки (лицо и оборот у «Простой» и у «Простой (с вводом ответа)»)
в каждой теме, рядом — стоковый стиль Anki для сравнения, плюс переключатель
ночного режима.

Шаблоны и CSS берутся из пакета, а не переписываются здесь: тема, добавленная в
`notetypes/assets/css`, появляется на странице сама. Разметка самой страницы —
`scripts/preview/page.html.j2` (Jinja2), её стиль и скрипт лежат там же файлами:
внутри .py их не подсвечивал редактор и правились они вслепую.

Каждая ячейка — iframe со своим документом: у тем есть правила для `body.card`,
и в одном документе они переопределяли бы друг друга. Экранирование делает Jinja
(`autoescape`), поэтому документ ячейки кладётся в `srcdoc` как есть.

Запуск: `uv run python scripts/build_theme_preview.py` (страница пересобирается
на месте). `tests/test_theme_preview.py` следит, что в репозитории лежит именно
то, что собирается сейчас.
"""

import argparse
from dataclasses import dataclass, field
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined

from anki_deck_gen import notetypes
from anki_deck_gen.bot import texts
from anki_deck_gen.domain import Theme
from anki_deck_gen.notetypes import stock, theme

REPO = Path(__file__).resolve().parents[1]
PARTS = Path(__file__).resolve().parent / "preview"
DEFAULT_OUTPUT = REPO / "themes" / "preview.html"

QUESTION = "Could you describe your symptoms?"
ANSWER = "Не могли бы вы описать свои симптомы?"

# Какие Карточки показываем: тип записи, номер карточки, сторона и подписи строки.
CARDS = [
    ("basic", 1, "q", "Простая, лицо", "вопрос с озвучкой"),
    ("basic", 1, "a", "Простая, оборот", "ответ с озвучкой"),
    ("basic-typing", 1, "q", "С вводом ответа, лицо", "поле, куда набирают ответ"),
    ("basic-typing", 1, "a", "С вводом ответа, оборот", "Anki подсветил ошибку"),
]

THEME_NOTES = {
    Theme.CARD: "Светлая карточка с тенью на серо-голубом фоне.",
    Theme.BOOK: "Слоновая кость, антиква, двойная линейка.",
}
STOCK_NOTE = "Arial 20, чёрное на белом. Так выглядит колода без темы."


def part(name: str) -> str:
    """Кусок страницы из scripts/preview/ — без завершающего перевода строки."""
    return (PARTS / name).read_text(encoding="utf-8").rstrip("\n")


@dataclass(frozen=True)
class Column:
    """Колонка страницы: одно Оформление (или стоковый Anki для сравнения)."""

    name: str
    note: str
    css: str
    chip: str = ""  # пометка на шапке; у наших тем её нет


@dataclass(frozen=True)
class Cell:
    title: str
    document: str


@dataclass(frozen=True)
class Row:
    """Строка страницы: одно состояние Карточки во всех колонках."""

    name: str
    note: str
    cells: list[Cell] = field(default_factory=list)


def fill(template: str, *, front_side: str = "", typed: str = "") -> str:
    """Подставить в шаблон Anki содержимое полей — как это делает сам Anki."""
    play = part("play-button.html")
    return (
        template.replace("{{FrontSide}}", front_side)
        .replace(stock.AUDIO_FRONT, play)
        .replace(stock.AUDIO_BACK, play)
        .replace("{{type:Back}}", typed)
        .replace("{{Front}}", QUESTION)
        .replace("{{Back}}", ANSWER)
    )


def card_html(note_type_id: str, ordinal: int, side: str) -> str:
    """Готовый HTML одной стороны Карточки выбранного Типа записи."""
    template = notetypes.get(note_type_id).templates()[ordinal - 1]
    question = fill(template["qfmt"], typed=part("type-input.html"))
    if side == "q":
        return question
    return fill(template["afmt"], front_side=question, typed=part("type-comparison.html"))


def document(css: str, body: str) -> str:
    """Документ одной ячейки: то, что Anki кладёт под карточку, плюс CSS темы."""
    return (
        '<!doctype html><html><head><meta charset="utf-8">'
        f"<style>{part('anki-base.css')}\n{css}</style></head>"
        f'<body class="card card1">{body}</body></html>'
    )


def columns() -> list[Column]:
    """Колонки страницы. Первая — стоковый Anki, дальше наши темы по порядку."""
    stock_column = Column(
        name="Стоковый Anki", note=STOCK_NOTE, css=part("anki-stock.css"), chip="для сравнения"
    )
    return [stock_column] + [
        Column(name=texts.theme_name(value), note=THEME_NOTES[value], css=theme.css_for(value))
        for value in Theme
    ]


def rows(cols: list[Column]) -> list[Row]:
    result = []
    for note_type_id, ordinal, side, name, note in CARDS:
        body = card_html(note_type_id, ordinal, side)
        result.append(
            Row(
                name=name,
                note=note,
                cells=[
                    Cell(title=f"{column.name}: {name}", document=document(column.css, body))
                    for column in cols
                ],
            )
        )
    return result


def render() -> str:
    """Собрать страницу целиком. Детерминированно: тот же код — тот же файл."""
    cols = columns()
    environment = Environment(
        loader=FileSystemLoader(PARTS), autoescape=True, undefined=StrictUndefined
    )
    page = environment.get_template("page.html.j2").render(
        columns=cols, rows=rows(cols), page_css=part("page.css"), page_js=part("page.js")
    )
    return page if page.endswith("\n") else page + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help="куда положить страницу; по умолчанию themes/preview.html в репозитории",
    )
    args = parser.parse_args(argv)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(render(), encoding="utf-8")
    print(f"Готово: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
