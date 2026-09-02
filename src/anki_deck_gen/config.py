"""Конфигурация из окружения / `.env`.

Два класса, потому что два входа. CLI собирает колоды и ничего не знает о
Telegram — ему не нужен токен, и требовать его было бы ошибкой запуска на
машине, где бота нет. Бот — надмножество: всё, что нужно сборке, плюс Telegram,
доступ и очередь.
"""

from pathlib import Path

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_SETTINGS_CONFIG = SettingsConfigDict(
    env_file=".env",
    env_file_encoding="utf-8",
    extra="ignore",
    populate_by_name=True,
)


class BuildSettings(BaseSettings):
    """Что нужно, чтобы собрать колоду. Общее для CLI и бота."""

    model_config = _SETTINGS_CONFIG

    work_dir: Path = Field(
        default=Path("/var/tmp/anki-deck-gen"),
        alias="WORK_DIR",
        description=(
            "Рабочий каталог: scratch на каждое Задание (удаляется по завершении) и, "
            "если MEDIA_CACHE_DIR не задан, кэш озвучки в подкаталоге media/"
        ),
    )
    media_cache_dir_raw: Path | None = Field(
        default=None,
        alias="MEDIA_CACHE_DIR",
        description=(
            "Постоянный кэш mp3 от gTTS: <dir>/<lang>/<slug>.mp3. Одна фраза — один запрос "
            "к Google за всю жизнь бота. По умолчанию WORK_DIR/media"
        ),
    )
    max_notes: int = Field(
        default=1000,
        alias="MAX_NOTES",
        description="Потолок Записей на одну колоду: столько же запросов к Google TTS",
    )

    @property
    def media_cache_dir(self) -> Path:
        return self.media_cache_dir_raw or self.work_dir / "media"

    @model_validator(mode="after")
    def _fail_fast(self) -> "BuildSettings":
        if self.max_notes < 1:
            raise ValueError(f"MAX_NOTES must be >= 1, got {self.max_notes}")
        return self


class BotSettings(BuildSettings):
    """Всё, что нужно боту и чего он не может узнать сам."""

    model_config = _SETTINGS_CONFIG

    bot_token: str = Field(
        alias="TELEGRAM_BOT_TOKEN",
        description=(
            "Токен от @BotFather. Имя TELEGRAM_BOT_TOKEN, а не BOT_TOKEN, — чтобы стоковое "
            "правило gitleaks, завязанное на слово telegram, ловило утечку"
        ),
    )
    # Сырая строка + разбор в property: pydantic-settings пытается JSON-декодировать
    # значения для сложных типов (set/frozenset) и падает на «1,2».
    admin_ids_raw: str = Field(
        alias="ADMIN_IDS",
        description=(
            "Telegram user id админов через запятую. Админы допущены без строки в БД "
            "и раздают доступ (/invite, /allow). Пустой список = бот никого не пускает"
        ),
    )
    telegram_proxy: str | None = Field(
        default=None,
        alias="TELEGRAM_PROXY",
        description=(
            "Прокси до api.telegram.org, напр. http://127.0.0.1:1080. Нужен там, где провайдер "
            "блокирует Telegram; пусто — прямое соединение"
        ),
    )
    database_url: str = Field(
        default="sqlite+aiosqlite:///anki-deck-gen.sqlite",
        alias="DATABASE_URL",
        description=(
            "SQLAlchemy-URL базы доступа (allowed_users, invites, user_prefs). "
            "Абсолютный путь у sqlite — четыре слэша: sqlite+aiosqlite:////var/db/…"
        ),
    )
    queue_limit: int = Field(
        default=5,
        alias="QUEUE_LIMIT",
        description="Заданий в системе одновременно (в очереди плюс одно в работе)",
    )
    job_timeout_s: int = Field(
        default=900,
        alias="JOB_TIMEOUT_S",
        description="Секунд на одно Задание от начала сборки до готового файла",
    )
    max_file_mb: int = Field(
        default=5,
        alias="MAX_FILE_MB",
        description="Потолок размера присланного файла; проверяется до скачивания",
    )
    pending_ttl_s: int = Field(
        default=1800,
        alias="PENDING_TTL_S",
        description=(
            "Сколько бот помнит разобранную Таблицу, пока человек выбирает настройки; "
            "каждый шаг диалога продлевает"
        ),
    )
    example_sheet_url: str | None = Field(
        default=None,
        alias="EXAMPLE_SHEET_URL",
        description=(
            "Публичная Google-таблица-пример для /help и README; пусто — строка не показывается"
        ),
    )

    @property
    def admin_ids(self) -> frozenset[int]:
        try:
            ids = {int(chunk) for chunk in self.admin_ids_raw.split(",") if chunk.strip()}
        except ValueError as exc:
            raise ValueError(
                f"ADMIN_IDS must be comma-separated ints, got {self.admin_ids_raw!r}"
            ) from exc
        return frozenset(ids)

    @property
    def max_file_bytes(self) -> int:
        return self.max_file_mb * 1024 * 1024

    @model_validator(mode="after")
    def _fail_fast_bot(self) -> "BotSettings":
        _ = self.admin_ids
        if self.queue_limit < 1:
            raise ValueError(f"QUEUE_LIMIT must be >= 1, got {self.queue_limit}")
        if self.job_timeout_s < 1:
            raise ValueError(f"JOB_TIMEOUT_S must be >= 1, got {self.job_timeout_s}")
        if self.max_file_mb < 1:
            raise ValueError(f"MAX_FILE_MB must be >= 1, got {self.max_file_mb}")
        if self.pending_ttl_s < 1:
            raise ValueError(f"PENDING_TTL_S must be >= 1, got {self.pending_ttl_s}")
        return self
