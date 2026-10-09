"""Read stored candles + indicators as engine Bars, and the India VIX snapshot."""
from datetime import datetime, timedelta

from sqlalchemy import and_, select
from sqlalchemy.orm import Session

from app.core.clock import to_ist
from app.db.models import IndicatorValue, MarketCandle
from app.indicators.wilder import WilderState
from app.market.symbols import VIX
from app.strategy.engine import Bar, VixSnapshot


def load_bars(db: Session, symbol: str, tf: str, adx_period: int, atr_period: int, limit: int,
              until: datetime | None = None) -> list[Bar]:
    """Latest `limit` candles (<= until) with ADX/DI of `adx_period` and ATR of `atr_period`."""
    adx = IndicatorValue.__table__.alias("adx")
    atr = IndicatorValue.__table__.alias("atr")
    q = (select(MarketCandle.ts, MarketCandle.open, MarketCandle.high, MarketCandle.low, MarketCandle.close,
                adx.c.adx, adx.c.pdi, adx.c.mdi, atr.c.atr)
         .join(adx, and_(adx.c.symbol == MarketCandle.symbol, adx.c.timeframe == MarketCandle.timeframe,
                         adx.c.ts == MarketCandle.ts, adx.c.period == adx_period), isouter=True)
         .join(atr, and_(atr.c.symbol == MarketCandle.symbol, atr.c.timeframe == MarketCandle.timeframe,
                         atr.c.ts == MarketCandle.ts, atr.c.period == atr_period), isouter=True)
         .where(MarketCandle.symbol == symbol, MarketCandle.timeframe == tf))
    if until is not None:
        q = q.where(MarketCandle.ts <= until)
    rows = db.execute(q.order_by(MarketCandle.ts.desc()).limit(limit)).all()
    out = []
    for r in reversed(rows):
        out.append(Bar(ts=_aware(r.ts), open=r.open, high=r.high, low=r.low, close=r.close,
                       adx=r.adx, pdi=r.pdi, mdi=r.mdi, atr=r.atr))
    return out


def wilder_state(db: Session, symbol: str, tf: str, period: int, at: datetime) -> WilderState | None:
    """Stored Wilder state of the latest candle at or before `at` (for forward projections)."""
    r = db.scalars(select(IndicatorValue).where(IndicatorValue.symbol == symbol, IndicatorValue.timeframe == tf,
                                                IndicatorValue.period == period, IndicatorValue.ts <= at)
                   .order_by(IndicatorValue.ts.desc()).limit(1)).first()
    if r is None:
        return None
    return WilderState(n=r.n, high=r.high, low=r.low, close=r.close, atr=r.atr, pdm=r.pdm, mdm=r.mdm, pdi=r.pdi,
                       mdi=r.mdi, dx=r.dx, adx=r.adx, tr_sum=r.tr_sum, pdm_sum=r.pdm_sum, mdm_sum=r.mdm_sum,
                       dx_sum=r.dx_sum)


def _aware(ts: datetime) -> datetime:
    from app.core.clock import UTC
    return ts if ts.tzinfo else ts.replace(tzinfo=UTC)


def vix_snapshot(db: Session, now: datetime, max_age_minutes: int, market_open: bool) -> VixSnapshot | None:
    # latest VIX candle completed by `now` (live: the newest stored one; backfill: as of the scanned candle)
    last = db.scalar(select(MarketCandle).where(MarketCandle.symbol == VIX, MarketCandle.timeframe == "5m",
                                                MarketCandle.ts <= now - timedelta(minutes=5))
                     .order_by(MarketCandle.ts.desc()).limit(1))
    if last is None:
        return None
    day = to_ist(last.ts).date()
    prev = db.scalar(select(MarketCandle).where(MarketCandle.symbol == VIX, MarketCandle.timeframe == "5m",
                                                MarketCandle.ts < _day_start_utc(day))
                     .order_by(MarketCandle.ts.desc()).limit(1))
    age = (now - (_aware(last.ts) + timedelta(minutes=5))).total_seconds() / 60
    return VixSnapshot(value=last.close, prev_close=prev.close if prev else None, ts=_aware(last.ts),
                       stale=market_open and age > max_age_minutes)


def _day_start_utc(d) -> datetime:
    from app.core.clock import as_utc, session_open
    return as_utc(session_open(d))
