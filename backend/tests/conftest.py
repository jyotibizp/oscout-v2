import os
from datetime import datetime, timedelta

import pytest

os.environ["START_SCHEDULER"] = "false"
os.environ["DATA_PROVIDER"] = "mock"
os.environ["LOG_JSON"] = "false"

from app.core.clock import IST, as_utc  # noqa: E402
from app.db.session import Base, SessionLocal, reset_engine  # noqa: E402
from app.market.factory import set_provider  # noqa: E402
from app.market.providers import MockProvider  # noqa: E402
from app.strategy.engine import Bar  # noqa: E402


@pytest.fixture()
def db(tmp_path):
    engine = reset_engine(f"sqlite:///{tmp_path / 'test.db'}")
    import app.db.models  # noqa: F401
    Base.metadata.create_all(engine)
    set_provider(MockProvider())
    s = SessionLocal()
    yield s
    s.close()


def ist(y, mo, d, h, mi, s=0):
    return as_utc(datetime(y, mo, d, h, mi, s, tzinfo=IST))


def make_bars(adx, pdi=None, mdi=None, start=None, close=None, atr=10.0, step_minutes=5):
    """Engine Bars with explicit ADX/DI values (prices follow `close` or stay flat at 100)."""
    start = start or ist(2026, 10, 7, 9, 15)
    n = len(adx)
    pdi = pdi if isinstance(pdi, list) else [pdi if pdi is not None else 25.0] * n
    mdi = mdi if isinstance(mdi, list) else [mdi if mdi is not None else 15.0] * n
    close = close if isinstance(close, list) else [close or 100.0] * n
    out = []
    t = start
    for i in range(n):
        c = close[i]
        out.append(Bar(t, c, c + 1, c - 1, c, adx[i], pdi[i], mdi[i], atr))
        t += timedelta(minutes=step_minutes)
    return out
