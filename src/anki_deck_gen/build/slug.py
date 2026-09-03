"""Безопасные имена: файла колоды, mp3 в кэше, меток."""

import hashlib
import re

_UNSAFE = re.compile(r"[^\w\s-]")
_MAX_SLUG_BYTES = 150  # запас до лимита имени файла в 255 байт; кириллица — 2 байта на символ


def sanitize(text: str, *, lower: bool = False) -> str:
    """Убрать всё, кроме букв, цифр, `_` и `-`; пробелы → `_` (перенос из старого генератора)."""
    result = _UNSAFE.sub("", text).replace(" ", "_")
    return result.lower() if lower else result


def slug(text: str) -> str:
    """Имя файла кэша озвучки: читаемое начало плюс хэш полного текста.

    Хэш обязателен всегда, не только для длинных фраз: `sanitize()` выбрасывает
    пунктуацию, и «Hi» с «Hi!» или «a/b» с «ab» дали бы одно имя — вторая фраза
    молча получила бы чужой mp3 из кэша.
    """
    base = sanitize(text.lower())
    digest = hashlib.sha1(text.encode("utf-8")).hexdigest()[:10]
    if not base:
        return digest
    if len(base.encode("utf-8")) > _MAX_SLUG_BYTES:
        base = base[:60]
    return f"{base}_{digest}"


def apkg_filename(deck_name: str) -> str:
    base = sanitize(deck_name, lower=True).strip("_") or "deck"
    return f"{base}.apkg"
