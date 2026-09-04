"""Тип записи и реестр типов.

Тип записи описывает данные — поля, шаблоны, стиль, как из строки Таблицы
получить поля, — и ничего не знает ни о genanki, ни о Telegram: собрать из него
`genanki.Model` — работа build/package.py, показать кнопкой — работа bot/.
Так добавить свой тип (вьетнамский) — один модуль и одна строка регистрации, и
он сразу виден и в CLI, и в боте (круг 3, Q19).
"""

from abc import ABC, abstractmethod
from typing import ClassVar

from anki_deck_gen.domain import COL_A, COL_Q, Row, Theme
from anki_deck_gen.notetypes import assets
from anki_deck_gen.notetypes.theme import css_for as theme_css

# Суффикс к имени типа внутри Anki. Без него пакет с типом «Простая», но с
# другим id, при импорте породил бы у пользователя дубль «Простая-a1b2c3»
# рядом со стоковым.
ANKI_NAME_SUFFIX = " (anki-deck-gen)"


class NoteType(ABC):
    """Тип записи Anki, каким его видит генератор."""

    id: ClassVar[str]
    label: ClassVar[str]  # имя как в русской локализации Anki — для текстов
    # Подпись кнопки. Отдельно от label: на телефоне кнопка обрезается около 26
    # символов, а перенос строки Telegram в подписях игнорирует. Полное имя типа
    # человек видит на следующем шаге («Тип записи: …»), связь с Anki не теряется.
    button: ClassVar[str]
    description: ClassVar[str]  # одно предложение для подсказки в боте
    model_id: ClassVar[int]  # фиксированный; сменил поля — сменил id (ARCHITECTURE)
    cards_per_note: ClassVar[int]
    required_columns: ClassVar[frozenset[str]] = frozenset({COL_Q, COL_A})
    optional_columns: ClassVar[frozenset[str]] = frozenset()
    visible_in_bot: ClassVar[bool] = True
    # Оформление (notetypes/theme.py) применяется к стоковым типам. Кастомный тип со
    # своим CSS ставит False — и бот не задаёт ему вопрос об оформлении.
    themed: ClassVar[bool] = True

    @abstractmethod
    def fields(self) -> list[str]:
        """Имена полей в порядке Anki."""

    @abstractmethod
    def templates(self) -> list[dict[str, str]]:
        """Шаблоны карточек в форме genanki: {"name", "qfmt", "afmt"}."""

    def css(self, theme: Theme) -> str:
        """Таблица стилей типа для выбранного Оформления.

        Не абстрактный: у стоковых типов реализация одна и та же, и три её копии
        расходились бы. Тип со своим CSS переопределяет метод и ставит
        ``themed = False``, иначе бот предложит выбрать Оформление, которое ни на
        что не влияет.
        """
        return theme_css(theme)

    @abstractmethod
    def note_fields(self, row: Row, *, audio_q: str, audio_a: str) -> list[str]:
        """Значения полей для одной строки; audio_* — `[sound:…]` или пустая строка."""

    def anki_name(self) -> str:
        return f"{self.label}{ANKI_NAME_SUFFIX}"

    def compatible_with(self, columns: frozenset[str]) -> bool:
        return self.required_columns <= columns


def card(name: str, note_type_id: str, ordinal: int) -> dict[str, str]:
    """Карточка в форме genanki: имя плюс две стороны из assets/templates."""
    return {
        "name": name,
        "qfmt": assets.template(note_type_id, ordinal, "q"),
        "afmt": assets.template(note_type_id, ordinal, "a"),
    }


REGISTRY: dict[str, NoteType] = {}


def register(cls: type[NoteType]) -> type[NoteType]:
    """Декоратор: положить тип в реестр под его id. Порядок регистрации = порядок кнопок."""
    instance = cls()
    if instance.id in REGISTRY:
        raise ValueError(f"note type {instance.id!r} registered twice")
    REGISTRY[instance.id] = instance
    return cls
