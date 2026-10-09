"""Plain-language scan commentary — pure functions over the engine's result (no database).

After every scan each symbol gets a short read-out: where each gate stands and how far the failing ones are
from flipping, then the same rule for both sides. One neutral step first (if price trades sideways, when does
5m ADX finish compressing?), then "a rise of U pts in V candles → CE breakout in W candles" and "a fall of X
pts in Y candles → PE breakout in Z candles". It explains the scan; it never changes a decision.

Projections run the exact Wilder recurrence forward on synthetic candles that open at the previous close,
move a fixed number of points and carry small wicks. They are estimates: real highs/lows shift the numbers.
"""
import math
from datetime import datetime, timedelta

from app.core.clock import session_close, to_ist
from app.indicators.wilder import WilderState, step
from app.strategy.config import StrategyConfig
from app.strategy.engine import PASS, WAIT, Bar, StrategyResult, _hhmm, _level_text, compression_level

OPT = {"CALL": "CE", "PUT": "PE"}
PROJECT_CANDLES = 3
WICK_ATR = 0.15          # synthetic wick as a fraction of ATR
PACE_STEPS = 60          # pace search: 0.05×ATR … 3×ATR per candle
HOLD_CANDLES = 75        # sideways candles simulated for compression (one session)


def _hm(dt: datetime) -> str:
    return f"{to_ist(dt):%H:%M}"


def _lead(pdi, mdi) -> str | None:
    if pdi is None or mdi is None or pdi == mdi:
        return None
    return "CALL" if pdi > mdi else "PUT"


def _close_time(b: Bar, k: int = 0) -> datetime:
    """Close time of the candle k candles after bar b (k=0 -> b itself)."""
    return b.ts + timedelta(minutes=5 * (k + 1))


def _close_of_day(b: Bar) -> datetime:
    return session_close(to_ist(b.ts).date())


def _when(at: datetime, last: Bar, cutoff: datetime) -> str:
    """'≈ 14:35 IST', '≈ 15:05 IST, after the entry cutoff' or 'after today's close' (never a time past 15:30)."""
    if at > _close_of_day(last):
        return f"after today's {_hm(_close_of_day(last))} close"
    return f"≈ {_hm(at)} IST" + (", after the entry cutoff" if at > cutoff else "")


def _adx_rate(bars: list[Bar], n: int = 5) -> float | None:
    """Average ADX change per candle over the last n candles (negative = falling)."""
    adx = [b.adx for b in bars[-n:] if b.adx is not None]
    return (adx[-1] - adx[0]) / (len(adx) - 1) if len(adx) >= 2 else None


def project_di(state: WilderState, period: int, direction: str, pace: float, candles: int = PROJECT_CANDLES):
    """Run `candles` synthetic candles moving `pace` points each in `direction` (CALL up, PUT down)."""
    s, wick, d, out = state, WICK_ATR * (state.atr or 0), 1 if direction == "CALL" else -1, []
    for _ in range(candles):
        o = s.close
        c = o + d * pace
        s = step(s, max(o, c) + wick, min(o, c) - wick, c, period)
        out.append(s)
    return out


def chop(state: WilderState, period: int, candles: int) -> list[WilderState]:
    """Neutral sideways market: candles of ~1 ATR range whose highs/lows step up then back down by 0.3 ATR in
    turn, so +DM and −DM appear equally and the DIs converge (no net move, no side favoured)."""
    s, out = state, []
    r, e = state.atr or 0, 0.3 * (state.atr or 0)
    lo = state.close - r / 2
    for i in range(candles):
        low = lo + (e if i % 2 == 0 else 0.0)
        s = step(s, low + r, low, low + r / 2, period)
        out.append(s)
    return out


def compression_path(state: WilderState, hist: list[float], cfg: StrategyConfig, compressed: bool):
    """(candles from now until compression is complete, states, adx sequence) assuming sideways trade."""
    f = cfg.five_min
    if compressed:
        return 0, [state], list(hist)
    run, seq = 0, list(hist)
    states = chop(state, f.adx_period, HOLD_CANDLES)
    for j, x in enumerate(states, start=1):
        seq.append(x.adx)
        lvl = compression_level(seq, len(seq) - 1, f)[0]
        run = run + 1 if x.adx is not None and lvl is not None and x.adx <= lvl else 0
        if run >= f.min_compression_candles:
            return j, states[:j], seq
    return None, states, seq


