"""Безопасные имена: файла колоды, mp3 в кэше, меток.

Имена файлов дополнительно латинизируются (`anyascii`, ISC, чистый python — на
FreeBSD без Rust ставится колесом): .apkg уезжает в Telegram, оттуда в кэш
Android, и по дороге кириллица в имени успевает потерять кодировку — AnkiDroid
отказывается открывать файл со «stream did not contain valid UTF-8», хотя внутри
архива всё корректно. Латиница проходит любой такой пересыл.

Метки латинизации НЕ подлежат: они видны человеку в Anki, «глаголы» должны
остаться «глаголами». Поэтому `sanitize()` работает с юникодом, а латиница —
отдельным шагом в именах файлов.
"""

import hashlib
import re

from anyascii import anyascii

_UNSAFE = re.compile(r"[^\w\s-]")
_MAX_SLUG_BYTES = 150  # запас до лимита имени файла в 255 байт


def sanitize(text: str, *, lower: bool = False) -> str:
    """Убрать всё, кроме букв, цифр, `_` и `-`; пробелы → `_` (перенос из старого генератора)."""
    result = _UNSAFE.sub("", text).replace(" ", "_")
    return result.lower() if lower else result


def slug(text: str) -> str:
    """Имя файла кэша озвучки: читаемое начало плюс хэш полного текста.

    Хэш обязателен всегда, не только для длинных фраз: `sanitize()` выбрасывает
    пунктуацию, и «Hi» с «Hi!» или «a/b» с «ab» дали бы одно имя — вторая фраза
    молча получила бы чужой mp3 из кэша.

    Хэш считается от ИСХОДНОГО текста, а не от латинизированного: «шар» и «schar»
    не должны делить один файл.

    Формат имени — часть контракта кэша: смена формата обнуляет кэш (файлы старого
    имени никто не прочитает и не удалит). Формат `{base}_{digest}` введён
    2026-09-03, латиница в `base` — 2026-09-04; кириллические файлы, записанные
    между этими датами, остались в кэше сиротами.
    """
    base = sanitize(anyascii(text).lower())
    digest = hashlib.sha1(text.encode("utf-8")).hexdigest()[:10]
    if not base:
        return digest
    if len(base.encode("utf-8")) > _MAX_SLUG_BYTES:
        base = base[:60]
    return f"{base}_{digest}"


def apkg_filename(deck_name: str) -> str:
    base = sanitize(anyascii(deck_name), lower=True).strip("_") or "deck"
    return f"{base}.apkg"
