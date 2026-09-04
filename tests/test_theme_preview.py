"""`themes/preview.html` показывает то, что бот действительно собирает.

Страница лежит в репозитории готовой — чтобы посмотреть темы, не запуская ничего.
Значит, она может протухнуть: поправили CSS в `notetypes/theme.py`, а картинка
осталась прежней. Этот тест — единственное, что этого не даёт.
"""

import html
import importlib.util
from pathlib import Path
from types import ModuleType

from anki_deck_gen.domain import Theme

REPO = Path(__file__).resolve().parents[1]
PREVIEW = REPO / "themes" / "preview.html"
BUILDER = REPO / "scripts" / "build_theme_preview.py"


def _builder() -> ModuleType:
    """Загрузить сборщик по пути: `scripts/` — не пакет и в sys.path не лежит."""
    spec = importlib.util.spec_from_file_location("build_theme_preview", BUILDER)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_the_committed_page_is_what_the_builder_makes_now() -> None:
    expected = _builder().render()
    assert PREVIEW.read_text(encoding="utf-8") == expected, (
        "themes/preview.html отстал от тем — соберите заново: "
        "uv run python scripts/build_theme_preview.py"
    )


def test_every_theme_has_a_column_and_its_css_on_the_page() -> None:
    """CSS попадает на страницу дважды: внутри srcdoc карточек и в раскрывающемся блоке.

    Оба раза — экранированным: srcdoc живёт в атрибуте, блок CSS показывается как текст.
    """
    page = PREVIEW.read_text(encoding="utf-8")
    builder = _builder()
    for value in Theme:
        escaped = html.escape(builder.theme.css_for(value))
        assert escaped in page, f"нет CSS темы {value.value}"
        assert f"CSS темы «{builder.texts.theme_name(value)}»" in page
    # Плюс колонка со стоковым Anki: без неё не с чем сравнивать.
    assert "Стоковый Anki" in page
