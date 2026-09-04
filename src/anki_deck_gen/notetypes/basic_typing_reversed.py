"""«Простая (с вводом ответа в обе стороны)» — две карточки, обе с набором ответа.

Стокового типа с такой парой у Anki нет: `Простая (с обратной карточкой)` даёт
две карточки без ввода, `Простая (с вводом ответа)` — ввод, но одну карточку.
Преподавателю нужно и то и другое сразу: одно и то же слово спрашивается с
английского и с русского, и оба раза набирается с клавиатуры.

Поля и порядок — как у стоковых типов, поэтому колонки Таблицы те же. Шаблоны
собраны по правилам Anki: на обороте стоит поле вопроса, а не `{{FrontSide}}`
(иначе разбор набранного выводится дважды, см. `stock.py`), и озвучка ответа
никогда не звучит на лице — она подсказала бы то, что человек набирает.
"""

from anki_deck_gen.domain import Row
from anki_deck_gen.notetypes import stock
from anki_deck_gen.notetypes.base import NoteType, card, register
from anki_deck_gen.notetypes.basic import stock_fields, stock_note_fields

# Шаблоны — assets/templates/basic-typing-reversed.card*.html: карточка 1 спрашивает
# вопрос и набирает ответ, карточка 2 меняет роли местами вместе с озвучкой.


@register
class BasicTypingReversed(NoteType):
    id = "basic-typing-reversed"
    label = "Простая (с вводом ответа в обе стороны)"
    button = "Ввод в обе стороны"
    description = "Две карточки, в обе стороны, ответ набирается с клавиатуры."
    model_id = 1756900005
    cards_per_note = 2

    def fields(self) -> list[str]:
        return stock_fields()

    def templates(self) -> list[dict[str, str]]:
        return [card(stock.CARD_1, self.id, 1), card(stock.CARD_2, self.id, 2)]

    def note_fields(self, row: Row, *, audio_q: str, audio_a: str) -> list[str]:
        return stock_note_fields(row, audio_q=audio_q, audio_a=audio_a)
