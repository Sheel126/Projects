# Finance Vibe Setup and Environment Runbook

This runbook lists everything needed to run the project and all supported environment variable overrides.

## 1) Prerequisites

- Python 3.12+ (project currently runs on your local Python as well)
- `pip` package manager
- Internet access for market data and optional AI/news APIs

Install dependencies (if not already installed in your environment):

```bash
pip install -r requirements.txt
```

If your repo does not have `requirements.txt`, use the existing environment where the project currently runs.

## 2) Core Commands

Run full pipeline:

```bash
python src/finance_vibe/run_vibe.py
```

Run AI review only:

```bash
python src/finance_vibe/ai_reviewer.py
```

## 3) Required vs Optional Environment Variables

### 3.1 Required only for AI review

- `OPENAI_API_KEY`  
  Required for `ai_reviewer.py` to call the LLM endpoint.

### 3.2 Optional AI provider settings

- `OPENAI_BASE_URL` (default: `https://api.openai.com/v1`)  
  Use this for OpenAI-compatible providers.
- `FINANCE_VIBE_AI_MODEL` (default: `gpt-4.1-mini`)
- `FINANCE_VIBE_AI_TIMEOUT_SECONDS` (default: `45`)
- `FINANCE_VIBE_AI_MAX_RETRIES` (default: `2`)
- `FINANCE_VIBE_AI_BATCH_SIZE` (default: `5`)
- `FINANCE_VIBE_AI_MAX_TICKERS` (default: `0`)  
  `0` means no cap (process all selected rows).

### 3.3 Optional AI input source and symbol selection

- `FINANCE_VIBE_AI_SOURCE` (default: `trade_plan`)  
  - `trade_plan`: only scanner-qualified setups (strict technical filter)
  - `vibe_report`: broad universe from vibe report (more symbols)
- `FINANCE_VIBE_AI_SYMBOLS` (optional)  
  Comma-separated list of symbols to review exactly, for example:
  `AAPL,MSFT,NVDA,AMD`

### 3.4 Optional News API settings

General:
- `FINANCE_VIBE_NEWS_PROVIDER` (set `eventregistry` for Event Registry)
- `FINANCE_VIBE_NEWS_API_URL`
- `FINANCE_VIBE_NEWS_API_KEY`
- `FINANCE_VIBE_NEWS_API_KEY_HEADER` (default: `Authorization`)
- `FINANCE_VIBE_NEWS_MAX_HEADLINES` (default: `3`)
- `FINANCE_VIBE_NEWS_LOOKBACK_DAYS` (default: `5`)
- `FINANCE_VIBE_NEWS_SLEEP_SECONDS` (default: `0.5`)

Also accepted aliases for compatibility:
- URL: `NEWS_API_URL`, `EVENTREGISTRY_API_URL`
- KEY: `NEWS_API_KEY`, `EVENTREGISTRY_API_KEY`, `news.api.key`

Event Registry example:

```bash
export FINANCE_VIBE_NEWS_PROVIDER=eventregistry
export FINANCE_VIBE_NEWS_API_URL="https://eventregistry.org/api/v1/article/getArticles"
export FINANCE_VIBE_NEWS_API_KEY="<your_eventregistry_key>"
```

### 3.5 Optional pipeline toggle

- `FINANCE_VIBE_ENABLE_AI_REVIEW`
  - `1`: run AI review automatically at end of `run_vibe.py`
  - `0`: skip AI step

## 4) Common Run Recipes

### A) Full pipeline + AI auto-review

```bash
export FINANCE_VIBE_ENABLE_AI_REVIEW=1
export OPENAI_API_KEY="<your_openai_key>"
python src/finance_vibe/run_vibe.py
```

### B) AI review for all available broad-universe tickers

```bash
export OPENAI_API_KEY="<your_openai_key>"
export FINANCE_VIBE_AI_SOURCE=vibe_report
export FINANCE_VIBE_AI_MAX_TICKERS=0
python src/finance_vibe/ai_reviewer.py
```

### C) AI review for only symbols you choose

```bash
export OPENAI_API_KEY="<your_openai_key>"
export FINANCE_VIBE_AI_SOURCE=vibe_report
export FINANCE_VIBE_AI_SYMBOLS="AAPL,MSFT,NVDA,AMD,TSLA"
python src/finance_vibe/ai_reviewer.py
```

### D) Strict setup-only review (scanner-qualified)

```bash
export OPENAI_API_KEY="<your_openai_key>"
export FINANCE_VIBE_AI_SOURCE=trade_plan
python src/finance_vibe/ai_reviewer.py
```

## 5) Output Files You Should Expect

Pipeline outputs in `data/logs/`:
- `vibe_report_YYYY-MM-DD.csv`
- `vibe_report_local_YYYY-MM-DD.csv`
- `swing_setups_YYYY-MM-DD.csv`
- `trade_plan_YYYY-MM-DD.csv`
- `trade_plan_clean_YYYY-MM-DD.csv`

AI outputs (new file each run, timestamped):
- `trade_plan_ai_<source-date>_<run-timestamp>.csv`
- `trade_plan_ai_<source-date>_<run-timestamp>.json`

## 6) Buy/Sell Timeline Fields in AI Output

The AI CSV includes:
- `AI Buy Timing`: when to consider entering
- `AI Sell Timing`: when to take profits / exit
- `AI Time Horizon`: expected holding window
- `Target 1`, `Target 2`, `Stock Stop`: concrete levels for planning exits and invalidation

This is now explicitly designed to answer "when to buy" and "when to sell" for selected tickers.

## 7) Troubleshooting

- If AI rows show `ai_unavailable`:
  - verify `OPENAI_API_KEY`
  - verify `OPENAI_BASE_URL` (if using non-default provider)
- If news is empty or flagged:
  - verify Event Registry provider/url/key vars
- If only a few symbols appear in `trade_plan` mode:
  - that is expected due to strict scanner filters; use `vibe_report` mode for broader coverage
- If terminal crashes on emoji/encoding:
  - use current updated scripts (ASCII-safe console prints)
