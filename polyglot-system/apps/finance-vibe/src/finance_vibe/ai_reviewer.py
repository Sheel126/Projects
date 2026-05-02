from __future__ import annotations

import json
import os
import sys
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import List

import pandas as pd


_FILE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(_FILE_DIR, "../../"))
SRC_PATH = os.path.join(PROJECT_ROOT, "src")

if SRC_PATH not in sys.path:
    sys.path.insert(0, SRC_PATH)

try:
    from finance_vibe import config
    from finance_vibe.ai_client import analyze_tickers_stream
    from finance_vibe.ai_models import AIAnalysisResult
    from finance_vibe.news_fetcher import NewsFetcher
except ImportError as exc:
    print(f"Import error: {exc}")
    sys.exit(1)


TRADE_PLAN_PREFIXES = ("trade_plan_clean_", "trade_plan_")
VIBE_REPORT_PREFIXES = ("vibe_report_local_", "vibe_report_")


def get_latest_trade_plan_path() -> Path:
    logs_dir = Path(config.LOGS_DIR)
    candidates: list[Path] = []

    for prefix in TRADE_PLAN_PREFIXES:
        candidates.extend(logs_dir.glob(f"{prefix}*.csv"))

    if not candidates:
        raise FileNotFoundError("No trade plan CSVs found in data/logs.")

    # Prefer cleaned file on same date; otherwise latest by filename date.
    candidates.sort(key=lambda p: (p.stem.split("_")[-1], "clean" in p.stem), reverse=True)
    return candidates[0]


def get_latest_vibe_report_path() -> Path:
    logs_dir = Path(config.LOGS_DIR)
    candidates: list[Path] = []
    for prefix in VIBE_REPORT_PREFIXES:
        candidates.extend(logs_dir.glob(f"{prefix}*.csv"))
    if not candidates:
        raise FileNotFoundError("No vibe report CSVs found in data/logs.")
    candidates.sort(key=lambda p: (p.stem.split("_")[-1], "local" in p.stem), reverse=True)
    return candidates[0]


def get_output_date_str(input_path: Path) -> str:
    return input_path.stem.split("_")[-1]


def load_trade_plan_rows(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    df.columns = df.columns.str.strip()
    return df


def build_rows_from_vibe_report(path: Path) -> pd.DataFrame:
    """
    Convert vibe report rows into a trade-plan-like dataframe so AI review can
    run across the full ticker universe when desired.
    """
    vibe_df = pd.read_csv(path)
    vibe_df.columns = vibe_df.columns.str.strip()

    rows: list[dict] = []
    for _, row in vibe_df.iterrows():
        symbol = str(row.get("Ticker", "")).strip().upper()
        if not symbol:
            continue
        price = pd.to_numeric(row.get("Price"), errors="coerce")
        sma50 = pd.to_numeric(row.get("SMA50"), errors="coerce")
        score = pd.to_numeric(row.get("Score"), errors="coerce")
        if pd.isna(price):
            continue

        # Heuristic levels for non-scanner mode.
        setup_type = "SETUP_LONG" if pd.isna(score) or score >= 0 else "SETUP_SHORT"
        stop = sma50 if not pd.isna(sma50) else price * (0.94 if setup_type == "SETUP_LONG" else 1.06)
        move = abs(price - stop)
        if move == 0:
            move = price * 0.03
        if setup_type == "SETUP_LONG":
            target_1 = price + move
            target_2 = price + (2 * move)
            leaps_type = "CALL"
            delta = "0.65 - 0.8"
        else:
            target_1 = price - move
            target_2 = price - (2 * move)
            leaps_type = "PUT"
            delta = "-0.8 - -0.65"

        rows.append(
            {
                "Symbol": symbol,
                "Setup Type": setup_type,
                "Stock Entry": round(float(price), 2),
                "Stock Stop": round(float(stop), 2),
                "Target 1": round(float(target_1), 2),
                "Target 2": round(float(target_2), 2),
                "LEAPS Type": leaps_type,
                "LEAPS Expiry Min": "",
                "LEAPS Expiry Max": "",
                "Suggested Delta": delta,
                "Risk Notes": "Heuristic levels generated from vibe report; validate before entry.",
            }
        )

    return pd.DataFrame(rows)


def parse_symbol_selection() -> set[str]:
    raw = os.getenv("FINANCE_VIBE_AI_SYMBOLS", "").strip()
    if not raw:
        return set()
    return {s.strip().upper() for s in raw.split(",") if s.strip()}


def apply_symbol_selection(df: pd.DataFrame, selected_symbols: set[str]) -> pd.DataFrame:
    if not selected_symbols:
        return df
    return df[df["Symbol"].astype(str).str.upper().isin(selected_symbols)].copy()


def build_ai_input_rows(df: pd.DataFrame, news_fetcher: NewsFetcher) -> List[dict]:
    rows: List[dict] = []
    limited_df = df.copy()
    if config.AI_MAX_TICKERS_PER_RUN > 0:
        limited_df = limited_df.head(config.AI_MAX_TICKERS_PER_RUN)

    for _, row in limited_df.iterrows():
        symbol = str(row.get("Symbol", "")).strip().upper()
        setup_type = str(row.get("Setup Type", "SETUP_LONG")).strip()

        news = news_fetcher.fetch_for_symbol(symbol)

        rows.append(
            {
                "Symbol": symbol,
                "Setup Type": setup_type,
                "Stock Entry": row.get("Stock Entry"),
                "Stock Stop": row.get("Stock Stop"),
                "Target 1": row.get("Target 1"),
                "Target 2": row.get("Target 2"),
                "LEAPS Type": row.get("LEAPS Type"),
                "LEAPS Expiry Min": row.get("LEAPS Expiry Min"),
                "LEAPS Expiry Max": row.get("LEAPS Expiry Max"),
                "Suggested Delta": row.get("Suggested Delta"),
                "Risk Notes": row.get("Risk Notes"),
                "News Flags": news.flags,
                "News Headlines": [asdict(headline) for headline in news.headlines],
            }
        )

    return rows


def ai_results_to_dataframe(results: List[AIAnalysisResult]) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "Symbol": result.symbol,
                "Setup Type": result.setup_type,
                "AI Recommendation": result.recommendation,
                "AI Time Horizon": result.time_horizon,
                "AI Confidence": result.confidence,
                "AI Risk Flags": "; ".join(result.risk_flags),
                "AI Rationale": " | ".join(result.rationale_bullets),
                "AI Invalidations": " | ".join(result.invalidations),
                "AI Action Plan": " | ".join(result.action_plan),
                "AI Beginner Notes": " | ".join(result.beginner_notes),
                "AI Position Size Hint": result.position_size_hint,
                "AI Buy Timing": result.buy_timing,
                "AI Sell Timing": result.sell_timing,
                "AI Status": result.status,
                "AI News Headlines": json.dumps(
                    [asdict(headline) for headline in result.news_headlines],
                    ensure_ascii=False,
                ),
                "AI Raw Output": result.raw_model_output or "",
            }
            for result in results
        ]
    )


