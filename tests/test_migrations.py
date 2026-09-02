"""Схема приходит из миграций — и только из них."""

import sqlite3
from pathlib import Path

from anki_deck_gen.db.migrate import run_migrations, sqlite_path
from tests.helpers.schema import apply_migrations

EXPECTED_TABLES = {"allowed_users", "invites", "user_prefs"}


def _tables(path: Path) -> set[str]:
    con = sqlite3.connect(path)
    try:
        rows = con.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    finally:
        con.close()
    return {name for (name,) in rows} - {"alembic_version"}


def test_migrations_create_the_three_tables(tmp_path: Path) -> None:
    db = tmp_path / "fresh.db"
    apply_migrations(f"sqlite:///{db}")
    assert _tables(db) == EXPECTED_TABLES


def test_migrations_are_idempotent(tmp_path: Path) -> None:
    db = tmp_path / "twice.db"
    apply_migrations(f"sqlite:///{db}")
    apply_migrations(f"sqlite:///{db}")
    assert _tables(db) == EXPECTED_TABLES


def test_run_migrations_works_from_sync_context_and_creates_parent_dir(tmp_path: Path) -> None:
    """Так его зовёт __main__ до asyncio.run — с ещё не существующим каталогом."""
    db = tmp_path / "nested" / "deeper" / "bot.sqlite"
    assert not db.parent.exists()

    run_migrations(f"sqlite+aiosqlite:///{db}")

    assert db.exists()
    assert _tables(db) == EXPECTED_TABLES


def test_sqlite_path_reads_relative_and_absolute_urls() -> None:
    assert sqlite_path("sqlite+aiosqlite:///anki-deck-gen.sqlite") == Path("anki-deck-gen.sqlite")
    assert sqlite_path("sqlite+aiosqlite:////var/db/ankideckgen/access.sqlite") == Path(
        "/var/db/ankideckgen/access.sqlite"
    )
    assert sqlite_path("sqlite+aiosqlite:///:memory:") is None
    assert sqlite_path("postgresql+asyncpg://u:p@h/db") is None
