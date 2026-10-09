"""Central strategy configuration. Every strategy parameter lives here (never hard-coded in the engine).

Each field carries its UI metadata (title, description, default, validation bounds). Saved configurations
are immutable and versioned (ADX Strategy vX.Y.Z); every scan, setup and trade records the version used.
Defaults come from the 2025-26 NIFTY/SENSEX research (ADX compression -> breakout held up best).
"""
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class _Group(BaseModel):
    model_config = ConfigDict(extra="forbid")


class FiveMinSettings(_Group):
    adx_period: int = Field(14, ge=5, le=50, title="ADX Period", description="Wilder period for 5m ADX, +DI, -DI.")
    compression_mode: Literal["peak_pct", "fixed"] = Field(
        "peak_pct", title="Compression Mode",
        description="peak_pct: compressed = ADX at or below a % of its recent peak (at 50%: a 40 peak compresses at 20, a 60 peak at 30). "
                    "fixed: ADX at or below the fixed threshold.")
    compression_peak_pct: float = Field(50.0, ge=10, le=90, title="Compression % of Peak",
                                        description="peak_pct mode: ADX at or below this % of its recent peak counts as compressed.")
    peak_lookback_candles: int = Field(75, ge=10, le=300, title="Peak Lookback",
                                       description="peak_pct mode: peak = highest 5m ADX over the last N candles (75 = one session).")
    compression_threshold: float = Field(20.0, ge=5, le=40, title="Fixed Compression Threshold",
                                         description="fixed mode: ADX at or below this level counts as compressed.")
    min_compression_candles: int = Field(6, ge=2, le=100, title="Min Compression Candles",
                                         description="ADX must stay compressed for at least this many 5m candles before the breakout.")
    max_compression_candles: int = Field(75, ge=2, le=500, title="Max Compression Candles",
                                         description="Longer compressions are treated as a dead market and ignored.")
    breakout_lookback: int = Field(5, ge=2, le=30, title="Breakout Lookback",
                                   description="Breakout: ADX closes above the average of its previous N values.")
    min_adx_increase: float = Field(0.5, ge=0, le=10, title="Min ADX Increase",
                                    description="ADX must rise at least this much on the breakout candle (points vs previous candle).")
    breakout_threshold: float = Field(0.0, ge=0, le=50, title="Breakout ADX Level",
                                      description="ADX must be at or above this level on the breakout candle (0 = off).")
    min_di_separation: float = Field(3.0, ge=0, le=40, title="Min DI Separation",
                                     description="|+DI − −DI| on the breakout candle. +DI leading = CALL, −DI leading = PUT.")
    breakout_valid_candles: int = Field(3, ge=1, le=12, title="Breakout Valid For",
                                        description="5m candles a breakout stays valid while waiting for 15m confirmation.")


    @model_validator(mode="before")
    @classmethod
    def _legacy_mode(cls, data):
        # configurations saved before peak-relative compression existed used the fixed threshold
        if isinstance(data, dict) and "compression_threshold" in data and "compression_mode" not in data:
            data = {**data, "compression_mode": "fixed"}
        return data


class FifteenMinSettings(_Group):
    adx_period: int = Field(14, ge=5, le=50, title="ADX Period", description="Wilder period for 15m ADX, +DI, -DI.")
    lookback_candles: int = Field(15, ge=5, le=100, title="Lookback Candles",
                                  description="Number of 15m candles analysed for the pattern.")
    slope_candles: int = Field(2, ge=1, le=10, title="Slope Candles", description="ADX slope = ADX now − ADX N candles ago.")
    min_adx_slope: float = Field(-1.0, ge=-10, le=10, title="Min ADX Slope",
                                 description="15m ADX slope must be above this (0 = ADX rising; -1 also lets a flat or slightly easing 15m ADX through).")
    min_adx: float = Field(0.0, ge=0, le=60, title="Min 15m ADX", description="15m ADX must be at least this (0 = off).")
    max_adx: float = Field(60.0, ge=10, le=100, title="Max 15m ADX",
                           description="Above this the 15m trend is considered already exhausted.")
    require_di_agreement: bool = Field(True, title="DI Must Agree",
                                       description="15m leading DI must point the same way as the 5m breakout.")
    min_di_consistency: float = Field(0.3, ge=0, le=1, title="DI Consistency",
                                      description="Share of lookback candles where the same DI leads (0.5 = half).")


class AtrSettings(_Group):
    mode: Literal["warning", "filter"] = Field("warning", title="ATR Mode",
                                               description="warning: ATR status is shown but never blocks a signal. "
                                                           "filter: EXHAUSTED blocks new entries.")
    atr_period: int = Field(14, ge=5, le=50, title="ATR Period", description="Wilder ATR period.")
    atr_timeframe: Literal["5m", "15m"] = Field("5m", title="ATR Timeframe", description="Timeframe used for ATR.")
    lookback_candles: int = Field(12, ge=2, le=100, title="Move Lookback",
                                  description="Move = distance from the extreme of the last N candles (against the trade) to price.")
    warning_multiple: float = Field(2.5, ge=0.5, le=20, title="Warning Multiple", description="Move / ATR at or above this = WARNING.")
    exhaustion_multiple: float = Field(3.5, ge=0.5, le=20, title="Exhaustion Multiple",
                                       description="Move / ATR at or above this = EXHAUSTED (no new entry).")

    @model_validator(mode="after")
    def _order(self):
        if self.warning_multiple > self.exhaustion_multiple:
            raise ValueError("ATR warning multiple must not exceed the exhaustion multiple")
        return self


    @model_validator(mode="before")
    @classmethod
    def _legacy_mode(cls, data):
        # configurations saved before ATR warning mode existed used ATR as a blocking filter
        if isinstance(data, dict) and "exhaustion_multiple" in data and "mode" not in data:
            data = {**data, "mode": "filter"}
        return data


