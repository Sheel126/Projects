"""Tests for paper trading bot components."""
from __future__ import annotations

import json
import os
import tempfile

import pytest

from finance_vibe.bot.models import CycleContext, TickerSnapshot, TradeAction
from finance_vibe.bot.ollama_agent import OllamaAgent
from finance_vibe.bot.risk_guard import RiskGuard
from finance_vibe.bot.store import BotStore
from finance_vibe.bot.market_hours import is_weekday, is_market_open


@pytest.fixture
def tmp_db():
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "test.db")
        yield BotStore(db_path=path)


def _snapshot(ticker: str, price: float = 100.0, setup: str | None = None, stop: float = 95.0):
    return TickerSnapshot(
        ticker=ticker, price=price, change_pct=-1.0, change_from_open_pct=-0.5,
        rsi=45.0, ema20=99.0, ema50=98.0, atr=2.0,
        setup_type=setup, setup_notes=None,
        entry=price, stop=stop, target1=110.0, target2=115.0,
        vs_qqq_pct=-0.5, regime_ok=True,
        vibe_score=7, conviction=55.0, signal_sources=["test"],
    )


def _ctx(equity: float = 100_000, halted: bool = False, watchlist=None):
    wl = watchlist or [_snapshot("PLTR"), _snapshot("SOFI", setup=None)]
    return CycleContext(
        account_equity=equity, account_cash=equity * 0.5,
        buying_power=equity, day_pnl_pct=0.0, halted=halted,
        watchlist=wl, open_positions=[], strategy_notes="test",
    )


class TestRiskGuard:
    def test_buy_approved_with_stop(self, monkeypatch):
        monkeypatch.setattr("finance_vibe.bot.risk_guard.is_market_open", lambda: True)
        monkeypatch.setattr("finance_vibe.bot.risk_guard.is_late_entry_window", lambda: False)
        guard = RiskGuard(risk_per_trade_pct=0.03, min_notional=50)
        snap = _snapshot("PLTR", setup="SETUP_LONG", stop=95.0)
        action = TradeAction("PLTR", "BUY", pct=20, stop=95.0, reason="setup")
        risk = guard.validate(action, _ctx(), snap, open_position_count=0)
        assert risk.approved
        assert risk.qty >= 1
        assert risk.qty == int(risk.qty)  # whole shares
        assert risk.notional >= 50

    def test_buy_blocked_when_entries_blocked(self):
        guard = RiskGuard()
        snap = _snapshot("PLTR", setup="SETUP_LONG")
        ctx = _ctx()
        ctx.entries_blocked = True
        action = TradeAction("PLTR", "BUY", pct=20, stop=95.0)
        risk = guard.validate(action, ctx, snap, 0)
        assert not risk.approved

    def test_buy_rejected_without_stop(self):
        guard = RiskGuard()
        snap = TickerSnapshot(
            ticker="PLTR", price=100.0, change_pct=0, change_from_open_pct=0,
            rsi=45, ema20=99, ema50=98, atr=None,
            setup_type="SETUP_LONG", setup_notes=None,
            entry=100, stop=None, target1=None, target2=None,
            vs_qqq_pct=0, regime_ok=True,
        )
        action = TradeAction("PLTR", "BUY", pct=20, stop=None)
        risk = guard.validate(action, _ctx(), snap, 0)
        assert not risk.approved

    def test_buy_blocked_when_halted(self):
        guard = RiskGuard()
        snap = _snapshot("PLTR", setup="SETUP_LONG")
        action = TradeAction("PLTR", "BUY", pct=20, stop=95.0)
        risk = guard.validate(action, _ctx(halted=True), snap, 0)
        assert not risk.approved

    def test_daily_halt_triggers(self):
        guard = RiskGuard()
        halted, pnl = guard.check_daily_halt(100_000, 94_000)
        assert halted
        assert pnl < 0

    def test_buy_blocked_when_qqq_red(self, monkeypatch):
        guard = RiskGuard()
        snap = _snapshot("PLTR", setup="SETUP_LONG")
        ctx = _ctx()
        ctx.benchmark_change_from_open_pct = -0.55
        ctx.entries_blocked = False
        action = TradeAction("PLTR", "BUY", pct=13, stop=95.0)
        monkeypatch.setattr(
            "finance_vibe.bot.risk_guard.is_market_open", lambda: True,
        )
        risk = guard.validate(action, ctx, snap, 0)
        assert not risk.approved
        assert "dip buys blocked" in risk.notes

    def test_buy_blocked_premarket(self, monkeypatch):
        guard = RiskGuard()
        snap = _snapshot("PLTR", setup="SETUP_LONG")
        ctx = _ctx()
        action = TradeAction("PLTR", "BUY", pct=13, stop=95.0)
        monkeypatch.setattr(
            "finance_vibe.bot.risk_guard.is_market_open", lambda: False,
        )
        risk = guard.validate(action, ctx, snap, 0)
        assert not risk.approved
        assert "Market not open" in risk.notes

    def test_buy_blocked_late_session(self, monkeypatch):
        guard = RiskGuard()
        snap = _snapshot("PLTR", setup="SETUP_LONG")
        ctx = _ctx()
        action = TradeAction("PLTR", "BUY", pct=13, stop=95.0)
        monkeypatch.setattr(
            "finance_vibe.bot.risk_guard.is_market_open", lambda: True,
        )
        monkeypatch.setattr(
            "finance_vibe.bot.risk_guard.is_late_entry_window", lambda: True,
        )
        risk = guard.validate(action, ctx, snap, 0)
        assert not risk.approved
        assert "3:30" in risk.notes

    def test_max_five_positions(self, monkeypatch):
        guard = RiskGuard(max_positions=5)
        snap = _snapshot("NVDA", setup="SETUP_LONG")
        action = TradeAction("NVDA", "BUY", pct=13, stop=95.0)
        monkeypatch.setattr(
            "finance_vibe.bot.risk_guard.is_market_open", lambda: True,
        )
        monkeypatch.setattr(
            "finance_vibe.bot.risk_guard.is_late_entry_window", lambda: False,
        )
        risk = guard.validate(action, _ctx(), snap, open_position_count=5)
        assert not risk.approved
        assert "Max 5" in risk.notes


