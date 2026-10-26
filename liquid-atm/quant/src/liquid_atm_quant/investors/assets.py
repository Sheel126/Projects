"""Cross-asset investor strategies of Phase 3b, traded through ETFs (lesson 03b §4).

    turtle_trend        Donchian breakout trend-following across stocks, bonds, gold, commodities
                        and real estate, sized by volatility    (Turtles / Seykota / Tudor Jones)
    all_weather         a fixed risk-balanced mix that does not care what the economy does
                                                                                   (Ray Dalio)
    quality_trend       half buffett_quality, half turtle_trend: stock picking for the long run,
                        trend-following for the crashes

The Turtle rules applied to single stocks are what Phase 3 tested and failed (a breakout entry
picks short-term reversal in large caps). Applied across asset classes they are a different
strategy: the documented edge of trend-following lives in diversified futures-like markets, and
its job here is to own bonds and gold when stocks are falling.
"""

from dataclasses import dataclass, field
from datetime import date

import numpy as np

from liquid_atm_quant.backtest.panel import DataView
from liquid_atm_quant.backtest.strategy import PortfolioSnapshot
from liquid_atm_quant.investors.base import (NO_RESIZE, PortfolioStrategy,
                                             first_session_of_month, first_session_of_quarter)

TREND_ASSETS = ("SPY", "QQQ", "IWM", "EFA", "EEM", "TLT", "IEF", "TIP", "LQD", "GLD", "DBC", "VNQ")


@dataclass(frozen=True)
class TurtleParams:
    assets: tuple[str, ...] = TREND_ASSETS
    entry_window: int = 55                # System 2: a new 55-day high
    exit_window: int = 20                 # out on a new 20-day low
    atr_window: int = 20                  # the Turtles' N
    risk_per_n: float = 0.0025
    """Fraction of equity that one N (one average day's range) of adverse move costs."""
    max_weight: float = 0.20
    cash_symbol: str = "SHY"
    """Whatever the trend book does not use earns T-bill-like yield instead of the engine's 0%."""
    min_cash_weight: float = 0.02


class TurtleTrend(PortfolioStrategy):
    """Long-only System 2 across `assets`, checked every close, entered at the next open.

    A position's weight is set once, at entry: weight = risk_per_n / (N / price), capped at
    `max_weight`, and the whole book scaled down if the weights add up to more than 100%. It is
    not resized while open (base.py `band` = never) - trimming a trend while it runs is selling the
    winner, at the short-term rate.
    """

    name = "turtle_trend"
    band = NO_RESIZE

    def __init__(self, params: TurtleParams | None = None) -> None:
        self.params = params or TurtleParams()
        self.band_overrides = {self.params.cash_symbol: 0.25}
        super().__init__()
        self.weights: dict[str, float] = {}
        self._started = False
        self._entries = 0
        self._exits = 0

    def _signal(self, view: DataView, symbol: str) -> tuple[bool, bool, float]:
        p = self.params
        window = max(p.entry_window, p.atr_window) + 1
        if symbol not in view.panel.index:
            return False, False, np.nan
        close = view.history("close", symbol, window, adjusted=True)
        high = view.history("high", symbol, window, adjusted=True)
        low = view.history("low", symbol, window, adjusted=True)
        if len(close) < window or not np.all(np.isfinite(close)):
            return False, False, np.nan
        today = close[-1]
        entry = today > np.max(high[-p.entry_window - 1:-1])
        exit_ = today < np.min(low[-p.exit_window - 1:-1])
        prev_close = close[-p.atr_window - 1:-1]
        tr = (np.maximum(high[-p.atr_window:], prev_close)
              - np.minimum(low[-p.atr_window:], prev_close))
        return bool(entry), bool(exit_), float(np.mean(tr) / today)

    def targets(self, view: DataView, book: PortfolioSnapshot) -> dict[str, float] | None:
        p = self.params
        changed = False
        for symbol in p.assets:
            entry, exit_, n_pct = self._signal(view, symbol)
            if symbol in self.weights and exit_:
                del self.weights[symbol]
                self._exits += 1
                changed = True
            elif symbol not in self.weights and entry and n_pct > 0:
                self.weights[symbol] = min(p.max_weight, p.risk_per_n / n_pct)
                self._entries += 1
                changed = True
        if not changed and self._started:
            return None
        self._started = True
        total = sum(self.weights.values())
        scale = 1.0 / total if total > 1.0 else 1.0
        out = {s: w * scale for s, w in self.weights.items()}
        cash = 1.0 - sum(out.values())
        if cash >= p.min_cash_weight:
            out[p.cash_symbol] = cash
        return out

    def diagnostics(self) -> dict:
        return {"entries": self._entries, "exits": self._exits}


