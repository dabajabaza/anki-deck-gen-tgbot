"""Состояния диалогов. Их два, и оба короткие.

Всё остальное — выбор Типа записи, Языков, Озвучки — состояния не требует:
выбор целиком едет в callback_data кнопки (см. bot/callbacks.py), а разобранная
Таблица лежит в bot/pending.py. FSM нужен ровно там, где бот ждёт от человека
ТЕКСТ: исправление строки и имя колоды.
"""

from aiogram.fsm.state import State, StatesGroup


class FixRows(StatesGroup):
    """Идём по Проблемным строкам; ``idx`` в данных — позиция в списке."""

    fixing = State()


class Rename(StatesGroup):
    """Ждём имя колоды одним сообщением."""

    waiting = State()
