import os

# --- 1. PROJECT PATH LOGIC (The Root Fix) ---
# This finds the absolute path to the 'finance-vibe' folder
# This file is in /src/finance_vibe/, so root is 2 levels up
_CONFIG_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(_CONFIG_DIR, "../.."))

# --- 2. API PARAMETERS ---
PERIOD = "10y"
INTERVAL = "1wk"

# --- 3. TICKER LISTS ---
STATIC_TICKERS = ["SPY", "QQQ", "IWM", "SCHD"]

# --- 4. FOLDER STRUCTURE (Absolute Paths) ---
BASE_DIR = os.path.join(PROJECT_ROOT, "data")
RAW_DIR = os.path.join(BASE_DIR, "raw")
LOGS_DIR = os.path.join(BASE_DIR, "logs")
TICKER_LIST_PATH = os.path.join(BASE_DIR, "active_tickers.csv")

# --- 5. FILENAME LOGIC ---


def get_raw_filename(ticker):
    """Generates standardized filename: e.g., AAPL_2y_1d.csv"""
    return f"{ticker}_{PERIOD}_{INTERVAL}.csv"


def get_raw_path(ticker):
    """Returns absolute path to a specific ticker's raw data file."""
    return os.path.join(RAW_DIR, get_raw_filename(ticker))


# --- 6. BACKTEST SETTINGS ---
BACKTEST_START_DATE = "2020-01-01"
BACKTEST_INITIAL_CAPITAL = 10000
BACKTEST_BUY_SCORE = 7   # "🟢 STARTER POSITION"
BACKTEST_SELL_SCORE = 1  # Exit when it hits "NO EDGE" or "REDUCE"

# --- 7. OPTIONAL AI / NEWS REVIEW SETTINGS ---
ENABLE_AI_REVIEW = os.getenv("FINANCE_VIBE_ENABLE_AI_REVIEW", "0") == "1"
# 0 means "no cap" (process all rows from the chosen input source).
AI_MAX_TICKERS_PER_RUN = int(os.getenv("FINANCE_VIBE_AI_MAX_TICKERS", "0"))
AI_BATCH_SIZE = int(os.getenv("FINANCE_VIBE_AI_BATCH_SIZE", "5"))
AI_MAX_RETRIES = int(os.getenv("FINANCE_VIBE_AI_MAX_RETRIES", "2"))
AI_REQUEST_TIMEOUT = int(os.getenv("FINANCE_VIBE_AI_TIMEOUT_SECONDS", "45"))
AI_MODEL = os.getenv("FINANCE_VIBE_AI_MODEL", "gpt-4.1-mini")
NEWS_MAX_HEADLINES_PER_TICKER = int(
    os.getenv("FINANCE_VIBE_NEWS_MAX_HEADLINES", "3")
)
NEWS_LOOKBACK_DAYS = int(os.getenv("FINANCE_VIBE_NEWS_LOOKBACK_DAYS", "5"))
NEWS_SLEEP_SECONDS = float(os.getenv("FINANCE_VIBE_NEWS_SLEEP_SECONDS", "0.5"))

# --- 8. DIRECTORY INITIALIZATION ---
# This ensures folders exist relative to the project root
os.makedirs(RAW_DIR, exist_ok=True)
os.makedirs(LOGS_DIR, exist_ok=True)
