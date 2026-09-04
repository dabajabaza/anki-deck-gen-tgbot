"""Собрать `themes/preview.html` — как выглядят Карточки в каждом Оформлении.

Страница нужна, чтобы выбрать тему, не собирая колоду и не открывая Anki: четыре
состояния Карточки (лицо и оборот у «Простой» и у «Простой (с вводом ответа)»)
в каждой теме, рядом — стоковый стиль Anki для сравнения, плюс переключатель
ночного режима.

Шаблоны и CSS берутся из пакета, а не переписываются здесь: тема, добавленная в
`notetypes/theme.py`, появляется на странице сама. Каждая ячейка — iframe со
своим документом: у тем есть правила для `body.card`, и в одном документе они
переопределяли бы друг друга.

Запуск: `uv run python scripts/build_theme_preview.py` (страница пересобирается
на месте). `tests/test_theme_preview.py` следит, что в репозитории лежит именно
то, что собирается сейчас.
"""

import argparse
import html
from pathlib import Path

from anki_deck_gen import notetypes
from anki_deck_gen.bot import texts
from anki_deck_gen.domain import Theme
from anki_deck_gen.notetypes import stock, theme

REPO = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = REPO / "themes" / "preview.html"

# Стиль, который Anki кладёт под карточку сам (`ts/reviewer/reviewer.scss`,
# проверено 2026-09-04). Тема его дополняет, поэтому в превью он тоже нужен —
# иначе страница показала бы то, чего у человека в Anki не будет.
ANKI_BASE_CSS = """
hr { background-color: darkgray; margin: 1em 0; border: none; height: 1px; }
body { margin: 20px; overflow-wrap: break-word; }
body.nightMode { background-color: #2c2c2c; color: #fcfcfc; }
#typeans { width: 100%; box-sizing: border-box; line-height: 1.75; }
code#typeans { white-space: pre-wrap; font-variant-ligatures: none; }
.typeGood { background: #afa; color: black; }
.typeBad { color: black; background: #faa; }
.typeMissed { color: black; background: #ccc; }
.replay-button { text-decoration: none; display: inline-flex; vertical-align: middle; margin: 3px; }
.replay-button svg { width: 40px; height: 40px; }
.replay-button svg circle { fill: #fff; stroke: #414141; }
.replay-button svg path { fill: #414141; }
"""

# Стоковый CSS типа записи (`rslib`, `styling.css`) — только для колонки сравнения:
# сам генератор его больше не ставит, колоды собираются с темой (A15).
ANKI_STOCK_CSS = (
    ".card {\n"
    "    font-family: arial;\n"
    "    font-size: 20px;\n"
    "    line-height: 1.5;\n"
    "    text-align: center;\n"
    "    color: black;\n"
    "    background-color: white;\n"
    "}\n"
)

# Кнопка озвучки — та же разметка, что Anki подставляет вместо `[sound:…]`
# (`rslib`; AnkiDroid оборачивает svg ещё и в span).
PLAY_BUTTON = (
    '<a class="replay-button" href="#" onclick="return false">'
    '<svg class="playImage" viewBox="0 0 64 64">'
    '<circle cx="32" cy="32" r="29"/>'
    '<path d="M56.502,32.301l-37.502,20.101l0.329,-40.804l37.173,20.703Z"/>'
    "</svg></a>"
)

QUESTION = "Could you describe your symptoms?"
ANSWER = "Не могли бы вы описать свои симптомы?"

# Поле ввода и разбор ответа Anki рисует сам, с inline-шрифтом поля (Arial 20px).
TYPE_INPUT = (
    "<center>\n"
    "<input type=text id=typeans style=\"font-family: 'Arial'; font-size: 20px;\">\n"
    "</center>"
)
TYPE_COMPARISON = (
    "<div style=\"font-family: 'Arial'; font-size: 20px\"><code id=typeans>"
    "<span class=typeGood>Не могли бы вы описать </span><span class=typeBad>ваши</span>"
    "<span class=typeGood> симптомы?</span><br><span id=typearrow>&darr;</span><br>"
    "<span class=typeGood>Не могли бы вы описать </span><span class=typeMissed>свои</span>"
    "<span class=typeGood> симптомы?</span></code></div>"
)

