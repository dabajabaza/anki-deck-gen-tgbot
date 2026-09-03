"""«Простая (с вводом ответа)» — стоковый Basic (type in the answer)."""

from anki_deck_gen.domain import Row, Theme
from anki_deck_gen.notetypes import stock
from anki_deck_gen.notetypes import theme as themes
from anki_deck_gen.notetypes.base import NoteType, register
from anki_deck_gen.notetypes.basic import stock_fields, stock_note_fields

# На лице озвучки ответа нет: она выдала бы ответ до того, как его набрали.
TYPE_QFMT = "{{Front}}{{Audio Front}}\n\n{{type:Back}}"
TYPE_AFMT = "{{FrontSide}}\n\n<hr id=answer>\n\n{{type:Back}}{{Audio Back}}"


@register
class BasicTyping(NoteType):
    id = "basic-typing"
    label = "Простая (с вводом ответа)"
    description = "Ответ набирается с клавиатуры, Anki подсветит ошибки."
    model_id = 1756900003
    cards_per_note = 1

    def fields(self) -> list[str]:
        return stock_fields()

    def templates(self) -> list[dict[str, str]]:
        return [{"name": stock.CARD_1, "qfmt": TYPE_QFMT, "afmt": TYPE_AFMT}]

    def css(self, theme: Theme) -> str:
        return themes.css_for(theme)

    def note_fields(self, row: Row, *, audio_q: str, audio_a: str) -> list[str]:
        return stock_note_fields(row, audio_q=audio_q, audio_a=audio_a)
