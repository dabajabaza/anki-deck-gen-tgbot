"""Воркер: статус всегда доходит до Вердикта, файл уходит со своим таймаутом."""

import asyncio
import threading
import time
from pathlib import Path
from typing import Any

import pytest
from aiogram import Bot
from aiogram.methods import DeleteMessage, SendDocument

from anki_deck_gen.bot import texts
from anki_deck_gen.bot.progress import ProgressReporter
from anki_deck_gen.domain import BuildRequest, BuildResult
from anki_deck_gen.errors import BuildAbandoned, MissingColumns, TtsUnavailable
from anki_deck_gen.runtime.worker import Request, RequestQueue, RequestWorker
from tests.helpers.bot_harness import RecordingSession
from tests.helpers.factories import (
    FAKE_BOT_TOKEN,
    build_settings,
    make_result,
    make_settings,
    make_table,
)


def _request(bot: Bot) -> Request:
    return Request(
        build=BuildRequest(
            table=make_table(("a", "б")), settings=make_settings(), deck_name="Тест"
        ),
        chat_id=1,
        user_id=1,
        reporter=ProgressReporter(bot, chat_id=1, message_id=42, min_interval=0),
    )


async def _drain(worker: RequestWorker, queue: RequestQueue) -> None:
    """Дать воркеру разобрать всё, что лежит в очереди, и остановить его."""
    task = asyncio.create_task(worker.run())
    try:
        async with asyncio.timeout(5):
            await queue._waiting.join()
            # release() вызывается в finally уже после task_done — дать доиграть.
            for _ in range(50):
                await asyncio.sleep(0)
    finally:
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)


async def _run_one(
    tmp_path: Path, build: Any, *, session: RecordingSession | None = None, **overrides: Any
) -> RecordingSession:
    session = session or RecordingSession()
    bot = Bot(token=FAKE_BOT_TOKEN, session=session)
    settings = build_settings(tmp_path, **overrides)
    queue = RequestQueue(5)
    worker = RequestWorker(queue=queue, bot=bot, settings=settings, build=build)
    queue.submit(_request(bot))
    await _drain(worker, queue)
    return session


async def test_a_built_deck_is_sent_with_its_own_timeout(tmp_path: Path) -> None:
    result = make_result(tmp_path)

    def build(request: BuildRequest, **kwargs: Any) -> BuildResult:
        return result

    session = await _run_one(tmp_path, build)
    sent = session.calls_of(SendDocument)
    assert len(sent) == 1
    assert sent[0].caption == texts.verdict(result.summary)
    assert session.timeout_of(SendDocument) == 120
    assert session.deleted(), "the status message gives way to the file"


async def test_progress_from_the_thread_reaches_the_status(tmp_path: Path) -> None:
    result = make_result(tmp_path)

    def build(request: BuildRequest, *, on_progress: Any, **kwargs: Any) -> BuildResult:
        on_progress(1, 2)
        time.sleep(0.01)
        on_progress(2, 2)
        return result

    session = await _run_one(tmp_path, build)
    edits = session.edit_texts()
    assert texts.BUILDING in edits
    assert any("озвучено" in text for text in edits)


async def test_tts_failure_is_a_verdict_not_a_crash(tmp_path: Path) -> None:
    def build(request: BuildRequest, **kwargs: Any) -> BuildResult:
        raise TtsUnavailable("429")

    session = await _run_one(tmp_path, build)
    assert session.last_edit_text() == texts.ERR_TTS
    assert not session.calls_of(SendDocument)


async def test_missing_columns_names_the_type(tmp_path: Path) -> None:
    def build(request: BuildRequest, **kwargs: Any) -> BuildResult:
        raise MissingColumns(note_type="vietnamese", missing=frozenset({"Q"}))

    session = await _run_one(tmp_path, build)
    assert "Вьетнамский" in session.last_edit_text()


async def test_an_unexpected_error_does_not_kill_the_consumer(tmp_path: Path) -> None:
    calls = 0
    result = make_result(tmp_path)

    def build(request: BuildRequest, **kwargs: Any) -> BuildResult:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise RuntimeError("boom")
        return result

    session = RecordingSession()
    bot = Bot(token=FAKE_BOT_TOKEN, session=session)
    queue = RequestQueue(5)
    worker = RequestWorker(queue=queue, bot=bot, settings=build_settings(tmp_path), build=build)
    queue.submit(_request(bot))
    queue.submit(_request(bot))
    await _drain(worker, queue)
    assert texts.ERR_BUILD_FAILED in session.edit_texts()
    assert len(session.calls_of(SendDocument)) == 1, "the second request still ran"


