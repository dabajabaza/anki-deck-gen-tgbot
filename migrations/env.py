import asyncio
import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from anki_deck_gen.config import BotSettings
from anki_deck_gen.db.models import Base  # импорт регистрирует все модели на Base.metadata

# Значение-заглушка из alembic.ini: означает «URL не задан».
_ALEMBIC_INI_PLACEHOLDER = "driver://user:pass@localhost/dbname"

config = context.config
target_metadata = Base.metadata


def _default_db_url() -> str:
    """Адрес базы без инстанцирования BotSettings.

    Полный конфиг требует TELEGRAM_BOT_TOKEN, а ручной `alembic upgrade` на
    машине без токена — законный сценарий. Берём DATABASE_URL из окружения,
    иначе — умолчание поля из config.py, чтобы источник правды был один.
    """
    from_env = os.environ.get("DATABASE_URL")
    if from_env:
        return from_env
    default = BotSettings.model_fields["database_url"].default
    assert isinstance(default, str)
    return default


def run_migrations_offline() -> None:
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        # SQLite не умеет ALTER TABLE в объёме, нужном alembic: batch-режим
        # пересоздаёт таблицу вместо изменения на месте.
        render_as_batch=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata, render_as_batch=True)
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


# Тесты передают живое синхронное соединение через config.attributes, минуя
# создание движка и чтение окружения — так alembic работает внутри уже
# запущенного цикла событий pytest, и fileConfig не перебивает перехват логов.
injected_connection = config.attributes.get("connection")

if injected_connection is not None:
    do_run_migrations(injected_connection)
else:
    if config.config_file_name is not None:
        # disable_existing_loggers=False обязателен. По умолчанию fileConfig
        # НАВСЕГДА выключает все уже созданные логгеры — а миграции в проде
        # выполняются внутри процесса бота (см. __main__.main), после первого
        # logging.basicConfig. Без флага anki_deck_gen.*, aiogram.* и watchdog
        # замолкают на весь срок жизни процесса, и второй basicConfig этого не
        # чинит. В тестах ветка не выполняется (там передаётся готовое
        # соединение), поэтому дефект жил бы незамеченным.
        fileConfig(config.config_file_name, disable_existing_loggers=False)
    # Только если вызывающий не задал URL сам. Безусловная перезапись сделала
    # бы аргумент `run_migrations(db_url)` мёртвым и разворачивала любой ручной
    # прогон alembic на боевую базу.
    if config.get_main_option("sqlalchemy.url") in (None, "", _ALEMBIC_INI_PLACEHOLDER):
        config.set_main_option("sqlalchemy.url", _default_db_url())
    if context.is_offline_mode():
        run_migrations_offline()
    else:
        run_migrations_online()
