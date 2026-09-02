"""Сигнал живости для супервизора.

Две половины одного договора. ``sd_notify`` говорит на протоколе systemd
notify, который на FreeBSD-сервере реализует ``sdnotify-supervise``; а
``run_watchdog`` шлёт keepalive только пока настоящий round-trip до Telegram
удаётся. Зависший процесс — мёртвый long-poll сокет, прокси, который принимает
соединения и молчит, — замолкает и перезапускается: ровно так зависание и
должно выглядеть снаружи.

Вне супервизора (``NOTIFY_SOCKET`` не задан) обе функции — no-op.
"""

import asyncio
import logging
import os
import socket

from aiogram import Bot

logger = logging.getLogger(__name__)


def sd_notify(state: str) -> bool:
    """Отправить строку notify-протокола. False — супервизора нет."""
    address = os.environ.get("NOTIFY_SOCKET")
    if not address:
        return False
    # Ведущий '@' — systemd так пишет абстрактное пространство имён,
    # которое ядро обозначает ведущим NUL.
    if address[0] == "@":
        address = "\0" + address[1:]
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM) as sock:
            sock.connect(address)
            sock.sendall(state.encode())
        return True
    except OSError as exc:
        logger.warning("sd_notify(%r) not delivered: %s", state, exc)
        return False


async def run_watchdog(bot: Bot, *, interval: float, probe_timeout: float) -> None:
    """Пинговать супервизор каждые ``interval`` секунд — но только пока Telegram отвечает."""
    if not os.environ.get("NOTIFY_SOCKET"):
        logger.info("NOTIFY_SOCKET unset — watchdog disabled (not running under a supervisor)")
        return
    logger.info("watchdog active: probe every %gs, probe timeout %gs", interval, probe_timeout)
    while True:
        await asyncio.sleep(interval)
        try:
            # Внешний таймаут — страховка: request_timeout покрывает HTTP-вызов,
            # этот — зависание, не дошедшее до HTTP-уровня.
            async with asyncio.timeout(probe_timeout + 5):
                await bot.get_me(request_timeout=int(probe_timeout))
        except Exception as exc:
            logger.warning(
                "Telegram probe failed (%s) — withholding the keepalive so the "
                "supervisor restarts us",
                type(exc).__name__,
            )
        else:
            sd_notify("WATCHDOG=1")
