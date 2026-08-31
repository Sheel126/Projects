#!/usr/bin/env python3
"""
ai_studio_scanner_analyst.py

Standalone Google AI Studio Market Analyst utility using Gemini 3.6 Flash.
Pulls credentials and environment setup directly from .env without touching pipeline code.
Exports the output report directly to the source CSV file's directory.
"""

import argparse
import os
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv
from google import genai
from google.genai import types

# Load environment variables (GEMINI_API_KEY)
load_dotenv()


def find_project_root(script_path: Path) -> Path:
    """Finds the true project root containing the 'data' directory."""
    current = script_path.resolve().parent
    for _ in range(4):
        if (current / "data").exists():
            return current
        if current.parent == current:
            break
        current = current.parent

    if Path("/app/data").exists():
        return Path("/app")
    return Path.cwd()


def get_today_csv_data(
    mode: str, root_dir: Path, custom_filename: str | None = None
) -> tuple[str, Path]:
    """
    Dynamically constructs today's date (YYYY-MM-DD) and searches for:
    {root_dir}/data/logs/{mode}/coiled_cobra_setups_YYYY-MM-DD.csv
    """
    log_dir = root_dir / "data" / "logs" / mode
    if not log_dir.exists():
        raise FileNotFoundError(f"Directory not found: {log_dir}")

    today_str = datetime.now().strftime("%Y-%m-%d")
    if custom_filename:
        target_filename = custom_filename
    else:
        target_filename = f"coiled_cobra_setups_{today_str}.csv"

    target_file = log_dir / target_filename

    if not target_file.exists():
        matching_files = list(log_dir.glob(f"*{today_str}*.csv"))
        if matching_files:
            target_file = matching_files[0]
        else:
            raise FileNotFoundError(
                f"Could not find today's scan file '{target_filename}' in {log_dir}. "
                f"Please ensure your market scanner ran for date: {today_str}"
            )

    with open(target_file, "r", encoding="utf-8") as f:
        content = f.read()

    return content, target_file


def run_studio_analysis(csv_data: str) -> str:
    """Executes the 4-point quantitative analysis using Gemini 3.6 Flash."""
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY environment variable is missing.")

    client = genai.Client(api_key=api_key)

    system_instruction = """
    You are an AI Quantitative Portfolio Manager and Lead Market Analyst reviewing daily momentum setups.
    Analyze the provided end-of-day market scanner CSV data and deliver a structured report addressing these 4 core tasks:

    1. ZERO-SHOT TECHNICAL ANALYSIS & RANK VALIDATION
       - Classify tickers into 3 Tiers: Core Buys, Secondary Watchlist, and Rejects.
       - Highlight over-extended candidates (e.g., Pct_From_EMA20 > 10% or RSI > 70).
       - Flag explicit disagreements between Machine Learning predictions (ML_Rank/ML_Pred_Return) and Mechanical Scores.

    2. STANDARDIZED EXECUTIVE SUMMARY & TAIL RISK
       - Top 3 Setup Candidates with proposed entries and ATR-based stops.
       - Tail-Risk Warnings regarding missing fields (e.g. Regime OK), volatility anomalies, or overextensions.

    3. POSITION SIZING & RISK ALLOCATION
       - Calculate position sizing for Top Candidates assuming a standard $100k portfolio with 1% risk per trade ($1,000 risk).
       - Use the ATR and Swing Low to define exact Stop-Loss prices and exact Share Quantities to buy.
       - Define multi-stage Profit Targets at 1.5R and 3.0R reward-to-risk ratios.

    4. SECTOR CONCENTRATION & MARKET REGIME FILTER
       - Group candidates by sector/industry theme to identify clustered exposure.
       - Flag liquidity/execution risks (e.g. low absolute stock price, elevated ATR_Pct > 5%).
       - Provide a final Portfolio Allocation Plan prioritizing setups with high RS_63d and positive ML_Pred_Return.
    """

    response = client.models.generate_content(
        model="gemini-3.6-flash",
        config=types.GenerateContentConfig(system_instruction=system_instruction),
        contents=f"### TODAY'S EOD SCANNER DATA:\n\n{csv_data}",
    )

    return response.text


def main():
    parser = argparse.ArgumentParser(
        description="Finance-Vibe AI Studio Scanner Analyst"
    )

    # Change --mode from an optional flag to a positional argument with fallback default
    parser.add_argument(
        "mode",
        nargs="?",
        default="daily",
        help="Execution profile mode (weekly, daily, high_beta)",
    )
    parser.add_argument(
        "--filename",
        help="Optional specific CSV filename to analyze instead of today's date",
    )

    args = parser.parse_args()


    root_dir = find_project_root(Path(__file__))
    today_str = datetime.now().strftime("%Y-%m-%d")

    print(
        f"⚡ [AI Studio] Locating scanner file for date [{today_str}] in mode: '{args.mode}'..."
    )
    csv_data, target_file = get_today_csv_data(args.mode, root_dir, args.filename)
    print(f"📄 Loaded target file: {target_file.resolve()}")

    print("🧠 Querying Gemini 3.6 Flash via Google GenAI SDK...")
    analysis_report = run_studio_analysis(csv_data)

    # Output file saved directly inside the same directory as the source CSV file
    source_dir = target_file.parent
    output_filename = f"ai_studio_report_{today_str}.md"
    output_path = source_dir / output_filename

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(analysis_report)

    print(
        f"✅ Master Analysis Report successfully written to source folder:\n   {output_path.resolve()}"
    )


if __name__ == "__main__":
    main()
