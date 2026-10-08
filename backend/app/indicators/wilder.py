"""Wilder ATR, +DI, -DI, DX and ADX as an exact step-by-step recurrence.

The same `step()` builds the full history and extends it one candle at a time, so incremental
updates are bit-for-bit identical to a full recalculation (no re-warm-up drift).

Definitions (period n):
  TR   = max(H-L, |H-Cprev|, |L-Cprev|);  +DM = H-Hprev if > Lprev-L and > 0;  -DM = Lprev-L likewise
  ATR, +DMs, -DMs: mean of the first n values, then Wilder smoothing  x = (x_prev*(n-1) + v) / n
  +DI = 100 * +DMs / ATR;  -DI = 100 * -DMs / ATR;  DX = 100 * |+DI - -DI| / (+DI + -DI)
  ADX: mean of the first n DX values, then Wilder smoothing.
First ATR/DI after n+1 candles; first ADX after 2n candles.
"""
from dataclasses import asdict, dataclass


@dataclass
class WilderState:
    n: int = 0             # candles seen
    high: float = 0.0
    low: float = 0.0
    close: float = 0.0
    atr: float | None = None
    pdm: float | None = None
    mdm: float | None = None
    pdi: float | None = None
    mdi: float | None = None
    dx: float | None = None
    adx: float | None = None
    tr_sum: float = 0.0
    pdm_sum: float = 0.0
    mdm_sum: float = 0.0
    dx_sum: float = 0.0

    def as_dict(self) -> dict:
        return asdict(self)


def step(prev: WilderState | None, high: float, low: float, close: float, period: int) -> WilderState:
    if prev is None or prev.n == 0:
        return WilderState(n=1, high=high, low=low, close=close)
    s = WilderState(**prev.as_dict())
    s.n = prev.n + 1
    tr = max(high - low, abs(high - prev.close), abs(low - prev.close))
    up, down = high - prev.high, prev.low - low
    pdm = up if (up > down and up > 0) else 0.0
    mdm = down if (down > up and down > 0) else 0.0
    k = s.n - 1  # number of TR/DM values so far
    if k < period:
        s.tr_sum += tr; s.pdm_sum += pdm; s.mdm_sum += mdm
    elif k == period:
        s.tr_sum += tr; s.pdm_sum += pdm; s.mdm_sum += mdm
        s.atr, s.pdm, s.mdm = s.tr_sum / period, s.pdm_sum / period, s.mdm_sum / period
    else:
        s.atr = (prev.atr * (period - 1) + tr) / period
        s.pdm = (prev.pdm * (period - 1) + pdm) / period
        s.mdm = (prev.mdm * (period - 1) + mdm) / period
    if s.atr is not None:
        s.pdi = 100.0 * s.pdm / s.atr if s.atr > 0 else 0.0
        s.mdi = 100.0 * s.mdm / s.atr if s.atr > 0 else 0.0
        tot = s.pdi + s.mdi
        s.dx = 100.0 * abs(s.pdi - s.mdi) / tot if tot > 0 else 0.0
        j = k - period + 1  # number of DX values so far
        if j < period:
            s.dx_sum += s.dx
        elif j == period:
            s.dx_sum += s.dx
            s.adx = s.dx_sum / period
        else:
            s.adx = (prev.adx * (period - 1) + s.dx) / period
    s.high, s.low, s.close = high, low, close
    return s


def series(highs, lows, closes, period: int = 14, start: WilderState | None = None) -> list[WilderState]:
    out, st = [], start
    for h, l, c in zip(highs, lows, closes):
        st = step(st, float(h), float(l), float(c), period)
        out.append(st)
    return out
