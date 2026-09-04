"""CSS и шаблоны Карточек лежат файлами: они должны быть на месте и в целости."""

from pathlib import Path

import pytest

from anki_deck_gen import notetypes
from anki_deck_gen.domain import Theme
from anki_deck_gen.notetypes import assets

ASSETS = Path(assets.__file__).parent
TEMPLATES = ASSETS / "templates"
CSS = ASSETS / "css"


def _template_files() -> list[Path]:
    return sorted(TEMPLATES.glob("*.html"))


def test_every_template_file_ends_with_exactly_one_newline() -> None:
    """Загрузчик снимает ровно один перевод строки — лишний уехал бы в шаблон Anki."""
    for path in _template_files():
        text = path.read_text(encoding="utf-8")
        assert text.endswith("\n"), path.name
        assert not text.endswith("\n\n"), path.name


def test_every_registered_type_gets_its_templates_from_files() -> None:
    for note_type in notetypes.REGISTRY.values():
        for card in note_type.templates():
            assert card["qfmt"].strip(), f"{note_type.id}: пустое лицо"
            assert card["afmt"].strip(), f"{note_type.id}: пустой оборот"
            assert not card["qfmt"].endswith("\n"), "перевод строки снимается загрузчиком"


def test_the_templates_folder_holds_exactly_what_the_registry_asks_for() -> None:
    """Лишний файл — след удалённого типа, недостающий — опечатка в имени."""
    wanted = set()
    for note_type in notetypes.REGISTRY.values():
        for ordinal in range(1, note_type.cards_per_note + 1):
            source = "basic" if note_type.id == "basic-reversed" and ordinal == 1 else note_type.id
            wanted |= {
                f"{source}.card{ordinal}.q.html",
                f"{source}.card{ordinal}.a.html",
            }
    assert {path.name for path in _template_files()} == wanted


def test_every_theme_has_its_css_file() -> None:
    for value in Theme:
        assert assets.css(theme_file(value)).strip(), value.value
    assert assets.css("vietnamese").strip(), "у вьетнамского типа свой стиль"


def theme_file(value: Theme) -> str:
    from anki_deck_gen.notetypes.theme import FILES

    return FILES[value]


def test_css_keeps_its_trailing_newline_but_a_template_does_not() -> None:
    assert assets.css("card").endswith("\n")
    assert not assets.template("basic", 1, "q").endswith("\n")


def test_a_file_without_a_trailing_newline_is_refused(tmp_path: Path) -> None:
    """Молча принять такой файл — значит однажды выкатить шаблон, обрезанный редактором."""
    broken = CSS / "broken-on-purpose.css"
    broken.write_text(".card { color: red; }", encoding="utf-8")
    try:
        with pytest.raises(ValueError, match="переводом строки"):
            assets.css("broken-on-purpose")
    finally:
        broken.unlink()
        assets.css.cache_clear()
