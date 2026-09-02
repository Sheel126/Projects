"""Trading cycle orchestration and CLI scheduler."""
from __future__ import annotations

import importlib.util
from pathlib import Path

_lp = Path(__file__).resolve().parent / "_load_path.py"
_spec = importlib.util.spec_from_file_location("fv_load_path", _lp)
_mod = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
_spec.loader.exec_module(_mod)

import argparse
import json
import logging
import sys
import time
from datetime import date

from finance_vibe.bot import config
from finance_vibe.bot.alpaca_client import AlpacaClient
from finance_vibe.bot.executor import Executor
from finance_vibe.bot.signal_engine import SignalEngine
from finance_vibe.bot.daily_activity import build_eod_flatten_decision
from finance_vibe.bot.market_hours import (
    is_eod_flat_window,
    is_eod_window,
    is_late_entry_window,
    is_market_open,
    is_premarket_plan_window,
    is_weekday,
    next_daemon_wakeup,
    next_weekday_open,
    now_et,
    seconds_until,
    should_preemptive_eod_flatten,
)
from finance_vibe.bot.models import AgentDecision, CycleContext, TradeAction
from finance_vibe.bot.ollama_agent import OllamaAgent
from finance_vibe.bot.regime import benchmark_blocks_new_buys, regime_summary
from finance_vibe.bot.risk_guard import RiskGuard
from finance_vibe.bot.session import prepare_clean_session
from finance_vibe.bot.store import BotStore

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger("bot.runner")


