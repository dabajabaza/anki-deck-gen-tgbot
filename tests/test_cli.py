"""CLI: тот же словарь, что у бота; регрессия на настоящей колоде Elena."""

import json
import sqlite3
import zipfile
from pathlib import Path

import pytest

from anki_deck_gen import cli
from tests.helpers.apkg import read_apkg

LOCAL = Path(__file__).resolve().parents[1] / "local"


def _inspect(apkg: Path) -> tuple[int, int, list[str]]:
    """Записи, карточки и имена колод из .apkg без Anki."""
    with zipfile.ZipFile(apkg) as archive, archive.open("collection.anki2") as member:
        db_bytes = member.read()
    tmp = apkg.with_suffix(".anki2")
    tmp.write_bytes(db_bytes)
    con = sqlite3.connect(tmp)
    try:
        notes = con.execute("SELECT count(*) FROM notes").fetchone()[0]
        cards = con.execute("SELECT count(*) FROM cards").fetchone()[0]
        decks = json.loads(con.execute("SELECT decks FROM col").fetchone()[0])
        names = sorted(d["name"] for d in decks.values() if d["name"] != "Default")
    finally:
        con.close()
    return notes, cards, names


def test_elena_regression_nine_subdecks_ninety_notes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = LOCAL / "elena_starter_at_the_appointment.csv"
    if not source.exists():
        pytest.skip("local fixture not present")
    monkeypatch.setenv("MEDIA_CACHE_DIR", str(tmp_path / "media"))
    code = cli.main(
        [
            "--source",
            str(source),
            "--note-type",
            "basic-reversed",
            "--audio-for",
            "none",
            "--deck-name",
            "At the appointment",
            "--output-dir",
            str(tmp_path / "out"),
        ]
    )
    assert code == 0
    apkg = tmp_path / "out" / "at_the_appointment.apkg"
    notes, cards, names = _inspect(apkg)
    assert (notes, cards) == (90, 180)
    assert len(names) == 9
    assert all(name.startswith("At the appointment::") for name in names)
    assert "At the appointment::1. Start the appointment" in names


def test_problem_rows_stop_the_cli_with_line_numbers(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    csv_path = tmp_path / "bad.csv"
    csv_path.write_text("Q,A\ncat,кот\ndog,\n", encoding="utf-8")
    code = cli.main(["--source", str(csv_path), "--output-dir", str(tmp_path / "out")])
    assert code == 1
    err = capsys.readouterr().err
    assert "строка 3" in err and "пустой ответ" in err
    assert not (tmp_path / "out").exists()


def test_text_source_builds_a_basic_deck(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MEDIA_CACHE_DIR", str(tmp_path / "media"))
    txt = tmp_path / "pairs.txt"
    txt.write_text("cat / кот\ndog / пёс\n", encoding="utf-8")
    code = cli.main(
        ["--source", str(txt), "--deck-name", "Звери", "--output-dir", str(tmp_path / "o")]
    )
    assert code == 0
    notes, cards, names = _inspect(tmp_path / "o" / "звери.apkg")
    assert (notes, cards, names) == (2, 2, ["Звери"])


def test_theme_flag_picks_the_css(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MEDIA_CACHE_DIR", str(tmp_path / "media"))
    txt = tmp_path / "pairs.txt"
    txt.write_text("cat / кот\ndog / пёс\n", encoding="utf-8")
    out = tmp_path / "o"
    code = cli.main(
        ["--source", str(txt), "--deck-name", "Звери", "--output-dir", str(out), "--theme", "book"]
    )
    assert code == 0
    (css,) = read_apkg(out / "звери.apkg").css.values()
    assert "Charter" in css, "book theme is the serif one"


def test_missing_file_is_a_clean_error(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    code = cli.main(["--source", str(tmp_path / "nope.xlsx")])
    assert code == 1
    assert "Файл не найден" in capsys.readouterr().err
