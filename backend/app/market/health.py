"""Feed freshness. A signal is never generated from stale or missing data."""
from datetime import datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.clock import is_market_open, latest_completed_start
from app.db.models import MarketCandle
from app.market.symbols import TRADABLE, VIX

# last ingestion outcome per symbol (process memory; also written to system_events)
LAST_SYNC: dict[str, dict] = {}


def feed_status(db: Session, symbol: str, tf: str, now: datetime, max_age_minutes: int) -> dict:
    last, count, updated = db.execute(select(func.max(MarketCandle.ts), func.count(), func.max(MarketCandle.created_at))
                                      .where(MarketCandle.symbol == symbol, MarketCandle.timeframe == tf)).one()
    expected = latest_completed_start(now, tf)
    open_ = is_market_open(now)
    if last is None:
        status, reason = "MISSING", f"No {tf} candles stored"
    elif open_ and last < expected - timedelta(minutes=max_age_minutes if tf == "5m" else max_age_minutes + 15):
        status, reason = "STALE", f"Latest {tf} candle {last.isoformat()} is behind the expected {expected.isoformat()}"
    else:
        status, reason = "HEALTHY", None
    sync = LAST_SYNC.get(symbol, {})
    if sync.get("error") and status == "HEALTHY" and open_:
        status, reason = "ERROR", sync["error"]
    return {"feed": f"{symbol} {tf.upper()}", "symbol": symbol, "timeframe": tf, "status": status, "reason": reason,
            "last_candle": last.isoformat() if last else None, "expected_candle": expected.isoformat(),
            "candles": count, "last_update": updated.isoformat() if updated else None,
            "last_sync": sync.get("at"), "last_error": sync.get("error"), "market_open": open_}


def all_feeds(db: Session, now: datetime, max_age_minutes: int) -> list[dict]:
    out = []
    for s in TRADABLE:
        out.append(feed_status(db, s, "5m", now, max_age_minutes))
        out.append(feed_status(db, s, "15m", now, max_age_minutes))
    v = feed_status(db, VIX, "5m", now, max_age_minutes)
    v["feed"] = "INDIA VIX"
    out.append(v)
    return out
