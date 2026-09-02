"""Прогон миграций на старте процесса.

Синхронно и ДО asyncio.run: alembic поднимает собственный цикл событий, из
работающего его не позвать. Вызывается из __main__.main() после захвата
single-instance lock — вторая копия иначе прогнала бы `upgrade head` по живой
базе параллельно с первой.
"""

from pathlib import Path
from urllib.parse import urlparse

from alembic import command
from alembic.config import Config as AlembicConfig

# Корень репозитория: src/anki_deck_gen/db/migrate.py → три уровня вверх.
# Якорь зависит от положения ЭТОГО файла. Перенеси модуль на уровень глубже —
# и REPO_ROOT молча укажет на src/, alembic.ini не найдётся, а бот не стартует.
# На сервере пакет установлен editable (`-e .`), поэтому alembic.ini и
# migrations/ лежат рядом с исходниками и путь верен.
REPO_ROOT = Path(__file__).resolve().parents[3]
ALEMBIC_INI = REPO_ROOT / "alembic.ini"


def sqlite_path(db_url: str) -> Path | None:
    """Путь к файлу для sqlite-URL; None для in-memory и не-sqlite драйверов.

    `sqlite+aiosqlite:///rel.sqlite` → относительный, `sqlite+aiosqlite:////var/db/x`
    → абсолютный: urlparse отдаёт path как `/rel.sqlite` и `//var/db/x`, лишний
    ведущий слэш относительного пути снимаем.
    """
    if not db_url.startswith("sqlite"):
        return None
    path = urlparse(db_url).path
    if not path or path == "/:memory:":
        return None
    if path.startswith("//"):
        return Path(path[1:])
    return Path(path.lstrip("/"))


def run_migrations(db_url: str) -> None:
    """`alembic upgrade head` по адресу базы, с созданием каталога под sqlite-файл.

    Каталог создаём сами: SQLite создаст файл, но не родителя, а первый локальный
    запуск с DATABASE_URL в ещё не существующий local/ падал бы на «unable to
    open database file» вместо чистого старта.
    """
    file = sqlite_path(db_url)
    if file is not None:
        file.parent.mkdir(parents=True, exist_ok=True)
    cfg = AlembicConfig(str(ALEMBIC_INI))
    cfg.set_main_option("sqlalchemy.url", db_url)
    command.upgrade(cfg, "head")
