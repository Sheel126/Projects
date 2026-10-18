"""The screener (lesson 03 §3): about 1,000 names down to a handful, in five filters.

    1. eligibility   member today (or a sector ETF), raw close >= $10, ADV >= $25M, a clean
                     single-identity history, not held, not blacklisted
    2. trend         close > SMA50 > SMA200 (adjusted)
    3. momentum      126-day return / 126-day vol, top 20% of what passed 1 and 2
    4. trigger       close above the prior 20-session high, on >= 1.5x relative dollar volume
    5. extension     (close - SMA20) <= 3 ATR: the move has not already happened

Every filter reads row `t` of the precomputed matrices and nothing later. The survivors carry
their bracket levels (§4-§5), on the raw price scale because they become real orders.
"""

import math
from dataclasses import dataclass, field
from decimal import ROUND_DOWN, ROUND_UP, Decimal

import numpy as np

from liquid_atm_quant.strategy.indicators import Indicators
from liquid_atm_quant.strategy.params import FunnelParams
from liquid_atm_quant.tax.money import cents

CENT = Decimal("0.01")
STAGES = ("universe", "eligible", "trend", "momentum", "trigger", "extension")


@dataclass(frozen=True)
class Candidate:
    symbol: str
    sector: str
    momentum: float
    rvol: float
    close: Decimal
    atr: Decimal
    entry_limit: Decimal
    stop_loss: Decimal
    take_profit: Decimal

    @property
    def risk_per_share(self) -> Decimal:
        return self.entry_limit - self.stop_loss

    @property
    def reason(self) -> str:
        return (f"breakout mom={self.momentum:.2f} rvol={self.rvol:.1f} "
                f"atr={self.atr} ({float(self.atr / self.close):.1%})")


@dataclass
class ScreenResult:
    candidates: list[Candidate]
    counts: dict[str, int] = field(default_factory=dict)
    """How many names survived each stage: the funnel's shape, reported per run."""


def bracket(close: float, atr: float, p: FunnelParams) -> tuple[Decimal, Decimal, Decimal] | None:
    """Entry a quarter-ATR above the close, stop 2 ATR below the entry, target 3 ATR above it.

    The stop rounds *down* and the target *up* to the cent, so rounding never tightens the bracket
    the lesson's math assumed.
    """
    a = Decimal(repr(atr))
    entry = cents(Decimal(repr(close)) + Decimal(repr(p.entry_offset_atr)) * a)
    stop = (entry - Decimal(repr(p.stop_atr)) * a).quantize(CENT, rounding=ROUND_DOWN)
    target = (entry + Decimal(repr(p.target_atr)) * a).quantize(CENT, rounding=ROUND_UP)
    if stop <= 0 or not stop < entry < target:
        return None
    return entry, stop, target


class Screener:
    def __init__(self, indicators: Indicators, symbols: list[str], member: np.ndarray,
                 params: FunnelParams, sectors: dict[str, str] | None = None,
                 etfs: dict[str, str] | None = None) -> None:
        self.ind = indicators
        self.symbols = symbols
        self.member = member
        self.params = params
        self.etfs = etfs or {}
        self.sectors = {**(sectors or {}), **self.etfs}
        self.etf_mask = np.array([s in self.etfs for s in symbols], dtype=bool)

    def screen(self, t: int, exclude: set[str] | frozenset[str] = frozenset()) -> ScreenResult:
        p, ind = self.params, self.ind
        counts: dict[str, int] = {}
        close, ac = ind.close[t], ind.adj_close[t]

        with np.errstate(invalid="ignore"):
            # 1. eligibility
            mask = (self.member[t] | self.etf_mask) & np.isfinite(close)
            counts["universe"] = int(mask.sum())
            mask &= (close >= p.min_price) & (ind.adv[t] >= p.min_adv) & (ind.run[t] >= p.history)
            if exclude:
                mask &= ~np.isin(self.symbols, list(exclude))
            counts["eligible"] = int(mask.sum())

            # 2. trend alignment
            mask &= (ac > ind.sma_fast[t]) & (ind.sma_fast[t] > ind.sma_slow[t])
            counts["trend"] = int(mask.sum())

            # 3. risk-adjusted momentum, ranked across what is left
            momentum = ind.momentum[t]
            mask &= np.isfinite(momentum)
            ranked = np.flatnonzero(mask)
            if ranked.size:
                keep = max(1, math.ceil(ranked.size * p.momentum_top))
                top = ranked[np.argsort(-momentum[ranked], kind="stable")[:keep]]
                mask = np.zeros_like(mask)
                mask[top] = True
            counts["momentum"] = int(mask.sum())

            # 4. trigger: a fresh 20-session closing high on heavy volume
            mask &= (ac > ind.prior_high[t]) & (ind.rvol[t] >= p.rvol_min)
            counts["trigger"] = int(mask.sum())

            # 5. not already extended
            atr_adj = ind.atr_adj[t]
            mask &= np.isfinite(atr_adj) & (atr_adj > 0) & \
                ((ac - ind.sma_short[t]) <= p.max_extension_atr * atr_adj)
            counts["extension"] = int(mask.sum())

        out = []
        atr_raw = ind.atr_raw(t)
        for j in np.flatnonzero(mask):
            levels = bracket(float(close[j]), float(atr_raw[j]), p)
            if levels is None:
                continue
            entry, stop, target = levels
            symbol = self.symbols[j]
            out.append(Candidate(symbol, self.sectors.get(symbol, "Unknown"), float(momentum[j]),
                                 float(ind.rvol[t, j]), cents(close[j]), cents(atr_raw[j]),
                                 entry, stop, target))
        out.sort(key=lambda c: (-c.momentum, -c.rvol, c.symbol))
        return ScreenResult(out, counts)
