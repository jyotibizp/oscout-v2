"""Backfill scans and signals into a SEPARATE database (research tool, never the live DB).

Fetches 5m history for NIFTY, SENSEX and India VIX, builds 15m candles and indicators exactly like live
ingestion, then runs the live scan pipeline (engine + signal lifecycle + exits) once per completed 5m candle,
in time order, as if the scanner had been running. Every scan run is tagged trigger=BACKFILL and uses one
strategy configuration (copied from another DB's active config, or the defaults).

Usage (from backend/, with the Kite key in .env and a token for today in the live DB):
  python -m app.tools.backfill --out oscout_v2_backfill.db --days 60 \
      --config-from oscout_v2_live.db --token-from oscout_v2_live.db --candles-from oscout_v2_live.db
--candles-from fills days the provider leaves out (after midnight Kite stops returning the previous day).
"""
import argparse
import json
import os
import sqlite3
import sys
import time
from datetime import datetime, timedelta


def _live_row(path: str, sql: str):
    con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)  # read-only: never touch the live DB
    try:
        return con.execute(sql).fetchone()
    finally:
        con.close()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True, help="new SQLite file to create (must not exist)")
    ap.add_argument("--days", type=int, default=60, help="trading days to scan")
    ap.add_argument("--warmup-days", type=int, default=5, help="extra trading days fetched before the first scan")
    ap.add_argument("--config-from", help="SQLite DB whose active strategy configuration is used")
    ap.add_argument("--token-from", help="SQLite DB holding today's Kite access token")
    ap.add_argument("--provider", default="kite", choices=["kite", "mock"])
    ap.add_argument("--candles-from", action="append", default=[],
                    help="SQLite DB(s) whose stored 5m candles fill any gap the provider leaves (e.g. the live DB)")
    a = ap.parse_args()
    if os.path.exists(a.out):
        sys.exit(f"{a.out} already exists; choose a new file")

    cal_days = int((a.days + a.warmup_days) * 7 / 5) + 10  # trading days -> calendar days, holidays included
    os.environ.update({"DATABASE_URL": f"sqlite:///{os.path.abspath(a.out)}", "DATA_PROVIDER": a.provider,
                       "INITIAL_BACKFILL_DAYS": str(cal_days), "START_SCHEDULER": "false", "LOG_JSON": "false",
                       "LOG_LEVEL": "WARNING"})
    if a.token_from:
        row = _live_row(a.token_from, "select access_token from broker_sessions where provider='kite'")
        if row and row[0]:
            os.environ["KITE_ACCESS_TOKEN"] = row[0]

    from sqlalchemy import select

    import app.db.models  # noqa: F401
    from app.core.clock import UTC, as_utc, latest_completed_start, now_utc, session_close, session_open, to_ist
    from app.db.models import MarketCandle, ScanResult, ScanRun, SignalSetup, StrategyConfiguration, Trade
    from app.db.session import Base, SessionLocal, get_engine
    from app.market.factory import get_provider
    from app.market.ingestion import _insert, aggregate_15m, sync_5m, update_indicators
    from app.market.symbols import TRADABLE, VIX
    from app.scanner.service import run_scan
    from app.strategy import store
    from app.strategy.config import StrategyConfig

    Base.metadata.create_all(get_engine())
    db = SessionLocal()
    if a.config_from:  # copied as stored, so the same one-time config moves apply as in the live app
        ver, params = _live_row(a.config_from, "select version, params from strategy_configurations where is_active=1")
        params = json.loads(params)
    else:
        ver, params = "1.0.0", StrategyConfig().model_dump()
    db.add(StrategyConfiguration(version=ver, params=params, is_active=True, note="Backfill"))
    db.commit()
    row, cfg = store.get_active(db)
    ver = row.version

    t0 = time.time()
    provider, now = get_provider(), now_utc()
    for sym in TRADABLE + [VIX]:
        r = sync_5m(db, provider, sym, now)
        filled = 0
        for src in a.candles_from:  # provider gaps (e.g. Kite returning nothing for the last day after midnight)
            have = set(db.scalars(select(MarketCandle.ts).where(MarketCandle.symbol == sym, MarketCandle.timeframe == "5m")))
            con = sqlite3.connect(f"file:{src}?mode=ro", uri=True)
            rows = [{"ts": as_utc(datetime.fromisoformat(t[:19]).replace(tzinfo=UTC)), "open": o, "high": h, "low": l, "close": c, "volume": v}
                    for t, o, h, l, c, v in con.execute("select ts, open, high, low, close, volume from market_candles "
                                                        "where symbol=? and timeframe='5m'", (sym,))]
            con.close()
            first = min(have) if have else None
            rows = [x for x in rows if x["ts"] not in have and (first is None or x["ts"] > first)]
            filled += _insert(db, sym, "5m", rows, "copy")[0]
        n15 = aggregate_15m(db, sym)
        for p in sorted(cfg.indicator_periods()):
            update_indicators(db, sym, "5m", p)
            update_indicators(db, sym, "15m", p)
        db.commit()
        print(f"{sym}: {r.inserted_5m} 5m candles from {provider.name}, {filled} copied, {n15} 15m", flush=True)

    days = sorted({to_ist(ts).date() for ts in db.scalars(
        select(MarketCandle.ts).where(MarketCandle.symbol == TRADABLE[0], MarketCandle.timeframe == "5m"))})
    last_done = latest_completed_start(now, "5m")
    scan_days = days[-a.days:]
    print(f"scanning {len(scan_days)} trading days {scan_days[0]} .. {scan_days[-1]} on config v{ver}", flush=True)
    n = 0
    for d in scan_days:
        t = session_open(d)
        while t < session_close(d) and t <= to_ist(last_done):
            run_scan(db, provider, trigger="BACKFILL", now=t + timedelta(minutes=5, seconds=20), ingest=False)
            n += 1
            t += timedelta(minutes=5)
    print(f"{n} scans in {time.time() - t0:.0f}s", flush=True)
    sig = db.query(SignalSetup).filter(SignalSetup.signal_ts.isnot(None)).count()
    trades = db.query(Trade).count()
    print(f"signals {sig}, trades {trades}, scan results {db.query(ScanResult).count()}, runs {db.query(ScanRun).count()}")


if __name__ == "__main__":
    main()
