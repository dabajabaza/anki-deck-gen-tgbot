"""user_prefs.theme

Оформление карточек стало частью Настроек колоды (ARCHITECTURE A15), и «Как в
прошлый раз» должно помнить и его. Старые строки получают 'card' — тему, которой
до этого фактически и собирались все колоды.

Колонка добавляется, только если её нет: тот же принцип, что у базовой ревизии, —
частично созданная руками схема не должна ронять upgrade.

Revision ID: b7d1e2c3f4a5
Revises: 8ac92f3a4fb0
Create Date: 2026-09-04 09:00:00

"""

import logging
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b7d1e2c3f4a5"
down_revision: str | Sequence[str] | None = "8ac92f3a4fb0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    columns = {column["name"] for column in sa.inspect(op.get_bind()).get_columns("user_prefs")}
    if "theme" in columns:
        return
    op.add_column(
        "user_prefs",
        sa.Column("theme", sa.String(), nullable=False, server_default="card"),
    )
    logging.getLogger("alembic.runtime.migration").info("Добавлена колонка user_prefs.theme")


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table("user_prefs") as batch:
        batch.drop_column("theme")