# Какие Карточки показываем: тип записи, подпись строки и пояснение.
CARDS = [
    ("basic", "Простая", "лицо", "вопрос с озвучкой", 0, "qfmt"),
    ("basic", "Простая", "оборот", "ответ с озвучкой", 0, "afmt"),
    ("basic-typing", "С вводом ответа", "лицо", "поле, куда набирают ответ", 0, "qfmt"),
    ("basic-typing", "С вводом ответа", "оборот", "Anki подсветил ошибку", 0, "afmt"),
]


def fill(template: str, *, front_side: str = "", typed: str = "") -> str:
    """Подставить в шаблон Anki содержимое полей — как это делает сам Anki."""
    return (
        template.replace("{{FrontSide}}", front_side)
        .replace(stock.AUDIO_FRONT, PLAY_BUTTON)
        .replace(stock.AUDIO_BACK, PLAY_BUTTON)
        .replace("{{type:Back}}", typed)
        .replace("{{Front}}", QUESTION)
        .replace("{{Back}}", ANSWER)
    )


def card_html(note_type_id: str, ordinal: int, side: str) -> str:
    """Готовый HTML одной стороны Карточки выбранного Типа записи."""
    template = notetypes.get(note_type_id).templates()[ordinal]
    question = fill(template["qfmt"], typed=TYPE_INPUT)
    if side == "qfmt":
        return question
    return fill(template["afmt"], front_side=question, typed=TYPE_COMPARISON)


def frame(css: str, body: str, title: str) -> str:
    document = (
        '<!doctype html><html><head><meta charset="utf-8">'
        f"<style>{ANKI_BASE_CSS}{css}</style></head>"
        f'<body class="card card1">{body}</body></html>'
    )
    return (
        f'<iframe class="cardframe" title="{html.escape(title)}" '
        f'srcdoc="{html.escape(document, quote=True)}"></iframe>'
    )


def columns() -> list[tuple[str, str, str, str]]:
    """Колонки страницы: подпись, пояснение, CSS, метка. Первая — стоковый Anki."""
    described = {
        Theme.CARD: "Светлая карточка с тенью на серо-голубом фоне.",
        Theme.BOOK: "Слоновая кость, антиква, двойная линейка.",
    }
    result = [
        (
            "Стоковый Anki",
            "Arial 20, чёрное на белом. Так выглядит колода без темы.",
            ANKI_STOCK_CSS,
            "для сравнения",
        )
    ]
    for value in Theme:
        result.append((texts.theme_name(value), described[value], theme.css_for(value), ""))
    return result


