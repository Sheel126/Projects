# Finance Vibe — Trader Guide (plain English)

This guide is for **traders**, not developers. It explains **what you get** after running Finance Vibe, what the outputs mean, and a simple glossary of the indicators used.

> Not financial advice. This is a screening + planning tool. Always sanity-check with a chart and your own risk rules.

---

## What Finance Vibe gives you

When you run the project, it produces two main CSV outputs in `data/logs/`:

- **Swing Setups**: `swing_setups_YYYY-MM-DD.csv`
  - A shortlist of tickers that match a *pullback-in-trend* setup (long or short).
- **Trade Plan**: `trade_plan_YYYY-MM-DD.csv`
  - A structured plan for each setup: entry, stop, targets, and an options-friendly suggestion (LEAPS type, expiry window, delta range).

It also stores the downloaded historical price data in `data/raw/` so everything is auditable and repeatable.

---

## Quick start (what to do as a trader)

1. Run the pipeline:

```bash
python src/finance_vibe/run_vibe.py
```

2. Open the newest files in `data/logs/`:
   - `swing_setups_YYYY-MM-DD.csv`
   - `trade_plan_YYYY-MM-DD.csv`

3. For each ticker:
   - Pull up a chart (weekly works best here)
   - Confirm the trend and the pullback visually
   - Decide if the plan fits your risk tolerance and time horizon

---

## Output 1: Swing Setups (what the columns mean)

This file is your **watchlist of “actionable” charts**.

Columns you’ll see:

- **Symbol**
  - The ticker.
- **Setup Type**
  - `SETUP_LONG`: bullish pullback setup
  - `SETUP_SHORT`: bearish pullback setup
- **Close**
  - Latest closing price (latest bar).
- **EMA20**
  - “Fast” trend line used like a pullback/support area.
- **EMA50**
  - “Slower” trend line used as the trend backbone / larger support area.
- **RSI**
  - Momentum heat gauge (0–100).
- **ATR**
  - How much the ticker tends to move (used to size stops/targets).
- **Notes**
  - A short human-readable reason (example: “Pullback into 20EMA”).

### How to read the Swing Setups file

- **If it’s `SETUP_LONG`**:
  - The tool is trying to find an uptrend and a pullback into a “buyable area” near the EMA20, with momentum turning back up.
- **If it’s `SETUP_SHORT`**:
  - It’s the mirror image: downtrend + pullback into EMA20, with bearish momentum returning.

---

## Output 2: Trade Plan (what the columns mean)

This file turns a setup into a **structured plan**. It’s meant to be reviewed and adjusted, not blindly executed.

Columns you’ll see:

- **Symbol**, **Setup Type**
  - Same meaning as above.
- **Stock Entry**
  - A suggested entry zone (built from EMA20 and a small volatility cushion).
- **Stock Stop**
  - A suggested invalidation level (anchored near EMA50 with a volatility cushion).
- **Target 1**, **Target 2**
  - Profit targets based on the ticker’s typical movement (ATR).
- **LEAPS Type**
  - `CALL` for long setups, `PUT` for short setups.
- **LEAPS Expiry Min / Max**
  - A suggested expiry *window* (not a single date): roughly 12–24 months out.
- **Suggested Delta**
  - A delta range (higher delta behaves more like stock; lower delta is more lottery-like).
- **Risk Notes**
  - Short note explaining the stop logic.

### How to use the Trade Plan (simple workflow)

- Start with **Stock Entry** and **Stock Stop**
  - Ask: “If I enter here and I’m wrong, is the stop acceptable for my account?”
- Then evaluate targets
  - Ask: “Does Target 1/2 give enough reward compared to the stop?”
- If you trade options
  - Use LEAPS fields as a *starting point* for contract selection (direction + timeframe + delta style).

---

## Optional Output 3: AI Review

If you want a plain-English second opinion on each setup, you can run:

```bash
python src/finance_vibe/ai_reviewer.py
```

This creates:

- `trade_plan_ai_YYYY-MM-DD.csv`
- `trade_plan_ai_YYYY-MM-DD.json`