async def test_timeout_abandons_the_thread_and_reports(tmp_path: Path) -> None:
    released = threading.Event()

    def build(request: BuildRequest, *, abandoned: threading.Event, **kwargs: Any) -> BuildResult:
        # Имитация озвучки: работаем, пока не попросят выйти.
        while not abandoned.wait(0.01):
            pass
        released.set()
        raise BuildAbandoned

    session = await _run_one(tmp_path, build, job_timeout_s=1)
    # Дождаться выхода потока по флагу — иначе он переживёт тест.
    assert released.wait(3)
    assert "Не успел" in session.last_edit_text()


async def test_a_failed_upload_is_reported(tmp_path: Path) -> None:
    result = make_result(tmp_path)

    def build(request: BuildRequest, **kwargs: Any) -> BuildResult:
        return result

    session = RecordingSession()
    session.fail_on["SendDocument"] = RuntimeError("network")
    session = await _run_one(tmp_path, build, session=session)
    assert session.last_edit_text() == texts.ERR_SEND_FAILED
    assert not session.calls_of(DeleteMessage)


async def test_scratch_dir_is_removed_after_the_request(tmp_path: Path) -> None:
    seen: list[Path] = []
    result = make_result(tmp_path)

    def build(request: BuildRequest, *, out_dir: Path, **kwargs: Any) -> BuildResult:
        seen.append(out_dir)
        return result

    await _run_one(tmp_path, build)
    assert seen and not seen[0].exists()


def test_queue_counts_the_in_flight_request() -> None:
    queue = RequestQueue(2)
    bot = Bot(token=FAKE_BOT_TOKEN, session=RecordingSession())
    assert queue.submit(_request(bot)) == 1
    assert queue.submit(_request(bot)) == 2
    with pytest.raises(asyncio.QueueFull):
        queue.submit(_request(bot))


async def test_timeout_waits_for_the_thread_before_cleanup_and_next_request(tmp_path: Path) -> None:
    """После таймаута воркер ждёт выхода потока: scratch жив, второе Задание не стартует."""
    events: list[tuple[str, float]] = []
    first_saw_scratch_alive = threading.Event()

    def slow_build(
        request: BuildRequest, *, out_dir: Path, abandoned: threading.Event, **kwargs: Any
    ) -> BuildResult:
        while not abandoned.wait(0.01):
            pass
        time.sleep(0.2)  # «дописываем фразу» уже после сигнала
        if out_dir.exists():
            first_saw_scratch_alive.set()
        events.append(("first_end", time.monotonic()))
        raise BuildAbandoned

    result = make_result(tmp_path)

    def quick_build(request: BuildRequest, **kwargs: Any) -> BuildResult:
        events.append(("second_start", time.monotonic()))
        return result

    calls = iter([slow_build, quick_build])

    def build(request: BuildRequest, **kwargs: Any) -> BuildResult:
        return next(calls)(request, **kwargs)

    session = RecordingSession()
    bot = Bot(token=FAKE_BOT_TOKEN, session=session)
    queue = RequestQueue(5)
    worker = RequestWorker(
        queue=queue, bot=bot, settings=build_settings(tmp_path, job_timeout_s=1), build=build
    )
    queue.submit(_request(bot))
    queue.submit(_request(bot))
    await _drain(worker, queue)

    names = [name for name, _ in events]
    assert names == ["first_end", "second_start"], names
    assert first_saw_scratch_alive.is_set(), "scratch was removed underneath the running thread"
    # Вердикт о таймауте идёт сразу за «Собираю…» первого задания — до ожидания потока.
    edits = session.edit_texts()
    assert edits[:2] == [texts.BUILDING, texts.ERR_TIMED_OUT.format(minutes=0)], edits
    assert len(session.calls_of(SendDocument)) == 1


async def test_a_real_failure_in_an_abandoned_thread_is_logged(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """Поток, упавший не по флагу (например, 429), оставляет след в логе."""

    def build(request: BuildRequest, *, abandoned: threading.Event, **kwargs: Any) -> BuildResult:
        while not abandoned.wait(0.01):
            pass
        raise TtsUnavailable("429 Too Many Requests")

    with caplog.at_level("WARNING", logger="anki_deck_gen.runtime.worker"):
        await _run_one(tmp_path, build, job_timeout_s=1)
    assert any("abandoned build failed" in m and "429" in m for m in caplog.messages)
