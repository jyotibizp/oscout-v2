"""Setup / signal lifecycle. One row per setup in signal_setups; every transition is an insert-only signal_event.

  BREAKOUT_DETECTED -> WAITING_CONFIRMATION -> SIGNAL_GENERATED -> ACTIVE -> EXIT_TRIGGERED
                    \\-> EXPIRED (confirmation window passed / invalidated)
                    \\-> REJECTED (ATR exhausted, VIX filter, entry window, signal already active)
"""
import logging
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.clock import is_session_last_candle, to_ist
from app.db.models import SignalEvent, SignalSetup, SystemEvent, Trade
from app.strategy.config import StrategyConfig
from app.strategy.engine import Bar, Position, StrategyResult, evaluate_exit

log = logging.getLogger(__name__)
PENDING = ("BREAKOUT_DETECTED", "WAITING_CONFIRMATION")
OPEN = ("SIGNAL_GENERATED", "ACTIVE")
DIR = {"CALL": 1, "PUT": -1}


def _event(db: Session, setup: SignalSetup, event: str, ts: datetime | None, price: float | None = None,
           note: str | None = None, data: dict | None = None):
    db.add(SignalEvent(setup_id=setup.id, event=event, candle_ts=ts, price=price, note=note, data=data))


def _set_state(db: Session, setup: SignalSetup, state: str, ts: datetime | None, note: str | None = None,
               price: float | None = None, data: dict | None = None):
    if setup.state != state:
        setup.state = state
        _event(db, setup, state, ts, price, note, data)


def update_open_signals(db: Session, symbol: str, bars5: list[Bar], cfg: StrategyConfig) -> list[SignalSetup]:
    """Advance every open signal of `symbol` over candles it has not seen yet. Returns setups that exited."""
    exited = []
    for s in db.scalars(select(SignalSetup).where(SignalSetup.symbol == symbol, SignalSetup.state.in_(OPEN))
                        .order_by(SignalSetup.id)):
        new = [b for b in bars5 if b.ts > (s.last_evaluated_ts or s.signal_ts)]
        if not new:
            continue
        ctx = s.signal_context or {}
        pos = Position(direction=DIR[s.direction], entry_price=s.entry_price, stop=s.stop_price, target=s.target_price,
                       peak_adx=s.peak_adx or ctx.get("adx5") or 0.0, last_adx=ctx.get("last_adx", s.peak_adx or 0.0),
                       declines=s.adx_declines or 0, held=ctx.get("held", 0))
        pos, ex = evaluate_exit(pos, new, cfg, lambda ts: is_session_last_candle(ts, "5m"))
        if s.state == "SIGNAL_GENERATED":
            _set_state(db, s, "ACTIVE", new[0].ts, "Signal active")
        s.peak_adx, s.adx_declines = pos.peak_adx, pos.declines
        s.signal_context = {**ctx, "last_adx": pos.last_adx, "held": pos.held}
        if ex is None:
            s.last_evaluated_ts = new[-1].ts
            continue
        s.last_evaluated_ts, s.exit_ts, s.exit_price, s.exit_reason = ex.ts, ex.ts, ex.price, ex.reason
        _set_state(db, s, "EXIT_TRIGGERED", ex.ts, ex.note, ex.price, {"reason": ex.reason})
        t = db.scalar(select(Trade).where(Trade.setup_id == s.id))
        if t is not None:
            d = DIR[s.direction]
            pts = (ex.price - t.entry_price) * d
            t.status, t.exit_ts, t.exit_price, t.exit_reason = "CLOSED", ex.ts, ex.price, ex.reason
            t.pnl_points = round(pts, 2)
            t.pnl_pct = round(pts / t.entry_price * 100, 4)
            t.r_multiple = round(pts / t.risk_points, 3) if t.risk_points else None
            t.holding_minutes = (ex.ts - t.entry_ts).total_seconds() / 60
        db.add(SystemEvent(ts=ex.ts, level="INFO", category="SIGNAL",
                           message=f"{symbol} {s.direction} exit: {ex.reason} @ {ex.price}",
                           data={"setup_id": s.id, "note": ex.note}))
        log.info("signal exit", extra={"ctx": {"symbol": symbol, "setup_id": s.id, "reason": ex.reason, "price": ex.price}})
        exited.append(s)
    return exited


