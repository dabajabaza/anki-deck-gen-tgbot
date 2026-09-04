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

Сам CSS лежит файлами в `assets/css` — так его подсвечивает редактор; здесь
только соответствие «тема → файл».
"""

from anki_deck_gen.domain import Theme
from anki_deck_gen.notetypes import assets

FILES: dict[Theme, str] = {Theme.CARD: "card", Theme.BOOK: "book"}


def css_for(theme: Theme) -> str:
    return assets.css(FILES[theme])
