"""What every Phase 3b stock strategy reads about a candidate at the close (lesson 03b §3).

One `Candidate` per tradable index member: liquidity checked, fundamentals snapshot attached, and
the market-dependent ratios (market cap, enterprise value, P/E) priced at today's close. The ratio
definitions live here once so that "earnings yield" means the same thing in every strategy.
"""

import warnings
from collections.abc import Iterable
from dataclasses import dataclass

import numpy as np

from liquid_atm_quant.backtest.fundamentals import Fundamentals, Snapshot, market_cap
from liquid_atm_quant.backtest.panel import DataView

CORPORATE_TAX = 0.21
"""US federal rate since 2018, used to put operating income on an after-tax footing for ROIC."""


@dataclass(frozen=True)
class Liquidity:
    min_price: float = 10.0
    min_adv: float = 10_000_000.0
    adv_window: int = 20
    min_history: int = 63
    """Sessions of single-identity history: keeps out IPO weeks and ticker changes."""


@dataclass
class Candidate:
    symbol: str
    sector: str
    snap: Snapshot
    mcap: float

    # ---- the ratios, each None when a needed input is missing or meaningless ----
    @property
    def ev(self) -> float | None:
        ev = self.mcap + self.snap.debt - self.snap.cash
        return ev if ev > 0 else None

    @property
    def ebit(self) -> float | None:
        return self.snap.ttm.get("operating_income")

    @property
    def net_income(self) -> float | None:
        return self.snap.ttm.get("net_income")

    @property
    def equity(self) -> float | None:
        return self.snap.instant.get("equity")

    @property
    def earnings_yield(self) -> float | None:
        """EBIT / EV: what the whole business earns per dollar it costs to buy outright."""
        ev, ebit = self.ev, self.ebit
        return ebit / ev if ev and ebit is not None else None

    @property
    def roic(self) -> float | None:
        """After-tax operating income / (equity + debt - cash)."""
        ebit, equity = self.ebit, self.equity
        if ebit is None or equity is None or equity <= 0:
            return None
        invested = equity + self.snap.debt - self.snap.cash
        return ebit * (1 - CORPORATE_TAX) / invested if invested > 0 else None

    @property
    def return_on_tangible_capital(self) -> float | None:
        """Greenblatt's ROC: EBIT / (net working capital + net PP&E)."""
        ebit = self.ebit
        ca = self.snap.instant.get("current_assets")
        cl = self.snap.instant.get("current_liabilities")
        ppe = self.snap.instant.get("ppe_net", 0.0)
        if ebit is None or ca is None or cl is None:
            return None
        capital = max(0.0, ca - cl - self.snap.cash) + ppe
        return ebit / capital if capital > 0 else None

    @property
    def debt_to_equity(self) -> float | None:
        equity = self.equity
        return self.snap.debt / equity if equity and equity > 0 else None

    @property
    def pe(self) -> float | None:
        ni = self.net_income
        return self.mcap / ni if ni and ni > 0 else None

    @property
    def fcf(self) -> float | None:
        cfo = self.snap.ttm.get("cfo")
        return None if cfo is None else cfo - self.snap.ttm.get("capex", 0.0)

    def growth(self, concept: str = "net_income") -> float | None:
        """TTM over the TTM a year earlier, both positive."""
        now, then = self.snap.ttm.get(concept), self.snap.ttm_prior.get(concept)
        if now is None or then is None or now <= 0 or then <= 0:
            return None
        return now / then - 1

    def quarter_yoy(self, back: int = 0, concept: str = "net_income") -> float | None:
        """Quarter `back` (0 = latest) against the same quarter a year earlier, base positive."""
        q = self.snap.quarters.get(concept, [])
        i = len(q) - 1 - back
        if i - 4 < 0:
            return None
        now, then = q[i], q[i - 4]
        return now / then - 1 if then > 0 else None

    def positive_quarters(self, concept: str = "net_income") -> tuple[int, int]:
        q = self.snap.quarters.get(concept, [])
        return sum(1 for v in q if v > 0), len(q)


