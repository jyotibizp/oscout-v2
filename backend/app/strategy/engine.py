"""ADX strategy engine — pure functions, no database, provider, scheduler or UI.

evaluate() receives completed 5m and 15m candles (with Wilder ADX/+DI/-DI/ATR), an India VIX snapshot,
data-freshness flags and a StrategyConfig, and returns a fully explained StrategyResult.
Given the same inputs and configuration it always returns the same result.

Pipeline (short-circuit for display; metrics are still computed for every gate):
  Gate 1  5m ADX compression -> breakout   (direction from the leading DI)
  Gate 2  15m ADX pattern confirmation
  ATR     exhaustion filter                  (filter only, never an entry reason)
  VIX     India VIX regime filter            (filter only)
  -> QUALIFIED (CALL / PUT) or a stated rejection
"""
from dataclasses import asdict, dataclass, field
from datetime import datetime, time, timedelta

from app.core.clock import to_ist
from app.strategy.config import StrategyConfig

PASS, FAIL, WAIT, SKIP = "PASS", "FAIL", "WAIT", "SKIP"


@dataclass
class Bar:
    ts: datetime
    open: float
    high: float
    low: float
    close: float
    adx: float | None
    pdi: float | None
    mdi: float | None
    atr: float | None = None  # ATR for the configured ATR period on this timeframe


@dataclass
class VixSnapshot:
    value: float | None
    prev_close: float | None
    ts: datetime | None
    stale: bool = False


@dataclass
class GateResult:
    status: str
    reasons: list[str] = field(default_factory=list)
    metrics: dict = field(default_factory=dict)


@dataclass
class StrategyResult:
    symbol: str
    candle_ts: datetime | None
    state: str
    final: str                      # SIGNAL_READY | NO_SIGNAL
    direction: str | None           # CALL | PUT
    reason: str
    gate1: GateResult
    gate2: GateResult
    atr: GateResult
    vix: GateResult
    entry_price: float | None = None
    stop_price: float | None = None
    target_price: float | None = None
    atr_value: float | None = None
    breakout: dict | None = None
    snapshot: dict = field(default_factory=dict)
    commentary: dict | None = None  # plain-language read-out (app.strategy.commentary), explanatory only

    def to_dict(self) -> dict:
        d = asdict(self)
        return d


def _f(x, nd=2):
    return None if x is None else round(float(x), nd)


def _dir_of(pdi, mdi) -> int:
    if pdi is None or mdi is None or pdi == mdi:
        return 0
    return 1 if pdi > mdi else -1


def _dname(d: int) -> str | None:
    return {1: "CALL", -1: "PUT"}.get(d)


def compression_level(adx: list[float | None], i: int, c) -> tuple[float | None, float | None]:
    """(compression level, recent peak) at index i. peak_pct mode: a % of the highest ADX over the lookback
    (at 50%: a 40 peak compresses at 20, a 60 peak at 30); fixed mode: the fixed threshold."""
    if c.compression_mode == "fixed":
        return c.compression_threshold, None
    vals = [x for x in adx[max(0, i - c.peak_lookback_candles + 1):i + 1] if x is not None]
    if not vals:
        return None, None
    peak = max(vals)
    return peak * c.compression_peak_pct / 100.0, peak


def compression_levels(adx: list[float | None], c) -> list[float | None]:
    return [compression_level(adx, i, c)[0] for i in range(len(adx))]


def compression_run(adx: list[float | None], end: int, levels: list[float | None], cap: int) -> int:
    """Consecutive candles ending at index `end` (inclusive) with ADX <= that candle's compression level
    (counted up to cap)."""
    n = 0
    i = end
    while i >= 0 and adx[i] is not None and levels[i] is not None and adx[i] <= levels[i] and n <= cap:
        n += 1
        i -= 1
    return n


def _level_text(c, level: float | None, peak: float | None) -> str:
    if c.compression_mode == "fixed" or peak is None:
        return f"≤ {level:g}" if level is not None else "≤ —"
    return f"≤ {level:.1f} ({c.compression_peak_pct:g}% of peak {peak:.1f})"


