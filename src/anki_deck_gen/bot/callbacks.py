"""Кодирование callback_data кнопок.

Telegram даёт 64 байта на callback_data, и весь выбор Настроек колоды должен в
них уместиться, чтобы между шагами не понадобилось FSM-состояние: тип записи,
пара языков и сторона озвучки едут в самой кнопке. Самый длинный вариант —
``s:basic-reversed:en-ru:both`` — 28 байт.

Формат — свой, а не ``CallbackData`` aiogram: строк пять, разбор прозрачнее,
чем фабрика с префиксами, и тест на длину пишется в одну строку.
"""

from dataclasses import dataclass

from anki_deck_gen.domain import AudioSide, DeckSettings

CALLBACK_DATA_LIMIT = 64

# Действия с Проблемными строками.
PROBLEMS_FIX = "p:fix"
PROBLEMS_SKIP = "p:skip"
PROBLEMS_CANCEL = "p:cancel"
# Переименовать колоду.
RENAME = "rename"
# Кнопка, которая ничего не делает (заголовок внутри клавиатуры).
NOOP = "noop"


def note_type(note_type_id: str) -> str:
    """Шаг 1: выбран Тип записи → показать Языки."""
    return f"nt:{note_type_id}"


def last_used(note_type_id: str) -> str:
    """«Как в прошлый раз»: последние языки и озвучка с выбранным типом."""
    return f"last:{note_type_id}"


def configure(note_type_id: str) -> str:
    """«Настроить…»: показать пары языков."""
    return f"cfg:{note_type_id}"


def language_pair(note_type_id: str, lang_q: str, lang_a: str) -> str:
    """Выбрана пара языков → показать сторону озвучки."""
    return f"lp:{note_type_id}:{lang_q}-{lang_a}"


def settings(value: DeckSettings) -> str:
    """Финальный выбор → Задание в очередь."""
    return f"s:{value.note_type_id}:{value.lang_q}-{value.lang_a}:{value.audio.value}"


@dataclass(frozen=True)
class Parsed:
    """Разобранная callback_data. Поля заполнены по действию."""

    action: str
    note_type_id: str | None = None
    lang_q: str | None = None
    lang_a: str | None = None
    audio: AudioSide | None = None

    def deck_settings(self) -> DeckSettings:
        assert self.note_type_id and self.lang_q and self.lang_a and self.audio
        return DeckSettings(
            note_type_id=self.note_type_id,
            lang_q=self.lang_q,
            lang_a=self.lang_a,
            audio=self.audio,
        )


def parse(data: str) -> Parsed | None:
    """None — не наша кнопка (или испорченная): обработчик молчит."""
    parts = data.split(":")
    action = parts[0]
    try:
        if action in ("nt", "last", "cfg") and len(parts) == 2:
            return Parsed(action=action, note_type_id=parts[1])
        if action == "lp" and len(parts) == 3:
            lang_q, lang_a = parts[2].split("-", 1)
            return Parsed(action=action, note_type_id=parts[1], lang_q=lang_q, lang_a=lang_a)
        if action == "s" and len(parts) == 4:
            lang_q, lang_a = parts[2].split("-", 1)
            return Parsed(
                action=action,
                note_type_id=parts[1],
                lang_q=lang_q,
                lang_a=lang_a,
                audio=AudioSide(parts[3]),
            )
    except ValueError:
        return None
    return None