PAGE_CSS = """
:root {
  --bg: #eef0f4; --surface: #ffffff; --ink: #1b2430; --muted: #5b6b7f; --line: #d6dce5;
  --accent: #2b4fc4; --accent-ink: #ffffff; --chip-bg: #e7eaef; --chip-ink: #4a5768;
  --code-bg: #f6f7f9;
  color-scheme: light;
}
@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) {
    --bg: #14171c; --surface: #1e232a; --ink: #e8ebf0; --muted: #98a3b3; --line: #2c333d;
    --accent: #7b97f0; --accent-ink: #14171c; --chip-bg: #2a313b; --chip-ink: #b6c0cd;
    --code-bg: #171b21;
    color-scheme: dark;
  }
}
:root[data-theme="dark"] {
  --bg: #14171c; --surface: #1e232a; --ink: #e8ebf0; --muted: #98a3b3; --line: #2c333d;
  --accent: #7b97f0; --accent-ink: #14171c; --chip-bg: #2a313b; --chip-ink: #b6c0cd;
  --code-bg: #171b21;
  color-scheme: dark;
}
body {
  background: var(--bg); color: var(--ink);
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Noto Sans", Arial,
    sans-serif;
  font-size: 15px; line-height: 1.5; margin: 0;
}
main { max-width: 1440px; margin: 0 auto; padding: 32px 24px 64px; }
header {
  display: flex; flex-wrap: wrap; align-items: flex-end; justify-content: space-between;
  gap: 16px 32px; margin-bottom: 28px;
}
h1 { font-size: 28px; font-weight: 600; letter-spacing: -0.01em; margin: 0 0 6px;
  text-wrap: balance; }
.lead { color: var(--muted); margin: 0; max-width: 62ch; }
.switch {
  display: inline-flex; align-items: center; gap: 10px; border: 1px solid var(--line);
  background: var(--surface); color: var(--ink); border-radius: 999px;
  padding: 8px 14px 8px 10px; font: inherit; font-weight: 500; cursor: pointer;
}
.switch:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; }
.switch .knob {
  width: 34px; height: 20px; border-radius: 999px; background: var(--line);
  position: relative; transition: background .2s;
}
.switch .knob::after {
  content: ""; position: absolute; top: 2px; left: 2px; width: 16px; height: 16px;
  border-radius: 50%; background: var(--surface); box-shadow: 0 1px 2px rgba(0,0,0,.25);
  transition: transform .2s;
}
.switch[aria-pressed="true"] .knob { background: var(--accent); }
.switch[aria-pressed="true"] .knob::after { transform: translateX(14px); }
@media (prefers-reduced-motion: reduce) {
  .switch .knob, .switch .knob::after { transition: none; }
}
.board { overflow-x: auto; padding-bottom: 8px; }
.grid {
  display: grid; grid-template-columns: 140px repeat(3, 320px); gap: 14px 16px;
  align-items: stretch; min-width: max-content;
}
.colhead { padding: 0 4px 6px; border-bottom: 2px solid var(--line); }
.colname { font-weight: 600; font-size: 17px; display: flex; align-items: center; gap: 8px; }
.colnote { color: var(--muted); font-size: 13px; margin-top: 2px; }
.chip {
  font-size: 11px; font-weight: 600; letter-spacing: 0.04em; text-transform: uppercase;
  border-radius: 999px; padding: 2px 8px; background: var(--chip-bg); color: var(--chip-ink);
}
.rowhead { display: flex; flex-direction: column; justify-content: center; padding-right: 8px; }
.rowname { font-weight: 500; }
.rownote { color: var(--muted); font-size: 13px; }
.cardframe {
  width: 320px; height: 380px; border: 1px solid var(--line); border-radius: 10px;
  background: #fff; display: block;
}
section.notes {
  margin-top: 40px; display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
  gap: 24px 40px;
}
h2 { font-size: 17px; font-weight: 600; margin: 0 0 8px; }
section.notes ul { margin: 0; padding-left: 1.1em; }
section.notes li { margin: 4px 0; max-width: 62ch; }
details { margin-top: 12px; border: 1px solid var(--line); border-radius: 10px;
  background: var(--surface); }
summary { cursor: pointer; padding: 10px 14px; font-weight: 500; }
summary:focus-visible { outline: 2px solid var(--accent); outline-offset: -2px;
  border-radius: 10px; }
pre {
  margin: 0; padding: 12px 14px; overflow-x: auto; background: var(--code-bg);
  border-top: 1px solid var(--line); border-radius: 0 0 10px 10px;
  font: 12.5px/1.5 ui-monospace, "JetBrains Mono", Menlo, Consolas, monospace;
}
code { font-family: inherit; }
"""

