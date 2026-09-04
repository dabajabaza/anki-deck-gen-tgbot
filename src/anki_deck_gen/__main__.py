"""Точка входа бота: long polling. Запуск — ``python -m anki_deck_gen``.

Порядок старта несёт смысл:
1. single-instance lock — две копии дрались бы за getUpdates (Telegram 409), а
   вторая ещё и прогнала бы миграции по живой базе;
2. миграции ДО ``asyncio.run`` — alembic поднимает собственный цикл событий;
3. только потом сеть.
"""

import asyncio
import contextlib
import fcntl
import logging
import os
import signal
import socket
import sys
import time
from typing import Any

from aiogram import Bot, Dispatcher
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.exceptions import (
    TelegramAPIError,
    TelegramNetworkError,
    TelegramRetryAfter,
    TelegramServerError,
)
from aiogram.types import ErrorEvent
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from anki_deck_gen.bot import texts
from anki_deck_gen.bot.commands import set_all_commands
from anki_deck_gen.bot.handlers import admin, draft, fallback, fix, source, start
from anki_deck_gen.bot.handlers import settings as settings_handlers
from anki_deck_gen.bot.loader import TableLoader
from anki_deck_gen.bot.middlewares import AuthMiddleware, PrivateChatOnlyMiddleware
from anki_deck_gen.bot.pending import PendingStore
from anki_deck_gen.bot.storage import BoundedMemoryStorage
from anki_deck_gen.config import BotSettings
from anki_deck_gen.db.engine import create_db
from anki_deck_gen.db.migrate import run_migrations
from anki_deck_gen.runtime.watchdog import run_watchdog, sd_notify
from anki_deck_gen.runtime.worker import Builder, RequestQueue, RequestWorker, default_builder

logger = logging.getLogger("anki_deck_gen")

_LOCK_NAME = "anki-deck-gen.lock"
_ALREADY_RUNNING = "Already running — a second copy would fight over getUpdates."

# aiogram ждёт (таймаут сессии + таймаут polling) на каждом getUpdates, так что
# умолчания скрывают мёртвый сокет полторы минуты. Ужато до ~35 с: честный
# long poll, но порванный туннель замечается быстро. Это per-request умолчание
# для ВСЕХ вызовов Bot API — поэтому отправка файла передаёт свой таймаут
# (runtime/worker.py).
_SESSION_TIMEOUT_S = 15
_POLLING_TIMEOUT_S = 20
# Частота keepalive. WatchdogSec у супервизора должен быть заметно больше,
# иначе одна медленная проба читается как зависание; сервер держит 90 с.
_WATCHDOG_INTERVAL_S = 30
_WATCHDOG_PROBE_TIMEOUT_S = 10
# Бюджет ретраев на достижимость Telegram при старте. Прокси может ещё
# подниматься — это блип, а не сбой; но бесконечный ретрай спрятал бы опечатку
# в адресе прокси навсегда, так что ожидание кончается и супервизор видит
# неудавшийся старт.
_CONNECT_RETRY_START_S = 3.0
_CONNECT_RETRY_MAX_S = 30.0
_CONNECT_BUDGET_S = 600.0
_START_EXTEND_USEC = 120 * 1_000_000
# Сколько ждём начатые обработчики после сигнала остановки. Супервизор даёт
# процессу 10 с до SIGKILL, и следом за этим ожиданием идёт ожидание воркера
# (5 с), поэтому запас держим: 3 с хватает на пару обращений к Telegram.
_HANDLER_GRACE_S = 3.0
# 5xx и 429 — родственники TelegramAPIError, а не сетевые ошибки, и оба проходят
# сами; считать их фатальными — сжечь лимит перезапусков.
_RETRYABLE = (TelegramNetworkError, TelegramServerError, TelegramRetryAfter)


