"""End-to-end trading logic smoke test (no live orders unless BOT_DRY_RUN=false)."""
from __future__ import annotations

import importlib.util
import json
import os
import sys
from pathlib import Path

# Bootstrap path
_root = Path(__file__).resolve().parents[1]
_lp = _root / "src" / "finance_vibe" / "bot" / "_load_path.py"
_spec = importlib.util.spec_from_file_location("fv_load_path", _lp)
_mod = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
_spec.loader.exec_module(_mod)

from finance_vibe.bot import config
from finance_vibe.bot.alpaca_client import AlpacaClient
from finance_vibe.bot.health import run_health_check
from finance_vibe.bot.signal_engine import SignalEngine
from finance_vibe.bot.models import CycleContext, TradeAction
from finance_vibe.bot.ollama_agent import OllamaAgent
from finance_vibe.bot.risk_guard import RiskGuard
from finance_vibe.bot.runner import TradingRunner


def _snap(ticker: str, price: float = 50.0, setup: str | None = "SETUP_LONG", stop: float = 47.0):
    from finance_vibe.bot.models import TickerSnapshot
    return TickerSnapshot(
        ticker=ticker, price=price, change_pct=-1.2, change_from_open_pct=-0.8,
        rsi=44.0, ema20=49.5, ema50=48.0, atr=1.5,
        setup_type=setup, setup_notes="test",
        entry=49.0, stop=stop, target1=55.0, target2=58.0,
        vs_qqq_pct=-0.5, regime_ok=True,
    )


def test_health():
    report = run_health_check(include_runner_hint=False)
    assert report.services[0].name == "Python deps"
    assert report.services[0].online, report.services[0].detail
    print("OK health:", report.headline)


def test_alpaca_connect():
    client = AlpacaClient()
    assert client.configured
    acct = client.get_account()
    assert acct["equity"] > 0
    prices = client.get_latest_prices(["QQQ", "SOFI"])
    assert "QQQ" in prices and prices["QQQ"]["price"] > 0
    print("OK alpaca: equity", acct["equity"], "QQQ", prices["QQQ"]["price"])


def test_indicators_live():
    pack = SignalEngine()
    snaps = pack.build_watchlist(config.WATCHLIST[:3])
    assert len(snaps) >= 2
    for s in snaps:
        assert s.ticker
        assert s.price > 0 or s.price == 0  # market closed ok
    print("OK indicators:", [
        f"{s.ticker} conv={s.conviction} vibe={s.vibe_score} setup={s.setup_type} cobra={s.coiled_cobra_grade}"
        for s in snaps
    ])


def test_ollama_or_fallback():
    agent = OllamaAgent()
    ctx = CycleContext(
        account_equity=100_000, account_cash=50_000, buying_power=100_000,
        day_pnl_pct=0.0, halted=False,
        watchlist=[_snap("SOFI"), _snap("PLTR", setup=None, stop=None)],
        open_positions=[], strategy_notes="test",
    )
    decision = agent.decide(ctx)
    assert decision.actions
    assert all(a.normalized_action() in ("BUY", "SELL", "HOLD") for a in decision.actions)
    print("OK agent:", decision.summary[:80], "fallback=", decision.used_fallback)


def test_risk_guard():
    guard = RiskGuard()
    ctx = CycleContext(
        account_equity=100_000, account_cash=50_000, buying_power=100_000,
        day_pnl_pct=0.0, halted=False,
        watchlist=[_snap("SOFI")], open_positions=[], strategy_notes="test",
    )
    buy = TradeAction("SOFI", "BUY", pct=15, stop=47.0, reason="test")
    risk = guard.validate(buy, ctx, _snap("SOFI"), 0)
    assert risk.approved and risk.qty > 0 and risk.notional >= config.MIN_ORDER_NOTIONAL

    sell_ctx = CycleContext(
        account_equity=100_000, account_cash=50_000, buying_power=100_000,
        day_pnl_pct=0.0, halted=False, watchlist=[], open_positions=[],
        strategy_notes="test",
    )
    sell_snap = _snap("SOFI")
    sell_snap.in_position = True
    sell_snap.position_qty = 10
    sell = TradeAction("SOFI", "SELL", pct=100, reason="take profit")
    sell_risk = guard.validate(sell, sell_ctx, sell_snap, 1)
    assert sell_risk.approved and sell_risk.qty == 10
    print("OK risk: buy qty", risk.qty, "sell qty", sell_risk.qty)


def test_dry_run_cycle():
    os.environ["BOT_DRY_RUN"] = "true"
    importlib.reload(config)
    runner = TradingRunner()
    result = runner.run_cycle(force=True)
    assert result["status"] in ("completed", "skipped")
    if result["status"] == "completed":
        assert "equity" in result
        print("OK dry cycle:", json.dumps({k: result[k] for k in ("status", "equity", "summary", "orders_placed")}))
    else:
        print("OK cycle skipped:", result.get("reason"))


def main() -> int:
    tests = [
        test_health,
        test_alpaca_connect,
        test_indicators_live,
        test_ollama_or_fallback,
        test_risk_guard,
        test_dry_run_cycle,
    ]
    failed = []
    for fn in tests:
        try:
            print(f"\n--- {fn.__name__} ---")
            fn()
        except Exception as exc:
            print(f"FAIL {fn.__name__}: {exc}")
            failed.append(fn.__name__)
    print("\n" + "=" * 50)
    if failed:
        print("FAILED:", ", ".join(failed))
        return 1
    print("ALL TRADING LOGIC TESTS PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
