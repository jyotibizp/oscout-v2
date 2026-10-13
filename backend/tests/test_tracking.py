from app.db.models import SignalSetup
from app.signals.tracking import track
from app.strategy.config import StrategyConfig
from tests.conftest import ist, make_bars

CFG = StrategyConfig()


def setup(**ctx):
    return SignalSetup(symbol="NIFTY", direction="CALL", state="ACTIVE", entry_price=100.0, stop_price=70.0,
                       target_price=145.0, peak_adx=25.0, adx_declines=ctx.pop("declines", 0),
                       signal_context={"held": 4, **ctx})


def bar(close, h=12, m=0):
    return make_bars([24.0], close=[close], start=ist(2026, 10, 7, h, m))[0]


def test_hold_reports_pnl_in_points_and_r():
    t = track(setup(), bar(115.0), CFG)
    assert t["verdict"] == "HOLD" and t["pnl_points"] == 15.0 and t["r"] == 0.5 and t["to_stop"] == 45.0


def test_watch_when_adx_exit_is_one_candle_away_in_profit():
    t = track(setup(declines=1), bar(110.0), CFG)
    assert t["verdict"] == "WATCH" and "one more lower close exits" in t["reasons"][0]


def test_adx_falling_while_red_is_only_a_note():
    t = track(setup(declines=1), bar(95.0), CFG)
    assert t["verdict"] == "HOLD" and "only fires in profit" in t["reasons"][0]


def test_watch_near_stop_and_near_session_end():
    assert track(setup(), bar(75.0), CFG)["verdict"] == "WATCH"
    t = track(setup(), bar(101.0, 15, 15), CFG)
    assert t["verdict"] == "WATCH" and t["candles_left"] == 2


def test_trail_verdict_after_stop_moved():
    t = track(setup(stop=100.0, stop_moved=True), bar(131.0), CFG)
    assert t["verdict"] == "TRAIL" and t["stop"] == 100.0 and t["initial_stop"] == 70.0
