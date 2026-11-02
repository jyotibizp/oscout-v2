"""Supported instruments. Adding an index later = one entry here (the strategy engine is symbol-agnostic)."""
from dataclasses import dataclass


@dataclass(frozen=True)
class Instrument:
    symbol: str
    kite_token: int
    quote_key: str
    tradable: bool          # False = filter feed only (India VIX)
    opt_exchange: str = ""  # options segment for the chain tab (NFO / BFO)
    opt_name: str = ""      # underlying name in Kite's instrument dump
    strike_step: int = 0    # mock chain only; Kite chain uses the listed strikes


INSTRUMENTS = {
    "NIFTY": Instrument("NIFTY", 256265, "NSE:NIFTY 50", True, "NFO", "NIFTY", 50),
    "SENSEX": Instrument("SENSEX", 265, "BSE:SENSEX", True, "BFO", "SENSEX", 100),
    "BANKNIFTY": Instrument("BANKNIFTY", 260105, "NSE:NIFTY BANK", True, "NFO", "BANKNIFTY", 100),
    "INDIAVIX": Instrument("INDIAVIX", 264969, "NSE:INDIA VIX", False),
}
TRADABLE = [s for s, i in INSTRUMENTS.items() if i.tradable]
VIX = "INDIAVIX"


def testing_symbols() -> set[str]:
    """Indexes still in Testing (backlog #19): scanned and recorded, card tagged, no chime. TESTING_SYMBOLS in .env."""
    from app.core.settings import get_settings
    return {x.strip().upper() for x in get_settings().testing_symbols.split(",") if x.strip()}
