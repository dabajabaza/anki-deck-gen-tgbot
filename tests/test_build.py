"""Сборка .apkg: имена колод по правилу, поля с озвучкой, медиа, отмена по флагу."""

import threading
from pathlib import Path

import pytest

from anki_deck_gen.build.audio import AudioCache
from anki_deck_gen.build.package import build_package, deck_id_for, deck_name_for
from anki_deck_gen.domain import AudioSide, BuildRequest, DeckSettings, Fix, Sheet, Table
from anki_deck_gen.errors import BuildAbandoned, MissingColumns, TableUnreadable
from anki_deck_gen.notetypes.base import ANKI_NAME_SUFFIX
from tests.helpers.apkg import read_apkg
from tests.helpers.tables import make_row, make_table


class FakeAudioCache(AudioCache):
    """Пишет пустые файлы вместо похода в Google; помнит, что просили озвучить."""

    def __init__(self, root: Path) -> None:
        super().__init__(root)
        self.requested: list[tuple[str, str]] = []

    def ensure(self, text: str, lang: str) -> Path:
        self.requested.append((text, lang))
        path = self.path_for(text, lang)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"")
        return path


def settings(note_type: str = "basic", audio: AudioSide = AudioSide.NONE) -> DeckSettings:
    return DeckSettings(note_type_id=note_type, lang_q="en", lang_a="ru", audio=audio)


def test_a_flat_table_becomes_one_deck_with_the_right_counts(tmp_path: Path) -> None:
    table = make_table(make_row(2, "a", "b", tags=("t1", "two words")), make_row(3, "c", "d"))
    result = build_package(
        BuildRequest(table=table, settings=settings("basic-reversed"), deck_name="My deck"),
        out_dir=tmp_path / "out",
        media_cache_dir=tmp_path / "media",
    )
    assert result.path.name == "my_deck.apkg"
    contents = read_apkg(result.path)
    assert contents.notes == 2
    assert contents.cards == 4
    assert contents.decks == {"My deck": 4}
    assert contents.models == ["Простая (с обратной карточкой)" + ANKI_NAME_SUFFIX]
    assert result.summary.notes == 2
    assert result.summary.cards == 4
    assert result.summary.subdecks == ("My deck",)
    assert result.summary.media_files == 0


def test_sheets_and_deck_column_nest_as_subdecks(tmp_path: Path) -> None:
    table = Table(
        sheets=(
            Sheet(
                name="1. Start",
                columns=frozenset({"Q", "A", "Deck"}),
                rows=(
                    make_row(2, "a", "b", sheet="1. Start", deck="Words"),
                    make_row(3, "c", "d", sheet="1. Start"),
                ),
            ),
            Sheet(
                name="2. End",
                columns=frozenset({"Q", "A", "Deck"}),
                rows=(make_row(2, "e", "f", sheet="2. End"),),
            ),
        )
    )
    result = build_package(
        BuildRequest(table=table, settings=settings(), deck_name="Base"),
        out_dir=tmp_path,
        media_cache_dir=tmp_path / "media",
    )
    assert result.summary.subdecks == ("Base::1. Start::Words", "Base::1. Start", "Base::2. End")
    assert read_apkg(result.path).decks == {
        "Base::1. Start::Words": 1,
        "Base::1. Start": 1,
        "Base::2. End": 1,
    }


def test_deck_name_rule_ignores_the_sheet_when_there_is_only_one() -> None:
    single = make_table(make_row(2, "a", "b", sheet="Only", deck="X"))
    assert deck_name_for("Base", single, single.rows[0]) == "Base::X"


def test_deck_ids_are_deterministic_and_never_the_default_deck() -> None:
    assert deck_id_for("At the appointment") == deck_id_for("At the appointment")
    assert deck_id_for("A") != deck_id_for("B")
    assert deck_id_for("A") != 1