def breakout_move(start: WilderState, seq: list[float], cfg: StrategyConfig, direction: str) -> dict | None:
    """Smallest steady move over 1-3 candles from a compressed state that makes a breakout on this side:
    ADX above its previous-lookback average and up by min_adx_increase, this side's DI ahead by the separation."""
    f = cfg.five_min
    for i in range(1, PACE_STEPS + 1):
        pace = start.atr * 0.05 * i
        path = project_di(start, f.adx_period, direction, pace)
        for k, p in enumerate(path, start=1):
            gap = (p.pdi - p.mdi) if direction == "CALL" else (p.mdi - p.pdi)
            full = seq + [x.adx for x in path[:k]]
            prev = full[-1 - f.breakout_lookback:-1]
            if p.adx is None or None in prev or gap < f.min_di_separation:
                continue
            if full[-1] > sum(prev) / len(prev) and full[-1] - full[-2] >= f.min_adx_increase:
                return {"move_pts": round(pace * k), "candles": k, "di_gap": round(gap, 1)}
    return None


def side_rules(symbol: str, state: WilderState | None, bars5: list[Bar], cfg: StrategyConfig, compressed: bool,
               cutoff: datetime) -> tuple[dict | None, list[dict]]:
    """One compression step shared by both sides, then the same breakout rule up (CE) and down (PE)."""
    if state is None or not state.atr or state.pdi is None or state.mdi is None or not bars5:
        return None, []
    last = bars5[-1]
    hist = [b.adx for b in bars5 if b.adx is not None]
    j, states, seq = compression_path(state, hist, cfg, compressed)
    f = cfg.five_min
    lt = _level_text(f, *compression_level(hist, len(hist) - 1, f))
    if j is None:
        return {"candles": None, "at": None, "text": f"Even trading sideways, 5m ADX would not hold {lt} "
                f"for {f.min_compression_candles} candles this session: no CE or PE breakout possible yet."}, []
    if j == 0:
        comp = {"candles": 0, "at": None, "text": "5m ADX is already compressed: the next candle can break out either way."}
    else:
        at = _close_time(last, j - 1)
        comp = {"candles": j, "at": at.isoformat(),
                "text": f"If {symbol} trades sideways, 5m ADX reaches {lt} and holds "
                        f"{f.min_compression_candles} candles in about {j} candles ({5 * j} min, {_when(at, last, cutoff)})."}
    rules = []
    for d in ("CALL", "PUT"):
        mv = breakout_move(states[-1], seq, cfg, d)
        if mv is None:
            continue
        z, k = j + mv["candles"], mv["candles"]
        at = _close_time(last, z - 1)
        verb = "rise" if d == "CALL" else "fall"
        lead = "Then a" if j else "A"
        rules.append({"direction": d, "option": OPT[d], **mv, "minutes": 5 * k, "signal_in": z,
                      "signal_at": at.isoformat(), "after_cutoff": at > cutoff,
                      "text": f"{lead} {verb} of {mv['move_pts']} pt{'s' if mv['move_pts'] != 1 else ''} in {k} candle{'s' if k > 1 else ''} ({5 * k} min) "
                              f"triggers a {OPT[d]} breakout, {z} candle{'s' if z > 1 else ''} from now ({_when(at, last, cutoff)})."})
    return comp, rules


