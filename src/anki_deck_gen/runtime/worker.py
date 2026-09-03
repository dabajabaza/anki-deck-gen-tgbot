"""Очередь и единственный воркер, который её разбирает.

Одно Задание за раз, намеренно. Сборка — это сотни запросов к Google TTS и
общий кэш mp3 на диске: параллельные Задания не закончились бы быстрее, зато
два потока могли бы писать один и тот же файл озвучки. Плюс супервизор убивает
процесс, если между WATCHDOG=1 пройдёт больше 90 с, — вся тяжёлая работа уходит
в поток (``asyncio.to_thread``), цикл событий остаётся живым.

Перенос RequestQueue/RequestWorker из clipivore; отличия — в ``_process``:
сборка вместо скачивания, документ вместо видео, флаг ``abandoned`` для потока.
"""

import asyncio
import functools
import logging
import shutil
import tempfile
import threading
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from aiogram import Bot
from aiogram.types import FSInputFile

from anki_deck_gen.bot import texts
from anki_deck_gen.bot.progress import ProgressReporter
from anki_deck_gen.build.package import build_package
from anki_deck_gen.config import BotSettings
from anki_deck_gen.domain import BuildRequest, BuildResult
from anki_deck_gen.errors import (
    AnkiDeckGenError,
    BuildAbandoned,
    MissingColumns,
    TtsUnavailable,
)
from anki_deck_gen.notetypes import REGISTRY

logger = logging.getLogger(__name__)

# Сессионный таймаут 15 с подобран под быстрое обнаружение мёртвого long-poll и
# для загрузки файла в мегабайты через прокси мал; отправка получает свой.
_UPLOAD_TIMEOUT_S = 120
# Сколько ждём поток сборки после того, как попросили его выйти. Поток проверяет
# флаг перед каждым запросом к Google, а у запроса есть таймаут (build/audio.py:
# 10 с на соединение, 60 с на чтение) — так что минуты хватает и ветка «не
# дождались» практически недостижима. При остановке процесса ждём меньше:
# супервизор даёт 10 с до SIGKILL.
_ABANDON_GRACE_S = 60.0
_SHUTDOWN_GRACE_S = 5.0

# Сигнатура build_package; параметр воркера, чтобы тесты подставляли подделку.
Builder = Callable[..., BuildResult]


@dataclass
class Request:
    """Одно Задание: самодостаточный заказ на сборку плюс куда отвечать."""

    build: BuildRequest
    chat_id: int
    user_id: int
    reporter: ProgressReporter


class RequestQueue:
    """Ограниченный список работы с одним потребителем.

    Предел считает и Задание в работе, не только ожидающие: пять — это пять в
    системе.
    """

    def __init__(self, limit: int) -> None:
        self._limit = limit
        self._waiting: asyncio.Queue[Request] = asyncio.Queue()
        self._in_flight = 0

    @property
    def limit(self) -> int:
        return self._limit

    @property
    def load(self) -> int:
        return self._waiting.qsize() + self._in_flight

    def submit(self, request: Request) -> int:
        """Принять Задание и вернуть его место в очереди (1 — следующее).

        Бросает `asyncio.QueueFull`, когда бот уже на пределе.
        """
        if self.load >= self._limit:
            raise asyncio.QueueFull
        self._waiting.put_nowait(request)
        return self.load

    async def take(self) -> Request:
        request = await self._waiting.get()
        self._in_flight += 1
        return request

    def release(self) -> None:
        self._in_flight = max(0, self._in_flight - 1)
        self._waiting.task_done()


