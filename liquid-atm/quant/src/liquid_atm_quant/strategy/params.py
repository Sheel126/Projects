"""Every number in lesson 03, written down before the first backtest of the funnel (§1).

Changing any field changes `fingerprint()`, and through it the run hash that Phase 4 counts as a
trial. That is the point: a "quick tweak" is not free, it is one of the budget.
"""

import hashlib
import json
from dataclasses import asdict, dataclass, fields, replace
from datetime import date

LOCKBOX_START = date(2024, 10, 1)
"""Phase 3 never runs a session on or after this date (lesson 03 §1)."""

TRIAL_BUDGET = 25
"""Raised from 20 to 25 on 2026-10-29, before any Phase 3d run, at the user's decision
(lesson 03d §1). Phase 4's Deflated Sharpe uses the number of trials actually run, so the raise
is paid for there."""

SECTOR_ETFS = {
    "XLB": "Materials", "XLC": "Communication", "XLE": "Energy", "XLF": "Financials",
    "XLI": "Industrials", "XLK": "Information Technology", "XLP": "Consumer Staples",
    "XLRE": "Real Estate", "XLU": "Utilities", "XLV": "Health Care",
    "XLY": "Consumer Discretionary",
}
"""Allowed through the screener alongside index members; each counts against its own sector.
SPY/QQQ/IWM/DIA are left out: they *are* the market the regime filter already reads."""


@dataclass(frozen=True)
class FunnelParams:
    # ---- regime (§2) -----------------------------------------------------------------
    regime_symbol: str = "SPY"
    trend_sma: int = 200
    trend_band: float = 0.01
    """Trend turns down below SMA × (1 − band) and back up above SMA × (1 + band)."""
    breadth_sma: int = 50
    breadth_min: float = 0.50
    vol_window: int = 20
    vol_max: float = 0.25

    # ---- screener (§3) ---------------------------------------------------------------
    min_price: float = 10.0
    min_adv: float = 25_000_000.0
    adv_window: int = 20
    history: int = 252
    """Sessions of clean, single-identity history a name needs before it can be screened."""
    sma_fast: int = 50
    sma_slow: int = 200
    momentum_window: int = 126
    momentum_top: float = 0.20
    breakout_window: int = 20
    rvol_window: int = 20
    rvol_min: float = 1.5
    sma_short: int = 20
    max_extension_atr: float = 3.0
    atr_window: int = 14
    include_sector_etfs: bool = True

    # ---- bracket (§4-§5) -------------------------------------------------------------
    entry_offset_atr: float = 0.25
    stop_atr: float = 2.0
    target_atr: float = 3.0
    time_stop_days: int = 10

    # ---- book (§6) -------------------------------------------------------------------
    risk_per_trade: float = 0.0075
    caution_risk_scale: float = 0.5
    max_position_weight: float = 0.15
    max_heat: float = 0.06
    max_per_sector: int = 3
    max_positions: int = 10
    max_new_per_day: int = 3
    max_new_per_day_caution: int = 1

    def __post_init__(self) -> None:
        if self.history < max(self.sma_slow, self.momentum_window + 1, self.trend_sma):
            raise ValueError("history must cover the longest lookback")
        if not 0 < self.momentum_top <= 1:
            raise ValueError("momentum_top is a fraction")
        if self.stop_atr <= 0 or self.target_atr <= 0:
            raise ValueError("bracket distances must be positive")

    def fingerprint(self) -> str:
        payload = json.dumps(asdict(self), sort_keys=True)
        return hashlib.sha256(payload.encode()).hexdigest()[:16]

    def with_overrides(self, overrides: dict[str, str]) -> "FunnelParams":
        """`--param stop_atr=2.5` from the command line, cast to the field's own type."""
        types = {f.name: f.type for f in fields(self)}
        cast = {}
        for key, raw in overrides.items():
            if key not in types:
                raise KeyError(f"unknown parameter {key!r}")
            kind = types[key]
            if kind is bool or kind == "bool":
                cast[key] = raw.lower() in ("1", "true", "yes")
            else:
                cast[key] = {"int": int, "float": float, "str": str}.get(
                    getattr(kind, "__name__", str(kind)), str)(raw)
        return replace(self, **cast)


class LockboxError(RuntimeError):
    pass


def assert_outside_lockbox(end: date, unlock: bool = False) -> None:
    """Refuse a run that reaches into the holdout unless it was asked for explicitly."""
    if end >= LOCKBOX_START and not unlock:
        raise LockboxError(
            f"run ends {end}, inside the lockbox that starts {LOCKBOX_START}. Phase 3 tunes on data "
            f"before it only; pass --unlock-lockbox for Phase 4's final run (lesson 03 §1)")