def _gate1(res: StrategyResult, bars5: list[Bar], cfg: StrategyConfig, cutoff: datetime) -> dict:
    c, g = cfg.five_min, res.gate1
    last = bars5[-1]
    m = g.metrics or {}
    if g.status == PASS:
        return {"gate": "5m ADX", "status": "PASS", "earliest": None,
                "text": f"Breakout at {m.get('ts') and _hm(datetime.fromisoformat(m['ts']))}: ADX {m.get('adx_before')} → "
                        f"{m.get('adx_at')} after {m.get('compression_candles')} compressed candles, "
                        f"{OPT.get(m.get('direction'), '')} side."}
    adx, need = last.adx, c.min_compression_candles
    thr = m.get("compression_level")
    lt = _level_text(c, thr, m.get("adx_peak"))
    run = m.get("compression_candles") or 0
    rate = _adx_rate(bars5)
    if adx is None or thr is None:
        return {"gate": "5m ADX", "status": g.status, "earliest": None, "text": g.reasons[0] if g.reasons else "No ADX"}
    if g.status == WAIT:
        prev = [b.adx for b in bars5[-c.breakout_lookback:] if b.adx is not None]
        trigger = max(sum(prev) / len(prev), adx + c.min_adx_increase) if prev else adx + c.min_adx_increase
        return {"gate": "5m ADX", "status": "WAIT", "earliest": _close_time(last, 1).isoformat(),
                "text": f"Compressed {run} candles (need {need}). Breakout needs next 5m ADX above {trigger:.1f} "
                        f"(now {adx:.1f}) with a DI gap of {c.min_di_separation:g}+."}
    if adx <= thr:
        k = max(need - run, 0) + 1
        text = f"ADX {adx:.1f} is compressed {run}/{need} candles; {max(need - run, 0)} more, then a breakout."
    elif rate is not None and rate < -0.05:
        to_thr = math.ceil((adx - thr) / -rate)
        k = to_thr + need
        text = (f"ADX {adx:.1f}, needs {lt} ({adx - thr:.1f} to go). Falling {-rate:.1f}/candle → about "
                f"{to_thr} candles to compress, then {need} compressed candles before a breakout.")
    else:
        trend = "rising" if rate is not None and rate > 0.05 else "flat"
        return {"gate": "5m ADX", "status": "FAIL", "earliest": None,
                "text": f"ADX {adx:.1f} is {trend}, above its compression level {lt}: the move is still trending, no compression forming."}
    earliest = _close_time(last, k)
    when = f" Earliest breakout: {_when(earliest, last, cutoff)}."
    return {"gate": "5m ADX", "status": g.status, "earliest": earliest.isoformat(), "text": text + when}


def _gate2(res: StrategyResult, bars15: list[Bar], cfg: StrategyConfig) -> dict:
    c, g = cfg.fifteen_min, res.gate2
    m = g.metrics or {}
    vals = [b.adx for b in bars15 if b.adx is not None][-c.lookback_candles:]
    slope, adx, cons, lead = m.get("slope"), m.get("adx"), m.get("di_consistency"), m.get("lead")
    if slope is None or adx is None:
        return {"gate": "15m pattern", "status": g.status, "text": g.reasons[0] if g.reasons else "No 15m data"}
    parts = []
    if slope > c.min_adx_slope:
        parts.append(f"slope {slope:+.1f} ok")
    elif len(vals) > c.slope_candles:
        ref = vals[-c.slope_candles]  # next slope = next ADX − this value
        parts.append(f"slope {slope:+.1f} (need > {c.min_adx_slope:g}); next 15m ADX must close above "
                     f"{ref + c.min_adx_slope:.1f} (now {adx:.1f})")
    parts.append(f"ADX {adx:.1f} {'≤' if adx <= c.max_adx else '>'} {c.max_adx:g}")
    if cons is not None:
        parts.append(f"DI lean {cons:.0%} {OPT.get(lead, 'flat')} (need {c.min_di_consistency:.0%})")
    ok = g.status == PASS or (slope > c.min_adx_slope and adx <= c.max_adx and (cons or 0) >= c.min_di_consistency)
    return {"gate": "15m pattern", "status": g.status, "would_pass": ok, "text": "15m " + "; ".join(parts) + "."}


def _atr(res: StrategyResult, cfg: StrategyConfig) -> dict:
    c, m = cfg.atr, res.atr.metrics or {}
    atr, move, ratio = m.get("atr"), m.get("move"), m.get("ratio")
    if atr is None or ratio is None:
        return {"gate": "ATR", "status": res.atr.status, "text": res.atr.reasons[0] if res.atr.reasons else "ATR unavailable"}
    room = c.exhaustion_multiple * atr - move
    tail = (f"{room:.0f} pts of room before exhausted ({c.exhaustion_multiple:g}×)." if room > 0
            else f"exhausted; needs to cool below {c.exhaustion_multiple:g}×.")
    return {"gate": "ATR", "status": res.atr.status,
            "text": f"Move {move:.0f} pts = {ratio:.2f}× ATR {atr:.1f} ({m.get('atr_status')}); {tail}"}