class RequestWorker:
    """Разбирает очередь по одному Заданию и рассказывает о ходе дела в чат."""

    def __init__(
        self,
        *,
        queue: RequestQueue,
        bot: Bot,
        settings: BotSettings,
        build: Builder = build_package,
        abandon_grace_s: float = _ABANDON_GRACE_S,
        shutdown_grace_s: float = _SHUTDOWN_GRACE_S,
    ) -> None:
        self._queue = queue
        self._bot = bot
        self._settings = settings
        self._build = build
        self._abandon_grace_s = abandon_grace_s
        self._shutdown_grace_s = shutdown_grace_s

    async def run(self) -> None:
        while True:
            request = await self._queue.take()
            try:
                await self._process(request)
            except asyncio.CancelledError:
                raise
            except Exception:
                # Воркер — единственный потребитель: одно необработанное
                # исключение оставило бы все следующие Задания в очереди навсегда.
                logger.exception("request from %s failed unexpectedly", request.user_id)
                await _say(request, texts.ERR_BUILD_FAILED)
            finally:
                self._queue.release()

    async def _process(self, request: Request) -> None:
        self._settings.work_dir.mkdir(parents=True, exist_ok=True)
        scratch = Path(tempfile.mkdtemp(dir=self._settings.work_dir, prefix="req-"))
        # Поток нельзя отменить — только попросить: сборка проверяет флаг между
        # фразами и выходит за одну (см. build/package.py).
        abandoned = threading.Event()
        loop = asyncio.get_running_loop()
        build: asyncio.Future[BuildResult] | None = None

        def on_progress(done: int, total: int) -> None:
            # Вызывается в рабочем потоке; ProgressReporter живёт в цикле событий.
            loop.call_soon_threadsafe(
                request.reporter.offer, texts.BUILDING_PROGRESS.format(done=done, total=total)
            )

        try:
            async with asyncio.timeout(self._settings.job_timeout_s):
                await request.reporter.set(texts.BUILDING)
                # run_in_executor + shield, а не to_thread: по таймауту отменяется только
                # ожидание, а future потока остаётся у нас в руках — чтобы после флага
                # abandoned ДОЖДАТЬСЯ выхода потока, прежде чем удалять его scratch и
                # брать следующее Задание. Иначе два build шли бы одновременно (A5), а
                # запоздалый поток писал бы .apkg в уже снесённый каталог.
                build = loop.run_in_executor(
                    None,
                    functools.partial(
                        self._build,
                        request.build,
                        out_dir=scratch,
                        media_cache_dir=self._settings.media_cache_dir,
                        on_progress=on_progress,
                        abandoned=abandoned,
                    ),
                )
                result = await asyncio.shield(build)
            # Вне дедлайна намеренно: он ограничивает РАБОТУ, а работа сделана.
            # Дедлайн, истёкший во время последней правки статуса, отменял саму
            # правку и оставлял «Собираю…» навсегда.
            await self._deliver(request, result)
        except TimeoutError:
            abandoned.set()
            minutes = self._settings.job_timeout_s // 60
            logger.warning("request from %s timed out after %s min", request.user_id, minutes)
            # Вердикт — сразу: человеку обещали N минут, и ждать ещё grace, держа
            # его на «Собираю…», значит соврать. Ожидание потока нужно только
            # ради сохранности scratch, оно идёт после.
            await _say(request, texts.ERR_TIMED_OUT.format(minutes=minutes))
            try:
                await _settle(build, grace=self._abandon_grace_s)
            except asyncio.CancelledError:
                # Остановка процесса пришла, пока мы ждали брошенный поток. Соседняя
                # ветка `except CancelledError` сюда не сработает: исключение из
                # блока except не передаётся другим except того же try. Поэтому
                # короткое ожидание остановки — здесь же, иначе scratch снесётся
                # под живым потоком молча, а его исключение пропадёт.
                logger.warning(
                    "shutdown interrupted the grace wait for %s; giving the build thread %ss",
                    request.user_id,
                    self._shutdown_grace_s,
                )
                await _settle(build, grace=self._shutdown_grace_s)
                raise
        except asyncio.CancelledError:
            abandoned.set()
            await _settle(build, grace=self._shutdown_grace_s)
            raise
        except TtsUnavailable as exc:
            logger.warning("gTTS unavailable: %s", exc.detail)
            await _say(request, texts.ERR_TTS)
        except MissingColumns as exc:
            label = REGISTRY[exc.note_type].label if exc.note_type in REGISTRY else exc.note_type
            await _say(
                request,
                texts.ERR_MISSING_COLUMNS.format(
                    label=label, columns=", ".join(sorted(exc.missing))
                ),
            )
        except BuildAbandoned:
            # Флаг взводим только мы; сюда попадает лишь гонка «поток вышел по флагу
            # раньше, чем таймаут дошёл до нас». Вердикт всё равно нужен.
            logger.warning("build for %s reported abandonment", request.user_id)
            await _say(
                request, texts.ERR_TIMED_OUT.format(minutes=self._settings.job_timeout_s // 60)
            )
        except AnkiDeckGenError as exc:
            logger.info("request from %s failed: %s: %s", request.user_id, type(exc).__name__, exc)
            await _say(request, texts.ERR_BUILD_FAILED)
        finally:
            # В scratch лежит готовый .apkg; оставить его — забить датасет jail'а.
            shutil.rmtree(scratch, ignore_errors=True)

    async def _deliver(self, request: Request, result: BuildResult) -> None:
        await request.reporter.set(texts.SENDING)
        try:
            await self._bot.send_document(
                chat_id=request.chat_id,
                document=FSInputFile(result.path, filename=result.path.name),
                caption=texts.verdict(result.summary),
                request_timeout=_UPLOAD_TIMEOUT_S,
            )
        except Exception as exc:
            logger.warning(
                "could not send the deck to %s: %s: %s", request.chat_id, type(exc).__name__, exc
            )
            await _say(request, texts.ERR_SEND_FAILED)
            return
        logger.info(
            "deck sent to %s: %s notes, %s cards, %s decks",
            request.user_id,
            result.summary.notes,
            result.summary.cards,
            len(result.summary.subdecks),
        )
        await request.reporter.replace_with_upload(texts.DONE_FALLBACK)


async def _settle(build: "asyncio.Future[BuildResult] | None", *, grace: float) -> None:
    """Дать потоку сборки выйти по флагу; исключение из него — ожидаемое, не шум.

    Не дождались за ``grace`` — говорим об этом в лог и идём дальше: держать
    очередь заложником зависшего запроса к Google нельзя, а сам поток всё равно
    не убить.
    """
    if build is None:
        return
    if not build.done():
        done, _ = await asyncio.wait({build}, timeout=grace)
        if not done:
            logger.warning(
                "build thread still running %.0fs after being abandoned; "
                "its scratch directory is removed underneath it",
                grace,
            )
            return
    if build.cancelled():
        return
    exc = build.exception()
    if exc is not None and not isinstance(exc, BuildAbandoned):
        # Брошенный поток упал не по нашему флагу, а по-настоящему — 429 от Google,
        # ошибка записи кэша, баг. Это единственное место, где такое исключение ещё
        # видно; молча выбросить его — потерять след повторяющейся проблемы.
        logger.warning("abandoned build failed: %s: %s", type(exc).__name__, exc)


async def _say(request: Request, text: str) -> None:
    """Вынести Вердикт. Никогда не бросает.

    Это последнее, что воркер делает для Задания, и вызывается из его же
    обработчика ошибок — исключение отсюда закончило бы единственного
    потребителя очереди. Ловится любое исключение, не только TelegramAPIError:
    фронт Telegram, ответивший HTML-страницей, даёт ClientDecodeError.
    """
    try:
        await request.reporter.finish(text)
    except Exception as exc:
        logger.warning(
            "could not report the outcome to %s: %s: %s",
            request.chat_id,
            type(exc).__name__,
            exc,
        )


def default_builder() -> Builder:
    """Настоящая сборка — для __main__; тесты подставляют свою."""
    return build_package