The AI review adds fields like:

- **AI Recommendation**
  - `TAKE`, `WATCH`, or `SKIP`
- **AI Time Horizon**
  - A rough holding window like `1-3 weeks`
- **AI Confidence**
  - A simple confidence score from 0 to 1
- **AI Risk Flags**
  - Short warnings such as `earnings_soon`, `news_unavailable`, or other setup risks
- **AI Rationale**
  - Short plain-English reasons the setup still looks interesting, weak, or risky
- **AI Invalidations**
  - What would clearly make the setup fail from the AI's point of view

### How to think about the AI review

- It is a **helper layer**, not a replacement for the chart or your own judgment.
- The main value is turning the setup into a fast, readable summary:
  - What looks good
  - What looks risky
  - What would invalidate the idea
- If you want this to run automatically after the normal pipeline, set:

```bash
FINANCE_VIBE_ENABLE_AI_REVIEW=1
```

before running `run_vibe.py`.

---

## Indicator glossary (beginner → practical)

These indicators are used because each answers a different trading question.

### EMA (Exponential Moving Average): **trend + pullback location**

- **What it is**
  - A moving average that reacts faster to recent price.
- **Why it’s useful**
  - Helps define “trend direction” and common pullback/support zones.
- **How to think about it**
  - **EMA20**: the “breathing line” in a trend (pullbacks often tag it).
  - **EMA50**: the “trend backbone” (if this breaks, the idea may be wrong).

### RSI (Relative Strength Index): **momentum temperature**

- **What it is**
  - A 0–100 gauge of recent up-moves vs down-moves.
- **Why it’s useful**
  - Helps avoid buying when something is already overheated (or shorting when it’s washed out).
- **Simple mental model**
  - Low RSI: weak / sold off
  - High RSI: strong / possibly stretched
  - Middle RSI: often “healthy trend” territory (context matters)

### MACD Histogram: **momentum turning**

- **What it is**
  - A momentum indicator showing acceleration/deceleration (not just direction).
- **Why it’s useful**
  - Helps spot when momentum is **rebuilding** after a pullback (or rolling over after a bounce).
- **Simple mental model**
  - Histogram rising: momentum improving
  - Histogram falling: momentum fading

### ATR (Average True Range): **how wild the ticker is**

- **What it is**
  - A measure of typical movement per bar (volatility), not direction.
- **Why it’s useful**
  - Great for building realistic stops/targets: high-volatility tickers need more room; low-volatility tickers need less.
- **Simple mental model**
  - ATR is “how much it usually wiggles.”

---

## Why this combination is practical for swing trading

This is the core idea the tool is trying to capture:

- **Trend filter** (EMA structure): don’t fight the bigger move.
- **Pullback entry** (price near EMA20): don’t chase.
- **Momentum confirmation** (RSI + MACD histogram behavior): don’t buy a pullback that’s still falling.
- **Risk structure** (ATR-based levels): build a plan that matches the ticker’s personality.

---

## Common “sanity checks” before taking a trade

- **Chart check**
  - Does it *look* like an uptrend/downtrend on the timeframe you trade?
- **Support/resistance**
  - Is your entry right into a major resistance (for longs) or support (for shorts)?
- **Event risk**
  - Earnings, macro events, or news can blow through technical levels.
- **Liquidity**
  - Options and smaller tickers can have spreads that make the plan unrealistic.

---

## FAQ (quick answers)

- **Why weekly data?**
  - Weekly bars reduce noise and focus on swing-worthy moves. It’s slower, but often cleaner.

- **Are the levels exact?**
  - No. Treat them as a **structured starting point**. Real execution depends on your style (limit vs market, scaling, etc.).

- **What if I don’t trade options?**
  - Ignore LEAPS fields. The stock plan (entry/stop/targets) is still useful.

---

## Where to look next

- If you want more setups: adjust the ticker universe (what symbols are scanned).
- If you want tighter/looser plans: adjust how ATR is used for stops/targets.
- If you want a ranking score: explore the “Vibe score” reports (separate from the swing setup flow).

