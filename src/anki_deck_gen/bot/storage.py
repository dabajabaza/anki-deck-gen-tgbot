"""FSM-хранилище с потолком.

aiogram достаёт FSM-контекст для каждого апдейта в мидлвари, зарегистрированной
внутри ``Dispatcher.__init__`` — то есть РАНЬШЕ проверки доступа, которую бот
добавляет потом. Стоковый ``MemoryStorage`` — defaultdict: обращение по ключу
создаёт запись, и каждый Посторонний, написавший боту, оставляет след, хотя
ему отказано. Рост без предела, движимый людьми, которым сюда нельзя.

У clipivore диалогов нет, и он берёт ``NoStorage``. Здесь диалоги есть —
правка Проблемных строк и переименование, — поэтому хранить надо, но с
потолком: старейшие ключи вытесняются. Диалог допущенного пользователя живёт
минуты, посторонних за это время не наберётся тысяча.

Перезапуск бота теряет диалоги — это принято (см. ARCHITECTURE.md): человек
шлёт таблицу снова, колоду пересобрать бесплатно.
"""

from collections import OrderedDict
from collections.abc import Mapping
from typing import Any

from aiogram.fsm.state import State
from aiogram.fsm.storage.base import BaseStorage, StorageKey

_DEFAULT_MAX_KEYS = 1000


class BoundedMemoryStorage(BaseStorage):
    """В памяти, не больше ``max_keys`` ключей, LRU-вытеснение.

    Ключ без состояния и без данных не хранится вовсе — чистое чтение от
    Постороннего не оставляет записи.
    """

    def __init__(self, max_keys: int = _DEFAULT_MAX_KEYS) -> None:
        self._max_keys = max_keys
        self._states: OrderedDict[StorageKey, str | None] = OrderedDict()
        self._data: dict[StorageKey, dict[str, Any]] = {}

    def __len__(self) -> int:
        return len(self._states)

    def _touch(self, key: StorageKey) -> None:
        if key in self._states:
            self._states.move_to_end(key)
            return
        self._states[key] = None
        while len(self._states) > self._max_keys:
            oldest, _ = self._states.popitem(last=False)
            self._data.pop(oldest, None)

    def _drop_if_empty(self, key: StorageKey) -> None:
        if self._states.get(key) is None and not self._data.get(key):
            self._states.pop(key, None)
            self._data.pop(key, None)

    async def set_state(self, key: StorageKey, state: State | str | None = None) -> None:
        value = state.state if isinstance(state, State) else state
        self._touch(key)
        self._states[key] = value
        self._drop_if_empty(key)

    async def get_state(self, key: StorageKey) -> str | None:
        return self._states.get(key)

    async def set_data(self, key: StorageKey, data: Mapping[str, Any]) -> None:
        self._touch(key)
        self._data[key] = dict(data)
        self._drop_if_empty(key)

    async def get_data(self, key: StorageKey) -> dict[str, Any]:
        return dict(self._data.get(key, {}))

    async def close(self) -> None:
        return None
