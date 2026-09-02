"""Контроль доступа на уровне сервиса: Гости, Админы, одноразовые Инвайты.

Фикстура session — в conftest.py: личная файловая копия базы, собранной
настоящими миграциями. Не in-memory — файл нужен и для копирования шаблона, и
для проб вторым соединением (is_allowed_readonly ходит через движок).

Проверки через диспетчер (Посторонний получает тишину, /start <код> пускает)
живут в test_handlers.py — им нужен харнесс бота.
"""

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from anki_deck_gen.db.models import AllowedUser, Invite
from anki_deck_gen.services import access
from anki_deck_gen.timeutils import now_ts

ADMIN = frozenset({111})
STRANGER = 999
INVITEE = 555


# ---------- допуск ----------


async def test_stranger_is_not_allowed(session: AsyncSession) -> None:
    assert await access.is_allowed(session, ADMIN, STRANGER) is False


async def test_admin_allowed_without_db_row(session: AsyncSession) -> None:
    """Админа пускает конфиг — строка в allowed_users ему не нужна."""
    assert await access.is_allowed(session, ADMIN, 111) is True
    assert await session.get(AllowedUser, 111) is None


async def test_allow_user_grants_access(session: AsyncSession) -> None:
    await access.allow_user(session, STRANGER, "vasya")
    assert await access.is_allowed(session, ADMIN, STRANGER) is True


async def test_allow_user_is_idempotent_and_refreshes_username(session: AsyncSession) -> None:
    await access.allow_user(session, STRANGER, "old")
    row = await access.allow_user(session, STRANGER, "new")
    assert row.username == "new"

    count = await session.scalar(select(func.count()).select_from(AllowedUser))
    assert count == 1


async def test_empty_admin_ids_blocks_everyone(session: AsyncSession) -> None:
    """Пустой ADMIN_IDS не должен случайно открывать доступ всем."""
    assert await access.is_allowed(session, frozenset(), 111) is False


async def test_is_allowed_readonly_matches_is_allowed(
    engine: AsyncEngine, session: AsyncSession
) -> None:
    """Быстрая проверка без транзакции записи видит то же, что и обычная, —
    в том числе строку, закоммиченную другим соединением."""
    assert await access.is_allowed_readonly(engine, ADMIN, 111) is True
    assert await access.is_allowed_readonly(engine, ADMIN, STRANGER) is False

    await access.allow_user(session, STRANGER, "vasya")
    await session.commit()

    assert await access.is_allowed_readonly(engine, ADMIN, STRANGER) is True
    assert await access.is_allowed_readonly(engine, frozenset(), 111) is False


# ---------- приглашения ----------


async def test_invite_grants_access(session: AsyncSession) -> None:
    invite = await access.create_invite(session, created_by=111)
    assert await access.redeem_invite(session, invite.code, INVITEE, "petya") is True
    assert await access.is_allowed(session, ADMIN, INVITEE) is True


async def test_invite_records_who_invited(session: AsyncSession) -> None:
    invite = await access.create_invite(session, created_by=111)
    await access.redeem_invite(session, invite.code, INVITEE, None)

    row = await session.get(AllowedUser, INVITEE)
    assert row is not None and row.invited_by == 111


async def test_invite_is_one_time(session: AsyncSession) -> None:
    invite = await access.create_invite(session, created_by=111)
    assert await access.redeem_invite(session, invite.code, INVITEE, None) is True
    # Второй пользователь по тому же коду пройти не должен.
    assert await access.redeem_invite(session, invite.code, 777, None) is False
    assert await access.is_allowed(session, ADMIN, 777) is False


async def test_unknown_code_rejected(session: AsyncSession) -> None:
    assert await access.redeem_invite(session, "no-such-code", INVITEE, None) is False
    assert await access.is_allowed(session, ADMIN, INVITEE) is False


async def test_expired_invite_rejected(session: AsyncSession) -> None:
    invite = Invite(code="expired", created_by=111, expires_at=now_ts() - 1)
    session.add(invite)
    await session.flush()

    assert await access.redeem_invite(session, "expired", INVITEE, None) is False
    assert await access.is_allowed(session, ADMIN, INVITEE) is False


async def test_invite_codes_are_unique(session: AsyncSession) -> None:
    codes = {(await access.create_invite(session, created_by=111)).code for _ in range(20)}
    assert len(codes) == 20


async def test_invite_lives_forty_eight_hours() -> None:
    assert access.INVITE_TTL_SECONDS == 48 * 3600


# ---------- обзор для /access ----------


async def test_list_allowed_returns_guests_in_admission_order(session: AsyncSession) -> None:
    assert await access.list_allowed(session) == []
    await access.allow_user(session, 10, "first")
    await access.allow_user(session, 20, "second")
    assert [row.user_id for row in await access.list_allowed(session)] == [10, 20]


async def test_live_invites_excludes_used_and_expired(session: AsyncSession) -> None:
    live = await access.create_invite(session, created_by=111)
    used = await access.create_invite(session, created_by=111)
    await access.redeem_invite(session, used.code, INVITEE, None)
    session.add(Invite(code="stale", created_by=111, expires_at=now_ts() - 1))
    await session.flush()

    assert [invite.code for invite in await access.live_invites(session)] == [live.code]