def gate1(bars: list[Bar], cfg: StrategyConfig) -> GateResult:
    c = cfg.five_min
    adx = [b.adx for b in bars]
    t = len(bars) - 1
    levels = compression_levels(adx, c)
    need = c.min_compression_candles + c.breakout_lookback + 2
    if t < need or adx[t] is None:
        return GateResult(FAIL, [f"Insufficient 5m ADX history ({len(bars)} candles)"])
    def is_breakout(b: int):
        """(run, avg, inc, sep) if candle b is a breakout out of a compression, else None."""
        if b < need or adx[b] is None or adx[b - 1] is None:
            return None
        run = compression_run(adx, b - 1, levels, c.max_compression_candles)
        if run < c.min_compression_candles or run > c.max_compression_candles:
            return None
        prev = [x for x in adx[b - c.breakout_lookback:b] if x is not None]
        if len(prev) < c.breakout_lookback:
            return None
        avg = sum(prev) / len(prev)
        inc = adx[b] - adx[b - 1]
        sep = (bars[b].pdi or 0) - (bars[b].mdi or 0)
        if not (adx[b] > avg and inc >= c.min_adx_increase and adx[b] >= c.breakout_threshold
                and abs(sep) >= c.min_di_separation and sep != 0):
            return None
        return run, avg, inc, sep

    # the earliest fresh breakout inside the validity window (a breakout is fresh if the candle before it
    # was not itself a breakout, so a continuing rise does not keep re-dating the setup)
    for back in reversed(range(c.breakout_valid_candles)):
        b = t - back
        hit = is_breakout(b)
        if hit is None or is_breakout(b - 1) is not None:
            continue
        run, avg, inc, sep = hit
        d = 1 if sep > 0 else -1
        comp = adx[b - run:b]
        bo = {"ts": bars[b].ts.isoformat(), "adx_before": _f(adx[b - 1]), "adx_at": _f(adx[b]), "adx_change": _f(inc),
              "adx_avg_before": _f(avg), "pdi": _f(bars[b].pdi), "mdi": _f(bars[b].mdi), "di_separation": _f(abs(sep)),
              "direction": _dname(d), "compression_candles": run, "compression_low": _f(min(comp)),
              "ohlc": {"open": bars[b].open, "high": bars[b].high, "low": bars[b].low, "close": bars[b].close},
              "candles_since": back, "compression_level": _f(levels[b - 1]),
              "adx_peak": _f(compression_level(adx, b - 1, c)[1])}
        now_dir = _dir_of(bars[t].pdi, bars[t].mdi)
        if now_dir != d:
            return GateResult(FAIL, [f"Breakout at {to_ist(bars[b].ts):%H:%M} invalidated: DI direction flipped"], bo)
        reasons = [f"ADX compressed {_level_text(c, *compression_level(adx, b - 1, c))} for {run} candles (low {min(comp):.1f})",
                   f"Breakout {to_ist(bars[b].ts):%H:%M}: ADX {adx[b-1]:.1f} → {adx[b]:.1f} (above {c.breakout_lookback}-candle avg {avg:.1f})",
                   f"{'+DI' if d > 0 else '−DI'} leads by {abs(sep):.1f} → {_dname(d)}"]
        return GateResult(PASS, reasons, bo)
    run_now = compression_run(adx, t, levels, c.max_compression_candles)
    level, peak = compression_level(adx, t, c)
    m = {"compression_candles": run_now, "adx": _f(adx[t]), "compression_level": _f(level), "adx_peak": _f(peak)}
    lt = _level_text(c, level, peak)
    if run_now >= c.min_compression_candles and run_now <= c.max_compression_candles:
        return GateResult(WAIT, [f"ADX compressed for {run_now} candles ({lt}); waiting for breakout"], m)
    if run_now > c.max_compression_candles:
        return GateResult(FAIL, [f"Compression longer than {c.max_compression_candles} candles (dead market)"], m)
    return GateResult(FAIL, [f"No ADX compression → breakout (ADX {adx[t]:.1f}, needs {lt}, compressed {run_now} candles)"], m)


