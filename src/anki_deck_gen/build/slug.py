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
    """Имя для файла кэша озвучки: детерминированное, непустое, не длиннее лимита ФС.

    Длинная фраза на кириллице легко переваливает за 255 байт имени файла —
    тогда хвост заменяется хэшем, а начало остаётся читаемым.
    """
    base = sanitize(text.lower())
    digest = hashlib.sha1(text.encode("utf-8")).hexdigest()
    if not base:
        return digest[:12]
    if len(base.encode("utf-8")) > _MAX_SLUG_BYTES:
        return f"{base[:60]}_{digest[:10]}"
    return base


def apkg_filename(deck_name: str) -> str:
    base = sanitize(deck_name, lower=True).strip("_") or "deck"
    return f"{base}.apkg"
