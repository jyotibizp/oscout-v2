from app.strategy.config import StrategyConfig
from app.strategy.engine import VixSnapshot, atr_filter, evaluate, gate1, gate2, vix_filter
from tests.conftest import ist, make_bars

CFG = StrategyConfig()


def adx_breakout(pre=14, comp_len=10, comp=17.0, breakout=19.5):
    """a 40 ADX peak (compression level 50% = 20), a compression run <= 20, then a rise above the 5-candle average."""
    return [40.0] * pre + [comp] * comp_len + [breakout]


# ---------------- Gate 1 ----------------
def test_gate1_compression_waiting():
    bars = make_bars([40.0] * 14 + [17.0] * 10)
    g = gate1(bars, CFG)
    assert g.status == "WAIT" and "compressed" in g.reasons[0]


def test_gate1_breakout_detected_call():
    bars = make_bars(adx_breakout(), pdi=28.0, mdi=14.0)
    g = gate1(bars, CFG)
    assert g.status == "PASS"
    assert g.metrics["direction"] == "CALL" and g.metrics["compression_candles"] == 10
    assert g.metrics["adx_before"] == 17.0 and g.metrics["adx_at"] == 19.5


def test_gate1_breakout_put_from_minus_di():
    bars = make_bars(adx_breakout(), pdi=12.0, mdi=27.0)
    assert gate1(bars, CFG).metrics["direction"] == "PUT"


def test_gate1_false_breakout_rejected_small_di_separation():
    bars = make_bars(adx_breakout(), pdi=20.0, mdi=19.0)
    assert gate1(bars, CFG).status != "PASS"


def test_gate1_false_breakout_rejected_without_compression():
    bars = make_bars([40.0] * 20 + [17.0] * 3 + [19.5])  # only 3 compressed candles (< 6)
    assert gate1(bars, CFG).status == "FAIL"


def test_gate1_false_breakout_rejected_small_increase():
    bars = make_bars([40.0] * 14 + [17.0] * 10 + [17.2])  # +0.2 < min increase 0.5
    assert gate1(bars, CFG).status != "PASS"


def test_gate1_breakout_invalidated_when_di_flips():
    adx = adx_breakout() + [19.0]
    bars = make_bars(adx, pdi=[28.0] * (len(adx) - 1) + [10.0], mdi=[14.0] * (len(adx) - 1) + [25.0])
    g = gate1(bars, CFG)
    assert g.status == "FAIL" and "invalidated" in g.reasons[0]


def test_gate1_breakout_stays_valid_for_configured_candles():
    adx = adx_breakout() + [20.5, 21.0]
    assert gate1(make_bars(adx, 28.0, 14.0), CFG).metrics["candles_since"] == 2
    adx = adx_breakout() + [20.5, 21.0, 21.5]
    assert gate1(make_bars(adx, 28.0, 14.0), CFG).status == "FAIL"  # older than 3 candles; the rise is not a new breakout


# ---------------- Gate 2 ----------------
def test_gate2_confirmed():
    b15 = make_bars([15 + i * 0.5 for i in range(20)], pdi=26.0, mdi=15.0, step_minutes=15)
    g = gate2(b15, 1, CFG)
    assert g.status == "PASS" and g.metrics["slope"] > 0


def test_gate2_failed_when_adx_falling():
    b15 = make_bars([30 - i * 0.5 for i in range(20)], pdi=26.0, mdi=15.0, step_minutes=15)
    g = gate2(b15, 1, CFG)
    assert g.status == "FAIL" and "slope" in g.reasons[0]


def test_gate2_failed_when_di_disagrees():
    b15 = make_bars([15 + i * 0.5 for i in range(20)], pdi=12.0, mdi=25.0, step_minutes=15)
    assert gate2(b15, 1, CFG).status == "FAIL"


def test_gate2_insufficient_candles():
    g = gate2(make_bars([20.0] * 5, step_minutes=15), 1, CFG)
    assert g.status == "FAIL" and "Insufficient" in g.reasons[0]


# ---------------- ATR ----------------
def test_atr_normal_warning_exhausted():
    flat = make_bars([20.0] * 12, close=[100.0] * 12, atr=10.0)
    assert atr_filter(flat, 1, CFG).metrics["atr_status"] == "NORMAL"
    warn = make_bars([20.0] * 12, close=[100.0] * 11 + [128.0], atr=10.0)    # (128 - 99) / 10 = 2.9
    assert atr_filter(warn, 1, CFG).metrics["atr_status"] == "WARNING"
    exh = make_bars([20.0] * 12, close=[100.0] * 11 + [140.0], atr=10.0)
    r = atr_filter(exh, 1, CFG)
    assert r.metrics["atr_status"] == "EXHAUSTED" and r.status == "FAIL"


