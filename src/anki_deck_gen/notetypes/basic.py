"""«Простая» — стоковый Basic: вопрос на лице, ответ на обороте, одна карточка."""

from anki_deck_gen.domain import Row
from anki_deck_gen.notetypes import stock
from anki_deck_gen.notetypes.base import NoteType, card, register

# Шаблоны — в assets/templates/basic.card1.*.html. Озвучка вопроса стоит сразу за
# вопросом на лице, озвучка ответа — за ответом на обороте; пустое поле не рисует
# ничего, поэтому колода без озвучки выглядит ровно как стоковая.


def stock_fields() -> list[str]:
    return [stock.FIELD_FRONT, stock.FIELD_BACK, stock.FIELD_AUDIO_FRONT, stock.FIELD_AUDIO_BACK]


def stock_note_fields(row: Row, *, audio_q: str, audio_a: str) -> list[str]:
    return [row.question, row.answer, audio_q, audio_a]


def stock_card_1() -> dict[str, str]:
    """Карточка 1 «Простой»: она же первая карточка у «с обратной карточкой»."""
    return card(stock.CARD_1, "basic", 1)


@register
class Basic(NoteType):
    id = "basic"
    label = "Простая"
    button = "Простая"
    description = "Вопрос на лице, ответ на обороте. Одна карточка на запись."
    model_id = 1756900001
    cards_per_note = 1

    def fields(self) -> list[str]:
        return stock_fields()

    def templates(self) -> list[dict[str, str]]:
        return [stock_card_1()]

    def note_fields(self, row: Row, *, audio_q: str, audio_a: str) -> list[str]:
        return stock_note_fields(row, audio_q=audio_q, audio_a=audio_a)
