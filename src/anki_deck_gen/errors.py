"""Таксономия отказов.

Всё, что бот умеет объяснить человеку, — подкласс `AnkiDeckGenError`. Воркер
и CLI подбирают текст по классу: один словарь `class → фраза`, никаких разборов
сообщений исключений. Что не попало сюда — неожиданная ошибка, и о ней говорят
общими словами, а подробности идут в лог.
"""


class AnkiDeckGenError(Exception):
    """Всё, что этот бот умеет объяснить человеку."""


class TableUnreadable(AnkiDeckGenError):
    """Файл или текст не разбирается как Таблица.

    ``detail`` — что именно не так, словами для пользователя: какой лист, что
    стояло в первой строке, каких колонок не хватает.
    """

    def __init__(self, detail: str) -> None:
        super().__init__(detail)
        self.detail = detail


class UnsupportedSource(AnkiDeckGenError):
    """Прислали то, из чего колоду не сделать: не xlsx/csv, не ссылка, не текст."""


class SheetNotShared(AnkiDeckGenError):
    """Google-таблица закрыта: экспорт отдал логин-страницу или 401/403."""


class SheetUnreachable(AnkiDeckGenError):
    """Google не ответил или ответил ошибкой сервера — сеть, не права доступа."""


class FileTooLarge(AnkiDeckGenError):
    """Размер файла превысил MAX_FILE_MB ещё до скачивания."""

    def __init__(self, *, size_bytes: int, limit_bytes: int) -> None:
        super().__init__(f"file is {size_bytes} bytes, limit {limit_bytes}")
        self.size_bytes = size_bytes
        self.limit_bytes = limit_bytes


class TooManyRows(AnkiDeckGenError):
    """Записей больше MAX_NOTES — это сотни запросов к Google TTS."""

    def __init__(self, *, count: int, limit: int) -> None:
        super().__init__(f"{count} rows, limit {limit}")
        self.count = count
        self.limit = limit


class MissingColumns(AnkiDeckGenError):
    """Выбранному Типу записи не хватает колонок в Таблице."""

    def __init__(self, *, note_type: str, missing: frozenset[str]) -> None:
        super().__init__(f"{note_type} needs columns {sorted(missing)}")
        self.note_type = note_type
        self.missing = missing


class UnknownNoteType(AnkiDeckGenError):
    """Идентификатор типа записи, которого нет в реестре."""


class TableExpired(AnkiDeckGenError):
    """Пользователь вернулся к диалогу после того, как Pending истёк."""


class TtsUnavailable(AnkiDeckGenError):
    """Google TTS не отвечает или отвечает 429 — колоду без озвучки молча не собираем."""

    def __init__(self, detail: str) -> None:
        super().__init__(detail)
        self.detail = detail


class BuildAbandoned(AnkiDeckGenError):
    """Сборку попросили остановиться (таймаут или отмена) — поток вышел по флагу."""
