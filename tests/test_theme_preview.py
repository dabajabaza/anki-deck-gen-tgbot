"""`themes/preview.html` показывает то, что бот действительно собирает.

Страница лежит в репозитории готовой — чтобы посмотреть темы, не запуская ничего.
Значит, она может протухнуть: поправили CSS в `notetypes/theme.py`, а картинка
осталась прежней. Этот тест — единственное, что этого не даёт.
"""

import importlib.util
from pathlib import Path
from types import ModuleType

from markupsafe import escape

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

    Оба раза — экранированным: srcdoc живёт в атрибуте, блок CSS показывается как
    текст. Экранирует Jinja (`autoescape`), поэтому и в тесте её же правила.
    """
    page = PREVIEW.read_text(encoding="utf-8")
    builder = _builder()
    for value in Theme:
        escaped = str(escape(builder.theme.css_for(value)))
        assert escaped in page, f"нет CSS темы {value.value}"
        assert f"CSS темы «{builder.texts.theme_name(value)}»" in page
    # Плюс колонка со стоковым Anki: без неё не с чем сравнивать.
    assert "Стоковый Anki" in page


def test_the_page_is_a_standalone_document() -> None:
    """Файл открывают прямо из репозитория, в том числе через локальный сервер IDE.

    Тот отдаёт его без charset в заголовке, и без meta Firefox показывает кириллицу
    кракозябрами.
    """
    page = PREVIEW.read_text(encoding="utf-8")
    assert page.lstrip().startswith("<!doctype html>")
    assert '<meta charset="utf-8">' in page
    assert '<html lang="ru">' in page and page.rstrip().endswith("</html>")


def test_the_pages_own_style_and_script_are_not_escaped() -> None:
    """Внутри <style> и <script> сущности не раскрываются.

    Стоит забыть |safe — и кавычки станут &#39;/&#34;: скрипт перестанет
    разбираться, а селекторы [data-theme="dark"] и шрифтовые стеки — совпадать.
    Ровно так однажды отвалился переключатель ночного режима.
    """
    page = PREVIEW.read_text(encoding="utf-8")
    for opening, closing in (("<style>", "</style>"), ("<script>", "</script>")):
        block = page[page.index(opening) + len(opening) : page.index(closing)]
        assert "&#39;" not in block and "&#34;" not in block, opening
    assert '[data-theme="dark"]' in page
    assert "document.querySelectorAll('iframe.cardframe')" in page


def test_card_documents_stay_escaped_inside_the_srcdoc_attribute() -> None:
    """А вот содержимое карточек экранироваться обязано: оно живёт в атрибуте."""
    page = PREVIEW.read_text(encoding="utf-8")
    assert 'srcdoc="&lt;!doctype html&gt;' in page
