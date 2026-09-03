"""Сборка .apkg из Таблицы и Настроек. Единственный модуль, знающий о genanki.

Синхронная функция: воркер бота запускает её в потоке (`asyncio.to_thread`), CLI —
напрямую. Поток нельзя отменить, только попросить: между фразами проверяется
флаг `abandoned`, и по нему сборка выходит через `BuildAbandoned` за одну фразу.
"""

import hashlib
import logging
import random
import re
import sys
import threading
from collections.abc import Iterable
from pathlib import Path

import genanki

from anki_deck_gen import notetypes
from anki_deck_gen.build.audio import AudioCache, sound_tag
from anki_deck_gen.build.slug import apkg_filename, sanitize
from anki_deck_gen.domain import (
    AudioSide,
    BuildRequest,
    BuildResult,
    ProgressCallback,
    Row,
    Summary,
    Table,
)
from anki_deck_gen.errors import BuildAbandoned, MissingColumns, TableUnreadable
from anki_deck_gen.tables.validate import apply, validate

_IMG_SRC = re.compile(r'<img\s+[^>]*src="([^"]+)"')
logger = logging.getLogger(__name__)


def build_package(
    request: BuildRequest,
    *,
    out_dir: Path,
    media_cache_dir: Path,
    on_progress: ProgressCallback | None = None,
    abandoned: threading.Event | None = None,
    audio_cache: AudioCache | None = None,
) -> BuildResult:
    """Собрать колоду и записать `.apkg` в `out_dir`.

    `audio_cache` подменяется в тестах, чтобы не ходить в Google.
    """
    table = apply(request.table, fixes=request.fixes, skips=request.skips)
    note_type = notetypes.get(request.settings.note_type_id)
    missing = note_type.required_columns - table.columns
    if missing:
        raise MissingColumns(note_type=note_type.label, missing=frozenset(missing))

    # Проблемные строки должны быть исправлены или пропущены ДО сборки: запись с
    # пустым полем Anki молча примет, а человек увидит пустую карточку через месяц.
    validation = validate(table, max_notes=sys.maxsize)
    if validation.problems:
        raise TableUnreadable(f"Осталось проблемных строк: {len(validation.problems)}.")
    rows = table.rows
    if not rows:
        raise TableUnreadable("В таблице нет ни одной записи.")

    cache = audio_cache or AudioCache(media_cache_dir)
    settings = request.settings
    model = genanki.Model(
        note_type.model_id,
        note_type.anki_name(),
        fields=[{"name": name} for name in note_type.fields()],
        templates=note_type.templates(),
        css=note_type.css(),
    )

    need_audio = settings.audio is not AudioSide.NONE
    total = len(rows) if need_audio else 0
    done = 0
    media: set[Path] = set()
    grouped: dict[str, list[genanki.Note]] = {}

    def check_abandoned() -> None:
        # Перед каждым запросом к Google, а не раз на строку: при озвучке обеих сторон
        # строка — два запроса, и воркер ждёт выхода потока ровно одну «фразу».
        if abandoned is not None and abandoned.is_set():
            raise BuildAbandoned()

    # Каталог — в начале, а не перед записью: воркер сносит scratch после того, как
    # брошенный поток вышел, и mkdir в конце воскресил бы уже удалённый каталог.
    out_dir.mkdir(parents=True, exist_ok=True)

    for row in rows:
        check_abandoned()
        audio_q = audio_a = ""
        if settings.audio.question:
            path = cache.ensure(row.question, settings.lang_q)
            media.add(path)
            audio_q = sound_tag(path)
        if settings.audio.answer:
            check_abandoned()
            path = cache.ensure(row.answer, settings.lang_a)
            media.add(path)
            audio_a = sound_tag(path)
        if need_audio:
            done += 1
            if on_progress is not None:
                on_progress(done, total)
        if request.media_dir is not None:
            media.update(_images_in(row, request.media_dir))

        note = genanki.Note(
            model=model,
            fields=note_type.note_fields(row, audio_q=audio_q, audio_a=audio_a),
            tags=[tag for tag in (sanitize(t) for t in row.tags) if tag],
        )
        grouped.setdefault(deck_name_for(request.deck_name, table, row), []).append(note)

    decks: list[genanki.Deck] = []
    for name, notes in grouped.items():
        # Тасуем внутри подколоды, как старый генератор: порядок в таблице —
        # тематический, а учить подряд «Do you have any …» ×7 скучно.
        random.shuffle(notes)
        deck = genanki.Deck(deck_id_for(name), name)
        for note in notes:
            deck.add_note(note)
        decks.append(deck)

    check_abandoned()
    path = out_dir / apkg_filename(request.deck_name)
    package = genanki.Package(decks, media_files=[str(p) for p in sorted(media)])
    package.write_to_file(str(path))

    summary = Summary(
        deck_name=request.deck_name,
        subdecks=tuple(grouped),
        notes=len(rows),
        cards=len(rows) * note_type.cards_per_note,
        media_files=len(media),
        skipped=len(request.skips),
        duplicates=len(validation.duplicates),
    )
    return BuildResult(path=path, summary=summary)


def deck_name_for(base: str, table: Table, row: Row) -> str:
    """Правило имён (круг 3, Q21): база, `::лист` при нескольких листах, `::Deck` при колонке."""
    parts = [base]
    if table.multi_sheet and row.sheet:
        parts.append(row.sheet)
    if row.deck:
        parts.append(row.deck)
    return "::".join(parts)


def deck_id_for(name: str) -> int:
    """Детерминированный id по имени: повторная сборка попадает в ту же колоду Anki.

    Старый генератор брал случайный id на каждый прогон — Anki сопоставляет
    колоды по имени, так что работало, но зачем полагаться на это.
    """
    digest = hashlib.sha1(name.encode("utf-8")).hexdigest()
    return int(digest[:8], 16) or 2  # 1 занят колодой Default


def _images_in(row: Row, media_dir: Path) -> Iterable[Path]:
    """Картинки `<img src="…">` из полей строки — только те, что лежат ВНУТРИ media_dir.

    Таблица — недоверенный ввод: `src="/etc/hostname"` или `src="../secret"` не должны
    уехать в .apkg, который человек потом кому-то отправит. Решение о допуске — по
    разрешённому пути (так отсекается и симлинк наружу), а отдаётся НЕразрешённый:
    genanki кладёт файл в архив под basename, и он обязан совпасть с тем, что написано
    в `src`, иначе симлинк `cat.png → photos/cat-hires.png` даст битую картинку.
    Отвергнутое — в лог: иначе не отличить от опечатки в имени.
    """
    root = media_dir.resolve()
    texts = [row.question, row.answer, *row.extra.values()]
    for text in texts:
        for filename in _IMG_SRC.findall(text):
            candidate = media_dir / filename
            resolved = candidate.resolve()
            if not resolved.is_relative_to(root):
                logger.info("image %r rejected: outside %s", filename, media_dir)
                continue
            if not candidate.is_file():
                logger.info("image %r not found in %s", filename, media_dir)
                continue
            yield candidate
