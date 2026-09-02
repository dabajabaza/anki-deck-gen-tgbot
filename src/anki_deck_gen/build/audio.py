"""Озвучка через gTTS с постоянным кэшем. Единственный модуль, знающий о gTTS.

Кэш — `<root>/<lang>/<slug>.mp3`. Одинаковая фраза на одном языке озвучивается
один раз за всю жизнь бота, что бы кто ни присылал; повторный прогон одной
таблицы в сеть не ходит вовсе.
"""

import html
import os
import re
import uuid
from pathlib import Path

import requests
from gtts import gTTS
from gtts.tts import gTTSError

from anki_deck_gen.build.slug import slug
from anki_deck_gen.errors import TtsUnavailable

_TAGS = re.compile(r"<[^>]+>")
_SPACES = re.compile(r"\s+")


def plain_text(text: str) -> str:
    """Текст для озвучки: без HTML-тегов и сущностей — иначе gTTS читает «br» вслух."""
    return _SPACES.sub(" ", html.unescape(_TAGS.sub(" ", text))).strip()


def sound_tag(path: Path) -> str:
    """Ссылка на медиафайл в поле Anki."""
    return f"[sound:{path.name}]"


class AudioCache:
    def __init__(self, root: Path) -> None:
        self.root = root

    def path_for(self, text: str, lang: str) -> Path:
        return self.root / lang.lower() / f"{slug(plain_text(text))}.mp3"

    def ensure(self, text: str, lang: str) -> Path:
        """Вернуть путь к mp3, при необходимости сходив в Google.

        Пишется во временный файл и переименовывается атомарно: сборка, убитая
        посреди записи, иначе оставила бы половину mp3, и кэш отдавал бы её как
        готовую вечно.
        """
        path = self.path_for(text, lang)
        if path.exists():
            return path
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_name(f"{path.name}.{uuid.uuid4().hex}.tmp")
        try:
            gTTS(text=plain_text(text), lang=lang).save(str(temporary))
        except (gTTSError, requests.RequestException, AssertionError, ValueError) as exc:
            # AssertionError — так gTTS отказывается от пустого текста,
            # ValueError — от неизвестного языка.
            temporary.unlink(missing_ok=True)
            raise TtsUnavailable(f"{type(exc).__name__}: {exc}") from exc
        os.replace(temporary, path)
        return path
