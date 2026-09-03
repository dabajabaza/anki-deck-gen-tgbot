"""Модели БД. Время — unix-секунды. FK намеренно не объявляем: целостность — в коде.

База здесь маленькая и служит одному: кто допущен к боту и что он выбирал в
прошлый раз. Заданий и колод в ней нет — колода собирается и отдаётся, история
не хранится (ARCHITECTURE.md, решение про SQLite только для доступа/настроек).
"""

from sqlalchemy import BigInteger, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from anki_deck_gen.domain import Theme
from anki_deck_gen.timeutils import now_ts


class Base(DeclarativeBase):
    pass


class AllowedUser(Base):
    """Гости — те, кого впустили явно: через /allow или погашенный Инвайт.

    Админов тут нет: их даёт ADMIN_IDS в конфиге, а не таблица. Всем, кого нет
    ни там, ни здесь, бот не отвечает вовсе — любой ответ подтвердил бы
    Постороннему, что бот существует.
    """

    __tablename__ = "allowed_users"

    user_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    username: Mapped[str | None] = mapped_column(String)
    created_at: Mapped[int] = mapped_column(BigInteger, nullable=False, default=now_ts)
    # Кто впустил: id Админа при /allow, автор Инвайта при переходе по ссылке.
    invited_by: Mapped[int | None] = mapped_column(BigInteger)


class Invite(Base):
    """Инвайт — одноразовая ссылка `/start <код>`, живёт INVITE_TTL_SECONDS.

    Одноразовость держится не проверкой в коде, а UPDATE ... WHERE used_by IS NULL
    (см. services/access.py): два одновременных перехода иначе могли бы погасить
    один код дважды.
    """

    __tablename__ = "invites"

    code: Mapped[str] = mapped_column(String, primary_key=True)
    created_by: Mapped[int] = mapped_column(BigInteger, nullable=False)
    created_at: Mapped[int] = mapped_column(BigInteger, nullable=False, default=now_ts)
    expires_at: Mapped[int] = mapped_column(BigInteger, nullable=False)
    used_by: Mapped[int | None] = mapped_column(BigInteger)
    used_at: Mapped[int | None] = mapped_column(BigInteger)


class UserPref(Base):
    """Последние Настройки колоды пользователя — для кнопки «Как в прошлый раз».

    Одна строка на человека, перезаписывается каждым Заданием. Это единственное,
    что бот помнит о чьих-то колодах: не что собирали, а как.
    """

    __tablename__ = "user_prefs"

    user_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    note_type_id: Mapped[str] = mapped_column(String, nullable=False)
    lang_q: Mapped[str] = mapped_column(String, nullable=False)
    lang_a: Mapped[str] = mapped_column(String, nullable=False)
    # Значения domain.AudioSide и domain.Theme, строками — чтобы таблица читалась глазами.
    audio: Mapped[str] = mapped_column(String, nullable=False)
    # Строки, записанные до появления оформления, получили 'card' от миграции.
    theme: Mapped[str] = mapped_column(
        String, nullable=False, default=Theme.CARD.value, server_default=Theme.CARD.value
    )
    updated_at: Mapped[int] = mapped_column(BigInteger, nullable=False, default=now_ts)
