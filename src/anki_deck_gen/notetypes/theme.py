"""Оформление карточек: две темы CSS для стоковых Типов записи (ARCHITECTURE A15).

Факты об Anki, на которые опирается CSS (проверено по исходникам 2026-09-04):

- класс ``card`` стоит на ``body``; ночной режим добавляет ``nightMode`` на десктопе,
  в AnkiDroid и AnkiMobile — отсюда ``.card.nightMode``;
- поле ввода и сравнение ответа Anki рисует сам, с inline-шрифтом поля (Arial 20px),
  и без ``!important`` тема до них не достаёт;
- кнопка озвучки — svg «круг + треугольник» 40px; AnkiDroid оборачивает svg в span и
  задаёт min-width 32px селектором ``.replay-button span svg`` — поэтому селекторов два;
- шрифты только системные: веб-шрифт пришлось бы класть файлом в каждую колоду.

Смена CSS не требует нового ``model_id``: при импорте Anki обновляет тип с тем же id,
если поля и шаблоны совпали, а mtime новее (rslib, ``update_or_duplicate_notetype``;
genanki ставит mtime = время сборки). Смена полей — требует (A1).

Вьетнамский тип со своим CSS тему не применяет (``NoteType.themed = False``).
"""

from anki_deck_gen.domain import Theme

CARD_CSS = """\
/* Тема «Карточка»: белая карточка с мягкой тенью на серо-голубом фоне, синяя кнопка озвучки. */
.card {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Noto Sans",
        "Helvetica Neue", Arial, sans-serif;
    font-size: 24px;
    line-height: 1.4;
    text-align: center;
    color: #1f2a37;
    background-color: #ffffff;
    width: min(26em, calc(100% - 28px));
    margin: 28px auto;
    padding: 1.8em 1.4em;
    box-sizing: border-box;
    overflow-wrap: break-word;
    border-radius: 22px;
    box-shadow:
        0 1px 3px rgba(31, 42, 55, 0.08),
        0 12px 32px rgba(31, 42, 55, 0.12),
        0 0 0 100vmax #dfe5ec;
}
hr#answer {
    border: 0;
    height: 1px;
    margin: 1.3em 0;
    background: #e3e8ee;
}
.replay-button {
    padding: 0.25em;
    margin: 0 0 0 0.1em;
    vertical-align: middle;
}
/* Размер в em: иконка идёт по строке и растёт вместе с текстом, в том числе когда
   человек увеличил шрифт на телефоне. 24 px — пол, чтобы в мелкий шрифт не съёжилась. */
.replay-button svg, .replay-button span svg {
    width: 1em;
    height: 1em;
    min-width: 24px;
    min-height: 24px;
}
.replay-button svg circle { fill: none; stroke: #2b4fc4; stroke-width: 4.5; }
.replay-button svg path { fill: #2b4fc4; }
/* Поле ввода и сравнение Anki рисует с inline-шрифтом (Arial 20px): нужен !important. */
input#typeans {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Noto Sans",
        "Helvetica Neue", Arial, sans-serif !important;
    font-size: 22px !important;
    line-height: 1.4;
    text-align: center;
    padding: 0.45em 0.7em;
    margin-top: 0.6em;
    border: 2px solid #d9e0e8;
    border-radius: 14px;
    background: #f5f7fa;
    color: inherit;
    outline: none;
    max-width: 22em;
}
input#typeans:focus { border-color: #2b4fc4; background: #ffffff; }
code#typeans {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Noto Sans",
        "Helvetica Neue", Arial, sans-serif !important;
    font-size: 22px !important;
    line-height: 1.6;
}
.typeGood { background: #d7f0dc; color: #1b4d2a; border-radius: 4px; }
.typeBad {
    background: #fadbd6; color: #7a2119; border-radius: 4px;
    text-decoration: line-through;
}
.typeMissed { background: #e6eaef; color: #56606d; border-radius: 4px; }
#typearrow { color: #8b96a5; }

.card.nightMode {
    color: #e7eaf0;
    background-color: #262a31;
    box-shadow:
        0 1px 3px rgba(0, 0, 0, 0.4),
        0 12px 32px rgba(0, 0, 0, 0.35),
        0 0 0 100vmax #15181d;
}
.nightMode hr#answer { background: #3a404a; }
.nightMode .replay-button svg circle { stroke: #7b97f0; }
.nightMode .replay-button svg path { fill: #7b97f0; }
.nightMode input#typeans { background: #1e2228; border-color: #3d434d; color: #e7eaf0; }
.nightMode input#typeans:focus { border-color: #7b97f0; }
.nightMode .typeGood { background: #22513a; color: #d6f3de; }
.nightMode .typeBad { background: #5e2722; color: #fadad5; }
.nightMode .typeMissed { background: #3b3f47; color: #d8d6d0; }
"""

