"""Откуда берётся Таблица: файл на диске, ссылка Google Sheets.

Документ Telegram скачивает бот сам (ему нужен `Bot.download`), здесь — то, что
не зависит от чата: распознавание ссылки, адрес экспорта и сам запрос к Google.
"""

import re
from email.message import Message
from pathlib import Path

import aiohttp

from anki_deck_gen.errors import SheetNotShared, SheetUnreachable, UnsupportedSource

SHEETS_URL = re.compile(r"https://docs\.google\.com/spreadsheets/d/([A-Za-z0-9_-]+)")

# Хосты и типы ответа, которые означают «таблица закрыта», а не «Google лежит».
# Закрытая таблица нередко отдаёт 200 со страницей логина — код ответа тут не
# показатель, показатель Content-Type.
_LOGIN_HOST = "accounts.google.com"
_HTML = "text/html"
_XLSX_SUFFIX = ".xlsx"


def extract_sheets_url(text: str | None) -> str | None:
    """Первая ссылка на Google-таблицу в тексте, целиком (до пробела), или None."""
    if not text:
        return None
    match = SHEETS_URL.search(text)
    if match is None:
        return None
    end = match.end()
    while end < len(text) and not text[end].isspace():
        end += 1
    return text[match.start() : end]


def sheet_id(url: str) -> str:
    match = SHEETS_URL.search(url)
    if match is None:
        raise UnsupportedSource(f"not a Google Sheets link: {url!r}")
    return match.group(1)


def export_url(url: str) -> str:
    """Экспорт всего документа как xlsx: все вкладки разом. `gid` в ссылке игнорируется
    сознательно — вкладка = подколода, значит нужны все (круг 3, Q23)."""
    return f"https://docs.google.com/spreadsheets/d/{sheet_id(url)}/export?format=xlsx"


async def fetch_google_sheet(
    url: str,
    *,
    timeout_s: float = 30.0,
    session: aiohttp.ClientSession | None = None,
) -> tuple[bytes, str | None]:
    """Скачать документ; вернуть байты xlsx и заголовок таблицы (из Content-Disposition).

    `session` — для тестов и для бота, который держит одну сессию; без неё
    открывается своя на один вызов.
    """
    own_session = session is None
    client = session or aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=timeout_s))
    try:
        async with client.get(export_url(url), allow_redirects=True) as response:
            if response.url.host == _LOGIN_HOST or response.status in (401, 403, 404):
                raise SheetNotShared(f"HTTP {response.status} at {response.url.host}")
            if response.status >= 500:
                raise SheetUnreachable(f"HTTP {response.status}")
            if response.status >= 400:
                raise SheetUnreachable(f"HTTP {response.status}")
            content_type = response.headers.get("Content-Type", "")
            if content_type.startswith(_HTML):
                raise SheetNotShared(f"got {content_type} instead of a workbook")
            data = await response.read()
            title = _title_from_disposition(response.headers.get("Content-Disposition"))
    except (aiohttp.ClientError, TimeoutError) as exc:
        raise SheetUnreachable(f"{type(exc).__name__}: {exc}") from exc
    finally:
        if own_session:
            await client.close()
    return data, title


def read_file(path: Path) -> tuple[bytes, str]:
    """Файл с диска для CLI: байты и имя без расширения — имя колоды по умолчанию."""
    return path.read_bytes(), path.stem


def _title_from_disposition(value: str | None) -> str | None:
    """Имя файла из Content-Disposition, включая RFC 2231 `filename*=UTF-8''…`.

    email.message разбирает оба варианта и снимает процентное кодирование —
    свой парсер тут был бы хуже стандартного.
    """
    if not value:
        return None
    message = Message()
    message["Content-Disposition"] = value
    filename = message.get_filename()
    if not filename:
        return None
    if filename.lower().endswith(_XLSX_SUFFIX):
        filename = filename[: -len(_XLSX_SUFFIX)]
    return filename.strip() or None
