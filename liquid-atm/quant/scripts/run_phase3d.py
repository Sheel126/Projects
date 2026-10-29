"""Phase 3d: the six pre-registered trials, against the same gate (lesson 03d).

    python scripts/run_phase3d.py                          # all six, nothing saved
    python scripts/run_phase3d.py --only noise_band,spy_core_noise
    python scripts/run_phase3d.py --save --json ../docs/phase3d/results.json

Data first (all free, all cached under data/cache/):

    python scripts/fetch_minutes.py SPY                    # 1-minute SPY, 2016 .. 2024-09
    python scripts/fetch_minutes.py --orb-opening --orb-days
    python -m liquid_atm_quant.data.cli insiders
    python -m liquid_atm_quant.data.cli form13f

Everything stops on 2024-09-30; the lockbox is neither downloaded nor read. The gate is lesson 03
§9's, unchanged: after-tax post-liquidation value above SPY buy-and-hold and naive momentum,
after-tax max drawdown within 20%, after-tax Calmar above SPY's. The two benchmarks are re-run
here on the same engine and window, because Phase 3d fixed how the engine handles stock splits
(lesson 03d §9) and naive momentum holds stocks that split.
"""

import argparse
import bisect
import json
import logging
import sys
import time
from dataclasses import asdict
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import psycopg  # noqa: E402

from liquid_atm_quant.backtest import metrics as m  # noqa: E402
from liquid_atm_quant.backtest import store  # noqa: E402
from liquid_atm_quant.backtest.engine import BacktestConfig, Backtester  # noqa: E402
from liquid_atm_quant.backtest.panel import Panel  # noqa: E402
from liquid_atm_quant.baselines import BuyAndHold, NaiveMomentum  # noqa: E402
from liquid_atm_quant.config import get_settings  # noqa: E402
from liquid_atm_quant.data import form13f, insiders  # noqa: E402
from liquid_atm_quant.intraday import bars, fvg, orb  # noqa: E402
from liquid_atm_quant.intraday.account import DailyBar, calendar_returns, run_account  # noqa: E402
from liquid_atm_quant.intraday.noise_band import NoiseBand, NoiseBandParams, SessionGrid  # noqa: E402
from liquid_atm_quant.investors import (PHASE3_STRATEGIES, PHASE3D_STRATEGIES,  # noqa: E402
                                        STRATEGIES, build)
from liquid_atm_quant.investors.clone13f import Clone13F, CloneParams, build_filings  # noqa: E402
from liquid_atm_quant.investors.insiders import InsiderCluster, InsiderParams, clusters  # noqa: E402
from liquid_atm_quant.strategy import LOCKBOX_START, TRIAL_BUDGET  # noqa: E402

log = logging.getLogger("run_phase3d")

START = date(2016, 1, 4)
END = LOCKBOX_START - timedelta(days=1)
WARMUP = timedelta(days=450)
OVERLAY_MAX_LEVERAGE = 2.5
"""spy_core_noise: with SPY held overnight at 1x, Alpaca's day-trading buying power is about
4 x (equity - 30% maintenance) = 2.8x; 2.5x leaves room for a margin call not to happen."""
VOL_TREND_OVERLAY_MAX_LEVERAGE = 2.0
"""vol_trend_noise: at vol_trend's 1.5x (half SPY, half SSO at 50% maintenance) the buying power
is about 4 x (1 - 0.40) = 2.4x, so the overlay is held to 2x."""


def gate(rep: dict, spy: dict, momentum: dict) -> list[tuple[str, bool, str]]:
    value, dd = rep["post_liquidation_value"], rep["after_tax"]["max_drawdown"]
    return [
        ("beats SPY after tax", value > spy["post_liquidation_value"],
         f"{value:,.0f} vs {spy['post_liquidation_value']:,.0f}"),
        ("beats naive momentum after tax", value > momentum["post_liquidation_value"],
         f"{value:,.0f} vs {momentum['post_liquidation_value']:,.0f}"),
        ("max drawdown <= 20%", dd >= -0.20, f"{dd:.1%}"),
        ("Calmar beats SPY's", rep["after_tax"]["calmar"] > spy["after_tax"]["calmar"],
         f"{rep['after_tax']['calmar']:.2f} vs {spy['after_tax']['calmar']:.2f}"),
    ]