class VixSettings(_Group):
    enabled: bool = Field(True, title="VIX Filter Enabled", description="Turn the India VIX filter on or off.")
    min_vix: float = Field(10.0, ge=0, le=100, title="Minimum VIX", description="Below this, option moves are too small.")
    max_vix: float = Field(30.0, ge=0, le=100, title="Maximum VIX", description="Above this, conditions are too unstable.")
    max_abs_change_pct: float = Field(15.0, ge=0, le=100, title="Max Day Change %",
                                      description="Fail if VIX moved more than this % vs previous close (either way).")
    spike_threshold_pct: float = Field(10.0, ge=0, le=100, title="Spike Threshold %",
                                       description="Fail if VIX is up more than this % vs previous close.")
    trend_requirement: Literal["any", "falling", "rising"] = Field("any", title="VIX Trend",
                                                                   description="Optional: require VIX falling or rising today.")
    max_age_minutes: int = Field(15, ge=5, le=240, title="Max VIX Age (min)", description="Older VIX data counts as stale.")

    @model_validator(mode="after")
    def _order(self):
        if self.min_vix > self.max_vix:
            raise ValueError("Minimum VIX must not exceed maximum VIX")
        return self


class ExitSettings(_Group):
    adx_decline_candles: int = Field(2, ge=1, le=10, title="Confirmation Candles",
                                     description="Exit after this many consecutive falling 5m ADX candles (ADX exhaustion).")
    min_adx_decline: float = Field(0.0, ge=0, le=20, title="Min ADX Decline",
                                   description="ADX must also be at least this many points below its peak since entry.")
    adx_peak_decline_pct: float = Field(0.0, ge=0, le=100, title="ADX Peak Decline %",
                                        description="Alternative exit: ADX this % below its peak since entry (0 = off).")
    adx_exit_only_in_profit: bool = Field(True, title="ADX Exit Only In Profit",
                                          description="Apply the ADX exhaustion exit only when the trade is in profit (else wait for stop/time).")
    di_reversal_exit: bool = Field(False, title="DI Reversal Exit",
                                   description="Exit when the DIs cross against the trade (off by default: it cut winners in 2025-26 replays).")
    stop_atr_multiple: float = Field(3.0, ge=0, le=20, title="Protective Stop (× ATR)",
                                     description="Safety stop from entry in 5m ATR multiples (0 = off).")
    target_atr_multiple: float = Field(4.5, ge=0, le=50, title="Profit Target (× ATR)",
                                       description="Optional profit target in 5m ATR multiples (0 = off).")
    max_hold_candles: int = Field(36, ge=1, le=300, title="Max Hold (5m candles)", description="Exit at close after this many candles.")
    exit_at_session_end: bool = Field(True, title="Exit At Session End", description="Close any open signal on the 15:25 candle.")
    allow_new_entry_while_active: bool = Field(False, title="Allow Overlapping Signals",
                                               description="Allow a new signal on a symbol while one is still active.")


class ScannerSettings(_Group):
    auto_scan_enabled: bool = Field(True, title="Auto Scan", description="Scan automatically during market hours.")
    interval_minutes: int = Field(5, ge=5, le=60, multiple_of=5, title="Scan Interval (min)",
                                  description="Automatic scan interval (multiples of 5, aligned to candle closes).")
    market_hours_only: bool = Field(True, title="Market Hours Only", description="Never scan outside 09:15–15:30 IST.")
    scan_delay_seconds: int = Field(20, ge=0, le=120, title="Scan Delay (s)",
                                    description="Wait after a candle closes so the broker has published it.")
    entry_start: str = Field("09:30", pattern=r"^\d{2}:\d{2}$", title="First Entry Time",
                             description="No new signals before this IST time.")
    entry_end: str = Field("14:45", pattern=r"^\d{2}:\d{2}$", title="Last Entry Time",
                           description="No new signals after this IST time.")
    max_data_age_minutes: int = Field(10, ge=5, le=60, title="Max Data Age (min)",
                                      description="Latest 5m candle older than this (in session) = stale data, no signal.")


class StrategyConfig(_Group):
    five_min: FiveMinSettings = FiveMinSettings()
    fifteen_min: FifteenMinSettings = FifteenMinSettings()
    atr: AtrSettings = AtrSettings()
    vix: VixSettings = VixSettings()
    exit: ExitSettings = ExitSettings()
    scanner: ScannerSettings = ScannerSettings()

    def indicator_periods(self) -> set[int]:
        return {self.five_min.adx_period, self.fifteen_min.adx_period, self.atr.atr_period}


GROUP_TITLES = {"five_min": "5M ADX", "fifteen_min": "15M ADX", "atr": "ATR", "vix": "INDIA VIX",
                "exit": "EXIT", "scanner": "SCANNER"}


def describe() -> list[dict]:
    """UI metadata: groups -> parameters with title, description, type, default, bounds, options."""
    schema = StrategyConfig.model_json_schema()
    defs = schema.get("$defs", {})
    out = []
    for gkey, gtitle in GROUP_TITLES.items():
        ref = schema["properties"][gkey].get("$ref") or schema["properties"][gkey]["allOf"][0]["$ref"]
        g = defs[ref.split("/")[-1]]
        params = []
        for k, p in g["properties"].items():
            params.append({"key": k, "title": p.get("title", k), "description": p.get("description", ""),
                           "type": p.get("type", "string"), "default": p.get("default"),
                           "min": p.get("minimum"), "max": p.get("maximum"), "multiple_of": p.get("multipleOf"),
                           "options": p.get("enum"), "pattern": p.get("pattern")})
        out.append({"key": gkey, "title": gtitle, "params": params})
    return out