class TestRegime:
    def test_benchmark_blocks_at_threshold(self):
        from finance_vibe.bot.regime import benchmark_blocks_new_buys
        assert benchmark_blocks_new_buys(-0.5)
        assert benchmark_blocks_new_buys(-0.4)
        assert not benchmark_blocks_new_buys(-0.3)
        assert not benchmark_blocks_new_buys(None)


class TestOllamaAgent:
    def test_rule_fallback_buy_setup(self, monkeypatch):
        monkeypatch.setattr("finance_vibe.bot.ollama_agent.config.TRADING_MODE", "swing")
        agent = OllamaAgent(enabled=False)
        snap = _snapshot("PLTR", setup="SETUP_LONG", stop=95.0)
        snap.conviction = 65.0
        snap.coiled_cobra_grade = "B - Valid Coil"
        ctx = _ctx(watchlist=[snap])
        decision = agent.decide(ctx)
        assert decision.used_fallback
        buy = [a for a in decision.actions if a.ticker == "PLTR"][0]
        assert buy.normalized_action() == "BUY"

    def test_daily_active_dip_buy(self, monkeypatch):
        monkeypatch.setattr("finance_vibe.bot.ollama_agent.config.TRADING_MODE", "daily_active")
        agent = OllamaAgent(enabled=False)
        snap = _snapshot("PLTR", price=25.0, stop=24.0)
        snap.change_from_open_pct = -0.8
        snap.rsi = 42.0
        snap.atr = 0.5
        snap.tight_stop = 24.5
        snap.active_score = 35.0
        snap.sector = "tech"
        ctx = _ctx(watchlist=[snap])
        decision = agent.decide(ctx)
        buy = [a for a in decision.actions if a.ticker == "PLTR"][0]
        assert buy.normalized_action() == "BUY"
        assert buy.stop is not None

    def test_daily_quick_sell(self, monkeypatch):
        from finance_vibe.bot.daily_activity import should_quick_sell
        monkeypatch.setattr("finance_vibe.bot.daily_activity.config.QUICK_PROFIT_PCT", 1.2)
        snap = _snapshot("PLTR", price=100.0)
        snap.in_position = True
        snap.position_pnl_pct = 1.5
        ok, reason, pct = should_quick_sell(snap)
        assert ok
        assert pct == 100.0

    def test_enforce_minimum_activity(self, monkeypatch):
        from finance_vibe.bot.daily_activity import enforce_minimum_activity
        from finance_vibe.bot.models import AgentDecision
        monkeypatch.setattr("finance_vibe.bot.daily_activity.config.REQUIRE_DAILY_ACTIVITY", True)
        snap = _snapshot("SOFI", price=10.0, stop=9.5)
        snap.change_from_open_pct = -1.2
        snap.rsi = 40.0
        snap.atr = 0.2
        snap.tight_stop = 9.85
        snap.active_score = 40.0
        snap.sector = "fintech"
        ctx = _ctx(watchlist=[snap])
        idle = AgentDecision(actions=[TradeAction("SOFI", "HOLD")], summary="idle")
        out = enforce_minimum_activity(idle, ctx)
        assert any(a.normalized_action() == "BUY" for a in out.actions)

    def test_parse_actions_json(self):
        agent = OllamaAgent(enabled=False)
        wl = [_snapshot("PLTR"), _snapshot("SOFI")]
        raw = json.dumps({
            "summary": "test",
            "actions": [
                {"ticker": "PLTR", "action": "HOLD", "pct": 0, "stop": None, "reason": "wait"},
                {"ticker": "SOFI", "action": "BUY", "pct": 15, "stop": 8.5, "reason": "dip"},
            ],
        })
        parsed = agent._parse_json(raw)
        actions = agent._parse_actions(parsed["actions"], wl)
        assert len(actions) == 2
        assert actions[1].normalized_action() == "BUY"


