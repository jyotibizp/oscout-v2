"""Live view of an open signal at the latest completed candle: P&L, live stop, and a HOLD / TRAIL / WATCH verdict.
Read-only: the exit engine (lifecycle.update_open_signals) decides exits; this only explains where a signal stands."""
from app.core.clock import session_close, tf_delta, to_ist
from app.db.models import SignalSetup
from app.strategy.config import StrategyConfig
from app.strategy.engine import Bar

DIR = {"CALL": 1, "PUT": -1}
NEAR_R = 0.25  # within this many R of the stop / target counts as "near"
SOON = 3       # candles left before a time exit counts as "soon"


def track(s: SignalSetup, last: Bar | None, cfg: StrategyConfig) -> dict | None:
    if last is None or s.entry_price is None:
        return None
    c, d, ctx = cfg.exit, DIR[s.direction], s.signal_context or {}
    stop = ctx.get("stop", s.stop_price)
    risk = abs(s.entry_price - s.stop_price) if s.stop_price else None
    pts = (last.close - s.entry_price) * d
    r = pts / risk if risk else None
    held = ctx.get("held", 0)
    declines = s.adx_declines or 0
    to_close = int((session_close(to_ist(last.ts).date()) - to_ist(last.ts)) / tf_delta("5m")) - 1
    left = max(0, min(c.max_hold_candles - held, to_close if c.exit_at_session_end else c.max_hold_candles))
    to_stop = (last.close - stop) * d if stop is not None else None
    to_target = (s.target_price - last.close) * d if s.target_price is not None else None

    watch = []
    if to_stop is not None and risk and to_stop <= NEAR_R * risk:
        watch.append(f"Price {to_stop:.1f} pts from the stop")
    adx_armed = pts > 0 or not c.adx_exit_only_in_profit
    if declines and adx_armed and declines >= c.adx_decline_candles - 1:
        watch.append(f"ADX fell {declines} candle{'s' if declines > 1 else ''}: one more lower close exits")
    if left <= SOON:
        watch.append(f"{left} candle{'s' if left != 1 else ''} to the time exit")
    notes = []
    if declines and not adx_armed:
        notes.append(f"ADX fell {declines} candle{'s' if declines > 1 else ''}, but the ADX exit only fires in profit")
    if to_target is not None and risk and to_target <= NEAR_R * risk:
        notes.append(f"Target {to_target:.1f} pts away")
    if ctx.get("stop_moved"):
        notes.append(f"Stop moved to {stop} ({'breakeven' if stop == s.entry_price else 'trailing'})")
    verdict = "WATCH" if watch else "TRAIL" if ctx.get("stop_moved") else "HOLD"
    return {"ts": last.ts.isoformat(), "price": last.close, "pnl_points": round(pts, 2),
            "r": round(r, 2) if r is not None else None, "stop": stop, "initial_stop": s.stop_price,
            "stop_moved": bool(ctx.get("stop_moved")), "target": s.target_price,
            "to_stop": round(to_stop, 2) if to_stop is not None else None,
            "to_target": round(to_target, 2) if to_target is not None else None,
            "held": held, "candles_left": left, "adx": last.adx, "peak_adx": s.peak_adx, "adx_declines": declines,
            "verdict": verdict, "reasons": watch + notes}