def _vix(res: StrategyResult, cfg: StrategyConfig) -> dict:
    c, m = cfg.vix, res.vix.metrics or {}
    v, chg = m.get("vix"), m.get("change_pct")
    if not c.enabled:
        return {"gate": "VIX", "status": res.vix.status, "text": "VIX filter disabled."}
    if v is None:
        return {"gate": "VIX", "status": res.vix.status, "text": res.vix.reasons[0] if res.vix.reasons else "VIX unavailable"}
    day = f", day {chg:+.1f}% (limit ±{c.max_abs_change_pct:g}%, spike {c.spike_threshold_pct:g}%)" if chg is not None else ""
    return {"gate": "VIX", "status": res.vix.status, "text": f"VIX {v:.2f} (band {c.min_vix:g}–{c.max_vix:g}){day}."}


def build(res: StrategyResult, bars5: list[Bar], bars15: list[Bar], cfg: StrategyConfig,
          di_state: WilderState | None = None) -> dict:
    """Commentary for one symbol's scan. `di_state` is the latest 5m Wilder state (for DI projections)."""
    if not bars5 or res.gate1.status == "FAIL" and "DATA" in (res.reason or ""):
        return {"headline": res.reason or "No data", "bias": None, "lines": [], "compression": None, "rules": [], "outlook": None}
    last = bars5[-1]
    cutoff = datetime.combine(to_ist(last.ts).date(), _hhmm(cfg.scanner.entry_end), tzinfo=to_ist(last.ts).tzinfo)
    lead = _lead(last.pdi, last.mdi)
    gap = abs((last.pdi or 0) - (last.mdi or 0))
    g1 = _gate1(res, bars5, cfg, cutoff)
    lines = [g1, _gate2(res, bars15, cfg), _atr(res, cfg), _vix(res, cfg)]

    # once a breakout is in, the setup question is the 15m confirmation, not another compression
    compression, rules = (None, []) if g1["status"] == PASS else side_rules(res.symbol, di_state, bars5, cfg,
                                                                            g1["status"] == WAIT, cutoff)

    bias = OPT.get(lead)
    if res.final == "SIGNAL_READY" or res.state in ("QUALIFIED", "SIGNAL_GENERATED"):
        headline, outlook = f"{OPT.get(res.direction, '')} signal qualified.", "All gates passed."
    elif res.state in ("BREAKOUT_DETECTED", "WAITING_CONFIRMATION"):
        headline = f"{OPT.get(res.direction, '')} breakout waiting for 15m confirmation."
        outlook = lines[1]["text"]
    elif res.state == "REJECTED":
        headline, outlook = f"Setup rejected: {res.reason}", None
    elif g1["status"] == "WAIT":
        headline, outlook = "Compression ready: a breakout can come on any candle.", g1["text"]
    else:
        earliest = g1.get("earliest")
        if earliest and datetime.fromisoformat(earliest) <= cutoff:
            outlook = f"Setup possible from about {_hm(datetime.fromisoformat(earliest))} IST if ADX keeps cooling."
        elif earliest and datetime.fromisoformat(earliest) > _close_of_day(last):
            outlook = "Compression cannot complete before the session close: no setup today."
        elif earliest:
            outlook = f"Earliest setup ≈ {_hm(datetime.fromisoformat(earliest))} IST, after the {cfg.scanner.entry_end} cutoff: unlikely today."
        else:
            outlook = "No compression forming yet."
        g1m = res.gate1.metrics or {}
        headline = (f"No setup near: 5m ADX {last.adx:.1f} must cool to "
                    f"{_level_text(cfg.five_min, g1m.get('compression_level'), g1m.get('adx_peak'))} first.")
    if compression:  # the shared compression step already says when a setup can form
        outlook = None
    return {"headline": headline, "bias": bias, "lines": lines, "compression": compression, "rules": rules, "outlook": outlook,
            "candle_close": _hm(_close_time(last))}