def build_dispatcher(
    settings: BotSettings,
    *,
    engine: AsyncEngine,
    sessionmaker: async_sessionmaker[AsyncSession],
    queue: RequestQueue,
    pending: PendingStore,
    loader: TableLoader,
) -> Dispatcher:
    """Собрать диспетчер в единственном порядке, который имеет значение.

    Общий с тестовым харнессом, чтобы они не разошлись: порядок гейтов ниже И
    ЕСТЬ политика доступа, а тест, собравший диспетчер сам, проверял бы другого
    бота.
    """
    # Хранилище с потолком, а не стоковое MemoryStorage: FSM-мидлварь aiogram
    # отрабатывает до наших гейтов и создаёт запись на каждого постороннего.
    dp = Dispatcher(storage=BoundedMemoryStorage())
    # Workflow data: aiogram отдаёт это любому обработчику, объявившему параметр
    # с тем же именем. Синглтоны без контейнера — запросного состояния нет.
    dp["settings"] = settings
    dp["engine"] = engine
    dp["sessionmaker"] = sessionmaker
    dp["queue"] = queue
    dp["pending"] = pending
    dp["loader"] = loader

    # Оба гейта — внешние мидлвари на `update`, до любого фильтра: сообщение
    # Постороннего не должно даже сопоставляться, не то что получать ответ.
    dp.update.outer_middleware(PrivateChatOnlyMiddleware())
    dp.update.outer_middleware(
        AuthMiddleware(admin_ids=settings.admin_ids, engine=engine, sessionmaker=sessionmaker)
    )

    dp.include_router(admin.router)  # первым: его команды прерывают диалоги
    dp.include_router(start.router)
    dp.include_router(source.router)  # файл и ссылка сбрасывают любой диалог
    dp.include_router(draft.router)
    dp.include_router(fix.router)
    dp.include_router(settings_handlers.router)
    dp.include_router(fallback.router)  # последним: ловит всё остальное

    dp.errors.register(on_error)
    return dp


async def on_error(event: ErrorEvent) -> bool:
    """В чате ничто не падает молча: человек получает вердикт в любом случае."""
    logger.exception("handler failed: %s", event.exception)
    message = event.update.message
    callback = event.update.callback_query
    with contextlib.suppress(TelegramAPIError):
        if message is not None:
            await message.answer(texts.ERR_BUILD_FAILED)
        elif callback is not None:
            await callback.answer(texts.ERR_BUILD_FAILED, show_alert=True)
    return True


def _acquire_single_instance_lock() -> Any:
    r"""Защита от второй копии.

    Оба варианта отдают гарантию ядру, которое снимает замок со смертью
    процесса, так что он не может протухнуть:

    * Linux — абстрактный unix-сокет (ведущий NUL), файла не остаётся;
    * иначе (FreeBSD-сервер) — flock на настоящем файле: абстрактного
      пространства там нет, bind("\0…") падает с ENOENT.
    """
    if sys.platform.startswith("linux"):
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        try:
            sock.bind("\0" + _LOCK_NAME)
        except OSError:
            raise SystemExit(_ALREADY_RUNNING) from None
        return sock

    lock_path = os.environ.get("LOCK_FILE") or os.path.join("/tmp", _LOCK_NAME)
    handle = open(  # noqa: SIM115 — держится открытым всю жизнь процесса
        lock_path,
        "w",
        encoding="utf-8",
    )
    try:
        fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        raise SystemExit(_ALREADY_RUNNING) from None
    return handle


async def _establish_connection(bot: Bot) -> Any:
    """Дождаться, пока Telegram станет достижим через настроенный прокси.

    Лежащий на старте прокси — временно; выход сжёг бы лимит перезапусков
    супервизора из-за блипа. Фатальные ошибки API (плохой токен → 401)
    пробрасываются как есть: их ретраем не починить.
    """
    delay = _CONNECT_RETRY_START_S
    attempt = 0
    deadline = time.monotonic() + _CONNECT_BUDGET_S
    while True:
        attempt += 1
        try:
            # me(), а не get_me(): aiogram кэширует результат.
            me = await bot.me()
            await bot.delete_webhook(drop_pending_updates=False)
            return me
        except Exception as exc:
            if isinstance(exc, TelegramAPIError) and not isinstance(exc, _RETRYABLE):
                raise
            if time.monotonic() >= deadline:
                logger.error(
                    "Telegram unreachable for %.0fs (%d attempts) — giving up so the "
                    "supervisor sees a failed start",
                    _CONNECT_BUDGET_S,
                    attempt,
                )
                raise
            sd_notify(f"EXTEND_TIMEOUT_USEC={_START_EXTEND_USEC}")
            logger.warning(
                "Telegram unreachable at startup (attempt %d): %r. Retrying in %gs.",
                attempt,
                exc,
                delay,
            )
            await asyncio.sleep(delay)
            delay = min(delay * 2, _CONNECT_RETRY_MAX_S)