def gate2(bars15: list[Bar], direction: int, cfg: StrategyConfig) -> GateResult:
    c = cfg.fifteen_min
    vals = [b for b in bars15 if b.adx is not None]
    if len(vals) < max(c.lookback_candles, c.slope_candles + 2):
        return GateResult(FAIL, [f"Insufficient 15m candles ({len(vals)} of {c.lookback_candles})"])
    w = vals[-c.lookback_candles:]
    adx = [b.adx for b in w]
    now = adx[-1]
    slope = now - adx[-1 - c.slope_candles]
    prev_slope = adx[-2] - adx[-2 - c.slope_candles] if len(adx) > c.slope_candles + 1 else 0.0
    lead = _dir_of(w[-1].pdi, w[-1].mdi)
    leads = [_dir_of(b.pdi, b.mdi) for b in w]
    want = direction or lead
    consistency = sum(1 for x in leads if x == want and x != 0) / len(leads) if want else 0.0
    hi, lo = max(adx), min(adx)
    m = {"adx": _f(now), "pdi": _f(w[-1].pdi), "mdi": _f(w[-1].mdi), "slope": _f(slope),
         "acceleration": _f(slope - prev_slope), "adx_high": _f(hi), "adx_low": _f(lo),
         "position": _f((now - lo) / (hi - lo), 2) if hi > lo else None, "lead": _dname(lead),
         "di_consistency": _f(consistency, 2), "compression_to_expansion": _f(now - lo), "lookback": len(w)}
    fails, oks = [], []
    (oks if slope > c.min_adx_slope else fails).append(
        f"15m ADX slope {slope:+.1f} over {c.slope_candles} candles (need > {c.min_adx_slope:g})")
    if c.min_adx > 0:
        (oks if now >= c.min_adx else fails).append(f"15m ADX {now:.1f} (need ≥ {c.min_adx:g})")
    (oks if now <= c.max_adx else fails).append(f"15m ADX {now:.1f} {'≤' if now <= c.max_adx else '>'} {c.max_adx:g} (not exhausted)")
    if c.require_di_agreement and direction:
        (oks if lead == direction else fails).append(
            f"15m leading DI {'agrees' if lead == direction else 'disagrees'} ({_dname(lead) or 'flat'} vs {_dname(direction)})")
    (oks if consistency >= c.min_di_consistency else fails).append(
        f"DI consistency {consistency:.0%} of {len(w)} candles (need ≥ {c.min_di_consistency:.0%})")
    return GateResult(PASS if not fails else FAIL, fails + oks if fails else oks, m)


def atr_filter(bars: list[Bar], direction: int, cfg: StrategyConfig) -> GateResult:
    c = cfg.atr
    if not bars or bars[-1].atr is None or bars[-1].atr <= 0:
        return GateResult(FAIL, [f"ATR unavailable on {c.atr_timeframe}"], {"atr_status": None})
    w = bars[-c.lookback_candles:]
    atr = bars[-1].atr
    close = bars[-1].close
    d = direction or 1
    move = close - min(b.low for b in w) if d > 0 else max(b.high for b in w) - close
    ratio = move / atr
    status = "EXHAUSTED" if ratio >= c.exhaustion_multiple else "WARNING" if ratio >= c.warning_multiple else "NORMAL"
    m = {"atr": _f(atr), "move": _f(move), "ratio": _f(ratio), "atr_status": status, "timeframe": c.atr_timeframe,
         "lookback": len(w)}
    msg = (f"Move {move:.1f} pts = {ratio:.2f}× ATR {atr:.1f} over {len(w)} {c.atr_timeframe} candles "
           f"(warning {c.warning_multiple:g}×, exhausted {c.exhaustion_multiple:g}×) → {status}")
    return GateResult(FAIL if status == "EXHAUSTED" else PASS, [msg], m)