# ---- Dalio All-Weather ------------------------------------------------------------------

ALL_WEATHER = (("SPY", 0.30), ("TLT", 0.40), ("IEF", 0.15), ("GLD", 0.075), ("DBC", 0.075))
"""The published retail version (Dalio's allocation as given in Robbins, *Money: Master the Game*,
2014): 30% stocks, 40% long Treasuries, 15% intermediate Treasuries, 7.5% gold, 7.5% commodities."""


@dataclass(frozen=True)
class AllWeatherParams:
    weights: tuple[tuple[str, float], ...] = ALL_WEATHER
    band: float = 0.20


class AllWeather(PortfolioStrategy):
    """Hold the fixed mix; on the first session of each quarter, resize anything more than 20%
    (relative) away from its target. Infrequent and banded, so most gains stay unrealized."""

    name = "all_weather"

    def __init__(self, params: AllWeatherParams | None = None) -> None:
        self.params = params or AllWeatherParams()
        self.band = self.params.band
        super().__init__()
        self._last: date | None = None

    def targets(self, view: DataView, book: PortfolioSnapshot) -> dict[str, float] | None:
        if not first_session_of_quarter(view.today, self._last):
            return None
        self._last = view.today
        return dict(self.params.weights)


# ---- Faber trend switch -----------------------------------------------------------------

@dataclass(frozen=True)
class TrendSwitchParams:
    risk_symbol: str = "SPY"
    safe_symbol: str = "SHY"
    """Short Treasuries, not long ones: 2022 showed long bonds can fall with stocks."""
    sma: int = 200
    """About Faber's 10 months."""


class TrendSwitch(PortfolioStrategy):
    """Faber (2007, revisited 2018): own the index while it is above its 10-month average,
    T-bills otherwise.

    Checked on the first session of each month (the paper's monthly rule, which also keeps the
    number of switches - each one a taxable sale - low). All in or all out, never resized.
    """

    name = "spy_trend"
    band = NO_RESIZE

    def __init__(self, params: TrendSwitchParams | None = None) -> None:
        self.params = params or TrendSwitchParams()
        super().__init__()
        self._last: date | None = None
        self._holding: str | None = None
        self._switches = 0

    def targets(self, view: DataView, book: PortfolioSnapshot) -> dict[str, float] | None:
        if not first_session_of_month(view.today, self._last):
            return None
        self._last = view.today
        p = self.params
        closes = view.history("close", p.risk_symbol, p.sma, adjusted=True)
        if len(closes) < p.sma or not np.all(np.isfinite(closes)):
            return None
        want = p.risk_symbol if closes[-1] > closes.mean() else p.safe_symbol
        if want == self._holding:
            return None
        self._switches += self._holding is not None
        self._holding = want
        return {want: 1.0}

    def diagnostics(self) -> dict:
        return {"switches": self._switches}


# ---- volatility target x trend ----------------------------------------------------------

@dataclass(frozen=True)
class VolTrendParams:
    index: str = "SPY"
    levered: str = "SSO"
    """Daily-reset 2x S&P 500: exposure above 1 without a margin account."""
    cash_symbol: str = "BIL"
    target_vol: float = 0.15
    max_exposure: float = 1.5
    fast_window: int = 20
    slow_window: int = 60
    """Forecast vol = max(20-day, 60-day realized): quick to cut, slow to re-lever."""
    sma: int = 200
    band: float = 0.10
    """Rebalance only when the weights would move by more than this in total (sum of |change|)."""
    step: float = 0.25
    """Exposure moves in whole steps with hysteresis: up once the raw target reaches the next step,
    down once it is half a step below the current one, to zero at once when the filter turns off.
    Continuous exposure (step 0) traded every 8 days and in 2008-2015 paid $28k of tax while its
    realized trades lost $18k: each trim of SPY at a loss, bought back days later, was a wash sale
    (lesson 03c §3)."""


