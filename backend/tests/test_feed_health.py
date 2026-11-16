from app.db.models import MarketCandle
from app.market.health import feed_status
from tests.conftest import ist


def _candle(db, ts):
    db.add(MarketCandle(symbol="NIFTY", timeframe="5m", ts=ts, open=1, high=1, low=1, close=1, source="mock"))
    db.commit()


def test_closed_market_flags_days_old_data_stale(db):
    _candle(db, ist(2026, 11, 9, 15, 25))           # Mon; Kite disconnected after that
    now = ist(2026, 11, 16, 9, 10)                   # next Monday, before the open
    assert feed_status(db, "NIFTY", "5m", now, 10)["status"] == "STALE"


def test_closed_market_allows_one_holiday(db):
    _candle(db, ist(2026, 11, 12, 15, 25))          # Thu; Fri a holiday
    now = ist(2026, 11, 14, 10, 0)                   # Saturday
    assert feed_status(db, "NIFTY", "5m", now, 10)["status"] == "HEALTHY"
