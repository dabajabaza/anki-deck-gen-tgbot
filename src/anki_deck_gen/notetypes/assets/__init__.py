"""Загрузка CSS и шаблонов Карточек из файлов рядом с кодом.

Раньше и то и другое лежало строками в .py: редактор не подсвечивал ни CSS, ни
HTML, а править многострочный литерал руками неудобно. Теперь это обычные файлы
в `assets/css` и `assets/templates`, а модули типов записей только называют их.

CSS читается как есть, вместе с завершающим переводом строки — он часть файла.
Шаблоны читаются **дословно**, без шаблонизатора. Синтаксис `{{Front}}`,
`{{type:Back}}`, `{{#Tags}}` — это язык самого Anki, он рендерит их у человека на
устройстве; Jinja2 попыталась бы истолковать те же скобки и сломала бы шаблон.
Единственная вольность — завершающий перевод строки у шаблона: файл обязан им
кончаться (иначе его допишет любой редактор и молча изменит шаблон), а загрузчик
его снимает — Anki хранит шаблоны без него.

Файлы лежат внутри пакета, поэтому едут в колесе вместе с кодом; читаются через
``importlib.resources``, а не по пути от ``__file__``, — на сервере пакет стоит
editable-ссылкой, и путь от файла указал бы мимо. ``tests/test_assets.py``
проверяет, что в собранном колесе они на месте.
"""

from functools import cache
from importlib.resources import files

_CSS = "css"
_TEMPLATES = "templates"


@cache
def css(name: str) -> str:
    """CSS по имени файла без расширения: ``card``, ``book``, ``vietnamese``."""
    return _read(_CSS, f"{name}.css")


@cache
def template(note_type_id: str, card: int, side: str) -> str:
    """Шаблон стороны Карточки: ``template("basic", 1, "q")``.

    Имя файла — ``<тип>.card<N>.<q|a>.html``, чтобы стороны одной карточки лежали
    рядом и порядок в каталоге совпадал с порядком в Anki.
    """
    return _read(_TEMPLATES, f"{note_type_id}.card{card}.{side}.html")[:-1]


def _read(folder: str, name: str) -> str:
    text = files(__package__).joinpath(folder, name).read_text(encoding="utf-8")
    if not text.endswith("\n"):
        raise ValueError(f"{folder}/{name}: файл должен кончаться переводом строки")
    return text
