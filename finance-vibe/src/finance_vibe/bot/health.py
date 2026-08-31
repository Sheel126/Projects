"""System health checks: Alpaca, Ollama, database, market schedule."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, time
from typing import Any

import requests

from finance_vibe.bot import config
from finance_vibe.bot.alpaca_client import AlpacaClient
from finance_vibe.bot.market_hours import (
    ET,
    MARKET_CLOSE,
    MARKET_OPEN,
    is_market_open,
    is_premarket_plan_window,
    is_weekday,
    next_cycle_time,
    now_et,
)
from finance_vibe.bot.store import BotStore


@dataclass
class ServiceStatus:
    name: str
    online: bool
    message: str
    detail: str = ""


@dataclass
class HealthReport:
    services: list[ServiceStatus] = field(default_factory=list)
    all_ready: bool = False
    headline: str = ""
    subline: str = ""
    market_phase: str = ""
    next_event: str = ""
    checked_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "all_ready": self.all_ready,
            "headline": self.headline,
            "subline": self.subline,
            "market_phase": self.market_phase,
            "next_event": self.next_event,
            "checked_at": self.checked_at,
            "services": [
                {
                    "name": s.name,
                    "online": s.online,
                    "message": s.message,
                    "detail": s.detail,
                }
                for s in self.services
            ],
        }


def check_ollama(
    base_url: str | None = None,
    model: str | None = None,
    enabled: bool | None = None,
    timeout: float = 5.0,
) -> ServiceStatus:
    base = (base_url or config.OLLAMA_BASE_URL).rstrip("/")
    model_name = model or config.OLLAMA_MODEL
    is_enabled = config.OLLAMA_ENABLED if enabled is None else enabled

    if not is_enabled:
        return ServiceStatus(
            name="Ollama",
            online=True,
            message="Disabled (rule-based mode)",
            detail=f"OLLAMA_ENABLED=false — using fallback rules, not {base}",
        )

    try:
        resp = requests.get(f"{base}/api/tags", timeout=timeout)
        resp.raise_for_status()
        data = resp.json()
        models = [m.get("name", "") for m in data.get("models", [])]
        # Match exact or prefix (e.g. qwen2.5:7b matches qwen2.5:7b-instruct)
        has_model = any(
            m == model_name or m.startswith(f"{model_name}:")
            or model_name.startswith(m.split(":")[0])
            for m in models
        )
        if not models:
            return ServiceStatus(
                name="Ollama",
                online=False,
                message="Server up, no models pulled",
                detail=f"Run: ollama pull {model_name}",
            )
        if not has_model:
            return ServiceStatus(
                name="Ollama",
                online=False,
                message=f"Model '{model_name}' not found",
                detail=f"Available: {', '.join(models[:5])}. Run: ollama pull {model_name}",
            )
        return ServiceStatus(
            name="Ollama",
            online=True,
            message=f"Online — {model_name}",
            detail=f"Connected to {base}",
        )
    except requests.ConnectionError:
        return ServiceStatus(
            name="Ollama",
            online=False,
            message="Cannot connect",
            detail=(
                f"Tried {base}. If Ollama runs in WSL/Ubuntu, set OLLAMA_BASE_URL to "
                "http://localhost:11434 (WSL2 usually forwards) or your WSL IP "
                "(run `hostname -I` in Ubuntu). Ensure `ollama serve` is running."
            ),
        )
    except requests.Timeout:
        return ServiceStatus(
            name="Ollama",
            online=False,
            message="Timed out",
            detail=f"No response from {base} within {timeout}s",
        )
    except Exception as exc:
        return ServiceStatus(
            name="Ollama",
            online=False,
            message="Error",
            detail=str(exc),
        )


def check_alpaca(client: AlpacaClient | None = None) -> ServiceStatus:
    client = client or AlpacaClient()
    if not client.configured:
        return ServiceStatus(
            name="Alpaca",
            online=False,
            message="Not configured",
            detail="Set ALPACA_API_KEY and ALPACA_SECRET_KEY in .env",
        )
    try:
        acct = client.get_account()
        equity = acct["equity"]
        paper = "paper" in client.base_url.lower()
        mode = "paper" if paper else "LIVE"
        return ServiceStatus(
            name="Alpaca",
            online=True,
            message=f"Online — {mode} account",
            detail=f"Equity ${equity:,.2f} | {client.base_url}",
        )
    except Exception as exc:
        return ServiceStatus(
            name="Alpaca",
            online=False,
            message="Connection failed",
            detail=str(exc),
        )


def check_database(store: BotStore | None = None) -> ServiceStatus:
    store = store or BotStore()
    try:
        store.set_state("_health_ping", "ok")
        val = store.get_state("_health_ping")
        if val == "ok":
            return ServiceStatus(
                name="Database",
                online=True,
                message="Online",
                detail=str(config.BOT_DB_PATH),
            )
        raise RuntimeError("read/write mismatch")
    except Exception as exc:
        return ServiceStatus(
            name="Database",
            online=False,
            message="Error",
            detail=str(exc),
        )


def _market_schedule_message() -> tuple[str, str, str]:
    """Return (phase, headline_part, next_event)."""
    now = now_et()
    today = now.date()

    if not is_weekday(today):
        nxt = next_cycle_time(config.CYCLE_MINUTES, now)
        day_name = nxt.strftime("%A")
        return (
            "weekend",
            "Weekend — markets closed",
            f"Next session: {day_name} {nxt.strftime('%b %d')} at 9:30 AM ET",
        )

    t = now.time()
    if t < MARKET_OPEN:
        if is_premarket_plan_window(now):
            return (
                "premarket",
                "Pre-market — bot can plan, trades at 9:30 AM ET",
                f"Market opens at 9:30 AM ET ({_minutes_until(now, MARKET_OPEN)} min)",
            )
        return (
            "before_open",
            "Waiting for market open",
            f"Opens 9:30 AM ET ({_minutes_until(now, MARKET_OPEN)} min)",
        )

    if is_market_open(now):
        nxt = next_cycle_time(config.CYCLE_MINUTES, now)
        return (
            "market_open",
            "Market open — trading active",
            f"Next cycle ~{nxt.strftime('%H:%M')} ET",
        )

    if t < time(16, 15):
        return (
            "after_close",
            "Market closed — EOD processing",
            "Session ended 4:00 PM ET",
        )

    return (
        "closed",
        "After hours — waiting for next trading day",
        _next_trading_day_message(now),
    )


def _minutes_until(now: datetime, target: time) -> int:
    target_dt = datetime.combine(now.date(), target, tzinfo=ET)
    return max(0, int((target_dt - now).total_seconds() // 60))


def _next_trading_day_message(now: datetime) -> str:
    nxt = next_cycle_time(config.CYCLE_MINUTES, now)
    return f"Next session: {nxt.strftime('%A %b %d')} at 9:30 AM ET"


def check_python_deps() -> ServiceStatus:
    """Verify Python version and packages required by the trading runner."""
    import sys

    ver = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    issues: list[str] = []

    if sys.version_info >= (3, 14):
        issues.append(
            f"Python {sys.version_info.major}.{sys.version_info.minor} is unsupported "
            "(pandas_ta requires 3.10–3.12)"
        )

    for label, mod in [
        ("pandas_ta", "pandas_ta"),
        ("flask", "flask"),
        ("alpaca-py", "alpaca.trading.client"),
        ("yfinance", "yfinance"),
    ]:
        try:
            __import__(mod)
        except ImportError as exc:
            issues.append(f"{label}: {exc}")

    try:
        from finance_vibe.swing_scanner import add_indicators  # noqa: F401
        from finance_vibe.bot.signal_engine import SignalEngine  # noqa: F401
    except ImportError as exc:
        issues.append(f"finance-vibe runner stack: {exc}")

    if issues:
        return ServiceStatus(
            name="Python deps",
            online=False,
            message="Missing or broken packages",
            detail=(
                f"Python {ver}. {' | '.join(issues)}. "
                "Fix: run .\\scripts\\setup-venv.ps1 then use .\\.venv\\Scripts\\python.exe "
                "or .\\start-paper-bot.ps1 (uses venv automatically)."
            ),
        )

    return ServiceStatus(
        name="Python deps",
        online=True,
        message=f"OK — Python {sys.version_info.major}.{sys.version_info.minor}",
        detail="pandas_ta, swing scanner, and runner modules load successfully",
    )


def check_runner_status() -> ServiceStatus:
    """Runner is external; dashboard only knows if daemon was started."""
    return ServiceStatus(
        name="Runner",
        online=True,
        message="Start via launcher",
        detail="Run: .\\start-paper-bot.ps1 (opens runner window)",
    )


def run_health_check(
    *,
    include_runner_hint: bool = True,
    ollama_timeout: float = 5.0,
) -> HealthReport:
    config.ensure_dirs()
    now = now_et()

    services = [
        check_python_deps(),
        check_alpaca(),
        check_ollama(timeout=ollama_timeout),
        check_database(),
    ]
    if include_runner_hint:
        services.append(check_runner_status())

    phase, schedule_headline, next_event = _market_schedule_message()

    # Core services required for trading (runner hint is informational only)
    core = [s for s in services if s.name != "Runner"]
    core_online = all(s.online for s in core)

    if core_online:
        if phase in ("weekend", "before_open", "closed", "after_close"):
            headline = "All systems online — waiting for trading day"
        elif phase == "premarket":
            headline = "All systems online — pre-market, ready for open"
        elif phase == "market_open":
            headline = "All systems online — trading session active"
        else:
            headline = "All systems online"
        subline = schedule_headline
    else:
        offline = [s.name for s in core if not s.online]
        headline = f"Setup incomplete — fix: {', '.join(offline)}"
        subline = "Resolve issues below before Monday"

    return HealthReport(
        services=services,
        all_ready=core_online,
        headline=headline,
        subline=subline,
        market_phase=phase,
        next_event=next_event,
        checked_at=now.strftime("%Y-%m-%d %H:%M:%S ET"),
    )


def ping_ollama_chat(base_url: str | None = None, model: str | None = None) -> tuple[bool, str]:
    """Optional deeper test: send a tiny chat request to Ollama."""
    base = (base_url or config.OLLAMA_BASE_URL).rstrip("/")
    model_name = model or config.OLLAMA_MODEL
    try:
        resp = requests.post(
            f"{base}/api/chat",
            json={
                "model": model_name,
                "messages": [{"role": "user", "content": 'Reply with JSON: {"ok": true}'}],
                "stream": False,
                "format": "json",
                "options": {"temperature": 0},
            },
            timeout=min(30, config.OLLAMA_TIMEOUT_SEC),
        )
        resp.raise_for_status()
        content = resp.json().get("message", {}).get("content", "")
        return True, content[:200]
    except Exception as exc:
        return False, str(exc)