def vix_filter(v: VixSnapshot | None, cfg: StrategyConfig) -> GateResult:
    c = cfg.vix
    if not c.enabled:
        return GateResult(PASS, ["VIX filter disabled"], {"enabled": False})
    if v is None or v.value is None:
        return GateResult(FAIL, ["VIX DATA UNAVAILABLE"], {})
    m = {"vix": _f(v.value), "prev_close": _f(v.prev_close)}
    if v.stale:
        return GateResult(FAIL, ["VIX DATA STALE"], m)
    chg = ((v.value - v.prev_close) / v.prev_close * 100) if v.prev_close else None
    m["change_pct"] = _f(chg)
    m["change"] = _f(v.value - v.prev_close) if v.prev_close else None
    m["regime"] = "LOW" if v.value < 13 else "NORMAL" if v.value < 18 else "HIGH"
    fails, oks = [], []

    def check(ok: bool, good: str, bad: str):
        (oks if ok else fails).append(good if ok else bad)

    check(c.min_vix <= v.value <= c.max_vix, f"VIX {v.value:.2f} within {c.min_vix:g}–{c.max_vix:g}",
          f"VIX {v.value:.2f} outside {c.min_vix:g}–{c.max_vix:g}")
    if chg is not None:
        check(abs(chg) <= c.max_abs_change_pct, f"Day change {chg:+.1f}% within ±{c.max_abs_change_pct:g}%",
              f"VIX day change {chg:+.1f}% beyond ±{c.max_abs_change_pct:g}%")
        check(chg <= c.spike_threshold_pct, f"No spike ({chg:+.1f}% ≤ {c.spike_threshold_pct:g}%)",
              f"VIX spike {chg:+.1f}% (> {c.spike_threshold_pct:g}%)")
        if c.trend_requirement == "falling":
            check(chg < 0, f"VIX falling today ({chg:+.1f}%)", f"VIX not falling today ({chg:+.1f}%)")
        elif c.trend_requirement == "rising":
            check(chg > 0, f"VIX rising today ({chg:+.1f}%)", f"VIX not rising today ({chg:+.1f}%)")
    else:
        oks.append("Previous VIX close unknown — change checks skipped")
    return GateResult(FAIL if fails else PASS, fails + oks, m)


def _hhmm(s: str) -> time:
    h, m = s.split(":")
    return time(int(h), int(m))


def evaluate(symbol: str, bars5: list[Bar], bars15: list[Bar], atr_bars: list[Bar], vix: VixSnapshot | None,
             cfg: StrategyConfig, stale: dict[str, str] | None = None) -> StrategyResult:
    """bars5/bars15: completed candles ascending; atr_bars: candles of the ATR timeframe carrying the ATR period."""
    last = bars5[-1] if bars5 else None
    snap = {"adx5": _f(last.adx) if last else None, "pdi5": _f(last.pdi) if last else None,
            "mdi5": _f(last.mdi) if last else None, "close": last.close if last else None}
    if bars15:
        b = bars15[-1]
        snap.update({"adx15": _f(b.adx), "pdi15": _f(b.pdi), "mdi15": _f(b.mdi)})
    empty = GateResult(SKIP)
    if stale:
        reason = "; ".join(stale.values())
        return StrategyResult(symbol, last.ts if last else None, "REJECTED", "NO_SIGNAL", None, reason,
                              GateResult(FAIL, [reason]), empty, empty, empty, snapshot=snap)

    g1 = gate1(bars5, cfg)
    d = {"CALL": 1, "PUT": -1}.get((g1.metrics or {}).get("direction"), 0) if g1.status == PASS else 0
    lead = d or _dir_of(last.pdi, last.mdi)
    g2 = gate2(bars15, d, cfg)
    ga = atr_filter(atr_bars, lead, cfg)
    gv = vix_filter(vix, cfg)
    snap.update({"atr": ga.metrics.get("atr"), "atr_status": ga.metrics.get("atr_status"),
                 "vix": gv.metrics.get("vix"), "vix_change_pct": gv.metrics.get("change_pct")})
    res = StrategyResult(symbol, last.ts, "WATCHING", "NO_SIGNAL", _dname(d) if d else None, "", g1, g2, ga, gv,
                         snapshot=snap)
    if g1.status != PASS:
        res.gate2, res.atr, res.vix = (GateResult(SKIP, g2.reasons, g2.metrics), GateResult(SKIP, ga.reasons, ga.metrics),
                                       GateResult(SKIP, gv.reasons, gv.metrics))
        res.state = "COMPRESSION" if g1.status == WAIT else "WATCHING"
        res.reason = g1.reasons[0] if g1.reasons else "No setup"
        return res
    res.breakout = g1.metrics
    since = g1.metrics.get("candles_since", 0)
    if g2.status != PASS:
        res.atr, res.vix = GateResult(SKIP, ga.reasons, ga.metrics), GateResult(SKIP, gv.reasons, gv.metrics)
        res.state = "BREAKOUT_DETECTED" if since == 0 else "WAITING_CONFIRMATION"
        res.reason = "15M PATTERN NOT CONFIRMED: " + (g2.reasons[0] if g2.reasons else "")
        return res
    if ga.status != PASS:
        res.vix = GateResult(SKIP, gv.reasons, gv.metrics)
        res.state, res.reason = "REJECTED", "ATR EXHAUSTED: " + ga.reasons[0]
        return res
    if gv.status != PASS:
        res.state, res.reason = "REJECTED", "VIX FILTER: " + gv.reasons[0]
        return res
    close_t = to_ist(last.ts + timedelta(minutes=5)).time()
    if not (_hhmm(cfg.scanner.entry_start) <= close_t <= _hhmm(cfg.scanner.entry_end)):
        res.state = "REJECTED"
        res.reason = f"Outside entry window {cfg.scanner.entry_start}–{cfg.scanner.entry_end} IST"
        return res
    atr5 = last.atr if last.atr else ga.metrics.get("atr")
    res.state, res.final = "QUALIFIED", "SIGNAL_READY"
    res.entry_price = last.close
    res.atr_value = _f(atr5)
    if atr5:
        if cfg.exit.stop_atr_multiple > 0:
            res.stop_price = round(last.close - d * cfg.exit.stop_atr_multiple * atr5, 2)
        if cfg.exit.target_atr_multiple > 0:
            res.target_price = round(last.close + d * cfg.exit.target_atr_multiple * atr5, 2)
    res.reason = (f"{_dname(d)} BUY: 5m ADX breakout {g1.metrics['adx_before']} → {g1.metrics['adx_at']} after "
                  f"{g1.metrics['compression_candles']} compressed candles; 15m ADX {g2.metrics.get('adx')} "
                  f"(slope {g2.metrics.get('slope'):+}); ATR {ga.metrics.get('atr_status')}; VIX {gv.metrics.get('vix', '—')}")
    return res


