"""The five stock-picking investor strategies of Phase 3b (lesson 03b §4).

Each turns one investor's published method (as summarised in questflowai/investorskills and the
investor's own books) into rules a computer can apply on the close of every day with no judgement.
The numbers are written down here, before the first backtest; changing any of them is a new trial.

    buffett_quality     wonderful businesses at a fair price: high ROIC, low debt, steady profits,
                        ranked by earnings yield                              (Buffett / Munger)
    greenblatt_magic    the Magic Formula: rank on return on capital + earnings yield (Greenblatt)
    lynch_peg           growth at a reasonable price: P/E / growth < 1            (Peter Lynch)
    canslim             earnings acceleration + new highs + relative strength + market direction
                                                                              (William O'Neil)
    templeton_value     maximum pessimism: profitable companies down 40%+ from their highs, held
                        for at least a year                                    (John Templeton)

Every strategy keeps its own selection (base.py rule 4) and uses `keep_then_fill` hysteresis so a
name is not traded every month for hovering around the cut-off.
"""

from dataclasses import dataclass, field
from datetime import date

import numpy as np

from liquid_atm_quant.backtest.fundamentals import Fundamentals
from liquid_atm_quant.backtest.panel import DataView
from liquid_atm_quant.backtest.strategy import PortfolioSnapshot
from liquid_atm_quant.investors.base import (NO_RESIZE, PortfolioStrategy, equal_weight,
                                             first_session_of_month, first_session_of_quarter)
from liquid_atm_quant.investors.screen import (Liquidity, candidates, cap_sectors, high_ratio,
                                               keep_then_fill, trailing_return)

NON_OPERATING = ("Financials", "Utilities", "Real Estate")
"""Sectors where EBIT, ROIC and EV do not mean what they mean for an operating business (a bank's
debt is its raw material). Greenblatt excludes them explicitly; the quality and GARP screens do
too, for the same reason."""


class _StockStrategy(PortfolioStrategy):
    def __init__(self, fundamentals: Fundamentals, sectors: dict[str, str]) -> None:
        super().__init__()
        self.fundamentals = fundamentals
        self.sectors = sectors
        self.selected: list[str] = []
        self._last: date | None = None
        self._screened: list[int] = []
        self._passed: list[int] = []

    def diagnostics(self) -> dict:
        def mean(xs: list[int]) -> float:
            return round(float(np.mean(xs)), 1) if xs else 0.0
        return {"rebalances": len(self._screened), "avg_candidates": mean(self._screened),
                "avg_passed": mean(self._passed)}


# ---- Buffett / Munger ---------------------------------------------------------------------

@dataclass(frozen=True)
class BuffettParams:
    n: int = 20
    hold_rank: int = 40
    min_roic: float = 0.15
    max_debt_to_equity: float = 1.0
    min_positive_quarters: int = 7
    """Of the last 8: 'consistent earning power'. One bad quarter in two years is allowed."""
    require_positive_fcf: bool = True
    max_per_sector: int = 5
    band: float = 0.5
    liquidity: Liquidity = field(default_factory=Liquidity)


class BuffettQuality(_StockStrategy):
    name = "buffett_quality"

    def __init__(self, fundamentals: Fundamentals, sectors: dict[str, str],
                 params: BuffettParams | None = None) -> None:
        self.params = params or BuffettParams()
        self.band = self.params.band
        super().__init__(fundamentals, sectors)

    def targets(self, view: DataView, book: PortfolioSnapshot) -> dict[str, float] | None:
        if not first_session_of_month(view.today, self._last):
            return None
        self._last = view.today
        p = self.params
        pool = candidates(view, self.fundamentals, self.sectors, p.liquidity, NON_OPERATING)
        passed = []
        for c in pool:
            roic, de, ey = c.roic, c.debt_to_equity, c.earnings_yield
            positive, seen = c.positive_quarters()
            if roic is None or de is None or ey is None or seen < 8:
                continue
            if roic < p.min_roic or de > p.max_debt_to_equity or positive < p.min_positive_quarters:
                continue
            if (c.net_income or 0) <= 0:
                continue
            if p.require_positive_fcf and (c.fcf is None or c.fcf <= 0):
                continue
            passed.append((ey, c.symbol))
        ranked = [s for _, s in sorted(passed, reverse=True)]
        self._screened.append(len(pool))
        self._passed.append(len(ranked))
        self.selected = keep_then_fill(ranked, set(self.selected), p.n, p.hold_rank,
                                       self.sectors, p.max_per_sector)
        return self.weigh(self.selected, {c.symbol: c.mcap for c in pool})

    def weigh(self, selected: list[str], mcaps: dict[str, float]) -> dict[str, float]:
        return equal_weight(selected)


