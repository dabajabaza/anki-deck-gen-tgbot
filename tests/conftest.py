"""Общие фикстуры.

Здесь пока только база: схема берётся из настоящих миграций, а не из
create_all — приближение умеет незаметно разойтись с тем, что выполняется в
проде, и тогда зелёные тесты перестают что-либо доказывать. Миграции гоняются
один раз за сессию, каждому тесту достаётся копия готового файла.

Ниже — `harness`: полноценный диспетчер, собранный той же функцией, что и в
проде, и подделка сети вместо Telegram.
"""

import shutil
from collections.abc import AsyncIterator
from pathlib import Path

import pytest
import pytest_asyncio
from aiogram import Bot
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from anki_deck_gen.__main__ import build_dispatcher
from anki_deck_gen.bot.handlers import admin, fallback, fix, source, start
from anki_deck_gen.bot.handlers import settings as settings_handlers
from anki_deck_gen.bot.pending import PendingStore
from anki_deck_gen.config import BotSettings
from anki_deck_gen.db.engine import create_db
from anki_deck_gen.runtime.worker import RequestQueue
from tests.helpers.bot_harness import BotHarness, FakeLoader, RecordingSession
from tests.helpers.factories import build_settings
from tests.helpers.schema import apply_migrations

# Роутеры — синглтоны уровня модуля, а Router может быть привязан к одному
# Dispatcher за жизнь; каждый тест собирает диспетчер заново, так что между
# тестами их надо отцеплять. Список сверяется с build_dispatcher в
# test_architecture.py.
_SHARED_ROUTERS = (
    admin.router,
    start.router,
    source.router,
    fix.router,
    settings_handlers.router,
    fallback.router,
)

# Переменные, которые pydantic-settings и env.py читают из окружения. Убираем,
# чтобы .env разработчика или shell с боевыми значениями не просочился в тесты.
_ENV_VARS = ("TELEGRAM_BOT_TOKEN", "ADMIN_IDS", "DATABASE_URL", "WORK_DIR", "MEDIA_CACHE_DIR")


@pytest.fixture(autouse=True)
def hermetic_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Держать окружение разработчика подальше от каждого теста.

    pydantic-settings резолвит `.env` относительно рабочего каталога, так что
    уход из репозитория — ровно то, что делает случайный .env невидимым.
    """
    for name in _ENV_VARS:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.chdir(tmp_path)


@pytest.fixture(scope="session")
def migrated_template(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Настоящая цепочка миграций, один раз на всю сессию тестов."""
    path = tmp_path_factory.mktemp("schema") / "template.db"
    apply_migrations(f"sqlite:///{path}")
    return path


@pytest.fixture
def db_path(migrated_template: Path, tmp_path: Path) -> Path:
    """Личная копия готовой схемы на каждый тест — просто копирование файла,
    зато состояние между тестами не протекает."""
    path = tmp_path / "test.db"
    shutil.copyfile(migrated_template, path)
    return path


@pytest_asyncio.fixture
async def _db(
    db_path: Path,
) -> AsyncIterator[tuple[AsyncEngine, async_sessionmaker[AsyncSession]]]:
    """Движок И фабрика сессий — оба из create_db, как в проде.

    Не create_async_engine напрямую: в create_db живут PRAGMA и — важнее —
    отключение собственного управления транзакциями у драйвера SQLite, без
    которого SAVEPOINT в allow_user не откатывается. Собери тесты своим
    движком — и они будут проверять не ту семантику транзакций, что в бою.
    """
    eng, sm = create_db(f"sqlite+aiosqlite:///{db_path}")
    yield eng, sm
    await eng.dispose()


@pytest_asyncio.fixture
async def engine(_db: tuple[AsyncEngine, async_sessionmaker[AsyncSession]]) -> AsyncEngine:
    return _db[0]


@pytest_asyncio.fixture
async def sessionmaker(
    _db: tuple[AsyncEngine, async_sessionmaker[AsyncSession]],
) -> async_sessionmaker[AsyncSession]:
    return _db[1]


@pytest_asyncio.fixture
async def session(sessionmaker: async_sessionmaker[AsyncSession]) -> AsyncIterator[AsyncSession]:
    async with sessionmaker() as s:
        yield s


@pytest.fixture
def settings(tmp_path: Path, db_path: Path) -> BotSettings:
    return build_settings(tmp_path, database_url=f"sqlite+aiosqlite:///{db_path}")


@pytest_asyncio.fixture
async def harness(
    settings: BotSettings,
    _db: tuple[AsyncEngine, async_sessionmaker[AsyncSession]],
) -> AsyncIterator[BotHarness]:
    engine, sessionmaker = _db
    session = RecordingSession()
    bot = Bot(token=settings.bot_token, session=session)
    queue = RequestQueue(settings.queue_limit)
    pending = PendingStore(settings.pending_ttl_s)
    loader = FakeLoader()
    dp = build_dispatcher(
        settings,
        engine=engine,
        sessionmaker=sessionmaker,
        queue=queue,
        pending=pending,
        loader=loader,
    )
    await dp.emit_startup()
    try:
        yield BotHarness(
            bot=bot,
            dp=dp,
            session=session,
            queue=queue,
            pending=pending,
            loader=loader,
            sessionmaker=sessionmaker,
        )
    finally:
        await dp.emit_shutdown()
        for router in _SHARED_ROUTERS:
            router._parent_router = None
