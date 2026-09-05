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
# IWM and JPM removed: over the last 30 sessions they reached +1.2% off the
# open on only 6.7% and 10% of days, so the profit target is unreachable.
DEFAULT_WATCHLIST = [
    "NVDA", "AMD", "META", "TSLA", "PLTR", "SMCI",
    "COIN", "HOOD", "SOFI",
    "AAPL", "AMZN", "NFLX",
    "XOM", "GLD",
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
    "Day-4 quality hybrid: buy Finance-Vibe setups/cobra/vibe leaders. "
    "Pullbacks or strength (SETUP/cobra + VWAP/ORB; RVOL not sole confirm). "
    "TP ~1.2%, SL ~1.8%, flat by 3:55. Block buys when QQQ red, after 3:30, or day PnL <= -1%.",
)

# ---------------------------------------------------------------------------
# THE NINE TUNABLE KNOBS
#
# Day-5 rewrite. The previous config carried 35 strategy parameters fitted to
# 28 trades; the standard is ~30 trades per parameter, so almost all of them
# were noise-fitting. Anything not on this list was deleted rather than tuned.
# Do not add a knob back unless it changes the *logic*, not the backtest score.
# ---------------------------------------------------------------------------

# 1. Exit distance, as a multiple of the stock's own daily ATR. Replaces the
#    fixed take-profit/stop pair: watchlist ATR spans 2.0% (GLD) to 6.8%
#    (COIN), so no single percentage fits both.
ATR_EXIT_MULT = float(os.getenv("BOT_ATR_EXIT_MULT", "0.5"))

# 2. The single quality floor. Everything the old vibe/conviction/setup gates
#    tested is already priced into active_score.
MIN_BUY_SCORE = float(os.getenv("BOT_MIN_BUY_SCORE", "38"))

# 3/4. One entry band, replacing four overlapping "distance from open" knobs
#      and the duplicated strength/pullback code paths.
ENTRY_MIN_FROM_OPEN_PCT = float(os.getenv("BOT_ENTRY_MIN_FROM_OPEN_PCT", "-2.5"))
ENTRY_MAX_FROM_OPEN_PCT = float(os.getenv("BOT_ENTRY_MAX_FROM_OPEN_PCT", "3.5"))

# 5. Anti-chase ceiling: never buy something already stretched above VWAP.
VWAP_BUY_MAX_ABOVE_PCT = float(os.getenv("BOT_VWAP_BUY_MAX_ABOVE_PCT", "1.0"))

# 6/7. Sizing and concurrency.
ACTIVE_POSITION_PCT = float(os.getenv("BOT_ACTIVE_POSITION_PCT", "13"))
MAX_POSITIONS = int(os.getenv("MAX_POSITIONS", "5"))

# 8. Daily brake: stop opening new positions once the day is this far down.
DAY_BLOCK_BUYS_PCT = float(os.getenv("BOT_DAY_BLOCK_BUYS_PCT", "-1.0"))

# 9. Regime brake: the only defence against a falling market.
BENCHMARK_BLOCK_PCT = float(os.getenv("BOT_BENCHMARK_BLOCK_PCT", "-0.4"))

# --- structural settings, not strategy tuning -------------------------------
REQUIRE_DAILY_ACTIVITY = os.getenv("BOT_REQUIRE_DAILY_ACTIVITY", "false").lower() in (
    "1", "true", "yes",
)
ACTIVE_MAX_BUYS_PER_CYCLE = int(os.getenv("BOT_ACTIVE_MAX_BUYS_PER_CYCLE", "2"))
WHOLE_SHARES_ONLY = os.getenv("BOT_WHOLE_SHARES_ONLY", "true").lower() in (
    "1", "true", "yes",
)
USE_INTRADAY_SIGNALS = os.getenv("BOT_USE_INTRADAY_SIGNALS", "true").lower() in (
    "1", "true", "yes",
)
LATE_ENTRY_HOUR = int(os.getenv("BOT_LATE_ENTRY_HOUR", "15"))
LATE_ENTRY_MINUTE = int(os.getenv("BOT_LATE_ENTRY_MINUTE", "30"))
EOD_FLAT_HOUR = int(os.getenv("BOT_EOD_FLAT_HOUR", "15"))
EOD_FLAT_MINUTE = int(os.getenv("BOT_EOD_FLAT_MINUTE", "55"))
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