class VolTargetTrend(PortfolioStrategy):
    """Exposure to the S&P 500 = min(cap, target vol / forecast vol) while the index closes above
    its 200-day average, zero below it (lesson 03c §3, `vt15_cap1.5_asym_trend_step25` in the
    screen).

    The vol scaling is Moreira & Muir (2017) and Harvey et al. (2018); the filter is the 200-day
    rule of Faber and Gayed & Bilello, checked daily. Neither half alone was enough in 1960-2015:
    vol targeting kept buy-and-hold's drawdowns, and the filter alone was -21%. The parameters were
    chosen on 1960-2015 only, by the rule written before the screen ran: highest CAGR with a max
    drawdown within 20% in every era.

    Exposure e is held as SPY (2 - e) + SSO (e - 1) above 1, SPY e + T-bills (1 - e) below.
    """

    name = "vol_trend"

    def __init__(self, params: VolTrendParams | None = None) -> None:
        self.params = params or VolTrendParams()
        self.band = 0.02
        super().__init__()
        self._held: dict[str, float] = {}
        self._level: float | None = None
        self._rebalances = 0
        self._exposures: list[float] = []

    def stepped(self, raw: float) -> float:
        step = self.params.step
        if step <= 0:
            return raw
        floor = np.floor(raw / step + 1e-9) * step
        level = self._level
        if level is None or raw <= 0 or raw >= level + step or raw < level - step / 2:
            self._level = float(floor)
        return self._level

    def exposure(self, view: DataView) -> float | None:
        p = self.params
        closes = view.history("close", p.index, max(p.sma, p.slow_window + 1), adjusted=True)
        if len(closes) < max(p.sma, p.slow_window + 1) or not np.all(np.isfinite(closes)):
            return None
        if closes[-1] <= closes[-p.sma:].mean():
            return 0.0
        vol = self.forecast_vol(np.diff(np.log(closes[-p.slow_window - 1:])))
        return float(min(p.max_exposure, p.target_vol / vol)) if vol > 0 else p.max_exposure

    def forecast_vol(self, rets: np.ndarray) -> float:
        fast = np.sqrt(252 * np.mean(rets[-self.params.fast_window:] ** 2))
        return float(max(fast, np.sqrt(252 * np.mean(rets ** 2))))

    def weights(self, e: float) -> dict[str, float]:
        p = self.params
        if e <= 1.0:
            return {p.index: e, p.cash_symbol: 1.0 - e}
        return {p.index: 2.0 - e, p.levered: e - 1.0}

    def targets(self, view: DataView, book: PortfolioSnapshot) -> dict[str, float] | None:
        e = self.exposure(view)
        if e is None:
            return None
        e = self.stepped(e)
        want = self.weights(e)
        symbols = set(want) | set(self._held)
        moved = sum(abs(want.get(s, 0.0) - self._held.get(s, 0.0)) for s in symbols)
        if self._held and moved <= self.params.band:
            return None
        self._held = want
        self._rebalances += 1
        self._exposures.append(e)
        return {s: w for s, w in want.items() if w > 1e-6}

    def diagnostics(self) -> dict:
        xs = self._exposures
        return {"rebalances": self._rebalances,
                "avg_exposure_at_rebalance": round(float(np.mean(xs)), 3) if xs else 0.0}


