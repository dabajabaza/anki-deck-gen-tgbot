"""Ссылка Google Sheets: распознавание, адрес экспорта, вердикты по ответу Google."""

from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer

from anki_deck_gen.errors import SheetNotShared, SheetUnreachable, UnsupportedSource
from anki_deck_gen.tables.sources import (
    export_url,
    extract_sheets_url,
    fetch_google_sheet,
    sheet_id,
)

SHEET = "https://docs.google.com/spreadsheets/d/1AbC-xyz_09/edit#gid=123"


def test_extract_takes_the_whole_link_up_to_whitespace() -> None:
    assert extract_sheets_url(f"вот таблица {SHEET} посмотри") == SHEET
    assert extract_sheets_url("никаких ссылок") is None
    assert extract_sheets_url(None) is None


def test_export_url_drops_the_gid_and_asks_for_the_whole_workbook() -> None:
    assert sheet_id(SHEET) == "1AbC-xyz_09"
    assert (
        export_url(SHEET) == "https://docs.google.com/spreadsheets/d/1AbC-xyz_09/export?format=xlsx"
    )


def test_a_non_sheets_link_is_unsupported() -> None:
    with pytest.raises(UnsupportedSource):
        export_url("https://example.com/file.xlsx")


class _Fake:
    """Сервер-заглушка: что ответить на ближайший запрос экспорта."""

    def __init__(self) -> None:
        self.status = 200
        self.body = b"PK\x03\x04fake"
        self.headers: dict[str, str] = {
            "Content-Type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            "Content-Disposition": "attachment; filename*=UTF-8''My%20Sheet.xlsx",
        }

    async def handle(self, request: web.Request) -> web.Response:
        return web.Response(status=self.status, body=self.body, headers=self.headers)


@pytest_asyncio.fixture
async def fake() -> AsyncIterator[tuple[_Fake, TestClient]]:
    fake = _Fake()
    app = web.Application()
    app.router.add_get("/spreadsheets/d/{sheet_id}/export", fake.handle)
    async with TestClient(TestServer(app)) as client:
        yield fake, client


def _patch_export(monkeypatch: pytest.MonkeyPatch, client: TestClient) -> None:
    # Подменяем адрес экспорта на локальный сервер; сама логика ответа не меняется.
    monkeypatch.setattr(
        "anki_deck_gen.tables.sources.export_url",
        lambda url: str(client.make_url(f"/spreadsheets/d/{sheet_id(url)}/export")),
    )


async def test_a_shared_sheet_yields_bytes_and_a_decoded_title(
    fake: tuple[_Fake, TestClient], monkeypatch: pytest.MonkeyPatch
) -> None:
    server, client = fake
    _patch_export(monkeypatch, client)
    data, title = await fetch_google_sheet(SHEET, session=client.session)
    assert data == server.body
    assert title == "My Sheet"


async def test_an_html_answer_means_the_sheet_is_not_shared(
    fake: tuple[_Fake, TestClient], monkeypatch: pytest.MonkeyPatch
) -> None:
    server, client = fake
    server.headers = {"Content-Type": "text/html; charset=utf-8"}
    server.body = b"<html>Sign in</html>"
    _patch_export(monkeypatch, client)
    with pytest.raises(SheetNotShared):
        await fetch_google_sheet(SHEET, session=client.session)


async def test_forbidden_means_not_shared(
    fake: tuple[_Fake, TestClient], monkeypatch: pytest.MonkeyPatch
) -> None:
    server, client = fake
    server.status = 403
    _patch_export(monkeypatch, client)
    with pytest.raises(SheetNotShared):
        await fetch_google_sheet(SHEET, session=client.session)


async def test_a_server_error_is_unreachable_not_unshared(
    fake: tuple[_Fake, TestClient], monkeypatch: pytest.MonkeyPatch
) -> None:
    server, client = fake
    server.status = 503
    _patch_export(monkeypatch, client)
    with pytest.raises(SheetUnreachable):
        await fetch_google_sheet(SHEET, session=client.session)


async def test_a_quoted_plain_filename_also_gives_a_title(
    fake: tuple[_Fake, TestClient], monkeypatch: pytest.MonkeyPatch
) -> None:
    server, client = fake
    server.headers["Content-Disposition"] = 'attachment; filename="Phrases.xlsx"'
    _patch_export(monkeypatch, client)
    _, title = await fetch_google_sheet(SHEET, session=client.session)
    assert title == "Phrases"


def test_google_style_disposition_prefers_the_rfc2231_name() -> None:
    """Google шлёт `filename=".xlsx"` и `filename*=UTF-8''…` разом — берём настоящее имя."""
    from anki_deck_gen.tables.sources import _title_from_disposition

    header = (
        'attachment; filename=".xlsx"; '
        "filename*=UTF-8''%D0%A4%D0%BE%D1%80%D0%BC%D1%83%D0%BB%D1%8B%20"
        "%D0%B2%D0%B5%D0%B6%D0%BB%D0%B8%D0%B2%D0%BE%D1%81%D1%82%D0%B8.xlsx"
    )
    assert _title_from_disposition(header) == "Формулы вежливости"
    assert _title_from_disposition('attachment; filename="Deck.xlsx"') == "Deck"
    assert _title_from_disposition('attachment; filename=".xlsx"') is None
    assert _title_from_disposition(None) is None
