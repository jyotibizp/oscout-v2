from datetime import datetime

from sqlalchemy import DateTime, create_engine, event
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from sqlalchemy.types import TypeDecorator

from app.core.clock import UTC, as_utc
from app.core.settings import get_settings


class UTCDateTime(TypeDecorator):
    """Stores timezone-aware datetimes as UTC on every backend (SQLite keeps no offset) and
    always returns aware UTC values."""
    impl = DateTime(timezone=True)
    cache_ok = True

    def process_bind_param(self, value: datetime | None, dialect):
        if value is None:
            return None
        v = as_utc(value)
        return v.replace(tzinfo=None) if dialect.name == "sqlite" else v

    def process_result_value(self, value: datetime | None, dialect):
        if value is None:
            return None
        return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


class Base(DeclarativeBase):
    pass


_engine = None
SessionLocal = sessionmaker(autoflush=True, expire_on_commit=False)


def get_engine():
    global _engine
    if _engine is None:
        url = get_settings().database_url
        kw = {"connect_args": {"check_same_thread": False}} if url.startswith("sqlite") else {"pool_pre_ping": True}
        _engine = create_engine(url, **kw)
        if url.startswith("sqlite"):
            @event.listens_for(_engine, "connect")
            def _fk_on(conn, _):  # enforce FKs on SQLite
                conn.execute("PRAGMA foreign_keys=ON")
        SessionLocal.configure(bind=_engine)
    return _engine


def reset_engine(url: str | None = None):
    """Tests: point the app at a different database."""
    global _engine
    if _engine is not None:
        _engine.dispose()
    _engine = None
    if url:
        get_settings().database_url = url
    return get_engine()


def get_db():
    get_engine()
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