class TestBotStore:
    def test_cycle_lifecycle(self, tmp_db):
        cid = tmp_db.start_cycle({"test": True})
        tmp_db.finish_cycle(cid, "completed", summary="ok")
        cycles = tmp_db.recent_cycles(1)
        assert cycles[0]["status"] == "completed"

    def test_daily_report(self, tmp_db):
        from datetime import date
        tmp_db.save_daily_report(date(2026, 8, 30), 100_000, 101_000, 3, 10, False)
        reports = tmp_db.daily_reports(1)
        assert reports[0]["pnl"] == 1000


class TestMarketHours:
    def test_weekday(self):
        from datetime import datetime
        from zoneinfo import ZoneInfo
        mon = datetime(2026, 8, 31, 10, 0, tzinfo=ZoneInfo("America/New_York"))
        assert is_weekday(mon.date())
        assert is_market_open(mon)


class TestHealth:
    def test_ollama_disabled_is_ok(self):
        from finance_vibe.bot.health import check_ollama
        svc = check_ollama(enabled=False)
        assert svc.online
        assert "Disabled" in svc.message

    def test_alpaca_not_configured(self, monkeypatch):
        from finance_vibe.bot.health import check_alpaca
        from finance_vibe.bot.alpaca_client import AlpacaClient
        monkeypatch.setattr("finance_vibe.bot.alpaca_client.config.ALPACA_API_KEY", "")
        monkeypatch.setattr("finance_vibe.bot.alpaca_client.config.ALPACA_SECRET_KEY", "")
        svc = check_alpaca(AlpacaClient(api_key="", secret_key=""))
        assert not svc.online

    def test_health_report_weekend_headline(self, monkeypatch):
        from datetime import datetime
        from zoneinfo import ZoneInfo
        from finance_vibe.bot.health import run_health_check, ServiceStatus

        sunday = datetime(2026, 8, 30, 12, 0, tzinfo=ZoneInfo("America/New_York"))
        monkeypatch.setattr("finance_vibe.bot.health.now_et", lambda: sunday)
        monkeypatch.setattr(
            "finance_vibe.bot.health.check_python_deps",
            lambda: ServiceStatus("Python deps", True, "ok"),
        )
        monkeypatch.setattr(
            "finance_vibe.bot.health.check_alpaca",
            lambda *a, **k: ServiceStatus("Alpaca", True, "ok"),
        )
        monkeypatch.setattr(
            "finance_vibe.bot.health.check_ollama",
            lambda *a, **k: ServiceStatus("Ollama", True, "ok"),
        )
        monkeypatch.setattr(
            "finance_vibe.bot.health.check_database",
            lambda *a, **k: ServiceStatus("Database", True, "ok"),
        )
        report = run_health_check()
        assert report.all_ready
        assert "waiting for trading day" in report.headline.lower()

    def test_compute_conviction(self):
        from finance_vibe.bot.signal_engine import compute_conviction
        snap = _snapshot("NVDA", setup="SETUP_LONG")
        snap.coiled_cobra_grade = "A - Coil Ready"
        snap.ml_rank = 1
        score = compute_conviction(snap)
        assert score >= 50

    def test_intraday_ibs_oversold(self):
        from finance_vibe.bot.intraday_signals import compute_ibs, intraday_buy_bonus
        assert compute_ibs(10, 12, 8) == 0.5
        snap = _snapshot("PLTR")
        snap.ibs = 0.15
        snap.price_vs_vwap_pct = -0.3
        assert intraday_buy_bonus(snap) >= 20

    def test_next_cycle_after_close_is_next_open(self):
        from datetime import datetime
        from zoneinfo import ZoneInfo
        from finance_vibe.bot.market_hours import next_cycle_time, next_weekday_open
        et = ZoneInfo("America/New_York")
        after = datetime(2026, 8, 31, 16, 5, tzinfo=et)
        nxt = next_cycle_time(20, after)
        assert nxt == next_weekday_open(after)
        assert nxt.hour == 9 and nxt.minute == 30
        assert nxt > after

    def test_next_cycle_aligned_from_market_open(self):
        from datetime import datetime
        from zoneinfo import ZoneInfo
        from finance_vibe.bot.market_hours import next_cycle_time
        et = ZoneInfo("America/New_York")
        at_open = datetime(2026, 9, 1, 9, 30, 27, tzinfo=et)
        assert next_cycle_time(20, at_open) == datetime(2026, 9, 1, 9, 50, tzinfo=et)
        mid = datetime(2026, 9, 1, 9, 45, tzinfo=et)
        assert next_cycle_time(20, mid) == datetime(2026, 9, 1, 9, 50, tzinfo=et)
        after_slot = datetime(2026, 9, 1, 9, 50, 1, tzinfo=et)
        assert next_cycle_time(20, after_slot) == datetime(2026, 9, 1, 10, 10, tzinfo=et)

    def test_daemon_wakeup_hits_eod_flat(self):
        from datetime import datetime
        from zoneinfo import ZoneInfo
        from finance_vibe.bot.market_hours import next_daemon_wakeup, eod_flat_datetime
        et = ZoneInfo("America/New_York")
        at_350 = datetime(2026, 9, 2, 15, 50, tzinfo=et)
        assert next_daemon_wakeup(20, at_350) == eod_flat_datetime(at_350.date())

    def test_preemptive_eod_at_last_cycle(self):
        from datetime import datetime
        from zoneinfo import ZoneInfo
        from finance_vibe.bot.market_hours import should_preemptive_eod_flatten
        et = ZoneInfo("America/New_York")
        at_350 = datetime(2026, 9, 2, 15, 50, tzinfo=et)
        assert should_preemptive_eod_flatten(at_350, 20)
        at_330 = datetime(2026, 9, 2, 15, 30, tzinfo=et)
        assert not should_preemptive_eod_flatten(at_330, 20)

    def test_late_entry_window(self, monkeypatch):
        from datetime import datetime
        from zoneinfo import ZoneInfo
        from finance_vibe.bot.market_hours import is_late_entry_window
        et = ZoneInfo("America/New_York")
        monkeypatch.setattr(
            "finance_vibe.bot.market_hours.now_et",
            lambda: datetime(2026, 9, 2, 15, 35, tzinfo=et),
        )
        assert is_late_entry_window()

    def test_executor_cancels_orders_before_sell(self, tmp_db, monkeypatch):
        from finance_vibe.bot.executor import Executor
        from finance_vibe.bot.models import RiskResult

        cancelled: list[str] = []

        class FakeAlpaca:
            configured = True

            def cancel_orders_for_symbol(self, symbol: str) -> int:
                cancelled.append(symbol)
                return 2

            def submit_market_order(self, symbol, qty, side):
                return {"id": "o1", "status": "submitted", "filled_avg_price": 0}

            def submit_limit_order(self, *a, **k):
                raise AssertionError("not expected")

            def submit_stop_order(self, *a, **k):
                raise AssertionError("not expected")

        monkeypatch.setattr("finance_vibe.bot.executor.config.USE_BROKER_STOPS", False)
        ex = Executor(alpaca=FakeAlpaca(), store=tmp_db, dry_run=False)
        risk = RiskResult(
            approved=True,
            action=TradeAction("META", "SELL", pct=100, reason="take profit"),
            qty=10,
            notional=1000,
        )
        ex.execute(risk, cycle_id=1, decision_id=1, price=500.0)
        assert cancelled == ["META"]

    def test_executor_no_broker_stops_in_daily_active(self, monkeypatch):
        from finance_vibe.bot.executor import Executor
        monkeypatch.setattr("finance_vibe.bot.executor.config.TRADING_MODE", "daily_active")
        monkeypatch.setattr("finance_vibe.bot.executor.config.USE_BROKER_STOPS", True)
        assert not Executor._use_broker_stops()

    def test_executor_retry_pending_sell(self, tmp_db, monkeypatch):
        from finance_vibe.bot.executor import Executor

        class FakeAlpaca:
            configured = True

            def cancel_orders_for_symbol(self, symbol):
                return 0

            def submit_market_order(self, symbol, qty, side):
                return {"id": "r1", "status": "filled", "filled_avg_price": 100}

        tmp_db.add_pending_sell("NVDA")
        ex = Executor(alpaca=FakeAlpaca(), store=tmp_db, dry_run=False)
        n = ex.retry_pending_sells(
            [{"symbol": "NVDA", "qty": 10}], cycle_id=1,
        )
        assert n == 1
        assert tmp_db.get_pending_sell_symbols() == []

    def test_store_pending_sells(self, tmp_db):
        tmp_db.add_pending_sell("AAPL")
        tmp_db.add_pending_sell("AAPL")
        assert tmp_db.get_pending_sell_symbols() == ["AAPL"]
        tmp_db.clear_pending_sell("AAPL")
        assert tmp_db.get_pending_sell_symbols() == []

    def test_prepare_clean_session_resets_state(self, tmp_db, monkeypatch):
        from datetime import date
        from finance_vibe.bot.session import prepare_clean_session

        class FakeAlpaca:
            configured = True

            def get_account(self):
                return {"equity": 99_500.0, "cash": 50_000.0}

            def cancel_all_orders(self):
                pass

            def get_open_orders(self):
                return [{"id": "1"}, {"id": "2"}]

            def get_positions(self):
                return []

        today = date(2026, 9, 1)
        monkeypatch.setattr("finance_vibe.bot.session.now_et", lambda: __import__("datetime").datetime(
            2026, 9, 1, 11, 0, tzinfo=__import__("zoneinfo").ZoneInfo("America/New_York"),
        ))
        tmp_db.set_state("entries_blocked_2026-09-01", "1")
        tmp_db.set_halted_today(today, True)
        report = prepare_clean_session(alpaca=FakeAlpaca(), store=tmp_db)
        assert report["equity_after"] == 99_500.0
        assert tmp_db.get_day_start_equity(today) == 99_500.0
        assert tmp_db.get_state("entries_blocked_2026-09-01") == "0"
        assert not tmp_db.is_halted_today(today)

    def test_activity_log(self, tmp_db):
        tmp_db.log_activity("test message", phase="cycle", cycle_id=1)
        acts = tmp_db.recent_activity(5)
        assert acts[0]["message"] == "test message"
        assert acts[0]["phase"] == "cycle"

    def test_check_setup_cli_json(self, monkeypatch):
        from finance_vibe.bot.check_setup import main
        from finance_vibe.bot.health import HealthReport, ServiceStatus

        fake = HealthReport(
            services=[
                ServiceStatus("Alpaca", True, "ok"),
                ServiceStatus("Ollama", True, "ok"),
                ServiceStatus("Database", True, "ok"),
            ],
            all_ready=True,
            headline="All systems online — waiting for trading day",
            subline="Weekend",
            market_phase="weekend",
            next_event="Monday",
            checked_at="now",
        )
        monkeypatch.setattr("finance_vibe.bot.check_setup.run_health_check", lambda **k: fake)
        assert main(["--json"]) == 0