def trials_used(conn: psycopg.Connection) -> int:
    names = (*PHASE3_STRATEGIES, *STRATEGIES, *PHASE3D_STRATEGIES)
    return sum(store.trial_count(conn, name) for name in names)


def spy_daily(panel: Panel, start: date = START) -> dict[date, DailyBar]:
    j = panel.index["SPY"]
    div = panel.dividends().get("SPY", {})
    return {s: DailyBar(float(panel.arrays["open"][t, j]), float(panel.arrays["close"][t, j]),
                        div.get(t, 0.0))
            for t, s in enumerate(panel.sessions) if s >= start}


class Runner:
    """`start`/`end` default to the in-sample window. Phase 4 passes the lockbox's, plus
    `panel_symbols` for a panel of just the ETFs: the Russell 1000 has no snapshots in the lockbox,
    and the intraday and `vol_trend` trials never read it."""

    def __init__(self, conn: psycopg.Connection, start: date = START, end: date = END,
                 panel_symbols: list[str] | None = None) -> None:
        self.conn = conn
        self.start, self.end, self.panel_symbols = start, end, panel_symbols
        self._panel: Panel | None = None
        self._grid: SessionGrid | None = None
        self._minutes = None
        self._vol_trend = None
        spy = Panel.from_db(conn, start - WARMUP, end, symbols=["SPY"])
        self.sessions = [s for s in spy.sessions if s >= start]
        self.daily = spy_daily(spy, start)

    @property
    def panel(self) -> Panel:
        if self._panel is None:
            t0 = time.time()
            if self.panel_symbols:
                self._panel = Panel.from_db(self.conn, self.start - WARMUP, self.end,
                                            symbols=self.panel_symbols)
            else:
                self._panel = Panel.from_db(self.conn, self.start - WARMUP, self.end,
                                            index_name="russell1000")
            log.info("panel %d x %d (%.0fs)", *self._panel.shape, time.time() - t0)
        return self._panel

    @property
    def grid(self) -> SessionGrid:
        if self._grid is None:
            # 90 days covers the 14-session noise area; minutes start in 2016.
            first = max(date(2016, 1, 1), self.start - timedelta(days=90))
            self._minutes = bars.load("SPY", first, self.end)
            self._grid = SessionGrid(self._minutes)
        return self._grid

    # ---- intraday trials --------------------------------------------------------------

    def noise_band(self) -> dict:
        nb = NoiseBand(self.grid, NoiseBandParams())
        result = run_account(self.sessions, self.daily, nb.day, "noise_band",
                             params={"strategy": nb.params.as_dict(), "core": False})
        result.diagnostics["strategy"] = nb.diagnostics()
        return self._intraday(result)

    def spy_core_noise(self) -> dict:
        nb = NoiseBand(self.grid, NoiseBandParams(max_leverage=OVERLAY_MAX_LEVERAGE))
        result = run_account(self.sessions, self.daily, nb.day, "spy_core_noise", core=True,
                             params={"strategy": nb.params.as_dict(), "core": True})
        result.diagnostics["strategy"] = nb.diagnostics()
        core_only = run_account(self.sessions, self.daily, None, "core_only", core=True)
        result.diagnostics["core_only_post_liquidation_value"] = core_only.post_liquidation_value
        return self._intraday(result)

    def vol_trend_noise(self, params: NoiseBandParams | None = None,
                        days: list[date] | None = None) -> dict:
        """Post-hoc (lesson 03d §10): Phase 3c's vol_trend held overnight, the Noise Band on top.

        Two books in one account, simulated as two ledgers: the engine runs vol_trend unchanged,
        and the overlay sizes each day from the *combined* after-tax equity at the prior close.
        Their capital losses are not netted against each other, which overstates tax slightly."""
        days = days or self.sessions
        if self._vol_trend is None or self._vol_trend[0] != days[0]:
            self._vol_trend = (days[0], Backtester(self.panel, BacktestConfig()).run(
                build("vol_trend", None, {}), days[0]))
        core = self._vol_trend[1]
        core_eq = core.equity["equity_after_tax"].astype(float)
        prior = core_eq.shift(1).fillna(float(BacktestConfig().initial_cash))
        nb = NoiseBand(self.grid, params or NoiseBandParams(
            max_leverage=VOL_TREND_OVERLAY_MAX_LEVERAGE))
        overlay = run_account(days, self.daily,
                              lambda day, own: nb.day(day, float(prior.get(day, 0.0)) + own),
                              "vol_trend_noise", initial_cash=0.0,
                              params={"strategy": nb.params.as_dict(), "core": "vol_trend"})
        combined = overlay.equity.copy()
        aligned = core.equity.reindex(combined.index).ffill()
        for col in ("equity", "reserve", "equity_after_tax", "tax_paid_cum"):
            combined[col] = combined[col] + aligned[col].astype(float)
        overlay.equity = combined
        overlay.post_liquidation_value += float(core.post_liquidation_value)
        overlay.diagnostics["core_post_liquidation_value"] = float(core.post_liquidation_value)
        overlay.diagnostics["strategy"] = nb.diagnostics()
        return self._intraday(overlay)

    def orb_in_play(self) -> dict:
        params = orb.OrbParams()
        picks = orb.select(orb.load_opening_bars(), self.panel, params)
        strategy = orb.OrbInPlay(picks, params)
        result = run_account(self.sessions, self.daily, strategy.day, "orb_in_play",
                             params={"strategy": params.as_dict(), "core": False})
        result.diagnostics["strategy"] = strategy.diagnostics()
        return self._intraday(result)

    def fvg_first_candle(self) -> dict:
        grid = self.grid                                  # loads the minutes as well
        highs, lows = fvg.bar_extremes(self._minutes, grid)
        strategy = fvg.FirstCandleFvg(grid, highs, lows)
        result = run_account(self.sessions, self.daily, strategy.day, "fvg_first_candle",
                             params={"strategy": asdict(strategy.params), "core": False})
        result.diagnostics["strategy"] = strategy.diagnostics()
        result.diagnostics["placebo"] = fvg.placebo(strategy)
        return self._intraday(result)

    def _intraday(self, result) -> dict:
        rep = result.report()
        rep["calendar_after_tax"] = calendar_returns(result.equity["equity_after_tax"])
        rep["_equity"] = result.equity
        rep["_params"] = result.params
        return rep

    def benchmarks(self) -> tuple[dict, dict]:
        out = []
        for strategy in (BuyAndHold("SPY"), NaiveMomentum()):
            result = Backtester(self.panel, BacktestConfig()).run(strategy, self.start)
            out.append(m.report(result))
        return out[0], out[1]

    # ---- engine trials ----------------------------------------------------------------

    def insider_cluster(self) -> dict:
        trades = insiders.load()
        cik_map = self._cik_map()
        triggers = clusters(trades[trades["filing_date"] <= self.end], cik_map, InsiderParams())
        strategy = InsiderCluster(triggers, InsiderParams())
        return self._engine(strategy)

    def clone_13f(self) -> dict:
        holdings = form13f.load()
        holdings = holdings[holdings["filing_date"] <= self.end]
        panel = self.panel
        close = panel.column("close")
        periods = sorted(set(holdings["period"]))
        closes = {}
        for q in periods:
            t = bisect.bisect_right(panel.sessions, q) - 1
            if t < 0:
                continue
            row = close[t]
            closes[q] = {s: float(row[j]) for j, s in enumerate(panel.symbols)
                         if row[j] == row[j] and row[j] > 0}
        names = self._names()
        cusip_map = form13f.match_cusips(holdings, closes, names)
        log.info("13F: %d of %d CUSIPs matched", len(cusip_map), holdings["cusip"].nunique())
        filings = build_filings(holdings, cusip_map)
        strategy = Clone13F(filings, panel, CloneParams())
        rep = self._engine(strategy)
        rep["diagnostics"]["cusips_matched"] = len(cusip_map)
        return rep

    def _engine(self, strategy) -> dict:
        result = Backtester(self.panel, BacktestConfig()).run(strategy, self.start)
        rep = m.report(result)
        rep["calendar_after_tax"] = calendar_returns(result.equity["equity_after_tax"])
        rep["_result"] = result
        return rep

    def _cik_map(self) -> dict[str, list[str]]:
        with self.conn.cursor() as cur:
            cur.execute("SELECT cik, symbol FROM instruments WHERE cik IS NOT NULL ORDER BY symbol")
            out: dict[str, list[str]] = {}
            for cik, symbol in cur.fetchall():
                out.setdefault(cik.zfill(10), []).append(symbol)
        return out

    def _names(self) -> dict[str, str]:
        with self.conn.cursor() as cur:
            cur.execute("SELECT symbol, name FROM instruments WHERE name IS NOT NULL")
            return dict(cur.fetchall())


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--only", help="comma-separated subset of: " + ", ".join(PHASE3D_STRATEGIES))
    parser.add_argument("--save", action="store_true")
    parser.add_argument("--label", default="phase3d")
    parser.add_argument("--json", type=Path)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    names = args.only.split(",") if args.only else list(PHASE3D_STRATEGIES)
    unknown = set(names) - set(PHASE3D_STRATEGIES)
    if unknown:
        parser.error(f"unknown strategies: {sorted(unknown)}")

    conn = psycopg.connect(get_settings().database_url, connect_timeout=5)
    reports = {}
    with conn:
        runner = Runner(conn)
        spy, momentum = runner.benchmarks()
        for name in names:
            t0 = time.time()
            reports[name] = getattr(runner, name)()
            log.info("%s done in %.0fs", name, time.time() - t0)
        if args.save:
            for name in names:
                rep = reports[name]
                if "_result" in rep:
                    run_id = store.save(conn, rep["_result"], label=args.label)
                else:
                    run_id = store.save_report(conn, name, rep["_params"], _public(rep),
                                               rep["_equity"], label=args.label)
                log.info("saved run %d (%s)", run_id, name)
            conn.commit()
        used = trials_used(conn)

    header = (f"{'strategy':<18} {'after-tax value':>15} {'CAGR':>7} {'maxDD':>7} {'Calmar':>7} "
              f"{'Sharpe':>7}  gate")
    print("\n" + header + "\n" + "-" * len(header))
    for label, rep in (("buy_and_hold_spy", spy), ("naive_momentum", momentum), *reports.items()):
        at = rep["after_tax"]
        checks = gate(rep, spy, momentum) if label in reports else []
        verdict = ("PASS" if all(ok for _, ok, _ in checks) else
                   f"fail {sum(not ok for _, ok, _ in checks)}/4") if checks else "(baseline)"
        print(f"{label:<18} {rep['post_liquidation_value']:>15,.0f} {at['cagr']:>7.2%} "
              f"{at['max_drawdown']:>7.1%} {at['calmar']:>7.2f} {at['sharpe']:>7.2f}  {verdict}")
    for name, rep in reports.items():
        print(f"\n=== {name}")
        for label, ok, detail in gate(rep, spy, momentum):
            print(f"  {'PASS' if ok else 'FAIL'}  {label:<32} {detail}")
        years = "  ".join(f"{y}: {r:+.1%}" for y, r in rep["calendar_after_tax"].items())
        print(f"  after-tax by year: {years}")
        diag = rep.get("diagnostics", {})
        print(f"  diagnostics: {json.dumps(_brief(diag), default=str)[:1500]}")
    print(f"\ntrials used: {used}/{TRIAL_BUDGET}"
          + ("" if args.save else " (not saved; pass --save to count these runs)"))

    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        payload = {name: {**_public(rep), "equity_after_tax": _curve(rep)}
                   for name, rep in reports.items()}
        args.json.write_text(json.dumps(store._finite(payload), indent=1, default=str))
        log.info("wrote %s", args.json)
    return 0


def _public(rep: dict) -> dict:
    return {k: v for k, v in rep.items() if not k.startswith("_")}


def _curve(rep: dict) -> dict:
    equity = rep["_result"].equity if "_result" in rep else rep["_equity"]
    return {str(d): float(v) for d, v in equity["equity_after_tax"].items()}


def _brief(diag: dict) -> dict:
    out = dict(diag.get("strategy", {}) or {})
    for key in ("placebo", "core_only_post_liquidation_value", "overlay_pnl_total",
                "margin_interest", "core_post_liquidation_value",
                "terminal_tax", "wash_sales", "cusips_matched"):
        if key in diag:
            out[key] = diag[key]
    out.pop("rebalances", None)
    return out


if __name__ == "__main__":
    sys.exit(main())
