"""«Китайский (чтение и на слух)» — для чтения и понимания на слух, без говорения и письма.

Две карточки: «Чтение» (иероглифы → чтение и значение) и «На слух» (звук → слово).
Карточек «значение → иероглифы» и ввода ответа нет намеренно: они тренируют
говорение и письмо.

Озвучка иероглифов лежит в своём поле `Audio`, а не в поле со словом: стоковые типы
приклеивают звук к вопросу, и на карточке «Чтение» он прозвучал бы на лице и подсказал
чтение. Без озвучки Карточка «На слух» не создаётся вовсе — её лицо пустое, и Anki
(genanki) такую карточку не заводит.

Пиньинь — колонка `Pinyin`, тоны знаками (`nǐ hǎo`). Он раскрашивается по слогам;
иероглифы на обороте — так же, если иероглифов столько же, сколько слогов (у эризации
вроде 一点儿 / yìdiǎnr не совпадает — тогда иероглифы остаются без цвета). Пустой
пиньинь не проблема строки: Запись собирается, на обороте просто нет чтения.
"""

import re
import unicodedata

from anki_deck_gen.domain import Row, Theme
from anki_deck_gen.notetypes import assets
from anki_deck_gen.notetypes.base import NoteType, card, register
from anki_deck_gen.notetypes.theme import css_for as theme_css

COL_PINYIN = "Pinyin"
COL_EXAMPLE = "Example"
COL_NOTE = "Note"

# Знак тона над гласной после разложения NFD. Умлаут у ü (U+0308) — не тон.
_TONE_MARKS = {"\u0304": 1, "\u0301": 2, "\u030c": 3, "\u0300": 4}
NEUTRAL = 5

_VOWELS = "aeiouüv"
# Слог: инициаль, гласные, кода, эризация (diǎnr). Кода n/ng/r не берётся, если за ней
# гласная, — тогда согласная начинает следующий слог: dàngāo → dàn·gāo, wǎnshang → wǎn·shang.
# Неоднозначное (xian = xiān или Xī'ān) пиньинь сам разводит апострофом.
_SYLLABLE = re.compile(
    rf"(?:zh|ch|sh|[bpmfdtnlgkhjqxrzcsyw])?[{_VOWELS}]+(?:ng|n)?r?(?![{_VOWELS}])",
    re.IGNORECASE,
)
_HAN = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]")


def _base(text: str) -> str:
    """Буквы без тонов, той же длины, что и исходник: позиции слогов совпадают."""
    return "".join(_strip_tone(ch) for ch in text)


def _strip_tone(ch: str) -> str:
    decomposed = unicodedata.normalize("NFD", ch)
    kept = "".join(c for c in decomposed if c not in _TONE_MARKS)
    return unicodedata.normalize("NFC", kept)


def _tone(syllable: str) -> int:
    for mark in unicodedata.normalize("NFD", syllable):
        if mark in _TONE_MARKS:
            return _TONE_MARKS[mark]
    return NEUTRAL


def syllables(pinyin: str) -> list[tuple[int, int, int]]:
    """Слоги пиньиня: (начало, конец, тон) в форме NFC. Пробелы, знаки, апострофы — не слоги."""
    text = unicodedata.normalize("NFC", pinyin)
    base = _base(text)
    if len(base) != len(text):  # буква, которая не раскладывается в одну, — не трогаем
        return []
    return [
        (m.start(), m.end(), _tone(text[m.start() : m.end()])) for m in _SYLLABLE.finditer(base)
    ]


def _is_erhua(syllable: str) -> bool:
    lowered = syllable.lower()
    return lowered.endswith("r") and lowered not in ("er", "r")


def _span(text: str, tone: int) -> str:
    return f'<span class="tone{tone}">{text}</span>'


def colour_pinyin(pinyin: str) -> str:
    """Каждый слог — в класс своего тона. Поле с HTML не трогаем: разметку не разобрать."""
    if "<" in pinyin:
        return pinyin
    text = unicodedata.normalize("NFC", pinyin)
    out: list[str] = []
    pos = 0
    for start, end, tone in syllables(text):
        out.append(text[pos:start])
        out.append(_span(text[start:end], tone))
        pos = end
    out.append(text[pos:])
    return "".join(out)


def colour_hanzi(hanzi: str, pinyin: str) -> str:
    """Иероглифы в цвет слогов по порядку; при несовпадении счёта — без цвета."""
    if "<" in hanzi:
        return hanzi
    tones: list[int] = []
    base = _base(unicodedata.normalize("NFC", pinyin))
    for start, end, tone in syllables(pinyin):
        tones.append(tone)
        if _is_erhua(base[start:end]):
            tones.append(NEUTRAL)  # diǎnr — это 点儿: у 儿 свой иероглиф
    if not tones or len(_HAN.findall(hanzi)) != len(tones):
        return hanzi
    remaining = iter(tones)
    return _HAN.sub(lambda m: _span(m.group(), next(remaining)), hanzi)


# Шаблоны — assets/templates/chinese.card*.html, тоны — assets/css/chinese.css
# поверх выбранного Оформления.


@register
class Chinese(NoteType):
    id = "chinese"
    label = "Китайский (чтение и на слух)"
    button = "Китайский"
    description = (
        "Карточки «Чтение» и «На слух»; пиньинь и иероглифы раскрашены по тонам. "
        "Нужна колонка Pinyin, необязательные — Example, Note."
    )
    model_id = 1756900006
    cards_per_note = 2
    required_columns = frozenset({"Q", "A", COL_PINYIN})
    optional_columns = frozenset({COL_EXAMPLE, COL_NOTE})

    def fields(self) -> list[str]:
        return [
            "Hanzi",
            "Hanzi Coloured",
            COL_PINYIN,
            "Meaning",
            COL_EXAMPLE,
            COL_NOTE,
            "Audio",
            "Audio Meaning",
        ]

    def templates(self) -> list[dict[str, str]]:
        return [card("Чтение", self.id, 1), card("На слух", self.id, 2)]

    def css(self, theme: Theme) -> str:
        return theme_css(theme) + "\n" + assets.css("chinese")

    def note_fields(self, row: Row, *, audio_q: str, audio_a: str) -> list[str]:
        pinyin = row.extra.get(COL_PINYIN, "")
        return [
            row.question,
            colour_hanzi(row.question, pinyin),
            colour_pinyin(pinyin),
            row.answer,
            row.extra.get(COL_EXAMPLE, ""),
            row.extra.get(COL_NOTE, ""),
            audio_q,
            audio_a,
        ]
