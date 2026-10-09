from app.indicators.wilder import series
from app.strategy.commentary import build, flip_level
from app.strategy.config import StrategyConfig
from app.strategy.engine import VixSnapshot, evaluate
from tests.conftest import make_bars

CFG = StrategyConfig()
VIX = VixSnapshot(14.0, 14.5, None)


def _uptrend_state(n=80):
    closes = [100 + i * 1.0 for i in range(n)]
    return series([c + 0.5 for c in closes], [c - 0.5 for c in closes], closes, 14)[-1]


def test_flip_level_finds_pe_below_price_in_an_uptrend():
    s = _uptrend_state()
    assert s.pdi > s.mdi
    lv = flip_level(s, 14, "PUT", 3.0)
    assert lv is not None and lv["option"] == "PE" and lv["price"] < s.close
    assert lv["mdi"] - lv["pdi"] >= 3.0 and 1 <= lv["candles"] <= 3


def test_commentary_cooling_adx_gives_eta_and_levels():
    adx = [30.0] * 20 + [26.0, 25.0, 24.0, 23.0, 22.0]
    bars5 = make_bars(adx, pdi=25.0, mdi=15.0)
    bars15 = make_bars([30.0 - i * 0.2 for i in range(20)], step_minutes=15)
    res = evaluate("NIFTY", bars5, bars15, bars5, VIX, CFG)
    c = build(res, bars5, bars15, CFG, _uptrend_state())
    assert c["bias"] == "CE" and c["headline"].startswith("No setup near")
    g1 = c["lines"][0]
    assert g1["gate"] == "5m ADX" and "needs ≤ 20" in g1["text"] and g1["earliest"]
    assert "slope" in c["lines"][1]["text"] and c["lines"][1]["would_pass"] is False
    assert [v["option"] for v in c["levels"]] == ["PE"]
    assert c["outlook"]


def test_commentary_compression_waiting_names_breakout_trigger():
    bars5 = make_bars([25.0] * 14 + [17.0] * 10)
    bars15 = make_bars([22.0] * 20, step_minutes=15)
    res = evaluate("NIFTY", bars5, bars15, bars5, VIX, CFG)
    c = build(res, bars5, bars15, CFG, None)
    assert c["lines"][0]["status"] == "WAIT" and "next 5m ADX above" in c["lines"][0]["text"]
    assert c["levels"] == [] and "Compression ready" in c["headline"]