def liquid(view: DataView, symbol: str, rules: Liquidity) -> bool:
    price = view.latest("close", symbol)
    if not np.isfinite(price) or price < rules.min_price:
        return False
    if view.adv(symbol, rules.adv_window) < rules.min_adv:
        return False
    return view.same_segment(symbol, rules.min_history)


def candidates(view: DataView, fundamentals: Fundamentals, sectors: dict[str, str],
               rules: Liquidity, exclude_sectors: Iterable[str] = ()) -> list[Candidate]:
    excluded = set(exclude_sectors)
    out: list[Candidate] = []
    for symbol in view.universe():
        sector = sectors.get(symbol, "Unknown")
        if sector in excluded or not liquid(view, symbol, rules):
            continue
        snap = fundamentals.snapshot(view, symbol)
        if snap is None:
            continue
        mcap = market_cap(view, symbol, snap)
        if mcap is None or mcap <= 0:
            continue
        out.append(Candidate(symbol, sector, snap, mcap))
    return out


def cap_sectors(ranked: list[str], sectors: dict[str, str], per_sector: int | None,
                n: int) -> list[str]:
    """The first `n` of `ranked`, skipping names whose sector already has `per_sector`."""
    chosen: list[str] = []
    counts: dict[str, int] = {}
    for symbol in ranked:
        sector = sectors.get(symbol, "Unknown")
        if per_sector is not None and counts.get(sector, 0) >= per_sector:
            continue
        chosen.append(symbol)
        counts[sector] = counts.get(sector, 0) + 1
        if len(chosen) >= n:
            break
    return chosen


def keep_then_fill(ranked: list[str], held: set[str], n: int, hold_rank: int,
                   sectors: dict[str, str], per_sector: int | None) -> list[str]:
    """Hysteresis: a holding stays while it ranks within `hold_rank`; new names fill to `n`.

    Without it a name hovering around rank `n` is bought and sold every month, which is pure
    turnover and pure short-term tax.
    """
    position = {s: i for i, s in enumerate(ranked)}
    kept = [s for s in ranked if s in held and position[s] < hold_rank]
    kept = cap_sectors(kept, sectors, per_sector, n)
    counts: dict[str, int] = {}
    for s in kept:
        counts[sectors.get(s, "Unknown")] = counts.get(sectors.get(s, "Unknown"), 0) + 1
    chosen = list(kept)
    for symbol in ranked:
        if len(chosen) >= n:
            break
        if symbol in chosen:
            continue
        sector = sectors.get(symbol, "Unknown")
        if per_sector is not None and counts.get(sector, 0) >= per_sector:
            continue
        chosen.append(symbol)
        counts[sector] = counts.get(sector, 0) + 1
    return chosen


def trailing_return(view: DataView, lookback: int) -> dict[str, float]:
    """Adjusted-close return over `lookback` sessions for every symbol with a full window."""
    closes = view.history("close", None, lookback + 1, adjusted=True)
    if closes.shape[0] < lookback + 1:
        return {}
    with np.errstate(divide="ignore", invalid="ignore"):
        ret = closes[-1] / closes[0] - 1.0
    return {s: float(r) for s, r in zip(view.symbols, ret) if np.isfinite(r)}


def high_ratio(view: DataView, lookback: int) -> dict[str, float]:
    """Today's adjusted close / its highest adjusted close over `lookback` sessions."""
    closes = view.history("close", None, lookback, adjusted=True)
    if closes.shape[0] < lookback:
        return {}
    with warnings.catch_warnings(), np.errstate(invalid="ignore", divide="ignore"):
        warnings.simplefilter("ignore", RuntimeWarning)       # all-NaN columns
        high = np.nanmax(closes, axis=0)
        ratio = closes[-1] / high
    return {s: float(r) for s, r in zip(view.symbols, ratio) if np.isfinite(r)}
