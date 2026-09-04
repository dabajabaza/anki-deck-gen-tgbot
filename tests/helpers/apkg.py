"""Чтение .apkg без Anki: zip → collection.anki2 → sqlite."""

import json
import sqlite3
import zipfile
from collections import Counter
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ApkgContents:
    notes: int
    cards: int
    decks: dict[str, int]  # имя колоды → карточек в ней (без Default)
    models: list[str]
    css: dict[str, str]  # имя типа записи → его CSS
    media: list[str]
    fields: list[list[str]]  # поля каждой записи, разбитые по \x1f
    tags: list[list[str]]  # метки каждой записи


def read_apkg(path: Path) -> ApkgContents:
    with zipfile.ZipFile(path) as archive:
        collection = archive.read("collection.anki2")
        media = list(json.loads(archive.read("media")).values())
    database = path.with_suffix(".sqlite")
    database.write_bytes(collection)
    connection = sqlite3.connect(database)
    try:
        notes = connection.execute("SELECT count(*) FROM notes").fetchone()[0]
        cards = connection.execute("SELECT count(*) FROM cards").fetchone()[0]
        per_deck = Counter(
            dict(connection.execute("SELECT did, count(*) FROM cards GROUP BY did").fetchall())
        )
        decks_json = json.loads(connection.execute("SELECT decks FROM col").fetchone()[0])
        decks = {
            deck["name"]: per_deck.get(int(did), 0)
            for did, deck in decks_json.items()
            if deck["name"] != "Default"
        }
        models_json = json.loads(connection.execute("SELECT models FROM col").fetchone()[0])
        models = [model["name"] for model in models_json.values()]
        css = {model["name"]: model["css"] for model in models_json.values()}
        fields = [
            row[0].split("\x1f") for row in connection.execute("SELECT flds FROM notes").fetchall()
        ]
        tags = [row[0].split() for row in connection.execute("SELECT tags FROM notes").fetchall()]
    finally:
        connection.close()
        database.unlink(missing_ok=True)
    return ApkgContents(
        notes=notes,
        cards=cards,
        decks=decks,
        models=models,
        css=css,
        media=media,
        fields=fields,
        tags=tags,
    )