@dataclass(frozen=True)
class BuffettCapParams(BuffettParams):
    max_weight: float = 0.10
    """No single company above 10%: the screen still picks, the market decides how much."""


class BuffettQualityCap(BuffettQuality):
    """`buffett_quality` with the same screen and selection, weighted by market cap (lesson 03c §2).

    The factor evidence the screen rests on (Novy-Marx 2013; Fama-French RMW; Asness, Frazzini and
    Pedersen's QMJ) is measured on value-weighted portfolios. Equal weighting the same picks tilts
    the book toward the smaller half, which cost 3.2 points a year against SPY in 2016-2024.
    """

    name = "buffett_quality_cw"

    def __init__(self, fundamentals: Fundamentals, sectors: dict[str, str],
                 params: BuffettCapParams | None = None) -> None:
        super().__init__(fundamentals, sectors, params or BuffettCapParams())

    def weigh(self, selected: list[str], mcaps: dict[str, float]) -> dict[str, float]:
        caps = {s: mcaps[s] for s in selected if mcaps.get(s, 0) > 0}
        return capped_weights(caps, self.params.max_weight) if caps else equal_weight(selected)


def capped_weights(sizes: dict[str, float], cap: float) -> dict[str, float]:
    """Proportional to `sizes`, no weight above `cap`: the excess is redistributed to the uncapped
    names in proportion, repeatedly, until nothing exceeds the cap (or everything is capped)."""
    weights: dict[str, float] = {}
    free = dict(sizes)
    budget = 1.0
    while free:
        total = sum(free.values())
        over = {s for s, v in free.items() if budget * v / total > cap}
        if not over:
            weights.update({s: budget * v / total for s, v in free.items()})
            break
        for s in over:
            weights[s] = cap
            del free[s]
        budget = 1.0 - sum(weights.values())
        if budget <= 0:
            break
    return weights


# ---- Greenblatt ---------------------------------------------------------------------------

@dataclass(frozen=True)
class GreenblattParams:
    n: int = 25
    hold_rank: int = 50
    band: float = 0.5
    liquidity: Liquidity = field(default_factory=Liquidity)


class GreenblattMagic(_StockStrategy):
    """Rank every operating company on ROC and on earnings yield; buy the best combined rank.

    Rebalanced quarterly: The Little Book holds each name about a year, and quarterly review with a
    wide hold rank gets close to that without the bookkeeping of yearly tranches.
    """

    name = "greenblatt_magic"

    def __init__(self, fundamentals: Fundamentals, sectors: dict[str, str],
                 params: GreenblattParams | None = None) -> None:
        self.params = params or GreenblattParams()
        self.band = self.params.band
        super().__init__(fundamentals, sectors)

    def targets(self, view: DataView, book: PortfolioSnapshot) -> dict[str, float] | None:
        if not first_session_of_quarter(view.today, self._last):
            return None
        self._last = view.today
        p = self.params
        pool = candidates(view, self.fundamentals, self.sectors, p.liquidity, NON_OPERATING)
        rows = [(c.symbol, c.return_on_tangible_capital, c.earnings_yield) for c in pool
                if (c.ebit or 0) > 0]
        rows = [(s, roc, ey) for s, roc, ey in rows if roc is not None and ey is not None]
        by_roc = {s: i for i, (s, _, _) in enumerate(sorted(rows, key=lambda r: -r[1]))}
        by_ey = {s: i for i, (s, _, _) in enumerate(sorted(rows, key=lambda r: -r[2]))}
        ranked = sorted(by_roc, key=lambda s: (by_roc[s] + by_ey[s], s))
        self._screened.append(len(pool))
        self._passed.append(len(ranked))
        self.selected = keep_then_fill(ranked, set(self.selected), p.n, p.hold_rank,
                                       self.sectors, None)
        return equal_weight(self.selected)


# ---- Lynch --------------------------------------------------------------------------------

@dataclass(frozen=True)
class LynchParams:
    n: int = 20
    hold_rank: int = 40
    max_peg: float = 1.0
    hold_max_peg: float = 1.5
    min_growth: float = 0.10
    max_growth: float = 0.50
    """Lynch distrusted growth above ~25-50% a year as unsustainable."""
    max_pe: float = 40.0
    max_debt_to_equity: float = 0.8
    max_per_sector: int = 5
    band: float = 0.5
    liquidity: Liquidity = field(default_factory=Liquidity)


