"""Единственное статус-сообщение, которое ведёт Задание от очереди до Вердикта.

Одно сообщение на Задание, редактируется на месте, чтобы занятый чат оставался
читаемым. Правки троттлятся: сборка сообщает прогресс на каждую фразу, а
Telegram начинает отклонять правки одного сообщения задолго до такой частоты.

Два свойства, которые этот класс обязан остальному боту:

* **Вердикт окончателен.** Как только Задание закончено, ничто не может
  переписать сказанное пользователю — включая колбэк прогресса из рабочего
  потока, который ещё разматывается (см. runtime/worker.py).
* **Никогда не бросает.** Статус, который не удалось обновить, — косметика;
  дать исключению уйти наверх — значит убить единственного потребителя очереди.

Перенос из clipivore без изменений по существу.
"""

import asyncio
import logging
from time import monotonic

from aiogram import Bot

logger = logging.getLogger(__name__)

_MIN_EDIT_INTERVAL_S = 5.0


class ProgressReporter:
    """Владеет одним статус-сообщением, темпом его изменений и последним словом."""

    def __init__(
        self,
        bot: Bot,
        *,
        chat_id: int,
        message_id: int,
        min_interval: float = _MIN_EDIT_INTERVAL_S,
    ) -> None:
        self._bot = bot
        self._chat_id = chat_id
        self._message_id = message_id
        self._min_interval = min_interval
        self._shown = ""
        self._pending: str | None = None
        self._last_edit = float("-inf")
        self._flusher: asyncio.Task[None] | None = None
        self._closed = False
        # Одна правка за раз: иначе троттлированный flush и смена состояния
        # летят к одному message_id одновременно, и порядок решает Telegram.
        self._edit_lock = asyncio.Lock()

    @property
    def closed(self) -> bool:
        return self._closed

    @property
    def message_id(self) -> int:
        return self._message_id

    async def set(self, text: str) -> None:
        """Показать ``text`` сейчас — для смены состояния, она редка и её стоит видеть."""
        if self._closed:
            return
        self._pending = None
        await self._edit(text)

    def offer(self, text: str) -> None:
        """Предложить ``text`` к показу, когда позволит троттлинг.

        Синхронно и без ожидания, чтобы цикл сборки никогда не ждал Telegram.
        Вызывать в потоке event loop (из рабочего потока — через
        ``loop.call_soon_threadsafe``).
        """
        if self._closed or text == self._shown:
            return
        self._pending = text
        if self._flusher is None or self._flusher.done():
            self._flusher = asyncio.create_task(self._flush())

    async def finish(self, text: str) -> None:
        """Оставить ``text`` последним словом и больше не обновлять."""
        if self._closed:
            return
        await self.close()
        await self._edit(text)

    async def replace_with_upload(self, fallback: str) -> None:
        """Убрать статус: его место занял отправленный файл.

        Удаление косметическое — бот не может удалять сообщения старше 48 часов —
        поэтому при неудаче статус получает ``fallback`` вместо исчезновения.
        """
        if self._closed:
            return
        await self.close()
        try:
            await self._bot.delete_message(chat_id=self._chat_id, message_id=self._message_id)
        except Exception as exc:
            logger.debug("could not delete status message: %s", exc)
            await self._edit(fallback)

    async def close(self) -> None:
        """Перестать обновлять это сообщение — навсегда."""
        self._closed = True
        self._pending = None
        flusher, self._flusher = self._flusher, None
        if flusher is not None and not flusher.done():
            flusher.cancel()
            try:
                await flusher
            except asyncio.CancelledError:
                # Отмена своего помощника ожидаема и не должна распространяться.
                # Но если отменяют САМОГО вызывающего — остановка пришла ровно
                # пока мы ждём здесь — проглотить её значило бы бросить воркер
                # посреди разбора, так что этот случай отдаётся назад.
                current = asyncio.current_task()
                if current is not None and current.cancelling():
                    raise

    async def _flush(self) -> None:
        while self._pending is not None and not self._closed:
            wait = self._min_interval - (monotonic() - self._last_edit)
            if wait > 0:
                await asyncio.sleep(wait)
            text, self._pending = self._pending, None
            # `set()` мог очистить pending, пока мы спали — смена состояния
            # важнее прогресса, который мы собирались показать.
            if text is not None and not self._closed:
                await self._edit(text)

    async def _edit(self, text: str) -> None:
        if text == self._shown:
            return
        async with self._edit_lock:
            if text == self._shown:
                return
            try:
                await self._bot.edit_message_text(
                    chat_id=self._chat_id,
                    message_id=self._message_id,
                    text=text,
                )
            except Exception as exc:
                # Намеренно любое исключение, не только TelegramAPIError: aiogram
                # бросает ClientDecodeError (AiogramError, не TelegramAPIError),
                # когда фронт Telegram отвечает HTML-страницей ошибки вместо JSON.
                # Выпустить это наверх — убить потребителя очереди из-за 502.
                logger.warning("status edit failed: %s: %s", type(exc).__name__, exc)
            else:
                self._shown = text
            finally:
                self._last_edit = monotonic()
