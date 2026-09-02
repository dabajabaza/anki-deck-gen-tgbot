"""access and prefs

Базовая схема: список Гостей, Инвайты и последние Настройки колоды на
пользователя. Ничего про Задания и колоды — их база не хранит.

Проверка инспектором перед КАЖДОЙ таблицей, а не одна на ревизию: база с ЧАСТЬЮ
схемы (скажем, allowed_users создали руками) иначе штамповалась бы на head с
навсегда отсутствующими таблицами, и починить её `upgrade head` уже не мог —
ревизия числится применённой. Урок lesson-tracker, повторять не хочется.

Revision ID: 8ac92f3a4fb0
Revises:
Create Date: 2026-09-03 02:26:26

"""

import logging
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "8ac92f3a4fb0"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _create_missing(name: str, *args: object) -> None:
    """Создать таблицу, если её ещё нет, — и сказать об этом в лог.

    Лог не для красоты: при разборе инцидента с частичной схемой первый вопрос —
    «что именно миграция создала на боевом файле», и ответа кроме этой строки нет.
    """
    if sa.inspect(op.get_bind()).has_table(name):
        return
    op.create_table(name, *args)
    logging.getLogger("alembic.runtime.migration").info("Создана таблица %s", name)


def upgrade() -> None:
    """Upgrade schema."""
    _create_missing(
        "allowed_users",
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("username", sa.String(), nullable=True),
        sa.Column("created_at", sa.BigInteger(), nullable=False),
        sa.Column("invited_by", sa.BigInteger(), nullable=True),
        sa.PrimaryKeyConstraint("user_id"),
    )
    _create_missing(
        "invites",
        sa.Column("code", sa.String(), nullable=False),
        sa.Column("created_by", sa.BigInteger(), nullable=False),
        sa.Column("created_at", sa.BigInteger(), nullable=False),
        sa.Column("expires_at", sa.BigInteger(), nullable=False),
        sa.Column("used_by", sa.BigInteger(), nullable=True),
        sa.Column("used_at", sa.BigInteger(), nullable=True),
        sa.PrimaryKeyConstraint("code"),
    )
    _create_missing(
        "user_prefs",
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("note_type_id", sa.String(), nullable=False),
        sa.Column("lang_q", sa.String(), nullable=False),
        sa.Column("lang_a", sa.String(), nullable=False),
        sa.Column("audio", sa.String(), nullable=False),
        sa.Column("updated_at", sa.BigInteger(), nullable=False),
        sa.PrimaryKeyConstraint("user_id"),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("user_prefs")
    op.drop_table("invites")
    op.drop_table("allowed_users")
