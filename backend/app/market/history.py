"""Load older history: fetch 5m candles before the earliest stored one, build their 15m candles and recompute the
Wilder indicators from the new start. Candles are only added (existing candles untouched). Indicator values are a
derived cache, so they are rebuilt for the whole series: the warm-up then starts at the new first candle.
Scan results keep the values they were scanned with. The loaded days then show as gaps on Scan gaps (#2/#23)."""
from datetime import date, datetime, timedelta

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.core.clock import UTC, as_utc, is_aligned, session_open, to_ist
from app.db.models import IndicatorValue, MarketCandle
from app.market.ingestion import _insert, aggregate_15m, update_indicators, valid_ohlc
from app.market.symbols import TRADABLE, VIX

MAX_DAYS = 400


def _utc(dt: datetime) -> datetime:
    return dt.replace(tzinfo=UTC) if dt.tzinfo is None else dt.astimezone(UTC)


def earliest(db: Session, symbol: str, tf: str = "5m") -> datetime | None:
    t = db.scalar(select(func.min(MarketCandle.ts)).where(MarketCandle.symbol == symbol, MarketCandle.timeframe == tf))
    return _utc(t) if t else None


def stored_from(db: Session) -> str | None:
    """First day with candles, over the tradable indexes (IST date)."""
    ts = [t for t in (earliest(db, s) for s in TRADABLE) if t]
    return to_ist(min(ts)).date().isoformat() if ts else None


def load(db: Session, provider, d_from: date, periods: set[int]) -> list[dict]:
    lo = as_utc(session_open(d_from))
    out = []
    for sym in TRADABLE + [VIX]:
        first = earliest(db, sym)
        if first is None:
            out.append({"symbol": sym, "status": "SKIPPED", "message": "No candles yet: the normal sync loads them"})
            continue
        if lo >= first:
            out.append({"symbol": sym, "status": "UP_TO_DATE", "inserted_5m": 0})
            continue
        rows = provider.fetch_5m(sym, lo, first - timedelta(seconds=1))
        clean = [{**r, "ts": as_utc(r["ts"])} for r in rows
                 if isinstance(r.get("ts"), datetime) and is_aligned(r["ts"], "5m") and valid_ohlc(r) and as_utc(r["ts"]) < first]
        ins, dup = _insert(db, sym, "5m", clean, provider.name)
        n15 = aggregate_15m(db, sym, before=earliest(db, sym, "15m"))
        db.execute(delete(IndicatorValue).where(IndicatorValue.symbol == sym))
        for p in sorted(periods):
            update_indicators(db, sym, "5m", p)
            update_indicators(db, sym, "15m", p)
        db.commit()
        out.append({"symbol": sym, "status": "LOADED", "inserted_5m": ins, "inserted_15m": n15, "duplicates": dup,
                    "rejected": len(rows) - len(clean),
                    "from": to_ist(earliest(db, sym)).date().isoformat()})
    return out
