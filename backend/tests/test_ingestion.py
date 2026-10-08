from datetime import timedelta

from sqlalchemy import func, select

from app.db.models import IndicatorValue, MarketCandle, ScanResult
from app.indicators.wilder import series
from app.market.ingestion import aggregate_15m, sync_5m, sync_symbol, update_indicators
from app.market.providers import MockProvider
from app.scanner.service import run_scan
from tests.conftest import ist


class CountingProvider(MockProvider):
    def __init__(self, extra_duplicates=False, drop=None):
        super().__init__()
        self.calls, self.extra, self.drop = [], extra_duplicates, set(drop or [])

    def fetch_5m(self, symbol, frm, to):
        self.calls.append((symbol, frm, to))
        rows = [r for r in super().fetch_5m(symbol, frm, to) if r["ts"] not in self.drop]
        return rows + rows[:5] if self.extra else rows


def count(db, sym, tf):
    return db.scalar(select(func.count()).select_from(MarketCandle).where(MarketCandle.symbol == sym, MarketCandle.timeframe == tf))


def test_incremental_fetch_only_new_candles(db):
    p = CountingProvider()
    sync_5m(db, p, "NIFTY", ist(2026, 10, 7, 10, 1))
    n1 = count(db, "NIFTY", "5m")
    r = sync_5m(db, p, "NIFTY", ist(2026, 10, 7, 10, 11))
    assert p.calls[-1][1] == ist(2026, 10, 7, 10, 0)  # starts right after the last stored candle (09:55)
    assert r.inserted_5m == 2 and count(db, "NIFTY", "5m") == n1 + 2
    r = sync_5m(db, p, "NIFTY", ist(2026, 10, 7, 10, 12))  # nothing new completed -> no fetch
    assert r.fetched == 0 and len(p.calls) == 2


def test_forming_candle_is_not_stored(db):
    sync_5m(db, MockProvider(), "NIFTY", ist(2026, 10, 7, 10, 3))
    last = db.scalar(select(func.max(MarketCandle.ts)).where(MarketCandle.symbol == "NIFTY"))
    assert last == ist(2026, 10, 7, 9, 55)


def test_duplicate_candles_ignored(db):
    r = sync_5m(db, CountingProvider(extra_duplicates=True), "NIFTY", ist(2026, 10, 7, 10, 1))
    assert r.duplicates == 5
    n = count(db, "NIFTY", "5m")
    assert n == db.scalar(select(func.count(func.distinct(MarketCandle.ts))).where(MarketCandle.symbol == "NIFTY"))


def test_missing_5m_candle_skips_its_15m_bucket(db):
    missing = ist(2026, 10, 7, 9, 35)
    sync_5m(db, CountingProvider(drop=[missing]), "NIFTY", ist(2026, 10, 7, 10, 1))
    aggregate_15m(db, "NIFTY")
    ts15 = set(db.scalars(select(MarketCandle.ts).where(MarketCandle.symbol == "NIFTY", MarketCandle.timeframe == "15m")))
    assert ist(2026, 10, 7, 9, 30) not in ts15 and ist(2026, 10, 7, 9, 15) in ts15 and ist(2026, 10, 7, 9, 45) in ts15


def test_incremental_indicators_match_full_series(db):
    p = MockProvider()
    sync_symbol(db, p, "NIFTY", {14}, ist(2026, 10, 7, 10, 1))
    sync_symbol(db, p, "NIFTY", {14}, ist(2026, 10, 7, 12, 1))
    rows = db.scalars(select(MarketCandle).where(MarketCandle.symbol == "NIFTY", MarketCandle.timeframe == "5m")
                      .order_by(MarketCandle.ts)).all()
    full = series([r.high for r in rows], [r.low for r in rows], [r.close for r in rows], 14)
    last = db.scalars(select(IndicatorValue).where(IndicatorValue.symbol == "NIFTY", IndicatorValue.timeframe == "5m")
                      .order_by(IndicatorValue.ts.desc())).first()
    assert abs(last.adx - full[-1].adx) < 1e-9 and abs(last.atr - full[-1].atr) < 1e-9
    assert update_indicators(db, "NIFTY", "5m", 14) == 0  # nothing left to compute


def test_stale_data_prevents_signal(db):
    p = MockProvider()
    run_scan(db, p, "MANUAL", ist(2026, 10, 7, 11, 1))
    run, _ = run_scan(db, p, "MANUAL", ist(2026, 10, 7, 12, 1), ingest=False)  # no new data for an hour
    res = db.scalars(select(ScanResult).where(ScanResult.scan_run_id == run.id)).all()
    assert all(r.state == "REJECTED" and r.final_result == "NO_SIGNAL" and "STALE" in r.rejection_reason for r in res)


def test_auto_scan_is_unique_per_candle(db):
    p = MockProvider()
    r1, c1 = run_scan(db, p, "AUTO", ist(2026, 10, 7, 10, 0, 20))
    r2, c2 = run_scan(db, p, "AUTO", ist(2026, 10, 7, 10, 2, 0))
    assert c1 and not c2 and r1.id == r2.id
    _, c3 = run_scan(db, p, "AUTO", ist(2026, 10, 7, 10, 5, 20))
    assert c3
    assert ist(2026, 10, 7, 10, 5, 20) - ist(2026, 10, 7, 10, 0, 20) == timedelta(minutes=5)
