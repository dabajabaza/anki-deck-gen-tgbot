"""Имена файлов кэша озвучки: разные фразы — разные файлы, всегда."""

from anki_deck_gen.build.slug import apkg_filename, sanitize, slug


def test_phrases_that_sanitize_alike_get_different_cache_files() -> None:
    assert slug("a/b") != slug("ab")
    assert slug("Hi") != slug("Hi!")
    assert slug("Do you have any pain?") != slug("Do you have any pain")


def test_slug_is_stable_readable_and_filesystem_safe() -> None:
    value = slug("Do you have any pain?")
    assert value == slug("Do you have any pain?")
    assert value.startswith("do_you_have_any_pain_")
    assert "/" not in value and "?" not in value and " " not in value


def test_a_very_long_phrase_is_truncated_but_unique() -> None:
    long_a = "слово " * 60
    long_b = "слово " * 60 + "ещё"
    assert slug(long_a) != slug(long_b)
    assert len(slug(long_a).encode("utf-8")) < 200


def test_empty_after_sanitize_still_gets_a_name() -> None:
    assert slug("???") and slug("???") != slug("!!!")


def test_apkg_filename_and_sanitize() -> None:
    assert apkg_filename("At the appointment") == "at_the_appointment.apkg"
    assert apkg_filename("???") == "deck.apkg"
    assert sanitize("a b/c") == "a_bc"


def test_file_names_are_ascii_so_they_survive_telegram_and_android() -> None:
    """AnkiDroid не открывает файл, чьё имя потеряло кодировку по дороге."""
    assert apkg_filename("Ппппп") == "ppppp.apkg"
    assert apkg_filename("Формулы вежливости") == "formuly_vezhlivosti.apkg"
    assert slug("вопрос").isascii() and slug("вопрос").startswith("vopros_")
    assert slug("cảm ơn").startswith("cam_on_"), "вьетнамский тоже латинизируется"
    assert apkg_filename("日本語").isascii()


def test_transliteration_does_not_merge_different_phrases() -> None:
    """Хэш берётся от исходного текста, поэтому «шар» и «schar» не делят файл."""
    assert slug("шар") != slug("schar")
