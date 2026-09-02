"""Bot configuration from environment variables."""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

_CONFIG_DIR = Path(__file__).resolve().parents[3]
load_dotenv(_CONFIG_DIR / ".env")

PROJECT_ROOT = _CONFIG_DIR
BOT_DATA_DIR = PROJECT_ROOT / "data" / "bot"
BOT_DB_PATH = BOT_DATA_DIR / "trading_bot.db"

# Alpaca
ALPACA_API_KEY = os.getenv("ALPACA_API_KEY", "")
ALPACA_SECRET_KEY = os.getenv("ALPACA_SECRET_KEY", "")
ALPACA_BASE_URL = os.getenv(
    "ALPACA_BASE_URL", "https://paper-api.alpaca.markets"
)

# Ollama
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:7b")
OLLAMA_ENABLED = os.getenv("OLLAMA_ENABLED", "true").lower() in ("1", "true", "yes")
OLLAMA_TIMEOUT_SEC = int(os.getenv("OLLAMA_TIMEOUT_SEC", "120"))

# Watchlist & strategy
TRADING_MODE = os.getenv("BOT_TRADING_MODE", "daily_active").strip().lower()

# Day-3: diversified volatile + macro names (no 3x ETFs / junk miners)
DEFAULT_WATCHLIST = [
    "NVDA", "AMD", "META", "TSLA", "PLTR", "SMCI",
    "COIN", "HOOD", "SOFI",
    "AAPL", "AMZN", "NFLX", "JPM",
    "XOM", "GLD", "IWM",
]
WATCHLIST = [
    t.strip().upper()
    for t in os.getenv("BOT_WATCHLIST", ",".join(DEFAULT_WATCHLIST)).split(",")
    if t.strip()
]
SWING_PROFILE = os.getenv("BOT_SWING_PROFILE", "high_beta")
BENCHMARK = os.getenv("BOT_BENCHMARK", "QQQ")
STRATEGY_NOTES = os.getenv(
    "BOT_STRATEGY_NOTES",
    "Quality hybrid: buy Finance-Vibe setups/cobra/vibe leaders with volume, "
    "not free-falling dips. Mild pullbacks OR constructive strength OK. "
    "TP ~1.2%, SL ~1.8%, flat by 3:55. Block buys when QQQ red or after 3:30.",
)

# Daily-active trading parameters (Day-3: 5 slots, ~13% each)
REQUIRE_DAILY_ACTIVITY = os.getenv("BOT_REQUIRE_DAILY_ACTIVITY", "false").lower() in (
    "1", "true", "yes",
)
DIP_BUY_FROM_OPEN_PCT = float(os.getenv("BOT_DIP_BUY_FROM_OPEN_PCT", "-0.25"))
QUICK_PROFIT_PCT = float(os.getenv("BOT_QUICK_PROFIT_PCT", "1.2"))
QUICK_STOP_LOSS_PCT = float(os.getenv("BOT_QUICK_STOP_LOSS_PCT", "1.8"))
ACTIVE_POSITION_PCT = float(os.getenv("BOT_ACTIVE_POSITION_PCT", "13"))
ACTIVE_MAX_BUYS_PER_CYCLE = int(os.getenv("BOT_ACTIVE_MAX_BUYS_PER_CYCLE", "2"))
ACTIVE_MIN_BUY_SCORE = float(os.getenv("BOT_ACTIVE_MIN_BUY_SCORE", "42"))
ACTIVE_MIN_RSI = float(os.getenv("BOT_ACTIVE_MIN_RSI", "30"))
ACTIVE_MAX_RSI = float(os.getenv("BOT_ACTIVE_MAX_RSI", "68"))
ACTIVE_SELL_RSI = float(os.getenv("BOT_ACTIVE_SELL_RSI", "72"))
ACTIVE_SELL_FROM_OPEN_PCT = float(os.getenv("BOT_ACTIVE_SELL_FROM_OPEN_PCT", "2.5"))
ACTIVE_STOP_PCT = float(os.getenv("BOT_ACTIVE_STOP_PCT", "1.8"))
ACTIVE_ATR_MULT = float(os.getenv("BOT_ACTIVE_ATR_MULT", "0.85"))
WHOLE_SHARES_ONLY = os.getenv("BOT_WHOLE_SHARES_ONLY", "true").lower() in (
    "1", "true", "yes",
)

