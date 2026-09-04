"""Остановка процесса не должна обрывать начатый ответ человеку.

Выкатка шлёт боту SIGTERM. aiogram по сигналу отменяет только опрос, а апдейты,
которые уже разбираются, живут отдельными задачами: закрыть сессию под ними —
значит оборвать ответ на полуслове и оставить «Читаю таблицу…» навсегда.
"""

import asyncio

from anki_deck_gen.__main__ import _drain_handlers


class FakeDispatcher:
    """Ровно то, чем пользуется _drain_handlers, — набор задач апдейтов."""

    def __init__(self) -> None:
        self._handle_update_tasks: set[asyncio.Task[None]] = set()


async def test_a_started_handler_gets_to_finish() -> None:
    finished = False

    async def handler() -> None:
        nonlocal finished
        await asyncio.sleep(0.05)
        finished = True

    dp = FakeDispatcher()
    dp._handle_update_tasks.add(asyncio.create_task(handler()))

    await _drain_handlers(dp, grace=2.0)  # type: ignore[arg-type]

    assert finished, "обработчик должен был договорить до закрытия сессии"


async def test_a_stuck_handler_does_not_hold_the_process() -> None:
    """За нами супервизор с SIGKILL — ждать бесконечно нельзя."""

    async def stuck() -> None:
        await asyncio.sleep(10)

    task = asyncio.create_task(stuck())
    dp = FakeDispatcher()
    dp._handle_update_tasks.add(task)

    started = asyncio.get_running_loop().time()
    await _drain_handlers(dp, grace=0.05)  # type: ignore[arg-type]
    waited = asyncio.get_running_loop().time() - started

    assert waited < 1.0, "ожидание ограничено grace"
    assert not task.done()
    task.cancel()


async def test_nothing_in_flight_is_not_waited_on() -> None:
    dp = FakeDispatcher()

    async def quick() -> None:
        return None

    done = asyncio.create_task(quick())
    await done
    dp._handle_update_tasks.add(done)

    await _drain_handlers(dp, grace=5.0)  # type: ignore[arg-type]
