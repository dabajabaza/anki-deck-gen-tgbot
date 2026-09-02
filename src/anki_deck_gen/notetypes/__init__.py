"""Реестр Типов записей: стоковые Anki плюс кастомные, добавленные в коде.

Импорт пакета регистрирует все типы — модули с конкретными типами импортируются
внизу ради этого побочного эффекта. Порядок импорта = порядок кнопок в боте.
"""

from anki_deck_gen.errors import UnknownNoteType
from anki_deck_gen.notetypes.base import REGISTRY, NoteType, register

__all__ = ["REGISTRY", "NoteType", "compatible", "get", "register"]


def get(note_type_id: str) -> NoteType:
    try:
        return REGISTRY[note_type_id]
    except KeyError:
        raise UnknownNoteType(note_type_id) from None


def compatible(columns: frozenset[str]) -> list[NoteType]:
    """Типы, показываемые в боте и укладывающиеся в колонки Таблицы, в порядке регистрации."""
    return [nt for nt in REGISTRY.values() if nt.visible_in_bot and nt.compatible_with(columns)]


# Регистрация. Порядок значим: так кнопки идут от простого к сложному.
from anki_deck_gen.notetypes import (  # noqa: E402
    basic,  # noqa: F401
    basic_reversed,  # noqa: F401
    basic_typing,  # noqa: F401
    vietnamese,  # noqa: F401
)
