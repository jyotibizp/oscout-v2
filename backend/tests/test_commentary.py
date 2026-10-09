from app.indicators.wilder import series
from app.strategy.commentary import build, chop, side_rules
from app.strategy.config import StrategyConfig
from app.strategy.engine import VixSnapshot, evaluate
from tests.conftest import make_bars

CFG = StrategyConfig()
VIX = VixSnapshot(14.0, 14.5, None)


def _uptrend_state(n=80):
    closes = [100 + i * 1.0 for i in range(n)]
    return series([c + 0.5 for c in closes], [c - 0.5 for c in closes], closes, 14)[-1]


def test_chop_is_neutral_and_cools_adx():
    s = _uptrend_state()
    out = chop(s, 14, 60)
    assert out[-1].adx < s.adx and abs(out[-1].pdi - out[-1].mdi) < abs(s.pdi - s.mdi)


def test_side_rules_same_rule_for_both_sides():
    s = _uptrend_state()
    bars5 = make_bars([30.0] * 20 + [26.0, 25.0, 24.0, 23.0, 22.0], pdi=25.0, mdi=15.0)
    comp, rules = side_rules("NIFTY", s, bars5, CFG, False, bars5[-1].ts.replace(hour=23))
    assert comp["candles"] and "trades sideways" in comp["text"]
    assert [r["option"] for r in rules] == ["CE", "PE"]
    ce, pe = rules
    assert ce["move_pts"] > 0 and pe["move_pts"] > 0
    assert "rise of" in ce["text"] and "fall of" in pe["text"]
    assert ce["signal_in"] == comp["candles"] + ce["candles"] and pe["signal_in"] == comp["candles"] + pe["candles"]


def test_commentary_cooling_adx_gives_eta_and_rules():
    adx = [30.0] * 20 + [26.0, 25.0, 24.0, 23.0, 22.0]
    bars5 = make_bars(adx, pdi=25.0, mdi=15.0)
    bars15 = make_bars([30.0 - i * 0.2 for i in range(20)], step_minutes=15)
    res = evaluate("NIFTY", bars5, bars15, bars5, VIX, CFG)
    c = build(res, bars5, bars15, CFG, _uptrend_state())
    assert c["bias"] == "CE" and c["headline"].startswith("No setup near")
    g1 = c["lines"][0]
    assert g1["gate"] == "5m ADX" and "needs ≤ 15.0 (50% of peak 30.0)" in g1["text"] and g1["earliest"]
    assert "slope" in c["lines"][1]["text"] and c["lines"][1]["would_pass"] is False
    assert [v["option"] for v in c["rules"]] == ["CE", "PE"]
    assert c["compression"]["text"] and c["outlook"] is None


def test_commentary_compression_waiting_names_breakout_trigger():
    bars5 = make_bars([40.0] * 14 + [17.0] * 10)
    bars15 = make_bars([22.0] * 20, step_minutes=15)
    res = evaluate("NIFTY", bars5, bars15, bars5, VIX, CFG)
    c = build(res, bars5, bars15, CFG, None)
    assert c["lines"][0]["status"] == "WAIT" and "next 5m ADX above" in c["lines"][0]["text"]
    assert c["rules"] == [] and "Compression ready" in c["headline"]


def test_times_past_the_session_say_after_close():
    from app.strategy.commentary import _when
    from tests.conftest import ist
    last = make_bars([20.0], start=ist(2026, 10, 9, 15, 0))[-1]
    cutoff = ist(2026, 10, 9, 14, 45)
    assert _when(ist(2026, 10, 9, 14, 30), last, cutoff) == "≈ 14:30 IST"
    assert _when(ist(2026, 10, 9, 15, 5), last, cutoff) == "≈ 15:05 IST, after the entry cutoff"
    assert _when(ist(2026, 10, 9, 15, 40), last, cutoff) == "after today's 15:30 close"