def test_audio_fields_and_media_follow_the_audio_side(tmp_path: Path) -> None:
    table = make_table(make_row(2, "How are you?", "Как дела?"), make_row(3, "Bye", "Пока"))
    cache = FakeAudioCache(tmp_path / "media")
    progress: list[tuple[int, int]] = []
    result = build_package(
        BuildRequest(table=table, settings=settings(audio=AudioSide.BOTH), deck_name="D"),
        out_dir=tmp_path,
        media_cache_dir=tmp_path / "media",
        on_progress=lambda done, total: progress.append((done, total)),
        audio_cache=cache,
    )
    contents = read_apkg(result.path)
    assert result.summary.media_files == 4
    assert sorted(contents.media) == sorted(
        ["how_are_you.mp3", "как_дела.mp3", "bye.mp3", "пока.mp3"]
    )
    for fields in contents.fields:
        assert fields[2].startswith("[sound:") and fields[3].startswith("[sound:")
    assert progress == [(1, 2), (2, 2)]
    assert [lang for _, lang in cache.requested] == ["en", "ru", "en", "ru"]


def test_question_only_audio_leaves_the_answer_field_empty(tmp_path: Path) -> None:
    table = make_table(make_row(2, "a", "b"))
    result = build_package(
        BuildRequest(table=table, settings=settings(audio=AudioSide.QUESTION), deck_name="D"),
        out_dir=tmp_path,
        media_cache_dir=tmp_path / "media",
        audio_cache=FakeAudioCache(tmp_path / "media"),
    )
    (fields,) = read_apkg(result.path).fields
    assert fields[2] == "[sound:a.mp3]"
    assert fields[3] == ""


def test_an_abandoned_build_stops_before_the_first_phrase(tmp_path: Path) -> None:
    flag = threading.Event()
    flag.set()
    cache = FakeAudioCache(tmp_path / "media")
    with pytest.raises(BuildAbandoned):
        build_package(
            BuildRequest(
                table=make_table(make_row(2, "a", "b")),
                settings=settings(audio=AudioSide.QUESTION),
                deck_name="D",
            ),
            out_dir=tmp_path,
            media_cache_dir=tmp_path / "media",
            abandoned=flag,
            audio_cache=cache,
        )
    assert cache.requested == []


def test_images_from_media_dir_are_packaged_and_missing_ones_ignored(tmp_path: Path) -> None:
    media_dir = tmp_path / "img"
    media_dir.mkdir()
    (media_dir / "flag.svg").write_text("<svg/>")
    table = make_table(
        make_row(2, '<img src="flag.svg"> What flag?', "Alpha"),
        make_row(3, '<img src="missing.png">', "Nothing"),
    )
    result = build_package(
        BuildRequest(table=table, settings=settings(), deck_name="Flags", media_dir=media_dir),
        out_dir=tmp_path,
        media_cache_dir=tmp_path / "media",
    )
    assert read_apkg(result.path).media == ["flag.svg"]
    assert result.summary.media_files == 1


def test_fixes_and_skips_are_applied_and_counted(tmp_path: Path) -> None:
    table = make_table(make_row(2, "a", ""), make_row(3, "", "x"), make_row(4, "c", "d"))
    result = build_package(
        BuildRequest(
            table=table,
            settings=settings(),
            deck_name="D",
            fixes={(None, 2): Fix(question="a", answer="b")},
            skips=frozenset({(None, 3)}),
        ),
        out_dir=tmp_path,
        media_cache_dir=tmp_path / "media",
    )
    assert result.summary.notes == 2
    assert result.summary.skipped == 1


def test_unfixed_problem_rows_refuse_to_build(tmp_path: Path) -> None:
    with pytest.raises(TableUnreadable):
        build_package(
            BuildRequest(
                table=make_table(make_row(2, "a", "")), settings=settings(), deck_name="D"
            ),
            out_dir=tmp_path,
            media_cache_dir=tmp_path / "media",
        )


def test_missing_required_columns_are_named(tmp_path: Path) -> None:
    table = make_table(make_row(2, "a", "b"), columns=frozenset({"Q"}))
    with pytest.raises(MissingColumns) as info:
        build_package(
            BuildRequest(table=table, settings=settings(), deck_name="D"),
            out_dir=tmp_path,
            media_cache_dir=tmp_path / "media",
        )
    assert info.value.missing == frozenset({"A"})


def test_duplicates_are_counted_in_the_summary(tmp_path: Path) -> None:
    table = make_table(make_row(2, "same", "1"), make_row(3, "same", "2"))
    result = build_package(
        BuildRequest(table=table, settings=settings(), deck_name="D"),
        out_dir=tmp_path,
        media_cache_dir=tmp_path / "media",
    )
    assert result.summary.duplicates == 1
    assert result.summary.notes == 2