class LynchPeg(_StockStrategy):
    """PEG = (P/E) / (annual earnings growth in %). Below 1, growth is on sale.

    Growth is TTM net income over the TTM a year earlier, not EPS: per-share history is broken by
    every split in the first-reported data, and net income growth understates EPS growth only for
    companies buying back stock - a conservative error.
    """

    name = "lynch_peg"

    def __init__(self, fundamentals: Fundamentals, sectors: dict[str, str],
                 params: LynchParams | None = None) -> None:
        self.params = params or LynchParams()
        self.band = self.params.band
        super().__init__(fundamentals, sectors)

    def targets(self, view: DataView, book: PortfolioSnapshot) -> dict[str, float] | None:
        if not first_session_of_month(view.today, self._last):
            return None
        self._last = view.today
        p = self.params
        pool = candidates(view, self.fundamentals, self.sectors, p.liquidity, ("Financials",))
        held = set(self.selected)
        scored = []
        for c in pool:
            pe, g, de = c.pe, c.growth(), c.debt_to_equity
            if pe is None or g is None or de is None:
                continue
            if pe > p.max_pe or not p.min_growth <= g <= p.max_growth or de > p.max_debt_to_equity:
                continue
            peg = pe / (100 * g)
            if peg <= (p.hold_max_peg if c.symbol in held else p.max_peg):
                scored.append((peg, c.symbol))
        ranked = [s for _, s in sorted(scored)]
        self._screened.append(len(pool))
        self._passed.append(len(ranked))
        self.selected = keep_then_fill(ranked, held, p.n, p.hold_rank, self.sectors,
                                       p.max_per_sector)
        return equal_weight(self.selected)


# ---- O'Neil CANSLIM -----------------------------------------------------------------------

@dataclass(frozen=True)
class CanslimParams:
    n: int = 15
    min_quarter_growth: float = 0.25      # C
    min_annual_growth: float = 0.25       # A
    max_below_high: float = 0.15          # N: within 15% of the 52-week high
    min_rs: float = 0.80                  # L: relative strength percentile
    hold_min_rs: float = 0.70
    hold_max_below_high: float = 0.25
    stop_loss: float = 0.08               # O'Neil's rule: cut every loss at 7-8%
    market_symbol: str = "SPY"            # M
    market_sma: int = 200
    rs_lookback: int = 252
    high_lookback: int = 252
    liquidity: Liquidity = field(default_factory=Liquidity)


class Canslim(_StockStrategy):
    """C, A, N, L and M of CANSLIM; S is the liquidity floor and I (institutional sponsorship)
    is skipped, because the 13F data it needs is not free.

    New names are picked on the first session of each month. Exits are checked every day: the 8%
    stop from the price the name was selected at, and the M rule - SPY closing under its 200-day
    average sends the whole book to cash until it closes back above.
    """

    name = "canslim"
    band = NO_RESIZE

    def __init__(self, fundamentals: Fundamentals, sectors: dict[str, str],
                 params: CanslimParams | None = None) -> None:
        self.params = params or CanslimParams()
        super().__init__(fundamentals, sectors)
        self._reference: dict[str, float] = {}
        self._stops = 0
        self._market_exits = 0

    def _market_up(self, view: DataView) -> bool:
        p = self.params
        closes = view.history("close", p.market_symbol, p.market_sma, adjusted=True)
        return len(closes) == p.market_sma and bool(np.all(np.isfinite(closes))) and \
            closes[-1] > closes.mean()

    def targets(self, view: DataView, book: PortfolioSnapshot) -> dict[str, float] | None:
        p = self.params
        if not self._market_up(view):
            if self.selected:
                self._market_exits += 1
                self.selected, self._reference = [], {}
                return {}
            return None

        changed = False
        for symbol in list(self.selected):
            price = view.latest("close", symbol, adjusted=True)
            if np.isfinite(price) and price < self._reference[symbol] * (1 - p.stop_loss):
                self.selected.remove(symbol)
                del self._reference[symbol]
                self._stops += 1
                changed = True

        if first_session_of_month(view.today, self._last):
            self._last = view.today
            self._refresh(view)
            changed = True
        # 1/n per name, not 1/len: three qualifying names get 3/15 of the book, not all of it.
        return {s: 1.0 / p.n for s in self.selected} if changed else None

    def _refresh(self, view: DataView) -> None:
        p = self.params
        returns = trailing_return(view, p.rs_lookback)
        highs = high_ratio(view, p.high_lookback)
        pool = candidates(view, self.fundamentals, self.sectors, p.liquidity)
        pool = [c for c in pool if c.symbol in returns and c.symbol in highs
                and view.same_segment(c.symbol, p.rs_lookback + 1)]
        ordered = sorted(returns[c.symbol] for c in pool)
        rs = {c.symbol: np.searchsorted(ordered, returns[c.symbol], side="right") / len(ordered)
              for c in pool} if ordered else {}

        keep = [c.symbol for c in pool if c.symbol in self.selected
                and rs[c.symbol] >= p.hold_min_rs and highs[c.symbol] >= 1 - p.hold_max_below_high]
        fresh = []
        for c in pool:
            if c.symbol in keep:
                continue
            q, a = c.quarter_yoy(), c.growth()
            if q is None or a is None or q < p.min_quarter_growth or a < p.min_annual_growth:
                continue
            if highs[c.symbol] < 1 - p.max_below_high or rs[c.symbol] < p.min_rs:
                continue
            fresh.append(c.symbol)
        fresh.sort(key=lambda s: -rs[s])
        self._screened.append(len(pool))
        self._passed.append(len(fresh))
        keep.sort(key=lambda s: -rs[s])
        chosen = (keep + fresh)[:p.n]
        for symbol in chosen:
            if symbol not in self._reference:
                self._reference[symbol] = float(view.latest("close", symbol, adjusted=True))
        self._reference = {s: v for s, v in self._reference.items() if s in chosen}
        self.selected = chosen

    def diagnostics(self) -> dict:
        return {**super().diagnostics(), "stop_exits": self._stops,
                "market_exits": self._market_exits}


