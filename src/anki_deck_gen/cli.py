"""CLI: та же сборка, что у бота, тем же словарём — без Telegram и без токена.

    anki-deck-gen --source table.xlsx --note-type basic-reversed --lang-pair en,ru \
                  --audio-for q --deck-name "At the appointment"

Проблемные строки здесь не чинятся в диалоге — печатаются с номерами, и человек
правит файл. Картиночные колоды (`<img src>` + `--media-dir`) — только отсюда.
"""

import argparse
import asyncio
import logging
import sys
from pathlib import Path

from anki_deck_gen import notetypes
from anki_deck_gen.build.package import build_package
from anki_deck_gen.config import BuildSettings
from anki_deck_gen.domain import (
    AudioSide,
    BuildRequest,
    DeckSettings,
    Problem,
    ProblemRow,
    Summary,
    Table,
    Theme,
)
from anki_deck_gen.errors import (
    AnkiDeckGenError,
    MissingColumns,
    SheetNotShared,
    SheetUnreachable,
    TableUnreadable,
    TooManyRows,
    TtsUnavailable,
    UnknownNoteType,
)
from anki_deck_gen.tables.parse import parse_csv, parse_text, parse_xlsx
from anki_deck_gen.tables.sources import extract_sheets_url, fetch_google_sheet, read_file
from anki_deck_gen.tables.validate import validate

logger = logging.getLogger("anki_deck_gen.cli")

_PROBLEM_TEXT = {
    Problem.EMPTY_QUESTION: "пустой вопрос",
    Problem.EMPTY_ANSWER: "пустой ответ",
    Problem.NO_SEPARATOR: "нет разделителя « / » между вопросом и ответом",
}


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    settings = BuildSettings()
    args = _parser(settings).parse_args(argv)

    try:
        table = _load(args.source)
        deck_name = args.deck_name or table.title or "Колода"
        validation = validate(table, max_notes=args.max_notes)
        if validation.problems:
            print("Таблица не годится для сборки, исправьте строки:", file=sys.stderr)
            for problem in validation.problems:
                print(f"  {describe_problem(problem)}", file=sys.stderr)
            return 1
        for question in validation.duplicates:
            print(f"предупреждение: вопрос встречается дважды — «{question}»", file=sys.stderr)

        lang_q, lang_a = _lang_pair(args.lang_pair)
        request = BuildRequest(
            table=table,
            settings=DeckSettings(
                note_type_id=args.note_type,
                lang_q=lang_q,
                lang_a=lang_a,
                audio=AudioSide(args.audio_for),
                theme=Theme(args.theme),
            ),
            deck_name=deck_name,
            media_dir=Path(args.media_dir) if args.media_dir else None,
        )
        result = build_package(
            request,
            out_dir=Path(args.output_dir),
            media_cache_dir=settings.media_cache_dir,
            on_progress=_print_progress,
        )
    except AnkiDeckGenError as exc:
        print(describe_error(exc), file=sys.stderr)
        return 1
    except FileNotFoundError as exc:
        print(f"Файл не найден: {exc.filename}", file=sys.stderr)
        return 1

    print(f"Готово: {result.path}")
    print(describe_summary(result.summary))
    return 0


def describe_problem(problem: ProblemRow) -> str:
    where = f"строка {problem.row.number}"
    if problem.row.sheet:
        where += f" (лист «{problem.row.sheet}»)"
    return f"{where}: {_PROBLEM_TEXT[problem.problem]}"


def describe_error(exc: AnkiDeckGenError) -> str:
    match exc:
        case TableUnreadable():
            return f"Не удалось прочитать таблицу. {exc.detail}"
        case SheetNotShared():
            return (
                "Google-таблица закрыта. Откройте доступ: «Настройки доступа» → "
                "«Все, у кого есть ссылка», и повторите."
            )
        case SheetUnreachable():
            return f"Google не отвечает: {exc}. Повторите позже."
        case TooManyRows():
            return f"Слишком много записей: {exc.count}, потолок {exc.limit}."
        case MissingColumns():
            return (
                f"Типу записи «{exc.note_type}» не хватает колонок: "
                f"{', '.join(sorted(exc.missing))}."
            )
        case TtsUnavailable():
            return f"Озвучка недоступна: {exc.detail}. Колода без озвучки не собрана."
        case UnknownNoteType():
            return f"Неизвестный тип записи: {exc}."
        case _:
            return f"Ошибка: {exc}"


def describe_summary(summary: Summary) -> str:
    line = (
        f"Колода «{summary.deck_name}»: подколод {len(summary.subdecks)}, "
        f"записей {summary.notes}, карточек {summary.cards}, медиафайлов {summary.media_files}"
    )
    if summary.duplicates:
        line += f", дублей вопросов {summary.duplicates}"
    return line


def _parser(settings: BuildSettings) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="anki-deck-gen",
        description="Собрать колоду Anki (.apkg) из таблицы: xlsx, csv, текст или Google Sheets.",
    )
    parser.add_argument(
        "--source",
        required=True,
        help="путь к .xlsx/.csv/.txt, ссылка на Google Sheets или «-» (текст со stdin)",
    )
    parser.add_argument(
        "--note-type",
        default="basic",
        choices=sorted(notetypes.REGISTRY),
        help="тип записи Anki: "
        + "; ".join(f"{k} — {v.label}" for k, v in notetypes.REGISTRY.items()),
    )
    parser.add_argument("--lang-pair", default="en,ru", help="язык вопроса,язык ответа (gTTS)")
    parser.add_argument(
        "--audio-for",
        default=AudioSide.NONE.value,
        choices=[side.value for side in AudioSide],
        help="что озвучить: none, q (вопрос), a (ответ), both",
    )
    parser.add_argument(
        "--theme",
        default=Theme.CARD.value,
        choices=[theme.value for theme in Theme],
        help="оформление карточек: card — «Карточка», book — «Учебник»",
    )
    parser.add_argument("--deck-name", default=None, help="имя колоды; по умолчанию — имя файла")
    parser.add_argument("--output-dir", default="out", help="куда положить .apkg")
    parser.add_argument("--media-dir", default=None, help="каталог картинок для <img src> в полях")
    parser.add_argument(
        "--max-notes",
        type=int,
        default=settings.max_notes,
        help=f"потолок записей (по умолчанию {settings.max_notes})",
    )
    return parser


def _load(source: str) -> Table:
    if source == "-":
        return parse_text(sys.stdin.read())
    sheets_url = extract_sheets_url(source)
    if sheets_url is not None:
        data, title = asyncio.run(fetch_google_sheet(sheets_url))
        return parse_xlsx(data, title=title)
    path = Path(source)
    data, stem = read_file(path)
    suffix = path.suffix.lower()
    if suffix == ".xlsx":
        return parse_xlsx(data, title=stem)
    if suffix == ".csv":
        return parse_csv(data, title=stem)
    return parse_text(data.decode("utf-8-sig"))


def _lang_pair(value: str) -> tuple[str, str]:
    parts = [part.strip() for part in value.split(",")]
    if len(parts) != 2 or not all(parts):
        raise TableUnreadable(
            f"--lang-pair ожидает два кода через запятую, например en,ru; получено {value!r}"
        )
    return parts[0], parts[1]


def _print_progress(done: int, total: int) -> None:
    print(f"\rозвучено {done}/{total}", end="" if done < total else "\n", file=sys.stderr)


if __name__ == "__main__":
    raise SystemExit(main())
