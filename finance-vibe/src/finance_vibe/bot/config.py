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
# daily_active = frequent dip-buys + quick profit-taking across volatile names
# swing = original SETUP_LONG / coiled-cobra swing style (fewer trades)
TRADING_MODE = os.getenv("BOT_TRADING_MODE", "daily_active").strip().lower()

DEFAULT_WATCHLIST = [
    # High-beta tech / fintech
    "NVDA", "AMD", "META", "PLTR", "SOFI", "TSLA", "HOOD", "COIN",
    # Semis / growth ETFs
    "SOXL", "XLK", "ARKK", "SMCI",
    # Finance / energy / small-cap (rotation)
    "BAC", "XLE", "IWM", "MARA", "RIOT", "NIO",
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
    "Daily-active mode: buy intraday dips, sell on small green (+0.35%+), "
    "rotate across sectors. Max 2-day holds. Trade every cycle when possible.",
)

# Daily-active trading parameters
REQUIRE_DAILY_ACTIVITY = os.getenv("BOT_REQUIRE_DAILY_ACTIVITY", "true").lower() in (
    "1", "true", "yes",
)
DIP_BUY_FROM_OPEN_PCT = float(os.getenv("BOT_DIP_BUY_FROM_OPEN_PCT", "-0.2"))
QUICK_PROFIT_PCT = float(os.getenv("BOT_QUICK_PROFIT_PCT", "0.35"))
QUICK_STOP_LOSS_PCT = float(os.getenv("BOT_QUICK_STOP_LOSS_PCT", "1.0"))
ACTIVE_POSITION_PCT = float(os.getenv("BOT_ACTIVE_POSITION_PCT", "10"))
ACTIVE_MAX_BUYS_PER_CYCLE = int(os.getenv("BOT_ACTIVE_MAX_BUYS_PER_CYCLE", "2"))
ACTIVE_MIN_BUY_SCORE = float(os.getenv("BOT_ACTIVE_MIN_BUY_SCORE", "22"))
ACTIVE_MIN_RSI = float(os.getenv("BOT_ACTIVE_MIN_RSI", "25"))
ACTIVE_MAX_RSI = float(os.getenv("BOT_ACTIVE_MAX_RSI", "68"))
ACTIVE_SELL_RSI = float(os.getenv("BOT_ACTIVE_SELL_RSI", "68"))
ACTIVE_SELL_FROM_OPEN_PCT = float(os.getenv("BOT_ACTIVE_SELL_FROM_OPEN_PCT", "1.2"))
ACTIVE_STOP_PCT = float(os.getenv("BOT_ACTIVE_STOP_PCT", "1.2"))
ACTIVE_ATR_MULT = float(os.getenv("BOT_ACTIVE_ATR_MULT", "0.75"))

# Intraday research signals (VWAP dip, IBS mean-reversion, opening range)
USE_INTRADAY_SIGNALS = os.getenv("BOT_USE_INTRADAY_SIGNALS", "true").lower() in (
    "1", "true", "yes",
)
ORB_MINUTES = int(os.getenv("BOT_ORB_MINUTES", "15"))
EOD_FLAT_HOUR = int(os.getenv("BOT_EOD_FLAT_HOUR", "15"))
EOD_FLAT_MINUTE = int(os.getenv("BOT_EOD_FLAT_MINUTE", "55"))
VWAP_BUY_BELOW_PCT = float(os.getenv("BOT_VWAP_BUY_BELOW_PCT", "-0.1"))
IBS_OVERSOLD = float(os.getenv("BOT_IBS_OVERSOLD", "0.25"))

# Risk (aggressive paper defaults — daily mode uses more smaller positions)
RISK_PER_TRADE_PCT = float(os.getenv("RISK_PER_TRADE_PCT", "0.02"))
MAX_POSITIONS = int(os.getenv("MAX_POSITIONS", "6"))
MAX_POSITION_PCT = float(os.getenv("MAX_POSITION_PCT", "0.18"))
DAILY_LOSS_HALT_PCT = float(os.getenv("DAILY_LOSS_HALT_PCT", "0.05"))
MIN_ORDER_NOTIONAL = float(os.getenv("MIN_ORDER_NOTIONAL", "50"))
CYCLE_MINUTES = int(os.getenv("CYCLE_MINUTES", "10"))

# Dashboard
DASHBOARD_HOST = os.getenv("BOT_DASHBOARD_HOST", "127.0.0.1")
DASHBOARD_PORT = int(os.getenv("BOT_DASHBOARD_PORT", "5001"))

# Runner
DRY_RUN = os.getenv("BOT_DRY_RUN", "false").lower() in ("1", "true", "yes")


def ensure_dirs() -> None:
    BOT_DATA_DIR.mkdir(parents=True, exist_ok=True)