class TradingRunner:
    def __init__(self) -> None:
        config.ensure_dirs()
        self.store = BotStore()
        self.alpaca = AlpacaClient()
        self.indicators = SignalEngine(self.alpaca)
        self.agent = OllamaAgent()
        self.risk = RiskGuard()
        self.executor = Executor(self.alpaca, self.store)
        self.store.set_runner_status(trading_mode=config.TRADING_MODE)
        self.store.log_activity(
            f"Runner initialized | mode={config.TRADING_MODE} | "
            f"watchlist={len(config.WATCHLIST)} tickers | max_pos={config.MAX_POSITIONS}",
            phase="init",
        )

    def _log(
        self,
        message: str,
        phase: str,
        cycle_id: int | None = None,
        level: str = "info",
    ) -> None:
        self.store.log_activity(message, level=level, phase=phase, cycle_id=cycle_id)
        logger.info("[%s] %s", phase, message)

    def _cancel_late_session_buys(self, cycle_id: int | None = None) -> None:
        """After 3:30 PM cancel stale limit buys so they cannot fill late."""
        if not is_late_entry_window():
            return
        try:
            n = self.alpaca.cancel_open_buy_orders()
            if n:
                self._log(f"Cancelled {n} stale BUY orders (late session)", "risk", cycle_id)
        except Exception as exc:
            logger.warning("Late-session buy cancel failed: %s", exc)

    def _build_context(
        self,
        account: dict,
        positions: list,
        open_orders: list,
        day_start: float,
        halted: bool,
        entries_blocked: bool,
        bench: dict,
        market_regime: dict,
        watchlist: list,
        conviction_ranking: list,
        day_pnl_pct: float,
    ) -> CycleContext:
        bench_open = bench.get("change_from_open_pct")
        regime_blocked = benchmark_blocks_new_buys(bench_open)
        if regime_blocked:
            entries_blocked = True

        return CycleContext(
            account_equity=account["equity"],
            account_cash=account["cash"],
            buying_power=account["buying_power"],
            day_pnl_pct=day_pnl_pct,
            halted=halted,
            watchlist=watchlist,
            open_positions=positions,
            strategy_notes=config.STRATEGY_NOTES,
            benchmark_change_pct=bench.get("change_pct"),
            benchmark_change_from_open_pct=bench_open,
            open_orders=open_orders,
            market_regime=market_regime,
            conviction_ranking=conviction_ranking,
            trading_mode=config.TRADING_MODE,
            entries_blocked=entries_blocked,
        )

    def run_cycle(self, force: bool = False) -> dict:
        self.store.set_runner_status(heartbeat=True)
        today = now_et().date()
        if not force and not is_market_open() and not is_premarket_plan_window():
            msg = "Market closed — skipping cycle"
            logger.info(msg)
            return {"status": "skipped", "reason": msg}

        if not self.alpaca.configured:
            raise RuntimeError("Alpaca not configured. See user.md")

        account = self.alpaca.get_account()
        positions = self.alpaca.get_positions()
        equity = account["equity"]
        cash = account["cash"]

        day_start = self.store.get_day_start_equity(today)
        if day_start is None:
            self.store.set_day_start_equity(today, equity)
            day_start = equity

        halted_flag = self.store.is_halted_today(today)
        halted, day_pnl_pct = self.risk.check_daily_halt(day_start, equity)
        if halted and not halted_flag:
            self.store.set_halted_today(today, True)
            logger.warning("Daily loss halt triggered at %.2f%%", day_pnl_pct)
        halted = halted or halted_flag

        entries_blocked = (
            self.store.get_state(f"entries_blocked_{today.isoformat()}") == "1"
            or is_eod_flat_window()
            or is_late_entry_window()
        )

        open_orders = []
        try:
            open_orders = self.alpaca.get_open_orders()
        except Exception as exc:
            logger.warning("Could not fetch open orders: %s", exc)

        self._cancel_late_session_buys()

        try:
            if open_orders:
                self.alpaca.cancel_all_orders()
                time.sleep(1.5)
                self._log(
                    f"Cancelled {len(open_orders)} stale open orders before cycle",
                    "trade",
                )
                open_orders = []
        except Exception as exc:
            logger.warning("Pre-cycle order cancel failed: %s", exc)

        watchlist = self.indicators.build_watchlist(
            config.WATCHLIST, positions, open_orders,
        )
        snap_map = {s.ticker: s for s in watchlist}

        prices = self.alpaca.get_latest_prices(
            list({*config.WATCHLIST, self.indicators.benchmark})
        )
        bench = prices.get(config.BENCHMARK, {})
        market_regime = self.indicators.build_market_regime(bench)
        conviction_ranking = SignalEngine.conviction_ranking(watchlist)

        ctx = self._build_context(
            account, positions, open_orders, day_start, halted,
            entries_blocked, bench, market_regime, watchlist,
            conviction_ranking, day_pnl_pct,
        )

        cycle_id = self.store.start_cycle(ctx.to_prompt_dict())
        self._log(
            f"Cycle {cycle_id} started | equity=${equity:,.2f} | day P&L {day_pnl_pct:.2f}%",
            "cycle", cycle_id,
        )

        regime_note = regime_summary(ctx.benchmark_change_from_open_pct, ctx.entries_blocked)
        if regime_note:
            self._log(f"Regime gate: {regime_note}", "risk", cycle_id)

        try:
            retried = self.executor.retry_pending_sells(positions, cycle_id)
            if retried:
                self._log(f"Retried {retried} pending sell(s)", "trade", cycle_id)
                positions = self.alpaca.get_positions()
                ctx.open_positions = positions

            preemptive_eod = (
                should_preemptive_eod_flatten(now_et(), config.CYCLE_MINUTES)
                and positions
                and config.TRADING_MODE == "daily_active"
            )

            if is_eod_flat_window() and config.TRADING_MODE == "daily_active":
                self.store.set_state(f"entries_blocked_{today.isoformat()}", "1")
                ctx.entries_blocked = True
                eod = build_eod_flatten_decision(ctx)
                if eod:
                    self._log("EOD flat window — closing all positions", "eod", cycle_id)
                    decision = eod
                else:
                    self._log(
                        "EOD flat window — flat; no new entries until next open",
                        "eod", cycle_id,
                    )
                    decision = AgentDecision(
                        actions=[
                            TradeAction(t.ticker, "HOLD", reason="EOD — entries closed")
                            for t in ctx.watchlist
                        ],
                        summary="EOD flat — session closed for new entries",
                        used_fallback=True,
                        model="eod_flat",
                    )
            elif preemptive_eod:
                self._log(
                    "Pre-emptive EOD flatten — last cycle before flat window",
                    "eod", cycle_id,
                )
                self.store.set_state(f"entries_blocked_{today.isoformat()}", "1")
                ctx.entries_blocked = True
                eod = build_eod_flatten_decision(ctx)
                decision = eod or AgentDecision(
                    actions=[TradeAction(t.ticker, "HOLD") for t in ctx.watchlist],
                    summary="Pre-emptive EOD — flat",
                    used_fallback=True,
                    model="eod_preempt",
                )
            elif ctx.entries_blocked:
                self._log("Entries blocked — sells/holds only", "risk", cycle_id)
                decision = self.agent.decide(ctx)
            else:
                self._log(
                    f"Evaluating {len(watchlist)} tickers (signals + intraday)",
                    "signals", cycle_id,
                )
                self._log("Consulting Ollama decision engine", "llm", cycle_id)
                decision = self.agent.decide(ctx)

            self._log(f"Decision: {decision.summary}", "decision", cycle_id)
            open_count = len(positions)
            orders_placed = 0

            # SELLs first (one at a time) — avoids held_for_orders when flattening
            sorted_actions = sorted(
                decision.actions,
                key=lambda a: {"SELL": 0, "BUY": 1, "HOLD": 2}.get(a.normalized_action(), 3),
            )

            for action in sorted_actions:
                snap = snap_map.get(action.ticker)
                act = action.normalized_action()
                if act in ("BUY", "SELL"):
                    self._log(
                        f"Risk check {action.ticker} {act} {action.pct:.0f}%",
                        "risk", cycle_id,
                    )
                risk = self.risk.validate(action, ctx, snap, open_count)
                dec_id = self.store.save_decision(
                    cycle_id, action.ticker, action.normalized_action(),
                    action.pct, action.stop, action.reason,
                    risk.approved, risk.notes, risk.qty, risk.notional,
                )
                if risk.approved and risk.action.normalized_action() in ("BUY", "SELL"):
                    self._log(
                        f"Placing {act} {action.ticker} qty={risk.qty:.2f} "
                        f"(${risk.notional:.0f})",
                        "trade", cycle_id,
                    )
                    price = snap.price if snap else 0.0
                    order = self.executor.execute(risk, cycle_id, dec_id, price)
                    if order:
                        orders_placed += 1
                        self._log(
                            f"Order submitted {act} {action.ticker} "
                            f"status={order.get('status', '?')}",
                            "trade", cycle_id,
                        )
                        if risk.action.normalized_action() == "BUY":
                            open_count += 1
                        elif risk.action.normalized_action() == "SELL":
                            open_count = max(0, open_count - 1)
                elif act in ("BUY", "SELL") and not risk.approved:
                    self._log(
                        f"Trade blocked {action.ticker}: {risk.notes}",
                        "risk", cycle_id, level="warn",
                    )

            # Safety net: if EOD window and still holding, force flatten
            if is_eod_flat_window() and config.TRADING_MODE == "daily_active":
                remaining = self.alpaca.get_positions()
                if remaining:
                    n = self.executor.flatten_positions(remaining, cycle_id)
                    if n:
                        self._log(f"EOD safety flatten: closed {n} position(s)", "eod", cycle_id)

            self.executor.ensure_stops(
                self.alpaca.get_positions(),
                snap_map,
            )

            account = self.alpaca.get_account()
            equity = account["equity"]
            cash = account["cash"]
            _, day_pnl_pct = self.risk.check_daily_halt(day_start, equity)

            self.store.finish_cycle(
                cycle_id, "completed",
                llm_response={"summary": decision.summary, "actions": [
                    {"ticker": a.ticker, "action": a.action, "pct": a.pct,
                     "stop": a.stop, "reason": a.reason}
                    for a in decision.actions
                ]},
                summary=decision.summary,
            )
            self.store.save_equity_snapshot(equity, cash, day_pnl_pct, cycle_id)

            self.store.set_runner_status(
                cycle_id=cycle_id,
                cycle_status="completed",
                cycle_summary=decision.summary,
            )
            result = {
                "status": "completed",
                "cycle_id": cycle_id,
                "equity": equity,
                "day_pnl_pct": day_pnl_pct,
                "halted": halted,
                "orders_placed": orders_placed,
                "summary": decision.summary,
                "used_fallback": decision.used_fallback,
            }
            logger.info("Cycle %s done | orders=%s | %s", cycle_id, orders_placed, decision.summary)
            return result

        except Exception as exc:
            logger.exception("Cycle %s failed", cycle_id)
            self.store.finish_cycle(cycle_id, "error", error=str(exc))
            raise

    def run_eod_report(self) -> dict:
        today = now_et().date()
        if not is_weekday(today):
            return {"status": "skipped", "reason": "weekend"}

        account = self.alpaca.get_account() if self.alpaca.configured else {
            "equity": 0, "cash": 0
        }
        equity_end = account["equity"]
        equity_start = self.store.get_day_start_equity(today) or equity_end
        num_cycles = self.store.count_cycles_today(today)
        num_trades = self.store.count_orders_today(today)
        halted = self.store.is_halted_today(today)

        self.store.save_daily_report(
            today, equity_start, equity_end, num_trades, num_cycles, halted,
            notes=f"EOD auto-report {now_et().isoformat()}",
        )
        pnl = equity_end - equity_start
        logger.info(
            "EOD %s | start=$%.2f end=$%.2f pnl=$%.2f | cycles=%s trades=%s",
            today, equity_start, equity_end, pnl, num_cycles, num_trades,
        )
        return {
            "status": "completed",
            "date": today.isoformat(),
            "equity_start": equity_start,
            "equity_end": equity_end,
            "pnl": pnl,
            "num_cycles": num_cycles,
            "num_trades": num_trades,
            "halted": halted,
        }

    def run_daemon(self) -> None:
        logger.info(
            "Daemon started | mode=%s | watchlist=%s | cycle=%sm | max_pos=%s",
            config.TRADING_MODE, config.WATCHLIST, config.CYCLE_MINUTES,
            config.MAX_POSITIONS,
        )
        eod_done_today: date | None = None
        flatten_done_today: date | None = None

        while True:
            now = now_et()
            today = now.date()

            if is_eod_window(now) and eod_done_today != today:
                try:
                    self.run_eod_report()
                except Exception as exc:
                    logger.error("EOD report failed: %s", exc)
                eod_done_today = today

            if (
                is_eod_flat_window(now)
                and self.store.get_state(f"entries_blocked_{today.isoformat()}") == "1"
            ):
                try:
                    positions = self.alpaca.get_positions() if self.alpaca.configured else []
                except Exception:
                    positions = []
                if not positions:
                    if flatten_done_today != today:
                        self._log(
                            "EOD complete — flat. Sleeping until next market open.",
                            "eod",
                        )
                        flatten_done_today = today
                        try:
                            self.run_eod_report()
                            eod_done_today = today
                        except Exception as exc:
                            logger.error("EOD report failed: %s", exc)
                    nxt = next_weekday_open(now)
                    wait = seconds_until(nxt)
                    logger.info(
                        "Session done — sleeping %.0fs until %s",
                        wait, nxt.strftime("%Y-%m-%d %H:%M ET"),
                    )
                    time.sleep(max(60, min(wait, 3600)))
                    continue

            if is_market_open(now) or is_premarket_plan_window(now):
                try:
                    self.run_cycle()
                except Exception as exc:
                    logger.error("Cycle error: %s", exc)
            else:
                nxt = next_weekday_open(now)
                wait = seconds_until(nxt)
                logger.info(
                    "Market closed — sleeping %.0fs until %s",
                    wait, nxt.strftime("%Y-%m-%d %H:%M ET"),
                )
                time.sleep(max(60, min(wait, 3600)))
                continue

            nxt = next_daemon_wakeup(config.CYCLE_MINUTES, now_et())
            wait = seconds_until(nxt)
            sleep_for = max(30 if is_eod_flat_window(now) else 60, wait) if wait > 0 else 60
            logger.info("Sleeping %.0fs until %s", sleep_for, nxt.strftime("%H:%M ET"))
            time.sleep(sleep_for)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Finance-Vibe paper trading bot")
    parser.add_argument(
        "command",
        choices=["cycle", "daemon", "eod", "status", "prepare-session", "resume-session"],
        help="cycle=one run, daemon=scheduled, eod=end-of-day report, "
        "status=account info, prepare-session=cancel/flatten/reset day baseline, "
        "resume-session=after outage (keep positions + day P&L)",
    )
    parser.add_argument("--force", action="store_true", help="Run cycle even if market closed")
    parser.add_argument(
        "--no-flatten", action="store_true",
        help="With prepare-session: cancel orders only, keep positions",
    )
    args = parser.parse_args(argv)

    runner = TradingRunner()

    if args.command == "cycle":
        result = runner.run_cycle(force=args.force)
        print(json.dumps(result, indent=2))
        return 0 if result.get("status") != "error" else 1

    if args.command == "eod":
        result = runner.run_eod_report()
        print(json.dumps(result, indent=2))
        return 0

    if args.command == "status":
        if not runner.alpaca.configured:
            print("Alpaca not configured")
            return 1
        acct = runner.alpaca.get_account()
        pos = runner.alpaca.get_positions()
        print(json.dumps({"account": acct, "positions": pos}, indent=2))
        return 0

    if args.command == "prepare-session":
        result = prepare_clean_session(
            alpaca=runner.alpaca,
            store=runner.store,
            flatten=not args.no_flatten,
        )
        print(json.dumps(result, indent=2))
        return 0

    if args.command == "resume-session":
        from finance_vibe.bot.session import resume_session
        result = resume_session(alpaca=runner.alpaca, store=runner.store)
        print(json.dumps(result, indent=2))
        return 0

    if args.command == "daemon":
        runner.run_daemon()
        return 0

    return 1


if __name__ == "__main__":
    sys.exit(main())

