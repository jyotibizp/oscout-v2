"""Black-Scholes Greeks and implied volatility (European, no dividend). Shared by the chain tab (#15) and Greeks (#1)."""
import math

RISK_FREE = 0.065  # ~ India 91-day T-bill
YEAR = 365 * 24 * 3600


def _cdf(x: float) -> float:
    return 0.5 * (1 + math.erf(x / math.sqrt(2)))


def _pdf(x: float) -> float:
    return math.exp(-x * x / 2) / math.sqrt(2 * math.pi)


def price(spot: float, strike: float, t: float, iv: float, call: bool, r: float = RISK_FREE) -> float:
    if t <= 0 or iv <= 0:
        return max(0.0, spot - strike) if call else max(0.0, strike - spot)
    d1 = (math.log(spot / strike) + (r + iv * iv / 2) * t) / (iv * math.sqrt(t))
    d2 = d1 - iv * math.sqrt(t)
    if call:
        return spot * _cdf(d1) - strike * math.exp(-r * t) * _cdf(d2)
    return strike * math.exp(-r * t) * _cdf(-d2) - spot * _cdf(-d1)


def implied_vol(premium: float, spot: float, strike: float, t: float, call: bool, r: float = RISK_FREE) -> float | None:
    """Bisection on 1%..300%. None when the premium is below intrinsic or above the 300% price."""
    if premium is None or premium <= 0 or t <= 0:
        return None
    lo, hi = 0.01, 3.0
    if premium < price(spot, strike, t, lo, call, r) or premium > price(spot, strike, t, hi, call, r):
        return None
    for _ in range(60):
        mid = (lo + hi) / 2
        if price(spot, strike, t, mid, call, r) > premium:
            hi = mid
        else:
            lo = mid
    return (lo + hi) / 2


def greeks(spot: float, strike: float, t: float, iv: float, call: bool, r: float = RISK_FREE) -> dict:
    """delta; theta per calendar day; gamma per point; vega per 1 IV point."""
    st = math.sqrt(t)
    d1 = (math.log(spot / strike) + (r + iv * iv / 2) * t) / (iv * st)
    d2 = d1 - iv * st
    common = -spot * _pdf(d1) * iv / (2 * st)
    if call:
        delta, theta = _cdf(d1), common - r * strike * math.exp(-r * t) * _cdf(d2)
    else:
        delta, theta = _cdf(d1) - 1, common + r * strike * math.exp(-r * t) * _cdf(-d2)
    return {"delta": delta, "theta": theta / 365, "gamma": _pdf(d1) / (spot * iv * st), "vega": spot * _pdf(d1) * st / 100}
