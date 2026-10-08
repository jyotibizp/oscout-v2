"""Supported instruments. Adding an index later = one entry here (the strategy engine is symbol-agnostic)."""
from dataclasses import dataclass


@dataclass(frozen=True)
class Instrument:
    symbol: str
    kite_token: int
    quote_key: str
    tradable: bool          # False = filter feed only (India VIX)


INSTRUMENTS = {
    "NIFTY": Instrument("NIFTY", 256265, "NSE:NIFTY 50", True),
    "SENSEX": Instrument("SENSEX", 265, "BSE:SENSEX", True),
    "INDIAVIX": Instrument("INDIAVIX", 264969, "NSE:INDIA VIX", False),
}
TRADABLE = [s for s, i in INSTRUMENTS.items() if i.tradable]
VIX = "INDIAVIX"
