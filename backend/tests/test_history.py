from datetime import timedelta

from sqlalchemy import func, select

from app.core.clock import to_ist
from app.db.models import IndicatorValue, MarketCandle
from app.market import history
from app.market.providers import MockProvider
from app.market.symbols import TRADABLE, VIX
from app.scanner import gaps
from app.scanner.service import ingest_all
from app.strategy import store
from tests.conftest import client_at, ist

NOW = ist(2026, 10, 7, 15, 40)


def _count(db, sym, tf):
    return db.scalar(select(func.count()).select_from(MarketCandle).where(MarketCandle.symbol == sym, MarketCandle.timeframe == tf))


def test_load_history_adds_older_candles_and_rebuilds_indicators(db):
    p = MockProvider()
    _, cfg = store.get_active(db)
    ingest_all(db, p, cfg, NOW)
    first = history.earliest(db, "NIFTY")
    before = {s: (_count(db, s, "5m"), db.scalars(select(MarketCandle.close).where(MarketCandle.symbol == s, MarketCandle.timeframe == "5m")
                                                  .order_by(MarketCandle.ts.desc()).limit(5)).all()) for s in TRADABLE}
    d_from = to_ist(first).date() - timedelta(days=14)
    out = history.load(db, p, d_from, cfg.indicator_periods())
    assert {r["symbol"] for r in out} == set(TRADABLE + [VIX]) and all(r["status"] == "LOADED" for r in out)
    for s in TRADABLE:
        assert history.earliest(db, s) < first
        n5, last = before[s]
        assert _count(db, s, "5m") == n5 + next(r["inserted_5m"] for r in out if r["symbol"] == s) > n5
        assert db.scalars(select(MarketCandle.close).where(MarketCandle.symbol == s, MarketCandle.timeframe == "5m")
                          .order_by(MarketCandle.ts.desc()).limit(5)).all() == last  # existing candles untouched
        for tf in ("5m", "15m"):
            for per in cfg.indicator_periods():
                assert db.scalar(select(func.count()).select_from(IndicatorValue).where(
                    IndicatorValue.symbol == s, IndicatorValue.timeframe == tf, IndicatorValue.period == per)) == _count(db, s, tf)
    assert history.stored_from(db) == d_from.isoformat() or history.stored_from(db) > d_from.isoformat()
    # the loaded days are now gaps on the Scan gaps page
    g = gaps.find(db, d_from, to_ist(first).date() - timedelta(days=1), NOW)
    assert g["blocks"] and all(b["data"] == "FULL" for b in g["blocks"])
    assert all(r["status"] == "UP_TO_DATE" for r in history.load(db, p, d_from, cfg.indicator_periods()) if r["symbol"] in TRADABLE)


def test_history_api_validates_range():
    c = client_at("127.0.0.1")
    assert c.post("/api/market/history", json={"from": "2020-01-01"}).status_code == 400
    assert client_at("100.64.0.9").post("/api/market/history", json={"from": "2026-10-01"}).status_code in (401, 403)
