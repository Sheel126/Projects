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
    is_market_open,
    is_premarket_plan_window,
    is_weekday,
    next_cycle_time,
    now_et,
    seconds_until,
)
from finance_vibe.bot.models import CycleContext
from finance_vibe.bot.ollama_agent import OllamaAgent
from finance_vibe.bot.risk_guard import RiskGuard
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
            f"watchlist={len(config.WATCHLIST)} tickers",
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

        open_orders = []
        try:
            open_orders = self.alpaca.get_open_orders()
        except Exception as exc:
            logger.warning("Could not fetch open orders: %s", exc)

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

        ctx = CycleContext(
            account_equity=equity,
            account_cash=cash,
            buying_power=account["buying_power"],
            day_pnl_pct=day_pnl_pct,
            halted=halted,
            watchlist=watchlist,
            open_positions=positions,
            strategy_notes=config.STRATEGY_NOTES,
            benchmark_change_pct=bench.get("change_pct"),
            open_orders=open_orders,
            market_regime=market_regime,
            conviction_ranking=conviction_ranking,
            trading_mode=config.TRADING_MODE,
        )

        cycle_id = self.store.start_cycle(ctx.to_prompt_dict())
        self._log(
            f"Cycle {cycle_id} started | equity=${equity:,.2f} | day P&L {day_pnl_pct:.2f}%",
            "cycle", cycle_id,
        )

        try:
            if is_eod_flat_window() and config.TRADING_MODE == "daily_active":
                eod = build_eod_flatten_decision(ctx)
                if eod:
                    self._log("EOD flat window — closing all positions", "eod", cycle_id)
                    decision = eod
                else:
                    self._log("EOD flat window — no positions to close", "eod", cycle_id)
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

            for action in decision.actions:
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

            self.executor.ensure_stops(
                self.alpaca.get_positions(),
                snap_map,
            )

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
        logger.info("Daemon started | mode=%s | watchlist=%s | cycle=%sm",
                    config.TRADING_MODE, config.WATCHLIST, config.CYCLE_MINUTES)
        eod_done_today: date | None = None

        while True:
            now = now_et()
            today = now.date()

            if is_eod_window(now) and eod_done_today != today:
                try:
                    self.run_eod_report()
                except Exception as exc:
                    logger.error("EOD report failed: %s", exc)
                eod_done_today = today

            if is_market_open(now) or is_premarket_plan_window(now):
                try:
                    self.run_cycle()
                except Exception as exc:
                    logger.error("Cycle error: %s", exc)

            nxt = next_cycle_time(config.CYCLE_MINUTES, now)
            wait = seconds_until(nxt)
            logger.info("Sleeping %.0fs until %s", wait, nxt.strftime("%H:%M ET"))
            time.sleep(max(30, wait))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Finance-Vibe paper trading bot")
    parser.add_argument(
        "command",
        choices=["cycle", "daemon", "eod", "status"],
        help="cycle=one run, daemon=scheduled, eod=end-of-day report, status=account info",
    )
    parser.add_argument("--force", action="store_true", help="Run cycle even if market closed")
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

    if args.command == "daemon":
        runner.run_daemon()
        return 0

    return 1


if __name__ == "__main__":
    sys.exit(main())
