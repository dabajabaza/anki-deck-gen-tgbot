"""«Вьетнамский словарь (с тонами)» — личный тип владельца, перенесён из старого генератора.

Слово раскрашивается по тону первой найденной гласной/дифтонга; диалект — по
региону. Двусторонние карточки с набором ответа, дополнительные колонки
Tips / Dialect / Note / Example необязательны. Пример того, как кастомный тип
живёт рядом со стоковыми: он в реестре, значит виден и в CLI, и в боте.
"""

import re

from anki_deck_gen.domain import Row
from anki_deck_gen.notetypes.base import NoteType, register

COL_TIPS = "Tips"
COL_DIALECT = "Dialect"
COL_NOTE = "Note"
COL_EXAMPLE = "Example"

DIALECT_COLORS = {
    "north": "blue",
    "south": "red",
}


class TonesRegistry:
    """Вьетнамские тоны → цвет.

    No tone (ngang) · Grave (huyền) ̀ · Acute (sắc) ́ · Hook above (hỏi) ̉ ·
    Tilde (ngã) ̃ · Dot below (nặng) ̣
    """

    NO_TONE = (
        {
            "a", "e", "i", "o", "u", "y", "ê", "ô", "ơ", "ă", "â", "ư",
            "ai", "ao", "au", "ay", "âu", "ây", "eo", "ia", "iê", "iu",
            "oa", "oă", "oe", "oi", "ôi", "ơi", "oo", "ou", "ua", "uă",
            "uâ", "ue", "ui", "uô", "uy", "uya", "uye", "ươ", "ưa", "ươi", "ưu",
        },
        "gray",
    )  # fmt: skip
    GRAVE = (
        {
            "à", "è", "ì", "ò", "ù", "ỳ", "ề", "ồ", "ờ", "ằ", "ầ", "ừ",
            "ài", "ào", "àu", "ày", "ầu", "ầy", "èo", "ìa", "iề", "ìu",
            "òa", "oằ", "òe", "òi", "ồi", "ời", "òu", "ùa", "uằ",
            "uầ", "uè", "ùi", "uồ", "ùy", "ùya", "uyề", "ườ", "ừa", "ười", "ừu",
        },
        "blue",
    )  # fmt: skip
    ACUTE = (
        {
            "á", "é", "í", "ó", "ú", "ý", "ế", "ố", "ớ", "ắ", "ấ", "ứ",
            "ái", "áo", "áu", "áy", "ấu", "ấy", "éo", "ía", "iế", "íu",
            "óa", "oắ", "óe", "ói", "ối", "ới", "óo", "óu", "úa", "uắ",
            "uấ", "ué", "úi", "uố", "úy", "úya", "uyế", "ướ", "ứa", "ưới", "ứu",
        },
        "red",
    )  # fmt: skip
    HOOK_ABOVE = (
        {
            "ả", "ẻ", "ỉ", "ỏ", "ủ", "ỷ", "ể", "ổ", "ở", "ẳ", "ẩ", "ử",
            "ải", "ảo", "ảu", "ảy", "ẩu", "ẩy", "ẻo", "ỉa", "iể", "ỉu",
            "ỏa", "oẳ", "ỏe", "ỏi", "ổi", "ởi", "ỏo", "ỏu", "ủa", "uẳ",
            "uẩ", "uẻ", "ủi", "uổ", "ủy", "ủya", "uyể", "ưở", "ửa", "ưởi", "ửu",
        },
        "green",
    )  # fmt: skip
    # В старом коде между 'uyễ' и 'ưỡ' была пропущена запятая, и Python склеивал
    # их в одну несуществующую строку 'uyễưỡ' — оба дифтонга не раскрашивались.
    TILDE = (
        {
            "ã", "ẽ", "ĩ", "õ", "ũ", "ỹ", "ễ", "ỗ", "ỡ", "ẵ", "ẫ", "ữ",
            "ãi", "ão", "ãu", "ãy", "ẫu", "ẫy", "ẽo", "ĩa", "iễ", "ĩu",
            "õa", "oẵ", "õe", "õi", "ỗi", "ỡi", "õo", "õu", "ũa", "uẵ",
            "uẫ", "uẽ", "ũi", "uỗ", "ũy", "ũya", "uyễ", "ưỡ", "ữa", "ưỡi", "ữu",
        },
        "purple",
    )  # fmt: skip
    DOT_BELOW = (
        {
            "ạ", "ẹ", "ị", "ọ", "ụ", "ỵ", "ệ", "ộ", "ợ", "ặ", "ậ", "ự",
            "ại", "ạo", "ạu", "ạy", "ậu", "ậy", "ẹo", "ịa", "iệ", "ịu",
            "ọa", "oặ", "ọe", "ọi", "ội", "ợi", "ọo", "ọu", "ụa", "uặ",
            "uậ", "uẹ", "ụi", "uộ", "ụy", "ụya", "uyệ", "ượ", "ựa", "ượi", "ựu",
        },
        "black",
    )  # fmt: skip

    @classmethod
    def letter_color_mapping(cls) -> dict[str, str]:
        mapping: dict[str, str] = {}
        for group, color in (
            cls.NO_TONE,
            cls.GRAVE,
            cls.ACUTE,
            cls.HOOK_ABOVE,
            cls.TILDE,
            cls.DOT_BELOW,
        ):
            for letter in group:
                mapping[letter] = color
        return mapping


