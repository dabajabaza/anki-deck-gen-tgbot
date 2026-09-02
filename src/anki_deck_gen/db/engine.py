"""Подключение к БД. По умолчанию SQLite (aiosqlite); URL — любой async-драйвер
SQLAlchemy, при переезде на PostgreSQL код не меняется.

Перенос из lesson-tracker с урезанным обоснованием: здесь нет единицы работы и
общего замка записи. Писателей мало — /allow, /invite, погашение инвайта,
«как в прошлый раз» — и каждый живёт в своей короткой сессии с commit. Но два
свойства движка остались нужны ровно по тем же причинам, что и там:

* BEGIN IMMEDIATE у писателей — против внешнего писателя: миграции на старте,
  ручного скрипта над боевой базой. DEFERRED-писатель, прочитавший данные до
  первой записи, получает мгновенный «database is locked», которому busy_timeout
  не помогает; IMMEDIATE честно ждёт.
* READONLY-соединения — для проверки доступа, которая идёт на КАЖДЫЙ апдейт, в
  том числе на поток чужих. Ей нужен DEFERRED: в WAL читатель не берёт
  блокировку записи вовсе, а IMMEDIATE взял бы её и на чистом SELECT — и каждый
  спам-месседж вставал бы в очередь за записью.
"""

from sqlalchemy import event
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

# Помечает соединение как заведомо читающее: транзакция откроется как DEFERRED
# и блокировку записи не тронет. Ставится через execution_options — см.
# services.access.is_allowed_readonly, единственного законного потребителя.
READONLY = "anki_deck_gen_readonly"


def create_db(db_url: str) -> tuple[AsyncEngine, async_sessionmaker[AsyncSession]]:
    engine = create_async_engine(db_url, echo=False)
    if db_url.startswith("sqlite"):

        @event.listens_for(engine.sync_engine, "connect")
        def _sqlite_pragmas(dbapi_conn, _record):
            # WAL + busy_timeout: читатели не ждут писателя, а опоздавший
            # писатель ждёт, а не падает.
            cur = dbapi_conn.cursor()
            cur.execute("PRAGMA journal_mode=WAL")
            cur.execute("PRAGMA busy_timeout=5000")
            cur.close()
            # Отключаем собственное управление транзакциями у драйвера pysqlite.
            # Без этого SAVEPOINT сломан: драйвер не открывает настоящую
            # транзакцию, RELEASE SAVEPOINT фактически фиксирует запись, и
            # последующий rollback её уже не отменяет. На это опирается
            # access.allow_user — begin_nested вокруг вставки.
            dbapi_conn.isolation_level = None

        @event.listens_for(engine.sync_engine, "begin")
        def _sqlite_begin(conn):
            # Раз драйвер больше не начинает транзакции сам, начинаем явно —
            # IMMEDIATE для писателей, DEFERRED для помеченных READONLY.
            if conn.get_execution_options().get(READONLY):
                conn.exec_driver_sql("BEGIN")
            else:
                conn.exec_driver_sql("BEGIN IMMEDIATE")

    sessionmaker = async_sessionmaker(engine, expire_on_commit=False)
    return engine, sessionmaker
