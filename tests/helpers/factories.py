"""Сборка объектов для тестов теми же типами, что у прода."""

from pathlib import Path
from typing import Any

from anki_deck_gen.config import BotSettings
from anki_deck_gen.domain import (
    COL_A,
    COL_DECK,
    COL_Q,
    COL_TAGS,
    AudioSide,
    BuildResult,
    DeckSettings,
    Row,
    Sheet,
    Summary,
    Table,
)

# Похож на настоящий токен, чтобы валидация aiogram прошла; занесён в allowlist
# .gitleaks.toml, чтобы сканер секретов на него не спотыкался.
FAKE_BOT_TOKEN = "123456:" + "A" * 35

ADMIN_ID = 1
SECOND_ADMIN_ID = 2
GUEST_ID = 555
STRANGER_ID = 999
TEST_ADMIN_IDS = frozenset({ADMIN_ID, SECOND_ADMIN_ID})


def build_settings(tmp_path: Path, **overrides: Any) -> BotSettings:
    work = tmp_path / "work"
    work.mkdir(parents=True, exist_ok=True)
    values: dict[str, Any] = {
        "bot_token": FAKE_BOT_TOKEN,
        "admin_ids_raw": ",".join(str(i) for i in sorted(TEST_ADMIN_IDS)),
        "work_dir": work,
        "database_url": f"sqlite+aiosqlite:///{tmp_path / 'unused.sqlite'}",
        "queue_limit": 5,
        "job_timeout_s": 900,
        "max_file_mb": 5,
        "max_notes": 1000,
        "pending_ttl_s": 1800,
    }
    values.update(overrides)
    return BotSettings(**values, _env_file=None)


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


def make_sheet(
    name: str | None,
    rows: list[Row],
    *,
    columns: frozenset[str] | None = None,
) -> Sheet:
    if columns is None:
        columns = frozenset({COL_Q, COL_A})
        if any(r.deck is not None for r in rows):
            columns |= {COL_DECK}
        if any(r.tags for r in rows):
            columns |= {COL_TAGS}
    return Sheet(name=name, columns=columns, rows=tuple(rows))


def make_table(*pairs: tuple[str, str], title: str | None = "Тест") -> Table:
    """Одна безымянная вкладка с парами вопрос/ответ; строки нумеруются со 2-й."""
    rows = [make_row(i, q, a) for i, (q, a) in enumerate(pairs, start=2)]
    return Table(sheets=(make_sheet(None, rows),), title=title)


def make_settings(
    note_type_id: str = "basic",
    lang_q: str = "en",
    lang_a: str = "ru",
    audio: AudioSide = AudioSide.NONE,
) -> DeckSettings:
    return DeckSettings(note_type_id=note_type_id, lang_q=lang_q, lang_a=lang_a, audio=audio)


def make_result(tmp_path: Path, *, deck_name: str = "Тест", notes: int = 2) -> BuildResult:
    path = tmp_path / "deck.apkg"
    path.write_bytes(b"PK\x03\x04fake")
    return BuildResult(
        path=path,
        summary=Summary(
            deck_name=deck_name,
            subdecks=(deck_name,),
            notes=notes,
            cards=notes,
            media_files=0,
            skipped=0,
            duplicates=0,
        ),
    )