# Quality hybrid buys (research stack + timing) — not pure knife-catching
BUY_MODE = os.getenv("BOT_BUY_MODE", "quality").strip().lower()
MAX_DIP_BUY_PCT = float(os.getenv("BOT_MAX_DIP_BUY_PCT", "-3.0"))
MIN_RVOL = float(os.getenv("BOT_MIN_RVOL", "0.85"))
MIN_BUY_CONVICTION = float(os.getenv("BOT_MIN_BUY_CONVICTION", "35"))
MIN_BUY_VIBE = float(os.getenv("BOT_MIN_BUY_VIBE", "5"))
REQUIRE_STRUCTURE = os.getenv("BOT_REQUIRE_STRUCTURE", "true").lower() in (
    "1", "true", "yes",
)
ALLOW_STRENGTH_BUYS = os.getenv("BOT_ALLOW_STRENGTH_BUYS", "true").lower() in (
    "1", "true", "yes",
)

# Regime gating — block dip-buys when benchmark is red from open
BENCHMARK_BLOCK_PCT = float(os.getenv("BOT_BENCHMARK_BLOCK_PCT", "-0.4"))
LATE_ENTRY_HOUR = int(os.getenv("BOT_LATE_ENTRY_HOUR", "15"))
LATE_ENTRY_MINUTE = int(os.getenv("BOT_LATE_ENTRY_MINUTE", "30"))

# Intraday research signals
USE_INTRADAY_SIGNALS = os.getenv("BOT_USE_INTRADAY_SIGNALS", "true").lower() in (
    "1", "true", "yes",
)
ORB_MINUTES = int(os.getenv("BOT_ORB_MINUTES", "15"))
EOD_FLAT_HOUR = int(os.getenv("BOT_EOD_FLAT_HOUR", "15"))
EOD_FLAT_MINUTE = int(os.getenv("BOT_EOD_FLAT_MINUTE", "55"))
VWAP_BUY_BELOW_PCT = float(os.getenv("BOT_VWAP_BUY_BELOW_PCT", "-0.1"))
IBS_OVERSOLD = float(os.getenv("BOT_IBS_OVERSOLD", "0.25"))

# Risk (Day-3: five ~13% positions)
RISK_PER_TRADE_PCT = float(os.getenv("RISK_PER_TRADE_PCT", "0.035"))
MAX_POSITIONS = int(os.getenv("MAX_POSITIONS", "5"))
MAX_POSITION_PCT = float(os.getenv("MAX_POSITION_PCT", "0.18"))
DAILY_LOSS_HALT_PCT = float(os.getenv("DAILY_LOSS_HALT_PCT", "0.05"))
MIN_ORDER_NOTIONAL = float(os.getenv("MIN_ORDER_NOTIONAL", "50"))
CYCLE_MINUTES = int(os.getenv("CYCLE_MINUTES", "20"))

# Dashboard
DASHBOARD_HOST = os.getenv("BOT_DASHBOARD_HOST", "127.0.0.1")
DASHBOARD_PORT = int(os.getenv("BOT_DASHBOARD_PORT", "5001"))

# Runner / execution
DRY_RUN = os.getenv("BOT_DRY_RUN", "false").lower() in ("1", "true", "yes")
# Broker stops lock shares — hard-disabled for daily_active in executor regardless
USE_BROKER_STOPS = os.getenv("BOT_USE_BROKER_STOPS", "false").lower() in (
    "1", "true", "yes",
)


def ensure_dirs() -> None:
    BOT_DATA_DIR.mkdir(parents=True, exist_ok=True)