BOOK_CSS = """\
/* Тема «Учебник»: слоновая кость, антиква, двойная линейка, кирпичный акцент. */
.card {
    font-family: Charter, "Bitstream Charter", "Iowan Old Style", Georgia, "Noto Serif",
        "Times New Roman", serif;
    font-size: 25px;
    line-height: 1.38;
    text-align: center;
    color: #2a2420;
    background-color: #fbf7ee;
    max-width: 30em;
    margin: 0 auto;
    padding: 1.8em 1.2em;
    box-sizing: border-box;
    overflow-wrap: break-word;
}
hr#answer {
    border: 0;
    border-top: 1px solid #b7a58b;
    border-bottom: 1px solid #b7a58b;
    height: 3px;
    width: 6em;
    margin: 1.3em auto;
    background: transparent;
}
.replay-button {
    padding: 0.25em;
    margin: 0 0 0 0.1em;
    vertical-align: middle;
}
/* Размер в em: иконка идёт по строке и растёт вместе с текстом, в том числе когда
   человек увеличил шрифт на телефоне. 24 px — пол, чтобы в мелкий шрифт не съёжилась. */
.replay-button svg, .replay-button span svg {
    width: 1em;
    height: 1em;
    min-width: 24px;
    min-height: 24px;
}
.replay-button svg circle { fill: none; stroke: #b4432f; stroke-width: 4.5; }
.replay-button svg path { fill: #b4432f; }
/* Поле ввода и сравнение Anki рисует с inline-шрифтом (Arial 20px): нужен !important. */
input#typeans {
    font-family: Charter, "Bitstream Charter", "Iowan Old Style", Georgia, "Noto Serif",
        "Times New Roman", serif !important;
    font-size: 23px !important;
    line-height: 1.4;
    text-align: center;
    padding: 0.3em 0.4em;
    margin-top: 0.6em;
    border: 0;
    border-bottom: 2px solid #b7a58b;
    border-radius: 0;
    background: transparent;
    color: inherit;
    outline: none;
    max-width: 22em;
}
input#typeans:focus { border-bottom-color: #b4432f; }
code#typeans {
    font-family: Charter, "Bitstream Charter", "Iowan Old Style", Georgia, "Noto Serif",
        "Times New Roman", serif !important;
    font-size: 23px !important;
    line-height: 1.6;
}
.typeGood { background: #dcebd3; color: #2c4a22; border-radius: 3px; }
.typeBad {
    background: #f3d3c9; color: #7a2b1c; border-radius: 3px;
    text-decoration: line-through;
}
.typeMissed { background: #e9e1d1; color: #5c5145; border-radius: 3px; }
#typearrow { color: #9a8c76; }

.card.nightMode { color: #ece5d8; background-color: #221f1c; }
.nightMode hr#answer { border-color: #6b5e4d; }
.nightMode .replay-button svg circle { stroke: #e0735f; }
.nightMode .replay-button svg path { fill: #e0735f; }
.nightMode input#typeans { border-bottom-color: #6b5e4d; color: #ece5d8; }
.nightMode input#typeans:focus { border-bottom-color: #e0735f; }
.nightMode .typeGood { background: #2f4d2a; color: #d9efd0; }
.nightMode .typeBad { background: #5e2b20; color: #f7d6cc; }
.nightMode .typeMissed { background: #3f392f; color: #ddd4c4; }
"""

CSS: dict[Theme, str] = {Theme.CARD: CARD_CSS, Theme.BOOK: BOOK_CSS}


def css_for(theme: Theme) -> str:
    return CSS[theme]
