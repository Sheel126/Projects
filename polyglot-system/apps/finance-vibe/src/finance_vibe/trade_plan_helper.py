# src/finance_vibe/trade_plan_helper.py

import pandas as pd
from pathlib import Path

# ---- Config ----
TRADE_PLAN_DIR = Path("./data/logs")


def get_latest_trade_plan_csv() -> Path:
    candidates = sorted(
        TRADE_PLAN_DIR.glob("trade_plan_*.csv"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    # Exclude derivatives produced later in the pipeline.
    candidates = [
        p for p in candidates if not p.name.startswith(("trade_plan_clean_", "trade_plan_ai_"))
    ]
    if not candidates:
        raise FileNotFoundError(f"No trade plan CSV found in {TRADE_PLAN_DIR}")
    return candidates[0]


scanner_csv = get_latest_trade_plan_csv()
date_str = scanner_csv.stem.replace("trade_plan_", "")

# ---- Read CSV safely ----
try:
    df = pd.read_csv(scanner_csv)
except FileNotFoundError:
    print(f"ERROR: File not found: {scanner_csv}")
    exit(1)

# Strip any whitespace from column headers
df.columns = df.columns.str.strip()

print("Loaded CSV columns:", df.columns.tolist())

# ---- Convert numeric columns safely ----
numeric_cols = ["Stock Entry", "Stock Stop", "Target 1", "Target 2"]
numeric_cols_existing = [c for c in numeric_cols if c in df.columns]

for col in numeric_cols_existing:
    df[col] = pd.to_numeric(df[col], errors="coerce")

# ---- Parse Suggested Delta ----
if "Suggested Delta" in df.columns:
    delta_split = df["Suggested Delta"].astype(
        str).str.split("–|-", expand=True)
    if delta_split.shape[1] == 2:
        df["Delta Min"] = pd.to_numeric(delta_split[0], errors="coerce")
        df["Delta Max"] = pd.to_numeric(delta_split[1], errors="coerce")
    else:
        print("⚠️ Could not parse Suggested Delta properly. Check format.")

# ---- Optional: Inspect first few rows ----
print("\nTrade Plan Preview:")
print(df.head(10).to_markdown(index=False))

# ---- Save cleaned CSV if needed ----
clean_csv = TRADE_PLAN_DIR / f"trade_plan_clean_{date_str}.csv"
df.to_csv(clean_csv, index=False)
print(f"\nCleaned trade plan saved: {clean_csv}")