def write_outputs(merged_df: pd.DataFrame, results: List[AIAnalysisResult], date_str: str) -> None:
    run_stamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    csv_path = Path(config.LOGS_DIR) / f"trade_plan_ai_{date_str}_{run_stamp}.csv"
    json_path = Path(config.LOGS_DIR) / f"trade_plan_ai_{date_str}_{run_stamp}.json"

    merged_df.to_csv(csv_path, index=False)
    with json_path.open("w", encoding="utf-8") as fh:
        json.dump([asdict(result) for result in results], fh, ensure_ascii=False, indent=2)

    print(f"AI-reviewed trade plan saved: {csv_path}")
    print(f"AI-reviewed JSON saved: {json_path}")


def run_ai_review() -> pd.DataFrame:
    source = os.getenv("FINANCE_VIBE_AI_SOURCE", "trade_plan").strip().lower()
    if source == "vibe_report":
        input_path = get_latest_vibe_report_path()
        plan_df = build_rows_from_vibe_report(input_path)
    else:
        input_path = get_latest_trade_plan_path()
        plan_df = load_trade_plan_rows(input_path)

    date_str = get_output_date_str(input_path)
    print(f"Using AI source ({source}): {input_path}")
    print(f"Rows loaded before filtering: {len(plan_df)}")

    selected_symbols = parse_symbol_selection()
    plan_df = apply_symbol_selection(plan_df, selected_symbols)
    print(f"Rows after symbol selection: {len(plan_df)}")

    news_fetcher = NewsFetcher()
    ai_input_rows = build_ai_input_rows(plan_df, news_fetcher)

    if not ai_input_rows:
        print("No trade plan rows available for AI review.")
        return pd.DataFrame()

    results = analyze_tickers_stream(ai_input_rows, batch_size=config.AI_BATCH_SIZE)
    ai_df = ai_results_to_dataframe(results)
    merged = plan_df.merge(ai_df, on=["Symbol", "Setup Type"], how="left")

    write_outputs(merged, results, date_str)
    print("\nAI Trade Plan Preview:")
    print(merged.head(10).to_markdown(index=False))
    return merged


if __name__ == "__main__":
    run_ai_review()
