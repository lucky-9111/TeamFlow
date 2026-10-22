"""Engine and session setup. SQLite-specific settings are confined to this module."""

from collections.abc import Iterator
from pathlib import Path

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings


def _sqlite_pragmas(enforce_foreign_keys: bool):
    def apply(dbapi_connection, _record) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute(f"PRAGMA foreign_keys={'ON' if enforce_foreign_keys else 'OFF'}")
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA busy_timeout=5000")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.close()

    return apply


def _sqlite_begin(conn) -> None:
    # pysqlite's default transaction handling defers BEGIN and breaks SAVEPOINT semantics.
    # Emit BEGIN ourselves; IMMEDIATE takes the write lock up front so read-then-write
    # transactions fail fast on busy_timeout instead of deadlocking on lock upgrade.
    conn.exec_driver_sql("BEGIN IMMEDIATE")


def create_db_engine(url: str, *, enforce_foreign_keys: bool = True) -> Engine:
    """`enforce_foreign_keys=False` is only for Alembic: SQLite batch migrations recreate tables,
    and with enforcement on, dropping a parent table would fire ON DELETE CASCADE."""
    if url.startswith("sqlite"):
        db_path = url.removeprefix("sqlite:///")
        if db_path and ":memory:" not in db_path:
            Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        engine = create_engine(url, connect_args={"check_same_thread": False, "isolation_level": None})
        event.listen(engine, "connect", _sqlite_pragmas(enforce_foreign_keys))
        event.listen(engine, "begin", _sqlite_begin)
        return engine
    return create_engine(url, pool_pre_ping=True)


engine = create_db_engine(get_settings().database_url)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