@dataclass(frozen=True)
class VolTrendV2Params(VolTrendParams):
    asymmetric: bool = False
    """20-day forecast only. The 60-day leg kept exposure near 0.4x through the 2020, 2019 and
    2023 recoveries; on 1960-2015 the symmetric forecast also earned more (10.3% vs 9.7%) inside
    the same 20% drawdown limit (lesson 03c §5)."""
    wash_aware: bool = False
    """Buy `index_twin` instead of a blacklisted SPY and wait out a blacklisted SSO. Off: in
    2008-2015 it did not reduce wash sales (34-63 either way), because most of them are on the
    "before" side of the window - a step up buys new SPY, a dip within 30 days cuts, and FIFO sells
    the OLD lot at a loss with the new one as its replacement. The blacklist cannot stop that;
    selling the newest lot first (specific identification) can, and that is a Phase 6 OMS
    requirement, not a strategy rule (lesson 03c §5)."""
    index_twin: str | None = "VTI"
    """CRSP US Total Market: a different index from SPY's, so not substantially identical, at
    ~0.99 daily correlation. Used only with `wash_aware`."""


class VolTargetTrendV2(VolTargetTrend):
    """`vol_trend` with the fix from its in-sample diagnosis (lesson 03c §5): a symmetric 20-day
    vol forecast, for faster re-entry after V-shaped recoveries. Optionally wash-sale-aware buying
    through the ledger's blacklist (off; see `wash_aware`)."""

    name = "vol_trend_v2"

    def __init__(self, params: VolTrendV2Params | None = None) -> None:
        super().__init__(params or VolTrendV2Params())
        self._twin_buys = 0
        self._deferred = 0

    def forecast_vol(self, rets: np.ndarray) -> float:
        if self.params.asymmetric:
            return super().forecast_vol(rets)
        return float(np.sqrt(252 * np.mean(rets[-self.params.fast_window:] ** 2)))

    def targets(self, view: DataView, book: PortfolioSnapshot) -> dict[str, float] | None:
        e = self.exposure(view)
        if e is None:
            return None
        e = self.stepped(e)
        p = self.params
        ideal = self.weights(e)
        blocked = book.blacklist if p.wash_aware else frozenset()
        index_slot = [p.index] + ([p.index_twin] if p.wash_aware and p.index_twin else [])
        want = self._fill(index_slot, ideal.get(p.index, 0.0), blocked)
        levered = self._fill([p.levered], ideal.get(p.levered, 0.0), blocked)
        want.update(levered)
        want[p.cash_symbol] = max(0.0, 1.0 - sum(want.values()))
        symbols = set(want) | set(self._held)
        moved = sum(abs(want.get(s, 0.0) - self._held.get(s, 0.0)) for s in symbols)
        if self._held and moved <= p.band:
            return None
        self._held = want
        self._rebalances += 1
        self._exposures.append(e)
        return {s: w for s, w in want.items() if w > 1e-6}

    def _fill(self, slot: list[str], target: float, blocked: frozenset) -> dict[str, float]:
        """Split one slot's target across its symbols: cut the twin first; add to the first symbol
        not on the blacklist, preferring whichever is already held; with none, hold what is held."""
        current = {s: self._held.get(s, 0.0) for s in slot}
        have = sum(current.values())
        out = dict(current)
        if target < have - 1e-9:
            excess = have - target
            for s in reversed(slot):
                cut = min(out[s], excess)
                out[s] -= cut
                excess -= cut
            return out
        add = target - have
        if add <= 1e-9:
            return out
        order = sorted(slot, key=lambda s: (current[s] <= 0, slot.index(s)))
        for s in order:
            if s not in blocked:
                out[s] += add
                if s != slot[0]:
                    self._twin_buys += 1
                return out
        self._deferred += 1
        return out

    def diagnostics(self) -> dict:
        return {**super().diagnostics(), "twin_buys": self._twin_buys,
                "deferred_for_wash_sale": self._deferred}


# ---- Keller VAA ---------------------------------------------------------------------------

@dataclass(frozen=True)
class VaaParams:
    risky: tuple[str, ...] = ("SPY", "EFA", "EEM", "AGG")
    defensive: tuple[str, ...] = ("LQD", "IEF", "SHY")
    top: int = 1


