from app.strategy.config import StrategyConfig
from app.strategy.engine import Position, evaluate_exit
from tests.conftest import make_bars

CFG = StrategyConfig()
never_last = lambda ts: False  # noqa: E731


def pos(**kw):
    p = dict(direction=1, entry_price=100.0, stop=70.0, target=145.0, peak_adx=25.0, last_adx=25.0)
    p.update(kw)
    return Position(**p)


def test_adx_exhaustion_needs_confirmation_candles():
    bars = make_bars([28.0, 27.0], close=[110.0, 111.0])
    p, ex = evaluate_exit(pos(), bars[:1], CFG, never_last)
    assert ex is None and p.declines == 0  # 28 > 25 (rising)
    p, ex = evaluate_exit(p, make_bars([27.0], close=[111.0]), CFG, never_last)
    assert ex is None and p.declines == 1
    p, ex = evaluate_exit(p, make_bars([26.5], close=[112.0]), CFG, never_last)
    assert ex is not None and ex.reason == "ADX_EXHAUSTION" and ex.price == 112.0


def test_adx_exit_waits_when_not_in_profit():
    bars = make_bars([24.0, 23.0, 22.0], close=[95.0, 94.0, 93.0])
    _, ex = evaluate_exit(pos(), bars, CFG, never_last)
    assert ex is None


def test_di_reversal_exit_when_enabled():
    cfg = CFG.model_copy(update={"exit": CFG.exit.model_copy(update={"di_reversal_exit": True})})
    bars = make_bars([26.0], pdi=12.0, mdi=24.0, close=[101.0])
    _, ex = evaluate_exit(pos(), bars, cfg, never_last)
    assert ex.reason == "DI_REVERSAL"


def test_stop_checked_before_target_and_gap_fills_at_open():
    from app.strategy.engine import Bar
    b = make_bars([26.0], close=[100.0])[0]
    gap = Bar(b.ts, 60.0, 62.0, 58.0, 61.0, 26.0, 25.0, 15.0, 10.0)
    _, ex = evaluate_exit(pos(), [gap], CFG, never_last)
    assert ex.reason == "STOP" and ex.price == 60.0
    tgt = Bar(b.ts, 140.0, 150.0, 139.0, 148.0, 26.0, 25.0, 15.0, 10.0)
    _, ex = evaluate_exit(pos(), [tgt], CFG, never_last)
    assert ex.reason == "TARGET" and ex.price == 145.0


def test_session_end_and_max_hold():
    _, ex = evaluate_exit(pos(), make_bars([26.0], close=[101.0]), CFG, lambda ts: True)
    assert ex.reason == "SESSION_END"
    p = pos()
    p.held = CFG.exit.max_hold_candles - 1
    _, ex = evaluate_exit(p, make_bars([26.0], close=[101.0]), CFG, never_last)
    assert ex.reason == "MAX_HOLD"
