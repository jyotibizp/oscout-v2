import random

from app.indicators.wilder import WilderState, series, step


def _walk(n, seed=1, drift=0.0):
    r = random.Random(seed)
    h, l, c = [], [], []
    p = 100.0
    for _ in range(n):
        o = p
        p = p * (1 + drift + r.gauss(0, 0.002))
        h.append(max(o, p) * 1.001)
        l.append(min(o, p) * 0.999)
        c.append(p)
    return h, l, c


def test_atr_first_value_is_mean_true_range():
    h, l, c = [10, 11, 12, 13], [9, 10, 11, 12], [9.5, 10.5, 11.5, 12.5]
    s = series(h, l, c, period=3)
    trs = [max(h[i] - l[i], abs(h[i] - c[i - 1]), abs(l[i] - c[i - 1])) for i in range(1, 4)]
    assert s[2].atr is None
    assert abs(s[3].atr - sum(trs) / 3) < 1e-12


def test_warmup_and_ranges():
    h, l, c = _walk(80)
    s = series(h, l, c, period=14)
    assert all(x.adx is None for x in s[:27]) and s[27].adx is not None  # first ADX on the 2n-th candle
    for x in s[30:]:
        assert 0 <= x.adx <= 100 and x.pdi >= 0 and x.mdi >= 0 and x.atr > 0


def test_incremental_equals_full_recalculation():
    h, l, c = _walk(300, seed=3)
    full = series(h, l, c, 14)
    part = series(h[:200], l[:200], c[:200], 14)
    st = WilderState(**part[-1].as_dict())
    for i in range(200, 300):
        st = step(st, h[i], l[i], c[i], 14)
    assert st.as_dict() == full[-1].as_dict()


def test_uptrend_has_plus_di_leading_and_high_adx():
    h, l, c = _walk(200, seed=5, drift=0.002)
    s = series(h, l, c, 14)[-1]
    assert s.pdi > s.mdi and s.adx > 25


def test_downtrend_has_minus_di_leading():
    h, l, c = _walk(200, seed=5, drift=-0.002)
    s = series(h, l, c, 14)[-1]
    assert s.mdi > s.pdi
