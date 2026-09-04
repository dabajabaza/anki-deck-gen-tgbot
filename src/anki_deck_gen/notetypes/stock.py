"""Стоковые шаблоны Anki — байт в байт.

Источник: `ankitects/anki`, `rslib/src/notetype/stock.rs` (проверено по исходникам
2026-09-03). Стоковый CSS (Arial 20px, чёрное на белом) не воспроизводится: стиль
даёт notetypes/theme.py. Имена полей `Front`/`Back` в русской
локализации Anki намеренно не переведены, так что и у русскоязычного
пользователя стоковая «Простая» имеет ровно эти шаблоны — наши типы выглядят
для него родными.

Наши типы добавляют к стоковым только ссылки на поля озвучки; `strip_audio`
снимает их обратно, и тест сравнивает результат с этими константами.
"""

STOCK_QFMT = "{{Front}}"
STOCK_AFMT = "{{FrontSide}}\n\n<hr id=answer>\n\n{{Back}}"

STOCK_REVERSE_QFMT = "{{Back}}"
STOCK_REVERSE_AFMT = "{{FrontSide}}\n\n<hr id=answer>\n\n{{Front}}"

STOCK_TYPE_QFMT = "{{Front}}\n\n{{type:Back}}"
# На обороте карточки с вводом ответа Anki ставит {{Front}}, а НЕ {{FrontSide}}:
# лицевая сторона уже содержит разбор набранного, и через FrontSide он выводится
# второй раз, да ещё с лишней чертой — Anki подставляет <hr id=answer> перед
# разбором сам, когда видит FrontSide (`typeAnsAnswerFilter`).
STOCK_TYPE_AFMT = "{{Front}}\n\n<hr id=answer>\n\n{{type:Back}}"

# Имена шаблонов карточек — тоже из локализации (`notetypes-card-1-name`).
CARD_1 = "Карточка 1"
CARD_2 = "Карточка 2"

FIELD_FRONT = "Front"
FIELD_BACK = "Back"
FIELD_AUDIO_FRONT = "Audio Front"
FIELD_AUDIO_BACK = "Audio Back"

AUDIO_FRONT = "{{Audio Front}}"
AUDIO_BACK = "{{Audio Back}}"


def strip_audio(template: str) -> str:
    """Шаблон без ссылок на озвучку — то, что должно совпасть со стоковым."""
    return template.replace(AUDIO_FRONT, "").replace(AUDIO_BACK, "")
