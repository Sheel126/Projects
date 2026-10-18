"""`MomentumFunnel`: regime → screener → (veto) → book → bracket intents (lesson 03).

The one strategy object used both inside the backtester and by `scripts/screen_today.py`, so there
is no second "live" screener to drift away from the tested one (§8).

The veto hook is where Phase 5's local-LLM catalyst gate goes. It takes a candidate and the
decision date and returns a reason string to reject it, or None to let it through.
"""

from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date

from liquid_atm_quant.backtest.panel import DataView, Panel
from liquid_atm_quant.backtest.strategy import BracketIntent, PortfolioSnapshot
from liquid_atm_quant.strategy import book as book_mod
from liquid_atm_quant.strategy.indicators import Indicators
from liquid_atm_quant.strategy.params import SECTOR_ETFS, FunnelParams
from liquid_atm_quant.strategy.regime import RegimeFilter, RegimeReading
from liquid_atm_quant.strategy.screener import STAGES, Candidate, Screener, ScreenResult

Veto = Callable[[Candidate, date], str | None]


@dataclass
class Decision:
    """Everything the funnel decided at one close: what `screen_today.py` prints."""

    as_of: date
    regime: RegimeReading
    screen: ScreenResult
    vetoed: dict[str, str]
    book: book_mod.BookResult

    @property
    def intents(self) -> list[BracketIntent]:
        return self.book.intents


@dataclass
class MomentumFunnel:
    params: FunnelParams = field(default_factory=FunnelParams)
    sectors: dict[str, str] = field(default_factory=dict)
    veto: Veto | None = None
    name: str = "momentum_funnel"

    def __post_init__(self) -> None:
        self._panel: Panel | None = None
        self._stats = {"sessions": 0, "regime_days": Counter(), "stage_totals": Counter(),
                       "sessions_screened": 0, "candidates": 0, "vetoed": 0, "intents": 0,
                       "sessions_with_intents": 0, "skipped": Counter()}

    # ---- the Strategy protocol -------------------------------------------------------

    def on_close(self, view: DataView, book: PortfolioSnapshot) -> list[BracketIntent]:
        return self.decide(view, book).intents

    def decide(self, view: DataView, book: PortfolioSnapshot) -> Decision:
        self._bind(view.panel)
        t = view.t
        reading = self._regime.at(t)

        held = {s for s, q in book.positions.items() if q > 0}
        screen = self._screener.screen(t, exclude=held | set(book.blacklist))
        candidates, vetoed = screen.candidates, {}
        if self.veto is not None and reading.state.value != "risk_off":
            kept = []
            for c in candidates:
                why = self.veto(c, view.today)
                if why:
                    vetoed[c.symbol] = why
                else:
                    kept.append(c)
            candidates = kept

        index = view.panel.index
        marks = {s: float(self._ind.close[t, index[s]]) for s in held if s in index}
        built = book_mod.build(candidates, book, reading.state, marks, self._screener.sectors,
                               self.params)
        self._record(reading, screen, vetoed, built)
        return Decision(view.today, reading, screen, vetoed, built)

    # ---- reporting -------------------------------------------------------------------

    def diagnostics(self) -> dict:
        """Merged into the run's diagnostics by the engine: the funnel's shape over the run."""
        s = self._stats
        screened = s["sessions_screened"] or 1
        return {
            "sessions": s["sessions"],
            "regime_days": dict(s["regime_days"]),
            "avg_per_stage": {k: round(s["stage_totals"][k] / screened, 2) for k in STAGES},
            "candidates": s["candidates"],
            "vetoed": s["vetoed"],
            "intents": s["intents"],
            "sessions_with_intents": s["sessions_with_intents"],
            "book_skips": dict(s["skipped"]),
        }

    # ---- internals -------------------------------------------------------------------

    def _bind(self, panel: Panel) -> None:
        """Build (or fetch the cached) matrices once per panel, never once per session."""
        if self._panel is panel:
            return
        self._panel = panel
        self._ind = Indicators.for_panel(panel, self.params)
        self._regime = RegimeFilter(self._ind, self.params)
        etfs = SECTOR_ETFS if self.params.include_sector_etfs else {}
        self._screener = Screener(self._ind, panel.symbols, panel.member, self.params,
                                  self.sectors, {k: v for k, v in etfs.items() if k in panel.index})

    def _record(self, reading, screen: ScreenResult, vetoed: dict, built) -> None:
        s = self._stats
        s["sessions"] += 1
        s["regime_days"][reading.state.value] += 1
        if reading.state.value != "risk_off":
            s["sessions_screened"] += 1
            s["stage_totals"].update(screen.counts)
            s["candidates"] += len(screen.candidates)
        s["vetoed"] += len(vetoed)
        s["intents"] += len(built.intents)
        s["sessions_with_intents"] += bool(built.intents)
        s["skipped"].update({k: v for k, v in built.skipped.items() if v})