PAGE_SCRIPT = """
(function () {
  var button = document.getElementById('night');
  var night = false;
  function paint(frame) {
    var doc = frame.contentDocument;
    if (!doc || !doc.body) return;
    doc.body.classList.toggle('nightMode', night);
    doc.body.classList.toggle('night_mode', night);
  }
  var frames = Array.prototype.slice.call(document.querySelectorAll('iframe.cardframe'));
  frames.forEach(function (frame) {
    frame.addEventListener('load', function () { paint(frame); });
  });
  button.addEventListener('click', function () {
    night = !night;
    button.setAttribute('aria-pressed', String(night));
    frames.forEach(paint);
  });
})();
"""


def render() -> str:
    """Собрать страницу целиком. Детерминированно: тот же код — тот же файл."""
    cols = columns()

    heads = ['<div class="corner"></div>']
    for name, note, _, chip in cols:
        badge = f'<span class="chip">{chip}</span>' if chip else ""
        heads.append(
            f'<div class="colhead"><div class="colname">{name}{badge}</div>'
            f'<div class="colnote">{note}</div></div>'
        )

    cells = []
    for note_type_id, label, side_name, side_note, ordinal, side in CARDS:
        cells.append(
            f'<div class="rowhead"><span class="rowname">{label}, {side_name}</span>'
            f'<span class="rownote">{side_note}</span></div>'
        )
        body = card_html(note_type_id, ordinal, side)
        for name, _, css, _ in cols:
            cells.append(frame(css, body, f"{name}: {label}, {side_name}"))

    details = "".join(
        f"<details><summary>CSS темы «{name}»</summary>"
        f"<pre><code>{html.escape(css)}</code></pre></details>"
        for name, _, css, chip in cols
        if not chip
    )

    return f"""<title>Темы карточек anki-deck-gen</title>
<!-- Страница собрана scripts/build_theme_preview.py; правьте CSS в
     src/anki_deck_gen/notetypes/theme.py и пересоберите её. -->
<style>{PAGE_CSS}</style>
<main>
<header>
  <div>
    <h1>Темы карточек anki-deck-gen</h1>
    <p class="lead">Одна и та же запись во всех оформлениях, которые предлагает бот.
    Переключатель показывает ночной режим Anki.</p>
  </div>
  <button class="switch" id="night" type="button" aria-pressed="false">
    <span class="knob" aria-hidden="true"></span>Ночной режим</button>
</header>
<div class="board"><div class="grid">
{"".join(heads)}
{"".join(cells)}
</div></div>
<section class="notes">
  <div>
    <h2>Общее у тем</h2>
    <ul>
      <li>Меняется только CSS типа записи. Поля, шаблоны и model_id прежние, поэтому
      Anki обновит оформление и в уже импортированных колодах.</li>
      <li>Шрифты только системные: веб-шрифт пришлось бы класть файлом в каждую колоду.</li>
      <li>Кнопка озвучки — контурный круг в цвете темы вместо стокового залитого.</li>
      <li>Ночной режим по классу card nightMode, который ставят Anki, AnkiDroid и
      AnkiMobile.</li>
      <li>Подсветка набранного ответа мягче стоковой: вместо чистых зелёного и красного.</li>
    </ul>
  </div>
  <div>
    <h2>Чем отличаются</h2>
    <ul>
      <li><strong>Карточка.</strong> Узнаваемый вид карточки: светлая панель с тенью.
      Фон вокруг рисуется тенью, поэтому работает и в старых версиях Anki.</li>
      <li><strong>Учебник.</strong> Антиква и двойная линейка, как в печатном пособии.
      На Android засечки заменит Noto Serif.</li>
    </ul>
  </div>
</section>
<section class="notes" style="grid-template-columns: 1fr">
  <div>
    <h2>CSS</h2>
    {details}
  </div>
</section>
</main>
<script>{PAGE_SCRIPT}</script>
"""


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help="куда положить страницу; по умолчанию themes/preview.html в репозитории",
    )
    args = parser.parse_args(argv)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(render(), encoding="utf-8")
    print(f"Готово: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
