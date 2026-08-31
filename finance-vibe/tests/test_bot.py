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
    def test_buy_approved_with_stop(self):
        guard = RiskGuard(risk_per_trade_pct=0.03, min_notional=50)
        snap = _snapshot("PLTR", setup="SETUP_LONG", stop=95.0)
        action = TradeAction("PLTR", "BUY", pct=20, stop=95.0, reason="setup")
        risk = guard.validate(action, _ctx(), snap, open_position_count=0)
        assert risk.approved
        assert risk.qty > 0
        assert risk.notional >= 50

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

    def test_daily_quick_sell(self):
        from finance_vibe.bot.daily_activity import should_quick_sell
        snap = _snapshot("PLTR", price=100.0)
        snap.in_position = True
        snap.position_pnl_pct = 0.5
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
