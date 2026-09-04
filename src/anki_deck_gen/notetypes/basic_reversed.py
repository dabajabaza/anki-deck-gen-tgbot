"""«Простая (с обратной карточкой)» — стоковый Basic (and reversed card): две карточки."""

from anki_deck_gen.domain import Row
from anki_deck_gen.notetypes import stock
from anki_deck_gen.notetypes.base import NoteType, card, register
from anki_deck_gen.notetypes.basic import stock_card_1, stock_fields, stock_note_fields

# Первая карточка — общая с «Простой», её файлы не дублируются. Вторая зеркальна:
# ответ спрашивают, вопрос показывают, и озвучка следует за своей стороной, а не
# за ролью «вопрос/ответ» (assets/templates/basic-reversed.card2.*.html).


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
        return [stock_card_1(), card(stock.CARD_2, self.id, 2)]

    def note_fields(self, row: Row, *, audio_q: str, audio_a: str) -> list[str]:
        return stock_note_fields(row, audio_q=audio_q, audio_a=audio_a)