async def _run_bot(settings: BotSettings, *, build: Builder) -> None:
    session = (
        AiohttpSession(proxy=settings.telegram_proxy, timeout=_SESSION_TIMEOUT_S)
        if settings.telegram_proxy
        else AiohttpSession(timeout=_SESSION_TIMEOUT_S)
    )
    bot = Bot(token=settings.bot_token, session=session)
    engine, sessionmaker = create_db(settings.database_url)

    queue = RequestQueue(settings.queue_limit)
    pending = PendingStore(settings.pending_ttl_s)
    loader = TableLoader(max_file_bytes=settings.max_file_bytes)
    worker = RequestWorker(queue=queue, bot=bot, settings=settings, build=build)
    dp = build_dispatcher(
        settings,
        engine=engine,
        sessionmaker=sessionmaker,
        queue=queue,
        pending=pending,
        loader=loader,
    )

    me = await _establish_connection(bot)
    await set_all_commands(bot, admin_ids=settings.admin_ids)
    logger.info("bot @%s started (long polling), %d admin(s)", me.username, len(settings.admin_ids))

    # Telegram ответил — готовность теперь честное утверждение.
    sd_notify("READY=1")
    worker_task = asyncio.create_task(worker.run())
    worker_task.add_done_callback(_worker_died)
    watchdog_task = asyncio.create_task(
        run_watchdog(bot, interval=_WATCHDOG_INTERVAL_S, probe_timeout=_WATCHDOG_PROBE_TIMEOUT_S)
    )
    try:
        # close_bot_session=False: собственный finally aiogram закрывает сессию
        # до возврата из start_polling, вырывая коннектор из-под отправки файла,
        # которую ещё доделывает воркер. Закрываем ниже, когда воркер остановлен.
        await dp.start_polling(
            bot,
            allowed_updates=["message", "callback_query"],
            polling_timeout=_POLLING_TIMEOUT_S,
            close_bot_session=False,
        )
    finally:
        # Сначала обработчики: aiogram по сигналу отменяет только опрос, а
        # начатые апдейты живут отдельными задачами. Закрыть сессию под ними —
        # это ServerDisconnectedError посреди ответа и статус «Читаю таблицу…»,
        # висящий у человека навсегда (так терялось сообщение при выкатке).
        await _drain_handlers(dp, grace=_HANDLER_GRACE_S)
        worker_task.remove_done_callback(_worker_died)
        worker_task.cancel()
        watchdog_task.cancel()
        # Ждём, а не бросаем: cancel() лишь планирует CancelledError, и закрытие
        # сессии под живой отправкой превращает чистую остановку в трейсбек.
        await asyncio.gather(worker_task, watchdog_task, return_exceptions=True)
        await bot.session.close()
        await engine.dispose()


async def _drain_handlers(dp: Dispatcher, *, grace: float) -> None:
    """Дать начатым обработчикам договорить, прежде чем закрывать сеть.

    Задачи апдейтов aiogram держит в ``_handle_update_tasks``; своего ожидания у
    неё нет — ``start_polling`` возвращается сразу после отмены опроса. Не
    дождались за ``grace`` — идём дальше: держать процесс дольше нельзя, за нами
    супервизор с SIGKILL.
    """
    tasks = {task for task in getattr(dp, "_handle_update_tasks", set()) if not task.done()}
    if not tasks:
        return
    logger.info("shutting down: waiting up to %.0fs for %d handler(s)", grace, len(tasks))
    _, pending = await asyncio.wait(tasks, timeout=grace)
    if pending:
        logger.warning(
            "%d handler(s) still running after %.0fs; their status messages stay as they are",
            len(pending),
            grace,
        )


def _worker_died(task: asyncio.Task[None]) -> None:
    """Мёртвый потребитель очереди = мёртвый процесс.

    Воркер — единственное, что собирает колоды. Остановись он сам, бот отвечал бы
    «Собираю…» вечно, а сторож рапортовал о здоровье — Telegram ведь доступен.
    Крэш, который супервизор видит и перезапускает, лучше живого бота, который
    ничего не делает.
    """
    if task.cancelled():
        return
    exception = task.exception()
    if exception is None:
        logger.error("request worker stopped on its own — exiting so the supervisor restarts us")
    else:
        logger.critical(
            "request worker died: %r — exiting so the supervisor restarts us", exception
        )
    # SIGTERM, а не sys.exit(): это колбэк цикла, где исключение лишь запишется
    # в лог как «exception in callback».
    os.kill(os.getpid(), signal.SIGTERM)


def main() -> None:
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)-8s %(name)s: %(message)s"
    )
    # Держится кадром main() всю жизнь процесса: ядро снимает замок со смертью
    # процесса, достаточно не дать объекту собраться сборщиком мусора раньше.
    _lock = _acquire_single_instance_lock()  # noqa: F841

    settings = BotSettings()
    settings.work_dir.mkdir(parents=True, exist_ok=True)
    settings.media_cache_dir.mkdir(parents=True, exist_ok=True)
    run_migrations(settings.database_url)
    asyncio.run(_run_bot(settings, build=default_builder()))


if __name__ == "__main__":
    # SystemExit от single-instance guard намеренно не подавляется.
    with contextlib.suppress(KeyboardInterrupt):
        main()
