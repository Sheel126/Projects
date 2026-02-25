import pandas as pd
import pandas_ta as ta
import os
import logging
from datetime import datetime
from collections import Counter
from pathlib import Path

# ============================================================
# Paths
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data"
RAW_DATA_DIR = DATA_DIR / "raw"
LOGS_DIR = DATA_DIR / "logs"
ACTIVE_TICKERS_PATH = DATA_DIR / "active_tickers.csv"
LOGS_DIR.mkdir(parents=True, exist_ok=True)

# ============================================================
# Logging
# ============================================================

LOG_LEVEL = logging.INFO

logging.basicConfig(
    level=LOG_LEVEL,
    format="%(asctime)s | %(levelname)s | %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(LOGS_DIR / "swing_scanner.log")
    ]
)
logger = logging.getLogger(__name__)

# ============================================================
# Indicator Engine
# ============================================================


def calculate_indicators(df):
    df["EMA20"] = ta.ema(df["Close"], length=20)
    df["EMA50"] = ta.ema(df["Close"], length=50)
    df["RSI14"] = ta.rsi(df["Close"], length=14)
    macd = ta.macd(df["Close"], fast=12, slow=26, signal=9)
    df["MACD_Hist"] = macd.iloc[:, 1]
    df["ATR14"] = ta.atr(df["High"], df["Low"], df["Close"], length=14)
    df["Volume_MA20"] = ta.sma(df["Volume"], length=20)
    df["EMA50_slope"] = df["EMA50"].diff(5)
    return df

# ============================================================
# Filters
# ============================================================


def bullish_trend(row):
    return row["EMA20"] > row["EMA50"] and row["Close"] > row["EMA20"] and row["EMA50_slope"] >= 0


def bearish_trend(row):
    return row["EMA20"] < row["EMA50"] and row["Close"] < row["EMA20"] and row["EMA50_slope"] <= 0


def volume_contracting(row):
    if pd.isna(row["Volume_MA20"]):
        return True
    return row["Volume"] < row["Volume_MA20"]


def long_pullback(row):
    return row["Close"] <= row["EMA20"] * 1.01 and row["Close"] >= row["EMA50"] and 35 <= row["RSI14"] <= 55 and volume_contracting(row)


def short_pullback(row):
    return row["Close"] >= row["EMA20"] * 0.99 and row["Close"] <= row["EMA50"] and 45 <= row["RSI14"] <= 65 and volume_contracting(row)


def momentum_ready(df):
    h = df["MACD_Hist"].tail(3)
    return h.iloc[-1] > h.min()


def volatility_ok(row):
    return (row["ATR14"] / row["Close"]) > 0.005  # 0.5%

# ============================================================
# Scanner Logic with Notes
# ============================================================


def scan_asset(df):
    row = df.iloc[-1]
    notes = []

    if not volatility_ok(row):
        notes.append("Low volatility")
    if not momentum_ready(df):
        notes.append("Momentum not rising")

    signal = "IGNORE"
    if bullish_trend(row) and long_pullback(row) and volatility_ok(row) and momentum_ready(df):
        signal = "SETUP_LONG"
        notes.append("Pullback into 20EMA")
    elif bearish_trend(row) and short_pullback(row) and volatility_ok(row) and momentum_ready(df):
        signal = "SETUP_SHORT"
        notes.append("Pullback into 20EMA")

    return signal, "; ".join(notes)

# ============================================================
# Main Scanner
# ============================================================


def run_scanner():
    raw_files = list(RAW_DATA_DIR.glob("*.csv"))
    gate_stats = Counter()
    results = []

    logger.info(f"Found {len(raw_files)} raw data files")

    active_tickers = None
    if ACTIVE_TICKERS_PATH.exists():
        active_tickers = set(pd.read_csv(ACTIVE_TICKERS_PATH)[
                             "Ticker"].str.upper())
        logger.info(f"Loaded {len(active_tickers)} active tickers")

    for file_path in raw_files:
        ticker = file_path.stem.split("_")[0].upper()

        if active_tickers and ticker not in active_tickers:
            gate_stats["inactive_ticker"] += 1
            continue

        df = pd.read_csv(file_path, parse_dates=True, index_col=0)
        if len(df) < 60:
            gate_stats["insufficient_data"] += 1
            continue

        df = calculate_indicators(df)
        signal, notes = scan_asset(df)

        if signal == "IGNORE":
            gate_stats[signal] += 1
            logger.debug(f"{ticker} rejected: {notes}")
            continue

        row = df.iloc[-1]
        results.append({
            "Symbol": ticker,
            "Setup Type": signal,
            "Close": round(row["Close"], 2),
            "EMA20": round(row["EMA20"], 2),
            "EMA50": round(row["EMA50"], 2),
            "RSI": round(row["RSI14"], 1),
            "ATR": round(row["ATR14"], 2),
            "Notes": notes
        })

    if results:
        summary_df = pd.DataFrame(results)
        today_str = datetime.now().strftime("%Y-%m-%d")
        output_path = LOGS_DIR / f"swing_setups_{today_str}.csv"
        summary_df.to_csv(output_path, index=False)
        print(summary_df.to_markdown(index=False))
        logger.info(f"Archive created: {output_path}")
    else:
        logger.warning("No valid swing setups found.")

    logger.info("Scanner rejection summary:")
    for gate, count in gate_stats.items():
        logger.info(f"  {gate}: {count}")

# ============================================================
# Entry
# ============================================================


if __name__ == "__main__":
    run_scanner()
