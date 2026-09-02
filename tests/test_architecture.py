"""Правила о форме кода, нарушение которых ни один юнит-тест не заметит.

Проверяются разбором импортов, а не grep'ом: докстринг, объясняющий, почему
модуль избегает genanki, не должен читаться как нарушение этого правила.
"""

import ast
from pathlib import Path

import anki_deck_gen
from anki_deck_gen.__main__ import build_dispatcher
from anki_deck_gen.bot.handlers import admin, fallback, fix, settings, source, start
from anki_deck_gen.bot.loader import TableLoader
from anki_deck_gen.bot.pending import PendingStore
from anki_deck_gen.db.engine import create_db
from anki_deck_gen.runtime.worker import RequestQueue
from tests.helpers.factories import build_settings

SRC = Path(anki_deck_gen.__file__).parent


def _modules() -> dict[str, ast.Module]:
    return {
        str(path.relative_to(SRC)): ast.parse(path.read_text(encoding="utf-8"))
        for path in SRC.rglob("*.py")
    }


def _imports(tree: ast.Module) -> set[str]:
    packages: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            packages.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            packages.add(node.module.split(".")[0])
    return packages


def _importers_of(package: str) -> set[str]:
    return {name for name, tree in _modules().items() if package in _imports(tree)}


def test_only_the_build_layer_knows_about_genanki() -> None:
    assert _importers_of("genanki") == {"build/package.py"}


def test_only_the_audio_module_knows_about_gtts() -> None:
    assert _importers_of("gtts") == {"build/audio.py"}


def test_only_the_presentation_layer_knows_about_aiogram() -> None:
    allowed = {"__main__.py", "runtime/watchdog.py", "runtime/worker.py"}
    offenders = {
        name
        for name in _importers_of("aiogram")
        if not name.startswith("bot/") and name not in allowed
    }
    assert offenders == set()


def test_the_core_is_free_of_both_frameworks() -> None:
    for name in ("domain.py", "errors.py", "tables/parse.py", "tables/validate.py"):
        imports = _imports(_modules()[name])
        assert not {"aiogram", "genanki", "gtts"} & imports, name


def test_the_catch_all_router_is_registered_last(tmp_path: Path) -> None:
    settings_ = build_settings(tmp_path)
    engine, sessionmaker = create_db(f"sqlite+aiosqlite:///{tmp_path / 'x.sqlite'}")
    dp = build_dispatcher(
        settings_,
        engine=engine,
        sessionmaker=sessionmaker,
        queue=RequestQueue(1),
        pending=PendingStore(60),
        loader=TableLoader(max_file_bytes=1),
    )
    try:
        assert dp.sub_routers[-1] is fallback.router
        assert dp.sub_routers[0] is admin.router
    finally:
        for router in dp.sub_routers:
            router._parent_router = None


def test_the_test_harness_hands_back_every_router_production_uses() -> None:
    from tests.conftest import _SHARED_ROUTERS

    assert set(_SHARED_ROUTERS) == {
        admin.router,
        start.router,
        source.router,
        fix.router,
        settings.router,
        fallback.router,
    }