# ---------------- exit engine ----------------

@dataclass
class Position:
    direction: int
    entry_price: float
    stop: float | None
    target: float | None
    peak_adx: float
    last_adx: float
    declines: int = 0
    held: int = 0


@dataclass
class ExitDecision:
    ts: datetime
    price: float
    reason: str
    note: str


def evaluate_exit(pos: Position, bars: list[Bar], cfg: StrategyConfig, last_of_session) -> tuple[Position, ExitDecision | None]:
    """Walk completed 5m candles after the last evaluated one. Stop is checked before target within a
    candle (conservative). `last_of_session(ts)` tells whether a candle is the session's final candle."""
    c = cfg.exit
    d = pos.direction
    for b in bars:
        pos.held += 1
        fav, adv = (b.high, b.low) if d > 0 else (b.low, b.high)
        if pos.stop is not None and (adv - pos.stop) * d <= 0:
            px = b.open if (b.open - pos.stop) * d < 0 else pos.stop  # gap through the stop fills at the open
            return pos, ExitDecision(b.ts, px, "STOP", f"Protective stop {pos.stop} hit")
        if pos.target is not None and (fav - pos.target) * d >= 0:
            return pos, ExitDecision(b.ts, pos.target, "TARGET", f"Profit target {pos.target} reached")
        if b.adx is not None:
            pos.declines = pos.declines + 1 if b.adx < pos.last_adx else 0
            pos.peak_adx = max(pos.peak_adx, b.adx)
            pos.last_adx = b.adx
            in_profit = (b.close - pos.entry_price) * d > 0
            allowed = in_profit or not c.adx_exit_only_in_profit
            drop = pos.peak_adx - b.adx
            if allowed and pos.declines >= c.adx_decline_candles and drop >= c.min_adx_decline:
                return pos, ExitDecision(b.ts, b.close, "ADX_EXHAUSTION",
                                         f"ADX fell {pos.declines} candles in a row ({pos.peak_adx:.1f} peak → {b.adx:.1f})")
            if allowed and c.adx_peak_decline_pct > 0 and pos.peak_adx > 0 and drop / pos.peak_adx * 100 >= c.adx_peak_decline_pct:
                return pos, ExitDecision(b.ts, b.close, "ADX_PEAK_DECLINE",
                                         f"ADX {drop / pos.peak_adx:.0%} below its peak {pos.peak_adx:.1f}")
        if c.di_reversal_exit and _dir_of(b.pdi, b.mdi) == -d:
            return pos, ExitDecision(b.ts, b.close, "DI_REVERSAL", "DIs crossed against the trade")
        if c.exit_at_session_end and last_of_session(b.ts):
            return pos, ExitDecision(b.ts, b.close, "SESSION_END", "Session end")
        if pos.held >= c.max_hold_candles:
            return pos, ExitDecision(b.ts, b.close, "MAX_HOLD", f"Held {pos.held} candles")
    return pos, None
