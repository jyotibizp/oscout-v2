"""Incremental candle ingestion + 15m aggregation + incremental indicators.

For each symbol: find the latest stored 5m candle, fetch only newer candles up to the latest COMPLETED
one, insert idempotently (unique (symbol, timeframe, ts)), then build any newly completed 15m candles
from stored 5m candles and extend the Wilder indicator series from its last stored state.
Nothing is ever deleted; duplicates are ignored.
"""
import logging
import math
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.clock import as_utc, is_aligned, latest_completed_start, now_utc, session_open, to_ist
from app.core.settings import get_settings
from app.db.models import IndicatorValue, MarketCandle
from app.indicators.wilder import WilderState, step

log = logging.getLogger(__name__)
TF5 = timedelta(minutes=5)


@dataclass
class SyncResult:
    symbol: str
    fetched: int = 0
    inserted_5m: int = 0
    duplicates: int = 0
    rejected: int = 0
    inserted_15m: int = 0
    indicators: dict = field(default_factory=dict)
    latest_5m: datetime | None = None
    error: str | None = None


def valid_ohlc(r: dict) -> bool:
    try:
        o, h, l, c = (float(r[k]) for k in ("open", "high", "low", "close"))
    except (KeyError, TypeError, ValueError):
        return False
    if not all(math.isfinite(x) and x > 0 for x in (o, h, l, c)):
        return False
    return h >= max(o, c) - 1e-9 and l <= min(o, c) + 1e-9


def latest_ts(db: Session, symbol: str, tf: str) -> datetime | None:
    return db.scalar(select(func.max(MarketCandle.ts)).where(MarketCandle.symbol == symbol, MarketCandle.timeframe == tf))


def candle_count(db: Session, symbol: str, tf: str) -> int:
    return db.scalar(select(func.count()).select_from(MarketCandle).where(
        MarketCandle.symbol == symbol, MarketCandle.timeframe == tf)) or 0


def _insert(db: Session, symbol: str, tf: str, rows: list[dict], source: str) -> tuple[int, int]:
    """Insert ignoring candles that already exist. Returns (inserted, duplicates)."""
    if not rows:
        return 0, 0
    existing = set(db.scalars(select(MarketCandle.ts).where(
        MarketCandle.symbol == symbol, MarketCandle.timeframe == tf,
        MarketCandle.ts >= min(r["ts"] for r in rows), MarketCandle.ts <= max(r["ts"] for r in rows))))
    seen, ins, dup = set(), 0, 0
    for r in sorted(rows, key=lambda x: x["ts"]):
        if r["ts"] in existing or r["ts"] in seen:
            dup += 1
            continue
        seen.add(r["ts"])
        db.add(MarketCandle(symbol=symbol, timeframe=tf, ts=r["ts"], open=r["open"], high=r["high"], low=r["low"],
                            close=r["close"], volume=r.get("volume", 0) or 0, source=source))
        ins += 1
    db.flush()
    return ins, dup


def sync_5m(db: Session, provider, symbol: str, now: datetime | None = None) -> SyncResult:
    now = now or now_utc()
    res = SyncResult(symbol)
    boundary = latest_completed_start(now, "5m")
    last = latest_ts(db, symbol, "5m")
    if last is not None and last >= boundary:
        res.latest_5m = last
        return res
    if last is None:
        start_day = (to_ist(boundary) - timedelta(days=get_settings().initial_backfill_days)).date()
        frm = as_utc(session_open(start_day))
    else:
        frm = last + TF5
    rows = provider.fetch_5m(symbol, frm, boundary + TF5 - timedelta(seconds=1))
    res.fetched = len(rows)
    clean = []
    for r in rows:
        ts = r.get("ts")
        if not isinstance(ts, datetime) or ts > boundary or not is_aligned(ts, "5m") or not valid_ohlc(r):
            res.rejected += 1  # forming / misaligned / malformed candle
            continue
        if last is not None and ts <= last:
            res.duplicates += 1
            continue
        clean.append({**r, "ts": as_utc(ts)})
    res.inserted_5m, d = _insert(db, symbol, "5m", clean, provider.name)
    res.duplicates += d
    res.latest_5m = latest_ts(db, symbol, "5m")
    return res


def aggregate_15m(db: Session, symbol: str) -> int:
    """Build 15m candles (aligned to 09:15 IST) from stored 5m candles. A 15m candle is written only
    when all three 5m candles exist, so it is never built from a partial bucket."""
    last15 = latest_ts(db, symbol, "15m")
    q = select(MarketCandle).where(MarketCandle.symbol == symbol, MarketCandle.timeframe == "5m")
    if last15 is not None:
        q = q.where(MarketCandle.ts >= last15 + timedelta(minutes=15))
    five = db.scalars(q.order_by(MarketCandle.ts)).all()
    buckets: dict[datetime, list[MarketCandle]] = {}
    for c in five:
        t = to_ist(c.ts)
        o = session_open(t.date())
        start = o + ((t - o) // timedelta(minutes=15)) * timedelta(minutes=15)
        buckets.setdefault(as_utc(start), []).append(c)
    rows = []
    for start, cs in sorted(buckets.items()):
        if len(cs) != 3:
            continue
        cs.sort(key=lambda c: c.ts)
        rows.append({"ts": start, "open": cs[0].open, "high": max(c.high for c in cs), "low": min(c.low for c in cs),
                     "close": cs[-1].close, "volume": sum(c.volume for c in cs)})
    ins, _ = _insert(db, symbol, "15m", rows, "agg")
    return ins


def update_indicators(db: Session, symbol: str, tf: str, period: int) -> int:
    """Extend the stored Wilder series to every candle that has no indicator row yet."""
    last_row = db.scalars(select(IndicatorValue).where(
        IndicatorValue.symbol == symbol, IndicatorValue.timeframe == tf, IndicatorValue.period == period)
        .order_by(IndicatorValue.ts.desc()).limit(1)).first()
    q = select(MarketCandle).where(MarketCandle.symbol == symbol, MarketCandle.timeframe == tf)
    state = None
    if last_row is not None:
        q = q.where(MarketCandle.ts > last_row.ts)
        state = WilderState(n=last_row.n, high=last_row.high, low=last_row.low, close=last_row.close,
                            atr=last_row.atr, pdm=last_row.pdm, mdm=last_row.mdm, pdi=last_row.pdi, mdi=last_row.mdi,
                            dx=last_row.dx, adx=last_row.adx, tr_sum=last_row.tr_sum, pdm_sum=last_row.pdm_sum,
                            mdm_sum=last_row.mdm_sum, dx_sum=last_row.dx_sum)
    n = 0
    for c in db.scalars(q.order_by(MarketCandle.ts)):
        state = step(state, c.high, c.low, c.close, period)
        db.add(IndicatorValue(symbol=symbol, timeframe=tf, period=period, ts=c.ts, **state.as_dict()))
        n += 1
    db.flush()
    return n


def sync_symbol(db: Session, provider, symbol: str, periods: set[int], now: datetime | None = None) -> SyncResult:
    res = sync_5m(db, provider, symbol, now)
    res.inserted_15m = aggregate_15m(db, symbol)
    for p in sorted(periods):
        res.indicators[f"5m/{p}"] = update_indicators(db, symbol, "5m", p)
        res.indicators[f"15m/{p}"] = update_indicators(db, symbol, "15m", p)
    log.info("ingestion", extra={"ctx": {"symbol": symbol, "fetched": res.fetched, "inserted_5m": res.inserted_5m,
                                         "inserted_15m": res.inserted_15m, "duplicates": res.duplicates,
                                         "rejected": res.rejected}})
    return res