class VigilantAssetAllocation(PortfolioStrategy):
    """Keller & Keuning (2017), VAA-G4: breadth momentum with the 13612W score.

    Monthly: score = 12 x 1-month + 4 x 3-month + 2 x 6-month + 12-month return. If every risky
    asset scores above zero, hold the best one; if any is negative, hold the best defensive one.
    One bad asset is enough to step aside ("winning more by losing less")."""

    name = "vaa_g4"
    band = NO_RESIZE

    def __init__(self, params: VaaParams | None = None) -> None:
        self.params = params or VaaParams()
        super().__init__()
        self._last: date | None = None
        self._holding: tuple[str, ...] = ()
        self._defensive_months = 0
        self._months = 0

    @staticmethod
    def score(view: DataView, symbol: str) -> float | None:
        closes = view.history("close", symbol, 253, adjusted=True)
        if len(closes) < 253 or not np.all(np.isfinite(closes)):
            return None
        now = closes[-1]
        return float(12 * (now / closes[-22] - 1) + 4 * (now / closes[-64] - 1)
                     + 2 * (now / closes[-127] - 1) + (now / closes[0] - 1))

    def targets(self, view: DataView, book: PortfolioSnapshot) -> dict[str, float] | None:
        if not first_session_of_month(view.today, self._last):
            return None
        self._last = view.today
        p = self.params
        risky = {s: self.score(view, s) for s in p.risky}
        safe = {s: self.score(view, s) for s in p.defensive}
        if any(v is None for v in (*risky.values(), *safe.values())):
            return None
        self._months += 1
        if min(risky.values()) > 0:
            pool = risky
        else:
            pool = safe
            self._defensive_months += 1
        pick = tuple(sorted(pool, key=lambda s: -pool[s])[:p.top])
        if pick == self._holding:
            return None
        self._holding = pick
        return {s: 1.0 / p.top for s in pick}

    def diagnostics(self) -> dict:
        return {"months": self._months, "defensive_months": self._defensive_months}


# ---- combination ------------------------------------------------------------------------

@dataclass(frozen=True)
class SleeveParams:
    sleeves: tuple[tuple[str, float], ...] = (("buffett_quality", 0.5), ("turtle_trend", 0.5))
    band: float = 0.5
    children: dict = field(default_factory=dict)
    """Each child's own parameters, so the run hash changes if any of them does."""


class Sleeves(PortfolioStrategy):
    """Several strategies side by side, each with a fixed share of the account.

    Each child decides on its own schedule; the combination remembers every child's latest targets
    and re-emits the weighted sum whenever any child changes its mind.
    """

    def __init__(self, children: list[tuple[PortfolioStrategy, float]], name: str,
                 band: float = 0.5) -> None:
        self.children = children
        self.name = name
        self.params = SleeveParams(
            sleeves=tuple((c.name, w) for c, w in children), band=band,
            children={c.name: _params_dict(c) for c, _ in children})
        self.band = self.params.band
        super().__init__()
        self._latest: dict[str, dict[str, float]] = {}

    def targets(self, view: DataView, book: PortfolioSnapshot) -> dict[str, float] | None:
        changed = False
        for child, _ in self.children:
            wanted = child.targets(view, book)
            if wanted is not None:
                self._latest[child.name] = wanted
                changed = True
        if not changed:
            return None
        out: dict[str, float] = {}
        for child, share in self.children:
            for symbol, weight in self._latest.get(child.name, {}).items():
                out[symbol] = out.get(symbol, 0.0) + share * weight
        return out

    def diagnostics(self) -> dict:
        return {c.name: c.diagnostics() for c, _ in self.children if hasattr(c, "diagnostics")}


def _params_dict(strategy: PortfolioStrategy) -> dict:
    from dataclasses import asdict
    params = getattr(strategy, "params", None)
    return asdict(params) if params is not None else {}


__all__ = ["ALL_WEATHER", "AllWeather", "AllWeatherParams", "Sleeves", "SleeveParams",
           "TREND_ASSETS", "TrendSwitch", "TrendSwitchParams", "TurtleParams", "TurtleTrend",
           "VaaParams", "VigilantAssetAllocation", "VolTargetTrend", "VolTargetTrendV2",
           "VolTrendParams", "VolTrendV2Params"]
