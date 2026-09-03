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

    def test_daily_active_quality_buy(self, monkeypatch):
        monkeypatch.setattr("finance_vibe.bot.ollama_agent.config.TRADING_MODE", "daily_active")
        monkeypatch.setattr("finance_vibe.bot.daily_activity.config.BUY_MODE", "quality")
        monkeypatch.setattr("finance_vibe.bot.daily_activity.config.REQUIRE_STRUCTURE", True)
        monkeypatch.setattr("finance_vibe.bot.daily_activity.config.ACTIVE_MIN_BUY_SCORE", 40)
        agent = OllamaAgent(enabled=False)
        snap = _snapshot("PLTR", price=25.0, stop=24.0, setup="SETUP_LONG")
        snap.change_from_open_pct = -0.8
        snap.rsi = 42.0
        snap.atr = 0.5
        snap.tight_stop = 24.5
        snap.active_score = 55.0
        snap.conviction = 50.0
        snap.vibe_score = 6
        snap.rs_63d = 0.05
        snap.rvol = 1.2
        snap.sector = "tech"
        ctx = _ctx(watchlist=[snap])
        decision = agent.decide(ctx)
        buy = [a for a in decision.actions if a.ticker == "PLTR"][0]
        assert buy.normalized_action() == "BUY"
        assert buy.stop is not None

    def test_quality_rejects_freefall_without_structure(self, monkeypatch):
        from finance_vibe.bot.daily_activity import _buy_eligible
        monkeypatch.setattr("finance_vibe.bot.daily_activity.config.BUY_MODE", "quality")
        monkeypatch.setattr("finance_vibe.bot.daily_activity.config.REQUIRE_STRUCTURE", True)
        monkeypatch.setattr("finance_vibe.bot.daily_activity.config.MAX_DIP_BUY_PCT", -3.0)
        snap = _snapshot("SMCI", price=50.0, stop=48.0)
        snap.change_from_open_pct = -4.5
        snap.setup_type = None
        snap.conviction = 20
        snap.vibe_score = 2
        snap.active_score = 60
        snap.rvol = 2.0
        assert not _buy_eligible(snap, _ctx(watchlist=[snap]), 0)

    def test_quality_allows_strength_with_structure(self, monkeypatch):
        from finance_vibe.bot.daily_activity import _buy_eligible, compute_active_score
        monkeypatch.setattr("finance_vibe.bot.daily_activity.config.BUY_MODE", "quality")
        monkeypatch.setattr("finance_vibe.bot.daily_activity.config.REQUIRE_STRUCTURE", True)
        monkeypatch.setattr("finance_vibe.bot.daily_activity.config.ALLOW_STRENGTH_BUYS", True)
        monkeypatch.setattr("finance_vibe.bot.daily_activity.config.ACTIVE_MIN_BUY_SCORE", 40)
        snap = _snapshot("NVDA", price=100.0, stop=95.0, setup="SETUP_LONG")
        snap.change_from_open_pct = 0.8
        snap.price_vs_vwap_pct = 0.2
        snap.rvol = 1.4
        snap.vibe_score = 7
        snap.conviction = 55
        snap.rs_63d = 0.04
        snap.rsi = 52
        snap.active_score = compute_active_score(snap)
        assert snap.active_score >= 40
        assert _buy_eligible(snap, _ctx(watchlist=[snap]), 0)

    def test_nvda_strength_a_setup_at_2_6_passes(self, monkeypatch):
        from finance_vibe.bot.daily_activity import _buy_eligible, compute_active_score
        monkeypatch.setattr("finance_vibe.bot.daily_activity.config.BUY_MODE", "quality")
        monkeypatch.setattr("finance_vibe.bot.daily_activity.config.REQUIRE_STRUCTURE", True)
        monkeypatch.setattr("finance_vibe.bot.daily_activity.config.ALLOW_STRENGTH_BUYS", True)
        monkeypatch.setattr("finance_vibe.bot.daily_activity.config.STRENGTH_MAX_OPEN_PCT", 3.5)
        monkeypatch.setattr("finance_vibe.bot.daily_activity.config.ACTIVE_MIN_BUY_SCORE", 38)
        monkeypatch.setattr("finance_vibe.bot.daily_activity.config.ACTIVE_SETUP_MIN_BUY_SCORE", 30)
        snap = _snapshot("NVDA", price=120.0, stop=115.0, setup="SETUP_LONG")
        snap.change_from_open_pct = 2.6
        snap.price_vs_vwap_pct = 0.05
        snap.rvol = 1.0
        snap.vibe_score = 9
        snap.conviction = 70
        snap.coiled_cobra_grade = "A - Coil"
        snap.rs_63d = 0.06
        snap.rsi = 55
        snap.active_score = compute_active_score(snap)
        assert _buy_eligible(snap, _ctx(watchlist=[snap]), 0)

    def test_strength_no_setup_fails(self, monkeypatch):
        from finance_vibe.bot.daily_activity import _buy_eligible
        monkeypatch.setattr("finance_vibe.bot.daily_activity.config.BUY_MODE", "quality")
        monkeypatch.setattr("finance_vibe.bot.daily_activity.config.REQUIRE_STRUCTURE", True)
        monkeypatch.setattr("finance_vibe.bot.daily_activity.config.ALLOW_STRENGTH_BUYS", True)
        snap = _snapshot("TSLA", price=200.0, stop=190.0)
        snap.setup_type = None
        snap.coiled_cobra_grade = None
        snap.change_from_open_pct = 3.0
        snap.price_vs_vwap_pct = 0.5
        snap.rvol = 2.0
        snap.vibe_score = 8
        snap.conviction = 60
        snap.active_score = 80
        snap.rsi = 50
        assert not _buy_eligible(snap, _ctx(watchlist=[snap]), 0)

    def test_strength_rvol_alone_fails(self, monkeypatch):
        from finance_vibe.bot.daily_activity import _buy_eligible
        monkeypatch.setattr("finance_vibe.bot.daily_activity.config.BUY_MODE", "quality")
        monkeypatch.setattr("finance_vibe.bot.daily_activity.config.ALLOW_STRENGTH_BUYS", True)
        snap = _snapshot("AMD", price=100.0, stop=95.0, setup="SETUP_LONG")
        snap.change_from_open_pct = 2.5
        snap.price_vs_vwap_pct = -0.5  # below VWAP
        snap.orb_signal = None
        snap.rvol = 3.0  # high RVOL alone must not unlock
        snap.vibe_score = 8
        snap.conviction = 60
        snap.active_score = 90
        snap.rsi = 50
        assert not _buy_eligible(snap, _ctx(watchlist=[snap]), 0)

    def test_mild_pullback_setup_passes(self, monkeypatch):
        from finance_vibe.bot.daily_activity import _buy_eligible, compute_active_score
        monkeypatch.setattr("finance_vibe.bot.daily_activity.config.BUY_MODE", "quality")
        monkeypatch.setattr("finance_vibe.bot.daily_activity.config.ACTIVE_MIN_BUY_SCORE", 38)
        snap = _snapshot("META", price=500.0, stop=490.0, setup="SETUP_LONG")
        snap.change_from_open_pct = -1.0
        snap.rvol = 1.1
        snap.vibe_score = 6
        snap.conviction = 50
        snap.rsi = 45
        snap.active_score = compute_active_score(snap)
        assert _buy_eligible(snap, _ctx(watchlist=[snap]), 0)

    def test_compute_relative_volume(self):
        import pandas as pd
        from finance_vibe.bot.signal_engine import compute_relative_volume
        df = __import__("pandas").DataFrame({"Volume": [100] * 20 + [250]})
        assert compute_relative_volume(df) == 2.5

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
        monkeypatch.setattr("finance_vibe.bot.daily_activity.config.BUY_MODE", "quality")
        monkeypatch.setattr("finance_vibe.bot.daily_activity.config.ACTIVE_MIN_BUY_SCORE", 40)
        snap = _snapshot("SOFI", price=10.0, stop=9.5, setup="SETUP_LONG")
        snap.change_from_open_pct = -0.8
        snap.rsi = 40.0
        snap.atr = 0.2
        snap.tight_stop = 9.85
        snap.active_score = 55.0
        snap.conviction = 50.0
        snap.vibe_score = 6
        snap.rs_63d = 0.03
        snap.rvol = 1.1
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

        events: list[str] = []

        class FakeAlpaca:
            configured = True
            _orders: list = []
            _pos_qty = 10.0

            def get_open_sell_orders(self, symbol):
                return [
                    o for o in self.get_open_orders(symbol)
                    if "SELL" in str(o.get("side", "")).upper()
                ]

            def get_position_qty(self, symbol):
                return self._pos_qty

            def get_open_orders(self, symbol=None):
                return list(self._orders)

            def cancel_and_wait_clear(self, symbol, timeout_sec=5.0):
                events.append(f"cancel_wait:{symbol}")
                self._orders = []
                return True

            def cancel_orders_for_symbol(self, symbol, wait_sec=1.0, **kw):
                events.append(f"cancel:{symbol}")
                self._orders = []
                return 2

            def get_positions(self):
                if self._pos_qty <= 0:
                    return []
                return [{"symbol": "META", "qty": self._pos_qty}]

            def wait_for_flat(self, symbol, timeout_sec=45.0):
                self._pos_qty = 0.0
                return True

            def close_position(self, symbol):
                events.append(f"close:{symbol}")
                return {"id": "o1", "status": "filled", "filled_avg_price": 500}

            def get_order(self, order_id):
                return {"id": order_id, "status": "filled", "filled_avg_price": 500}

            def submit_market_order(self, symbol, qty, side):
                return {"id": "o1", "status": "submitted", "filled_avg_price": 0}

            def submit_limit_order(self, *a, **k):
                raise AssertionError("not expected")

            def submit_stop_order(self, *a, **k):
                raise AssertionError("not expected")

        monkeypatch.setattr("finance_vibe.bot.executor.config.USE_BROKER_STOPS", False)
        fake = FakeAlpaca()
        fake._orders = [{"id": "b1", "side": "BUY", "status": "new", "symbol": "META"}]
        ex = Executor(alpaca=fake, store=tmp_db, dry_run=False)
        risk = RiskResult(
            approved=True,
            action=TradeAction("META", "SELL", pct=100, reason="take profit"),
            qty=10,
            notional=1000,
        )
        ex.execute(risk, cycle_id=1, decision_id=1, price=500.0)
        assert "cancel_wait:META" in events
        assert "close:META" in events

    def test_executor_no_broker_stops_in_daily_active(self, monkeypatch):
        from finance_vibe.bot.executor import Executor
        monkeypatch.setattr("finance_vibe.bot.executor.config.TRADING_MODE", "daily_active")
        monkeypatch.setattr("finance_vibe.bot.executor.config.USE_BROKER_STOPS", True)
        assert not Executor._use_broker_stops()

    def test_executor_retry_pending_sell(self, tmp_db, monkeypatch):
        from finance_vibe.bot.executor import Executor

        class FakeAlpaca:
            configured = True
            _pos_qty = 10.0

            def get_open_sell_orders(self, symbol):
                return []

            def get_position_qty(self, symbol):
                return self._pos_qty

            def get_open_orders(self, symbol=None):
                return []

            def cancel_and_wait_clear(self, symbol, timeout_sec=5.0):
                return True

            def cancel_orders_for_symbol(self, symbol, wait_sec=1.0, **kw):
                return 0

            def get_positions(self):
                return [{"symbol": "NVDA", "qty": self._pos_qty}] if self._pos_qty else []

            def wait_for_flat(self, symbol, timeout_sec=45.0):
                self._pos_qty = 0.0
                return True

            def close_position(self, symbol):
                return {"id": "r1", "status": "filled", "filled_avg_price": 100}

            def get_order(self, order_id):
                return {"id": order_id, "status": "filled", "filled_avg_price": 100}

        tmp_db.add_pending_sell("NVDA")
        fake = FakeAlpaca()
        ex = Executor(alpaca=fake, store=tmp_db, dry_run=False)
        n = ex.retry_pending_sells(
            [{"symbol": "NVDA", "qty": 10}], cycle_id=1,
        )
        assert n == 1
        assert tmp_db.get_pending_sell_symbols() == []

    def test_no_duplicate_sell_if_open_sell_exists(self, tmp_db, monkeypatch):
        from finance_vibe.bot.executor import Executor
        from finance_vibe.bot.models import RiskResult

        closes = []

        class FakeAlpaca:
            configured = True

            def get_open_sell_orders(self, symbol):
                return [{"id": "sell1", "side": "SELL", "status": "new", "symbol": "AAPL"}]

            def get_position_qty(self, symbol):
                return 5.0

            def get_open_orders(self, symbol=None):
                return self.get_open_sell_orders(symbol)

            def cancel_and_wait_clear(self, symbol, timeout_sec=5.0):
                raise AssertionError("should not cancel when reusing sell")

            def close_position(self, symbol):
                closes.append(symbol)
                return {"id": "x", "status": "filled"}

            def get_positions(self):
                return [{"symbol": "AAPL", "qty": 5}]

            def wait_for_flat(self, symbol, timeout_sec=45.0):
                return False

            def get_order(self, order_id):
                return {"id": order_id, "status": "new", "filled_avg_price": 0}

        ex = Executor(alpaca=FakeAlpaca(), store=tmp_db, dry_run=False)
        risk = RiskResult(
            approved=True,
            action=TradeAction("AAPL", "SELL", pct=100),
            qty=5, notional=500,
        )
        order = ex.execute(risk, 1, 1, 100.0)
        assert order["id"] == "sell1"
        assert closes == []
        assert "AAPL" in tmp_db.get_pending_sell_symbols()  # in-flight new

    def test_flatten_idempotent_repeated_call(self, tmp_db):
        from finance_vibe.bot.executor import Executor

        class FakeAlpaca:
            configured = True
            closed = 0
            _qty = 10.0

            def get_open_sell_orders(self, symbol):
                return []

            def get_position_qty(self, symbol):
                return self._qty

            def get_open_orders(self, symbol=None):
                return []

            def cancel_and_wait_clear(self, symbol, timeout_sec=5.0):
                return True

            def get_positions(self):
                return [{"symbol": "TSLA", "qty": self._qty}] if self._qty > 0 else []

            def wait_for_flat(self, symbol, timeout_sec=45.0):
                self._qty = 0.0
                return True

            def close_position(self, symbol):
                self.closed += 1
                self._qty = 0.0
                return {"id": f"c{self.closed}", "status": "filled"}

            def get_order(self, order_id):
                return {"id": order_id, "status": "filled"}

        fake = FakeAlpaca()
        ex = Executor(alpaca=fake, store=tmp_db, dry_run=False)
        n1 = ex.flatten_positions([{"symbol": "TSLA", "qty": 10}], cycle_id=1)
        n2 = ex.flatten_positions([], cycle_id=1)  # already empty list
        n3 = ex.flatten_positions(
            [{"symbol": "TSLA", "qty": 10}], cycle_id=1,
        )  # live qty 0 → noop
        assert n1 == 1
        assert fake.closed == 1
        assert n3 == 0  # no live qty

    def test_partial_fill_sells_remaining_qty(self, tmp_db):
        from finance_vibe.bot.executor import Executor

        submitted_qty: list[float] = []

        class FakeAlpaca:
            configured = True
            _qty = 7.0  # remaining after partial fill

            def get_open_sell_orders(self, symbol):
                return []

            def get_position_qty(self, symbol):
                return self._qty

            def get_open_orders(self, symbol=None):
                return []

            def cancel_and_wait_clear(self, symbol, timeout_sec=5.0):
                return True

            def get_positions(self):
                return [{"symbol": "AMD", "qty": self._qty}]

            def wait_for_flat(self, symbol, timeout_sec=45.0):
                self._qty = 0.0
                return True

            def close_position(self, symbol):
                submitted_qty.append(self._qty)
                self._qty = 0.0
                return {"id": "p1", "status": "filled"}

            def submit_market_order(self, symbol, qty, side):
                submitted_qty.append(qty)
                return {"id": "p2", "status": "new"}

            def get_order(self, order_id):
                return {"id": order_id, "status": "filled"}

        ex = Executor(alpaca=FakeAlpaca(), store=tmp_db, dry_run=False)
        # Request full 10 but live remaining is 7
        order = ex._submit_sell("AMD", 10.0)
        assert order["status"] == "filled"
        assert submitted_qty == [7.0]

    def test_cancel_timeout_raises_no_blind_sell(self, tmp_db):
        from finance_vibe.bot.executor import Executor
        import pytest

        class FakeAlpaca:
            configured = True

            def get_open_sell_orders(self, symbol):
                return []

            def get_position_qty(self, symbol):
                return 5.0

            def get_open_orders(self, symbol=None):
                return [{"id": "stuck", "side": "BUY", "status": "pending_cancel"}]

            def cancel_and_wait_clear(self, symbol, timeout_sec=5.0):
                return False  # still open

            def close_position(self, symbol):
                raise AssertionError("must not close while orders stuck")

            def get_positions(self):
                return [{"symbol": "META", "qty": 5}]

        ex = Executor(alpaca=FakeAlpaca(), store=tmp_db, dry_run=False)
        with pytest.raises(RuntimeError, match="cancel timeout"):
            ex._submit_sell("META", 5.0)

    def test_restart_while_sell_pending_reuses_open_sell(self, tmp_db):
        from finance_vibe.bot.executor import Executor

        class FakeAlpaca:
            configured = True
            close_calls = 0

            def get_open_sell_orders(self, symbol):
                return [{"id": "pending_sell", "side": "SELL", "status": "pending_new"}]

            def get_position_qty(self, symbol):
                return 3.0

            def get_open_orders(self, symbol=None):
                return self.get_open_sell_orders(symbol)

            def close_position(self, symbol):
                self.close_calls += 1
                return {"id": "dup", "status": "new"}

            def get_positions(self):
                return [{"symbol": "NVDA", "qty": 3}]

            def wait_for_flat(self, symbol, timeout_sec=45.0):
                return False

            def get_order(self, order_id):
                return {"id": order_id, "status": "pending_new"}

        tmp_db.add_pending_sell("NVDA")
        fake = FakeAlpaca()
        ex = Executor(alpaca=fake, store=tmp_db, dry_run=False)
        n = ex.retry_pending_sells([{"symbol": "NVDA", "qty": 3}], cycle_id=2)
        assert n == 1
        assert fake.close_calls == 0
        # Still pending because in-flight
        assert "NVDA" in tmp_db.get_pending_sell_symbols()

    def test_stale_cancel_then_replacement_sell(self, tmp_db):
        from finance_vibe.bot.executor import Executor

        class FakeAlpaca:
            configured = True
            phase = "stale"

            def get_open_sell_orders(self, symbol):
                return []

            def get_position_qty(self, symbol):
                return 4.0

            def get_open_orders(self, symbol=None):
                if self.phase == "stale":
                    return [{"id": "stale_buy", "side": "BUY", "status": "new"}]
                return []

            def cancel_and_wait_clear(self, symbol, timeout_sec=5.0):
                self.phase = "clear"
                return True

            def close_position(self, symbol):
                assert self.phase == "clear"
                return {"id": "replacement", "status": "filled"}

            def get_positions(self):
                return [{"symbol": "HOOD", "qty": 4}]

            def wait_for_flat(self, symbol, timeout_sec=45.0):
                return True

            def get_order(self, order_id):
                return {"id": order_id, "status": "filled"}

        ex = Executor(alpaca=FakeAlpaca(), store=tmp_db, dry_run=False)
        order = ex._submit_sell("HOOD", 4.0)
        assert order["id"] == "replacement"

    def test_day_loss_block_and_caution(self, monkeypatch):
        from finance_vibe.bot.risk_guard import RiskGuard
        monkeypatch.setattr("finance_vibe.bot.risk_guard.config.DAY_CAUTION_PCT", -0.5)
        monkeypatch.setattr("finance_vibe.bot.risk_guard.config.DAY_BLOCK_BUYS_PCT", -1.0)
        monkeypatch.setattr("finance_vibe.bot.risk_guard.is_market_open", lambda: True)
        monkeypatch.setattr("finance_vibe.bot.risk_guard.is_late_entry_window", lambda: False)
        guard = RiskGuard()
        assert guard.day_loss_caution(-0.5)
        assert not guard.day_loss_blocks_buys(-0.5)
        assert guard.day_loss_blocks_buys(-1.0)

        snap = _snapshot("PLTR", setup="SETUP_LONG", stop=95.0)
        ctx = _ctx()
        ctx.day_pnl_pct = -1.0
        ctx.entries_blocked = True  # runner sets this when day-loss blocks
        buy = TradeAction("PLTR", "BUY", pct=13, stop=95.0)
        sell_snap = _snapshot("PLTR", price=100.0)
        sell_snap.in_position = True
        sell_snap.position_qty = 10
        assert not guard.validate(buy, ctx, snap, 0).approved
        sell = TradeAction("PLTR", "SELL", pct=100)
        assert guard.validate(sell, ctx, sell_snap, 1).approved

        # Caution caps size — no increase above ACTIVE_POSITION_PCT
        monkeypatch.setattr("finance_vibe.bot.risk_guard.config.ACTIVE_POSITION_PCT", 13)
        ctx2 = _ctx()
        ctx2.day_pnl_pct = -0.6
        ctx2.entries_blocked = False
        fat = TradeAction("PLTR", "BUY", pct=20, stop=95.0)  # would want 20%
        risk = guard.validate(fat, ctx2, snap, 0)
        assert risk.approved
        assert risk.action.pct <= 13.0 + 1e-6

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

            def wait_until_all_orders_clear(self, timeout_sec=5.0):
                return True

            def get_open_orders(self):
                return [{"id": "1"}, {"id": "2"}]

            def get_positions(self):
                return []

        today = date(2026, 9, 1)
        monkeypatch.setattr("finance_vibe.bot.session.now_et", lambda: __import__("datetime").datetime(
            2026, 9, 1, 11, 0, tzinfo=__import__("zoneinfo").ZoneInfo("America/New_York"),
        ))
        tmp_db.set_state("entries_blocked_2026-09-01", "1")
        tmp_db.set_state("buys_blocked_day_loss_2026-09-01", "1")
        tmp_db.set_halted_today(today, True)
        report = prepare_clean_session(alpaca=FakeAlpaca(), store=tmp_db)
        assert report["equity_after"] == 99_500.0
        assert tmp_db.get_day_start_equity(today) == 99_500.0
        assert tmp_db.get_state("entries_blocked_2026-09-01") == "0"
        assert tmp_db.get_state("buys_blocked_day_loss_2026-09-01") == "0"
        assert not tmp_db.is_halted_today(today)

    def test_resume_keeps_day_start(self, tmp_db, monkeypatch):
        from datetime import date
        from finance_vibe.bot.session import resume_session

        class FakeAlpaca:
            configured = True

            def get_account(self):
                return {"equity": 100_300.0, "cash": 50_000.0}

            def cancel_all_orders(self):
                raise AssertionError("resume must not cancel_all (would kill working sells)")

            def cancel_stale_non_sell_orders(self, timeout_sec=5.0, symbol=None):
                return 1

            def get_open_orders(self):
                return []

            def get_positions(self):
                return [{"symbol": "NVDA", "qty": 10}]

            def close_all_positions(self):
                raise AssertionError("resume must not flatten")

        today = date(2026, 9, 2)
        monkeypatch.setattr(
            "finance_vibe.bot.session.now_et",
            lambda: __import__("datetime").datetime(
                2026, 9, 2, 12, 0,
                tzinfo=__import__("zoneinfo").ZoneInfo("America/New_York"),
            ),
        )
        tmp_db.set_day_start_equity(today, 100_000.0)
        tmp_db.set_state("buys_blocked_day_loss_2026-09-02", "1")
        tmp_db.add_pending_sell("NVDA")
        report = resume_session(alpaca=FakeAlpaca(), store=tmp_db)
        assert report["day_start_equity"] == 100_000.0
        # Resume keeps day-loss block AND pending sells
        assert tmp_db.get_state("buys_blocked_day_loss_2026-09-02") == "1"
        assert "NVDA" in tmp_db.get_pending_sell_symbols()

    def test_cancel_stale_leaves_working_sells(self):
        from finance_vibe.bot.alpaca_client import AlpacaClient

        cancelled: list[str] = []
        live = [
            {"id": "b1", "side": "BUY", "type": "limit", "symbol": "NVDA"},
            {"id": "s1", "side": "SELL", "type": "market", "symbol": "NVDA"},
        ]
        client = AlpacaClient.__new__(AlpacaClient)
        client._ensure_clients = lambda: None
        client.get_open_orders = lambda symbol=None: [
            o for o in live if o["id"] not in cancelled
        ]

        class _Trading:
            def cancel_order_by_id(self, oid):
                cancelled.append(oid)

        client._trading = _Trading()
        n = client.cancel_stale_non_sell_orders()
        assert n == 1
        assert cancelled == ["b1"]

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