# ---------------- VIX ----------------
def test_vix_pass_fail_missing_disabled():
    assert vix_filter(VixSnapshot(14.0, 14.2, None), CFG).status == "PASS"
    assert vix_filter(VixSnapshot(35.0, 34.0, None), CFG).status == "FAIL"           # above max
    assert vix_filter(VixSnapshot(16.0, 14.0, None), CFG).status == "FAIL"           # +14% spike
    assert vix_filter(None, CFG).reasons == ["VIX DATA UNAVAILABLE"]
    assert vix_filter(VixSnapshot(14.0, 14.0, None, stale=True), CFG).reasons == ["VIX DATA STALE"]
    off = CFG.model_copy(update={"vix": CFG.vix.model_copy(update={"enabled": False})})
    assert vix_filter(None, off).status == "PASS"


# ---------------- final signal ----------------
def _scenario(**over):
    start = ist(2026, 10, 7, 9, 15)
    adx = adx_breakout(pre=26)                      # breakout candle at 9:15 + 36*5 = 12:15
    b5 = make_bars(adx, 28.0, 14.0, start=start)
    b15 = make_bars([15 + i * 0.5 for i in range(20)], 26.0, 15.0, start=ist(2026, 10, 6, 10, 0), step_minutes=15)
    vix = VixSnapshot(14.0, 14.1, b5[-1].ts)
    kw = dict(symbol="NIFTY", bars5=b5, bars15=b15, atr_bars=b5, vix=vix, cfg=CFG, stale=None)
    kw.update(over)
    return evaluate(**kw)


def test_all_gates_pass_generates_signal():
    r = _scenario()
    assert r.state == "QUALIFIED" and r.final == "SIGNAL_READY" and r.direction == "CALL"
    assert r.entry_price == 100.0 and r.stop_price == 70.0 and r.target_price == 145.0  # 3x / 4.5x ATR 10


def test_any_mandatory_gate_failure_means_no_signal():
    assert _scenario(vix=VixSnapshot(40.0, 39.0, None)).final == "NO_SIGNAL"
    b15_bad = make_bars([30 - i * 0.5 for i in range(20)], 26.0, 15.0, step_minutes=15)
    r = _scenario(bars15=b15_bad)
    assert r.final == "NO_SIGNAL" and r.state == "BREAKOUT_DETECTED" and r.atr.status == "SKIP"
    r = _scenario(stale={"5m": "5M DATA STALE"})
    assert r.state == "REJECTED" and r.reason == "5M DATA STALE"


def test_outside_entry_window_rejected():
    adx = adx_breakout(pre=74)  # breakout at 09:15 + 84 candles = 16:15 -> after 14:45
    b5 = make_bars(adx, 28.0, 14.0, start=ist(2026, 10, 7, 9, 15))
    r = _scenario(bars5=b5, atr_bars=b5)
    assert r.state == "REJECTED" and "entry window" in r.reason


# ---------------- compression relative to the ADX peak ----------------
def test_compression_level_follows_the_peak():
    from app.strategy.engine import compression_level
    c = CFG.five_min
    assert compression_level([40.0] * 10 + [30.0], 10, c)[0] == 20.0   # 50% of a 40 peak
    assert compression_level([60.0] * 10 + [35.0], 10, c)[0] == 30.0   # 50% of a 60 peak


def test_high_peak_compresses_above_20():
    bars = make_bars([60.0] * 14 + [27.0] * 10)  # 27 <= 30 (50% of 60): compressed although above 20
    g = gate1(bars, CFG)
    assert g.status == "WAIT" and g.metrics["compression_level"] == 30.0 and "50% of peak 60.0" in g.reasons[0]


def test_low_peak_needs_deeper_compression():
    bars = make_bars([30.0] * 14 + [18.0] * 10)  # 18 > 15 (50% of 30): not compressed although below 20
    assert gate1(bars, CFG).status == "FAIL"


def test_fixed_mode_and_legacy_configs_keep_the_fixed_threshold():
    fixed = StrategyConfig.model_validate({"five_min": {"compression_mode": "fixed"}})
    assert gate1(make_bars([30.0] * 14 + [18.0] * 10), fixed).status == "WAIT"
    legacy = StrategyConfig.model_validate({"five_min": {"compression_threshold": 20.0}})
    assert legacy.five_min.compression_mode == "fixed"
    assert StrategyConfig().five_min.compression_mode == "peak_pct"