def apply_result(db: Session, r: StrategyResult, cfg: StrategyConfig, config_id: int, config_version: str,
                 now: datetime) -> tuple[SignalSetup | None, str, str | None]:
    """Turn an engine result into lifecycle changes. Returns (setup, effective scan state, note)."""
    symbol = r.symbol
    pending = db.scalars(select(SignalSetup).where(SignalSetup.symbol == symbol, SignalSetup.state.in_(PENDING))).all()
    bo_ts = datetime.fromisoformat(r.breakout["ts"]) if r.breakout else None
    expired_note = None
    current = None
    for p in pending:
        if bo_ts is not None and p.breakout_ts == bo_ts and p.direction == r.direction:
            current = p
        else:
            why = ("Confirmation window passed" if bo_ts is None or bo_ts > p.breakout_ts
                   else "Breakout invalidated")
            if r.gate1.status == "FAIL" and r.gate1.reasons and "invalidated" in r.gate1.reasons[0]:
                why = r.gate1.reasons[0]
            _set_state(db, p, "EXPIRED", r.candle_ts, why)
            p.closed_reason = why
            expired_note = f"Setup #{p.id} expired: {why}"
    if bo_ts is None:
        return None, ("EXPIRED" if expired_note else r.state), expired_note

    if current is None:
        existing = db.scalar(select(SignalSetup).where(SignalSetup.symbol == symbol, SignalSetup.breakout_ts == bo_ts,
                                                       SignalSetup.direction == r.direction))
        if existing is not None:  # already resolved (signal / rejected / expired): don't re-open it
            return existing, (existing.state if existing.state in OPEN else r.state), None
        current = SignalSetup(symbol=symbol, direction=r.direction, state="NEW", breakout_ts=bo_ts, detected_at=now,
                              config_id=config_id, config_version=config_version, breakout=r.breakout)
        db.add(current)
        db.flush()
        bo = r.breakout
        comp_start = bo_ts - timedelta(minutes=5 * bo["compression_candles"])
        _event(db, current, "COMPRESSION", comp_start, None,
               f"ADX compressed ≤ threshold for {bo['compression_candles']} candles (low {bo['compression_low']})", bo)
        _event(db, current, "BREAKOUT", bo_ts, bo["ohlc"]["close"],
               f"5m ADX breakout {bo['adx_before']} → {bo['adx_at']}, {bo['direction']} ({'+DI' if bo['direction'] == 'CALL' else '−DI'} leads by {bo['di_separation']})", bo)

    if r.state in ("BREAKOUT_DETECTED", "WAITING_CONFIRMATION"):
        _set_state(db, current, r.state, r.candle_ts, r.gate2.reasons[0] if r.gate2.reasons else None,
                   data={"gate2": r.gate2.metrics})
        return current, r.state, None
    if r.state == "REJECTED":
        _set_state(db, current, "REJECTED", r.candle_ts, r.reason)
        current.closed_reason = r.reason
        return current, "REJECTED", r.reason
    if r.state != "QUALIFIED":
        return current, r.state, None

    active = db.scalar(select(SignalSetup).where(SignalSetup.symbol == symbol, SignalSetup.state.in_(OPEN),
                                                 SignalSetup.id != current.id))
    if active is not None and not cfg.exit.allow_new_entry_while_active:
        note = f"Signal #{active.id} ({active.direction}) still active — new entry not allowed"
        _set_state(db, current, "REJECTED", r.candle_ts, note)
        current.closed_reason = note
        return current, "ACTIVE", note
    for g, name in ((r.gate2, "GATE2_PASS"), (r.atr, "ATR_PASS"), (r.vix, "VIX_PASS")):
        _event(db, current, name, r.candle_ts, None, g.reasons[0] if g.reasons else None, g.metrics)
    current.signal_ts = r.candle_ts
    current.entry_price, current.entry_atr = r.entry_price, r.atr_value
    current.stop_price, current.target_price = r.stop_price, r.target_price
    current.peak_adx = r.snapshot.get("adx5")
    current.adx_declines = 0
    current.last_evaluated_ts = r.candle_ts
    current.signal_context = {"adx5": r.snapshot.get("adx5"), "adx15": r.snapshot.get("adx15"),
                              "atr_status": r.snapshot.get("atr_status"), "vix": r.snapshot.get("vix"),
                              "last_adx": r.snapshot.get("adx5"), "held": 0, "reason": r.reason,
                              "gate2": r.gate2.metrics, "atr": r.atr.metrics, "vix_filter": r.vix.metrics}
    _set_state(db, current, "SIGNAL_GENERATED", r.candle_ts, r.reason, r.entry_price)
    risk = abs(r.entry_price - r.stop_price) if r.stop_price else (
        r.atr_value * (cfg.exit.stop_atr_multiple or 1) if r.atr_value else None)
    db.add(Trade(setup_id=current.id, symbol=symbol, direction=r.direction, status="OPEN", entry_ts=r.candle_ts,
                 entry_price=r.entry_price, risk_points=round(risk, 2) if risk else None, config_version=config_version,
                 breakout_adx_change=r.breakout.get("adx_change"), adx5_entry=r.snapshot.get("adx5"),
                 adx15_entry=r.snapshot.get("adx15"), atr_status=r.snapshot.get("atr_status"),
                 vix_entry=r.snapshot.get("vix")))
    db.add(SystemEvent(ts=now, level="INFO", category="SIGNAL",
                       message=f"{symbol} {r.direction} BUY signal @ {r.entry_price} ({to_ist(r.candle_ts):%H:%M} IST)",
                       data={"setup_id": current.id, "reason": r.reason}))
    log.info("signal generated", extra={"ctx": {"symbol": symbol, "direction": r.direction, "entry": r.entry_price,
                                                 "setup_id": current.id, "config_version": config_version}})
    return current, "SIGNAL_GENERATED", r.reason