# ---- Templeton ----------------------------------------------------------------------------

@dataclass(frozen=True)
class TempletonParams:
    n: int = 20
    high_lookback: int = 504              # two years of sessions
    min_drawdown: float = 0.40            # at most 60% of the two-year high
    max_pe: float = 15.0
    max_debt_to_equity: float = 1.5
    min_hold_days: int = 366              # past a year: long-term rates
    recovered_drawdown: float = 0.15      # sell once back within 15% of the high...
    max_hold_days: int = 1095             # ...or after three years regardless
    idle_symbol: str = "SPY"
    """Slots not yet filled sit in the index rather than in cash: an equity investor waiting for
    bargains is still an equity investor."""
    band: float = 0.5
    liquidity: Liquidity = field(default_factory=Liquidity)


class TempletonValue(_StockStrategy):
    """Buy the most-hated profitable companies and give them time.

    Entry: down at least 40% from the two-year high, still profitable (TTM net income > 0), P/E at
    most 15, debt/equity at most 1.5; deepest drawdown first, into empty slots, monthly.
    Exit: earnings turn negative (any time - a loss harvested early is short-term and worth more),
    or, after a year and a day, the price has recovered to within 15% of its high or three years
    have passed.
    """

    name = "templeton_value"

    def __init__(self, fundamentals: Fundamentals, sectors: dict[str, str],
                 params: TempletonParams | None = None) -> None:
        self.params = params or TempletonParams()
        self.band = self.params.band
        super().__init__(fundamentals, sectors)
        self._since: dict[str, date] = {}

    def targets(self, view: DataView, book: PortfolioSnapshot) -> dict[str, float] | None:
        if not first_session_of_month(view.today, self._last):
            return None
        self._last = view.today
        p = self.params
        highs = high_ratio(view, p.high_lookback)

        for symbol in list(self.selected):
            snap = self.fundamentals.snapshot(view, symbol)
            held = (view.today - self._since[symbol]).days
            broke = snap is not None and (snap.ttm.get("net_income") or 0) <= 0
            gone = not view.traded_today(symbol)
            recovered = highs.get(symbol, 0.0) >= 1 - p.recovered_drawdown
            if broke or gone or (held >= p.min_hold_days and
                                 (recovered or held >= p.max_hold_days)):
                self.selected.remove(symbol)
                del self._since[symbol]

        pool = candidates(view, self.fundamentals, self.sectors, p.liquidity)
        scored = []
        for c in pool:
            ratio = highs.get(c.symbol)
            if ratio is None or c.symbol in self.selected:
                continue
            if ratio > 1 - p.min_drawdown or not view.same_segment(c.symbol, p.high_lookback):
                continue
            pe, de = c.pe, c.debt_to_equity
            if pe is None or de is None or pe > p.max_pe or de > p.max_debt_to_equity:
                continue
            scored.append((ratio, c.symbol))
        self._screened.append(len(pool))
        self._passed.append(len(scored))
        for _, symbol in sorted(scored):
            if len(self.selected) >= p.n:
                break
            self.selected.append(symbol)
            self._since[symbol] = view.today

        weights = {s: 1.0 / p.n for s in self.selected}
        idle = 1.0 - len(self.selected) / p.n
        if idle > 0:
            weights[p.idle_symbol] = weights.get(p.idle_symbol, 0.0) + idle
        return weights


__all__ = ["BuffettCapParams", "BuffettParams", "BuffettQuality", "BuffettQualityCap", "Canslim", "CanslimParams", "GreenblattMagic",
           "GreenblattParams", "LynchParams", "LynchPeg", "TempletonParams", "TempletonValue",
           "cap_sectors", "capped_weights"]
