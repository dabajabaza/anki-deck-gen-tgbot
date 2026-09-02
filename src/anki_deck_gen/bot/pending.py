"""Единственный носитель контекста между шагами диалога.

Человек прислал Таблицу, бот её разобрал — и дальше несколько шагов кнопками и,
возможно, диалог правки строк. Всё это время разобранная Таблица, имя колоды,
правки и пропуски лежат здесь, по одному набору на пользователя. Один
механизм, а не два: клавиатуры висят на статус-сообщении (его id тоже здесь),
правило «отвечать на сообщение-источник» не используется — два способа найти
контекст неизбежно расходятся в обработчиках.

Живёт ``ttl_s`` от последнего шага: каждый шаг диалога продлевает. Истекло —
пользователь получает «таблица устарела, пришлите снова»; для колод это дёшево.
Новая Таблица от того же человека замещает старую целиком.

Только для допущенных: Посторонний до обработчиков не доходит, так что размер
ограничен числом Гостей и в потолке не нуждается.
"""

from dataclasses import dataclass, field
from time import monotonic

from anki_deck_gen.domain import Fix, ProblemRow, RowKey, Table, Validation


@dataclass
class Pending:
    """Разобранная Таблица и всё, что человек успел про неё сказать."""

    table: Table
    validation: Validation
    deck_name: str
    chat_id: int
    status_message_id: int
    fixes: dict[RowKey, Fix] = field(default_factory=dict)
    skips: set[RowKey] = field(default_factory=set)
    deadline: float = 0.0

    def unresolved(self) -> list[ProblemRow]:
        """Проблемные строки, для которых нет ни правки, ни пропуска."""
        return [
            problem
            for problem in self.validation.problems
            if problem.row.key not in self.fixes and problem.row.key not in self.skips
        ]

    @property
    def notes(self) -> int:
        """Сколько Записей выйдет с учётом правок и пропусков."""
        return self.validation.notes + len(self.fixes)


class PendingStore:
    """``user_id → Pending`` с TTL."""

    def __init__(self, ttl_s: float) -> None:
        self._ttl_s = ttl_s
        self._items: dict[int, Pending] = {}

    def put(self, user_id: int, pending: Pending) -> None:
        pending.deadline = monotonic() + self._ttl_s
        self._items[user_id] = pending

    def get(self, user_id: int) -> Pending | None:
        """Живой Pending или None; истёкший при этом забывается."""
        pending = self._items.get(user_id)
        if pending is None:
            return None
        if monotonic() >= pending.deadline:
            del self._items[user_id]
            return None
        return pending

    def touch(self, user_id: int) -> Pending | None:
        """Как ``get``, но шаг диалога продлевает жизнь."""
        pending = self.get(user_id)
        if pending is not None:
            pending.deadline = monotonic() + self._ttl_s
        return pending

    def pop(self, user_id: int) -> Pending | None:
        pending = self._items.pop(user_id, None)
        if pending is not None and monotonic() >= pending.deadline:
            return None
        return pending

    def __len__(self) -> int:
        return len(self._items)