_LETTER_COLORS = TonesRegistry.letter_color_mapping()
_WORD_SEPARATORS = re.compile(r"[ ,-]+")


def colour_question(question: str) -> str:
    """Каждое слово — в цвет своего тона: сначала трифтонги, потом дифтонги, потом гласные."""
    result: list[str] = []
    for word in _WORD_SEPARATORS.split(question):
        color = None
        for length in (3, 2, 1):
            for start in range(len(word) - length + 1):
                segment = word[start : start + length]
                if segment in _LETTER_COLORS:
                    color = _LETTER_COLORS[segment]
                    break
            if color:
                break
        result.append(f'<font color="{color}">{word}</font>' if color else word)
    return " ".join(result)


def colour_dialect(dialect: str) -> str:
    if not dialect:
        return dialect
    color = DIALECT_COLORS.get(dialect.lower(), "black")
    return f'<font color="{color}">{dialect}</font>'


_EXTRA_BLOCK = (
    "{{{{#{field}}}}}\n"
    "  <hr>\n"
    "\t<div class=field_container>\n"
    "\t\t<span class=field_label>{field}:</span> <span class={cls}_content>{{{{{field}}}}}</span>\n"
    "\t</div>\n"
    "{{{{/{field}}}}}"
)
_AUDIO_BLOCK = (
    "{{#Audio Front}}\n"
    "  <hr>\n"
    "\t<div class=field_container>\n"
    "\t\t<span class=audio_content>{{Audio Front}}</span>\n"
    "\t</div>\n"
    "{{/Audio Front}}"
)


def _block(field: str) -> str:
    return _EXTRA_BLOCK.format(field=field, cls=field.lower())


# Четыре шаблона старого каталога two-way_typing_with_audio_and_extra_fields,
# {{Audio}} → {{Audio Front}}: озвучен только изучаемый (вьетнамский) язык.
VI_TO_EN_QFMT = (
    "{{Front}}\n\n<div class=input>\n    {{type:Back}}\n</div>\n\n"
    + _block(COL_DIALECT)
    + "\n\n"
    + _block(COL_TIPS)
)
VI_TO_EN_AFMT = (
    "{{Front}}\n\n<hr id=answer>\n\n<div class=back>\n    {{type:Back}}\n</div>\n\n"
    + _block(COL_DIALECT)
    + "\n\n"
    + _block(COL_NOTE)
    + "\n\n"
    + _block(COL_EXAMPLE)
    + "\n\n"
    + _AUDIO_BLOCK
)
EN_TO_VI_QFMT = "{{Back}}\n\n{{type:Front}}\n\n" + _block(COL_DIALECT) + "\n\n" + _block(COL_TIPS)
EN_TO_VI_AFMT = (
    "{{Back}}\n\n<hr id=answer>\n\n<div class=back>\n    {{type:Front}}\n</div>\n\n"
    + _block(COL_DIALECT)
    + "\n\n"
    + _block(COL_NOTE)
    + "\n\n"
    + _block(COL_EXAMPLE)
    + "\n\n"
    + _AUDIO_BLOCK
)

CSS = (
    "input {\n"
    "    font-size: 0.5em;\n"
    "    font-family: ayuthaya;\n"
    "}\n"
    ".card {\n"
    "    font-family: ayuthaya;\n"
    "    font-size: 2.5em;\n"
    "    text-align: center;\n"
    "    background-color: white;\n"
    "}\n"
    ".field_container {\n"
    "    font-size: 0.7em;\n"
    "}\n"
    ".field_label {\n"
    "    color: gray\n"
    "}\n"
)


@register
class Vietnamese(NoteType):
    id = "vietnamese"
    label = "Вьетнамский словарь (с тонами)"
    description = (
        "Две карточки с вводом ответа; слова раскрашены по тонам. "
        "Необязательные колонки: Tips, Dialect, Note, Example."
    )
    model_id = 1756900004
    cards_per_note = 2
    optional_columns = frozenset({COL_TIPS, COL_DIALECT, COL_NOTE, COL_EXAMPLE})

    def fields(self) -> list[str]:
        return [
            "Front",
            "Back",
            COL_DIALECT,
            COL_NOTE,
            COL_EXAMPLE,
            COL_TIPS,
            "Audio Front",
            "Audio Back",
        ]

    def templates(self) -> list[dict[str, str]]:
        return [
            {"name": "Вьетнамский → Английский", "qfmt": VI_TO_EN_QFMT, "afmt": VI_TO_EN_AFMT},
            {"name": "Английский → Вьетнамский", "qfmt": EN_TO_VI_QFMT, "afmt": EN_TO_VI_AFMT},
        ]

    def css(self) -> str:
        return CSS

    def note_fields(self, row: Row, *, audio_q: str, audio_a: str) -> list[str]:
        return [
            colour_question(row.question),
            row.answer,
            colour_dialect(row.extra.get(COL_DIALECT, "")),
            row.extra.get(COL_NOTE, ""),
            row.extra.get(COL_EXAMPLE, ""),
            row.extra.get(COL_TIPS, ""),
            audio_q,
            audio_a,
        ]
