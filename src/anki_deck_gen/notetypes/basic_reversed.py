"""«Простая (с обратной карточкой)» — стоковый Basic (and reversed card): две карточки."""

from anki_deck_gen.domain import Row
from anki_deck_gen.notetypes import stock
from anki_deck_gen.notetypes.base import NoteType, register
from anki_deck_gen.notetypes.basic import AFMT, QFMT, stock_fields, stock_note_fields

# Вторая карточка зеркальна: ответ спрашивают, вопрос показывают. Озвучка
# следует за своей стороной, а не за ролью «вопрос/ответ».
REVERSE_QFMT = "{{Back}}{{Audio Back}}"
REVERSE_AFMT = "{{FrontSide}}\n\n<hr id=answer>\n\n{{Front}}{{Audio Front}}"


@register
class BasicReversed(NoteType):
    id = "basic-reversed"
    label = "Простая (с обратной карточкой)"
    description = "Две карточки на запись: вопрос → ответ и ответ → вопрос."
    model_id = 1756900002
    cards_per_note = 2

    def fields(self) -> list[str]:
        return stock_fields()

    def templates(self) -> list[dict[str, str]]:
        return [
            {"name": stock.CARD_1, "qfmt": QFMT, "afmt": AFMT},
            {"name": stock.CARD_2, "qfmt": REVERSE_QFMT, "afmt": REVERSE_AFMT},
        ]

    def note_fields(self, row: Row, *, audio_q: str, audio_a: str) -> list[str]:
        return stock_note_fields(row, audio_q=audio_q, audio_a=audio_a)
