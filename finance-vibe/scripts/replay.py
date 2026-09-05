"""Replay stored cycles through the live decision code to measure a config change.

Every cycle the bot ran is persisted in `cycles.context_json` with the full
per-ticker snapshot it saw. This walks those snapshots back through the real
`_pick_buys` / `should_quick_sell` and prices the resulting trades against a
capital-constrained portfolio, so a proposed change can be measured instead of
guessed at.

Faithfulness notes:
  - Entry/exit prices are the snapshot prices the bot actually saw that cycle,
    not minute bars, so there is no lookahead and no optimistic intra-bar fill.
  - `in_position` / `open_positions` are rewritten to the simulated portfolio,
    never the historical one, otherwise the gates read stale state.
  - The EOD flatten uses the 15:55 minute bar, since cycles stop before it.

Usage:
  python scripts/replay.py
  python scripts/replay.py --start 2026-08-31 --end 2026-09-01
  python scripts/replay.py --set QUICK_PROFIT_PCT=1.5 --set MAX_POSITIONS=6
  python scripts/replay.py --exit fixed:1.2/1.8 --label baseline
  python scripts/replay.py --holdout 2026-09-02
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

_lp = Path(__file__).resolve().parent.parent / "src" / "finance_vibe" / "bot" / "_load_path.py"
_spec = importlib.util.spec_from_file_location("fv_load_path", _lp)
_mod = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
_spec.loader.exec_module(_mod)

import argparse
import json
import random
import sqlite3
from datetime import date, datetime, time as dtime
from typing import Any, Callable
from zoneinfo import ZoneInfo

from finance_vibe.bot import config
from finance_vibe.bot.daily_activity import (
    _buy_eligible,
    _pick_buys,
    compute_active_score,
    should_quick_sell,
)
from finance_vibe.bot.models import CycleContext, TickerSnapshot

ET = ZoneInfo("America/New_York")
EOD = dtime(15, 55)
_rng = random.Random()

SNAPSHOT_FIELDS = set(TickerSnapshot.__dataclass_fields__)


# --------------------------------------------------------------------------
# loading


def load_cycles(start: date | None, end: date | None) -> list[tuple[datetime, dict]]:
    conn = sqlite3.connect(str(config.BOT_DB_PATH))
    out: list[tuple[datetime, dict]] = []
    for created, raw in conn.execute(
        "SELECT created_at, context_json FROM cycles "
        "WHERE context_json IS NOT NULL ORDER BY created_at"
    ):
        try:
            ts = datetime.fromisoformat(created)
        except ValueError:
            continue
        ts = ts.astimezone(ET)
        if ts.weekday() >= 5:        # weekend setup cycles are not trading days
            continue
        if start and ts.date() < start:
            continue
        if end and ts.date() > end:
            continue
        try:
            out.append((ts, json.loads(raw)))
        except json.JSONDecodeError:
            continue
    conn.close()
    return out


def to_snapshot(d: dict[str, Any]) -> TickerSnapshot | None:
    """Rebuild a snapshot, tolerating older rows that predate newer fields."""
    if not d.get("ticker") or not d.get("price"):
        return None
    kwargs = {k: v for k, v in d.items() if k in SNAPSHOT_FIELDS}
    kwargs.setdefault("change_pct", 0.0)
    kwargs.setdefault("change_from_open_pct", 0.0)
    for k in ("rsi", "ema20", "ema50", "atr", "setup_type", "setup_notes",
              "entry", "stop", "target1", "target2", "vs_qqq_pct", "regime_ok"):
        kwargs.setdefault(k, None)
    try:
        return TickerSnapshot(**kwargs)
    except TypeError:
        return None


def eod_prices(symbols: set[str], days: set[date]) -> dict[tuple[str, date], float]:
    """15:55 close per symbol per day, for the forced flatten."""
    if not symbols or not days:
        return {}
    from finance_vibe.bot.alpaca_client import AlpacaClient
    from alpaca.data.requests import StockBarsRequest
    from alpaca.data.timeframe import TimeFrame, TimeFrameUnit

    client = AlpacaClient()
    if not client.configured:
        return {}
    client._ensure_clients()
    lo, hi = min(days), max(days)
    try:
        res = client._data.get_stock_bars(StockBarsRequest(
            symbol_or_symbols=sorted(symbols),
            timeframe=TimeFrame(amount=1, unit=TimeFrameUnit.Minute),
            start=datetime.combine(lo, dtime(9, 0), tzinfo=ET),
            end=datetime.combine(hi, dtime(20, 0), tzinfo=ET),
            feed="iex",
        ))
    except Exception as exc:  # pragma: no cover - network
        print(f"  (warning: could not load EOD bars: {exc})")
        return {}

    out: dict[tuple[str, date], float] = {}
    for sym in symbols:
        for bar in res.data.get(sym, []):
            t = bar.timestamp.astimezone(ET)
            if t.time() <= EOD:
                out[(sym, t.date())] = float(bar.close)
    return out


# --------------------------------------------------------------------------
# exit rules


def exit_from_config(snap: TickerSnapshot) -> tuple[bool, str]:
    ok, reason, _ = should_quick_sell(snap)
    return ok, reason


def fixed_exit(tp: float, sl: float) -> Callable[[TickerSnapshot], tuple[bool, str]]:
    def rule(snap: TickerSnapshot) -> tuple[bool, str]:
        pnl = snap.position_pnl_pct or 0.0
        if pnl >= tp:
            return True, f"tp {pnl:.2f}%"
        if pnl <= -sl:
            return True, f"sl {pnl:.2f}%"
        return False, ""
    return rule


def atr_exit(mult: float) -> Callable[[TickerSnapshot], tuple[bool, str]]:
    def rule(snap: TickerSnapshot) -> tuple[bool, str]:
        pnl = snap.position_pnl_pct or 0.0
        if not snap.atr or snap.price <= 0:
            return False, ""
        band = min(max(mult * (snap.atr / snap.price * 100), 0.6), 4.0)
        if pnl >= band:
            return True, f"tp {pnl:.2f}% (band {band:.2f})"
        if pnl <= -band:
            return True, f"sl {pnl:.2f}% (band {band:.2f})"
        return False, ""
    return rule


# --------------------------------------------------------------------------
# simulation


class Portfolio:
    def __init__(self, equity: float) -> None:
        self.equity = equity
        self.positions: dict[str, tuple[float, int]] = {}   # sym -> (entry, qty)
        self.trades: list[dict[str, Any]] = []

    def value_at(self, prices: dict[str, float]) -> float:
        held = sum(
            (prices.get(s, e) - e) * q for s, (e, q) in self.positions.items()
        )
        return self.equity + held

    def buy(self, sym: str, price: float, pct: float) -> bool:
        qty = int(self.equity * pct / 100 / price)
        if qty < 1:
            return False
        self.positions[sym] = (price, qty)
        return True

    def sell(self, sym: str, price: float, reason: str, when: datetime) -> None:
        entry, qty = self.positions.pop(sym)
        pnl = (price - entry) * qty
        self.equity += pnl
        self.trades.append({
            "ticker": sym, "entry": entry, "exit": price, "qty": qty,
            "pnl": pnl, "pnl_pct": (price / entry - 1) * 100,
            "reason": reason, "closed_at": when,
        })


def replay(
    cycles: list[tuple[datetime, dict]],
    exit_rule: Callable[[TickerSnapshot], tuple[bool, str]],
    start_equity: float = 100_000.0,
    rank: str = "score",
    restrict_watchlist: bool = True,
) -> dict[str, Any]:
    # Older cycles were recorded against a different watchlist (IWM, MARA, BAC,
    # SOXL, JPM). Replaying those inflates the result with trades the live bot
    # can no longer take, so by default only the configured tickers count.
    allowed = {t.upper() for t in config.WATCHLIST} if restrict_watchlist else None

    by_day: dict[date, list[tuple[datetime, dict]]] = {}
    for ts, ctx in cycles:
        by_day.setdefault(ts.date(), []).append((ts, ctx))

    symbols = {
        s["ticker"] for _, ctx in cycles for s in ctx.get("watchlist", [])
        if s.get("ticker") and (allowed is None or s["ticker"].upper() in allowed)
    }
    closes = eod_prices(symbols, set(by_day))

    pf = Portfolio(start_equity)
    daily: list[dict[str, Any]] = []
    exposure_samples: list[float] = []

    for day in sorted(by_day):
        day_start = pf.equity
        for ts, ctx in sorted(by_day[day]):
            snaps = [s for s in (to_snapshot(d) for d in ctx.get("watchlist", [])) if s]
            if allowed is not None:
                snaps = [s for s in snaps if s.ticker.upper() in allowed]
            if not snaps:
                continue
            prices = {s.ticker: s.price for s in snaps}

            # portfolio state overrides whatever was historically true
            for s in snaps:
                if s.ticker in pf.positions:
                    entry, qty = pf.positions[s.ticker]
                    s.in_position = True
                    s.position_qty = qty
                    s.position_pnl_pct = (s.price / entry - 1) * 100
                else:
                    s.in_position = False
                    s.position_qty = 0.0
                    s.position_pnl_pct = None
                s.has_open_buy_order = False
                s.has_open_sell_order = False
                if not s.active_score:
                    s.active_score = compute_active_score(s)

            # 1) exits
            for s in snaps:
                if s.ticker in pf.positions:
                    do_sell, reason = exit_rule(s)
                    if do_sell:
                        pf.sell(s.ticker, s.price, reason, ts)

            equity_now = pf.value_at(prices)
            day_pnl_pct = (equity_now / day_start - 1) * 100
            exposure_samples.append(
                sum(q * prices.get(sym, e) for sym, (e, q) in pf.positions.items())
                / equity_now * 100 if equity_now else 0.0
            )

            # 2) entry gating that lives in the runner, not in _pick_buys
            bench = ctx.get("benchmark_change_from_open_pct")
            blocked = (
                ts.time() >= dtime(config.LATE_ENTRY_HOUR, config.LATE_ENTRY_MINUTE)
                or ts.time() >= EOD
                or day_pnl_pct <= config.DAY_BLOCK_BUYS_PCT
                or (bench is not None and bench <= config.BENCHMARK_BLOCK_PCT)
            )
            if blocked or len(pf.positions) >= config.MAX_POSITIONS:
                continue

            sim_ctx = CycleContext(
                account_equity=equity_now,
                account_cash=pf.equity,
                buying_power=equity_now,
                day_pnl_pct=day_pnl_pct,
                halted=False,
                watchlist=snaps,
                open_positions=[{"symbol": s} for s in pf.positions],
                strategy_notes="replay",
                benchmark_change_from_open_pct=bench,
                market_regime=ctx.get("market_regime", {}),
                entries_blocked=False,
            )

            room = config.MAX_POSITIONS - len(pf.positions)
            n = min(config.ACTIVE_MAX_BUYS_PER_CYCLE, room)

            if rank == "score":
                picks = _pick_buys(snaps, sim_ctx, len(pf.positions), n)
            elif rank == "shuffle":
                # Same gates, random order: isolates whether *ranking* adds value,
                # which is the only thing the LLM can influence.
                elig = [s for s in snaps
                        if _buy_eligible(s, sim_ctx, len(pf.positions))]
                _rng.shuffle(elig)
                picks = elig[:n]
            else:
                # No gates at all: isolates whether *selection* adds value.
                cands = [s for s in snaps if not s.in_position]
                _rng.shuffle(cands)
                picks = cands[:n]

            for snap in picks:
                if snap.ticker in pf.positions:
                    continue
                pf.buy(snap.ticker, snap.price, config.ACTIVE_POSITION_PCT)

        # 3) forced flatten at 15:55
        for sym in list(pf.positions):
            price = closes.get((sym, day))
            if price is None:
                price = pf.positions[sym][0]
            pf.sell(sym, price, "EOD flat", datetime.combine(day, EOD, tzinfo=ET))

        daily.append({
            "day": day,
            "start": day_start,
            "end": pf.equity,
            "pct": (pf.equity / day_start - 1) * 100,
        })

    wins = [t for t in pf.trades if t["pnl"] > 0]
    peak = start_equity
    max_dd = 0.0
    for d in daily:
        peak = max(peak, d["end"])
        max_dd = min(max_dd, (d["end"] / peak - 1) * 100)

    return {
        "daily": daily,
        "trades": pf.trades,
        "final_equity": pf.equity,
        "total_pct": (pf.equity / start_equity - 1) * 100,
        "green_days": sum(1 for d in daily if d["pct"] > 0),
        "n_days": len(daily),
        "n_trades": len(pf.trades),
        "win_rate": len(wins) / len(pf.trades) * 100 if pf.trades else 0.0,
        "trades_per_day": len(pf.trades) / len(daily) if daily else 0.0,
        "max_drawdown": max_dd,
        "avg_exposure": sum(exposure_samples) / len(exposure_samples)
        if exposure_samples else 0.0,
    }


def report(label: str, res: dict[str, Any], verbose: bool = False) -> None:
    print(f"\n=== {label} ===")
    for d in res["daily"]:
        print(f"   {d['day']}  ${d['start']:>10,.0f} -> ${d['end']:>10,.0f}   {d['pct']:+6.2f}%")
    print(
        f"   total {res['total_pct']:+.2f}%   green {res['green_days']}/{res['n_days']}"
        f"   trades {res['n_trades']} ({res['trades_per_day']:.1f}/day)"
        f"   win {res['win_rate']:.0f}%"
    )
    print(
        f"   max drawdown {res['max_drawdown']:.2f}%   avg capital deployed "
        f"{res['avg_exposure']:.0f}%"
    )
    if verbose:
        for t in res["trades"]:
            print(
                f"      {t['closed_at']:%m-%d %H:%M} {t['ticker']:5} "
                f"{t['pnl_pct']:+6.2f}%  ${t['pnl']:+8,.0f}  {t['reason']}"
            )


def parse_exit(spec: str | None) -> Callable[[TickerSnapshot], tuple[bool, str]]:
    if not spec:
        return exit_from_config
    if spec.startswith("fixed:"):
        tp, sl = spec.split(":", 1)[1].split("/")
        return fixed_exit(float(tp), float(sl))
    if spec.startswith("atr:"):
        return atr_exit(float(spec.split(":", 1)[1]))
    raise SystemExit(f"bad --exit {spec!r}; use fixed:1.2/1.8 or atr:0.5")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Replay stored cycles under a config")
    p.add_argument("--start", type=date.fromisoformat)
    p.add_argument("--end", type=date.fromisoformat)
    p.add_argument("--holdout", type=date.fromisoformat,
                   help="split: everything before this is in-sample, rest is holdout")
    p.add_argument("--set", action="append", default=[], metavar="KEY=VALUE",
                   help="override a config value for this run")
    p.add_argument("--exit", dest="exit_spec",
                   help="fixed:TP/SL or atr:MULT (default: live should_quick_sell)")
    p.add_argument("--rank", default="score", choices=["score", "shuffle", "nogates"],
                   help="score=live logic, shuffle=same gates in random order, "
                        "nogates=random from the whole watchlist")
    p.add_argument("--seed", type=int, help="seed the random arms for reproducibility")
    p.add_argument("--repeat", type=int, default=1,
                   help="run N times and report the spread (for the random arms)")
    p.add_argument("--label", default="replay")
    p.add_argument("--equity", type=float, default=100_000.0)
    p.add_argument("--verbose", action="store_true", help="list every trade")
    p.add_argument("--all-tickers", action="store_true",
                   help="include tickers from retired watchlists (inflates results)")
    p.add_argument("--json", action="store_true")
    args = p.parse_args(argv)
    keep = not args.all_tickers

    for override in args.set:
        key, _, raw = override.partition("=")
        key = key.strip()
        if not hasattr(config, key):
            raise SystemExit(f"unknown config key: {key}")
        current = getattr(config, key)
        if isinstance(current, bool):
            value: Any = raw.strip().lower() in ("1", "true", "yes")
        elif isinstance(current, int):
            value = int(raw)
        elif isinstance(current, float):
            value = float(raw)
        else:
            value = raw
        setattr(config, key, value)
        print(f"config override: {key} = {value}")

    rule = parse_exit(args.exit_spec)
    cycles = load_cycles(args.start, args.end)
    if not cycles:
        raise SystemExit("no stored cycles in that range")

    if args.holdout:
        ins = [c for c in cycles if c[0].date() < args.holdout]
        out = [c for c in cycles if c[0].date() >= args.holdout]
        if not ins or not out:
            raise SystemExit("holdout split leaves one side empty")
        a = replay(ins, rule, args.equity, args.rank, keep)
        b = replay(out, rule, args.equity, args.rank, keep)
        report(f"{args.label} [in-sample]", a, args.verbose)
        report(f"{args.label} [HOLDOUT]", b, args.verbose)
        print(
            f"\n   in-sample {a['total_pct']:+.2f}% vs holdout {b['total_pct']:+.2f}%"
            "  <- a large gap means the config is fitted to the in-sample days"
        )
        if args.json:
            print(json.dumps({"in_sample": a, "holdout": b}, indent=2, default=str))
        return 0

    if args.repeat > 1:
        totals = []
        for i in range(args.repeat):
            _rng.seed((args.seed or 0) + i)
            r = replay(cycles, rule, args.equity, args.rank, keep)
            totals.append(r["total_pct"])
            print(f"   run {i + 1:2}: {r['total_pct']:+.2f}%  "
                  f"{r['n_trades']} trades  win {r['win_rate']:.0f}%")
        mean = sum(totals) / len(totals)
        print(
            f"\n=== {args.label} over {args.repeat} runs ===\n"
            f"   mean {mean:+.2f}%   range {min(totals):+.2f}% to {max(totals):+.2f}%"
        )
        return 0

    if args.seed is not None:
        _rng.seed(args.seed)
    res = replay(cycles, rule, args.equity, args.rank, keep)
    report(args.label, res, args.verbose)
    if args.json:
        print(json.dumps(res, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
