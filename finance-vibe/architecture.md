# Finance-Vibe Paper Trading Bot — Architecture

## Scope (Phase 1 + 2)

| Phase | Goal | Duration |
|-------|------|----------|
| **1 — Build** | Alpaca paper bot + Ollama agent + dashboard, runnable Monday | Days 1–2 |
| **2 — Paper trial** | Autonomous 15-min cycles, EOD review, prompt/tuning | Up to 14 days |

Live money ($500–1k) is **out of scope** until paper proves edge.

---

## System Diagram

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         SCHEDULER (APScheduler)                          │
│   Pre-market 9:00 ET │ Cycles every 15m 9:30–15:45 ET │ EOD 16:05 ET   │
└───────────────────────────────────┬─────────────────────────────────────┘
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                              RUNNER                                      │
│  1. Market-hours gate  2. Load account  3. Build context  4. Decide     │
│  5. Risk guard  6. Execute  7. Persist  8. Check stops                  │
└───────┬─────────────────┬──────────────────────┬────────────────────────┘
        ▼                 ▼                      ▼
┌───────────────┐ ┌───────────────┐    ┌────────────────┐
│ INDICATOR     │ │ OLLAMA AGENT  │    │ ALPACA CLIENT  │
│ PACK          │ │ (Qwen)        │    │ (paper API)    │
│ finance-vibe  │ │ JSON actions  │    │ quotes/orders  │
│ swing + levels│ │ BUY/SELL/HOLD │    │ positions      │
└───────────────┘ └───────────────┘    └────────────────┘
        │                 │                      │
        └─────────────────┴──────────────────────┘
                          ▼
                 ┌─────────────────┐
                 │ SQLite STORE    │
                 │ cycles/decisions│
                 │ orders/snapshots│
                 └────────┬────────┘
                          ▼
                 ┌─────────────────┐
                 │ FLASK DASHBOARD │
                 │ :5001           │
                 └─────────────────┘
```

---

## Design Choices

### 1. Finance-Vibe as indicator layer, Qwen as portfolio brain

- **Deterministic:** EMA stack, RSI, ATR, swing setup detection, entry/stop/target from `trade_planner` / `config.compute_swing_levels`.
- **LLM:** Compares all watchlist names, rotation logic (sell extended green → buy supported red), outputs structured JSON. Never sets prices without indicator anchors.
- **Python risk guard:** Final gate — position limits, stops required on buys, daily loss halt. LLM cannot override.

This matches industry pattern (Alpaca multi-agent article, TradingAgents): **LLM proposes, code disposes.**

### 2. Alpaca paper for Phase 1–2

- Official API, free paper account (~$100k simulated).
- Same order/position endpoints as live.
- Schwab/Robinhood adapter added later as a thin `BrokerClient` swap.

### 3. Data sources

| Data | Source | Use |
|------|--------|-----|
| Daily OHLCV (120 bars) | Alpaca `StockBars` | Finance-Vibe indicators, setup detection |
| Intraday snapshot | Alpaca `latest quote` + `snapshot` | `change_pct`, bid/ask |
| Benchmark QQQ | Alpaca daily bars | Regime / relative strength (high_beta profile) |
| Account / positions | Alpaca Trading API | Sizing, rotation, P&L |

Yahoo (`yfinance`) is **fallback** if Alpaca data fails for a ticker.

### 4. Swing profile: `high_beta`

- Long-only, QQQ regime gate, relative strength — fits active single-name basket.
- No options; stock/fractional only.

### 5. SQLite persistence (`data/bot/trading_bot.db`)

| Table | Purpose |
|-------|---------|
| `cycles` | Each 15-min run: timestamp, context JSON, LLM response, status |
| `decisions` | Parsed actions per cycle: ticker, action, size, stop, approved/rejected |
| `orders` | Alpaca order IDs linked to decisions |
| `equity_snapshots` | Equity/cash after each cycle (equity curve) |
| `daily_reports` | EOD summary: P&L, trades, halt flags |
| `bot_state` | Key-value: `day_start_equity`, `halted_until`, `last_cycle_id` |

Enables EOD review without parsing logs.

### 6. Aggressive paper risk (tunable via `.env`)

| Parameter | Default | Rationale |
|-----------|---------|-----------|
| `RISK_PER_TRADE_PCT` | 3% | Meaningful moves on $100k paper |
| `MAX_POSITIONS` | 3 | Rotation across 8-name basket |
| `MAX_POSITION_PCT` | 35% | Allow concentration on best idea |
| `DAILY_LOSS_HALT_PCT` | 5% | Stop bot for rest of day |
| `CYCLE_MINUTES` | 15 | Balance API limits vs responsiveness |

Live ($500+) will use lower risk — not configured until Phase 3.

### 7. Dashboard on port 5001

Separate from existing `app.py` (5000) to avoid breaking the trade-plan browser. Polls SQLite + Alpaca every 30s for equity, positions, recent LLM decisions, cycle log.

### 8. Ollama integration

- HTTP `POST /api/chat` to local Ollama.
- Model from `OLLAMA_MODEL` (e.g. `qwen2.5:7b`).
- Strict JSON schema in prompt; parser validates with fallback to HOLD-all if malformed.
- `OLLAMA_ENABLED=false` runs **indicator-only** mode (buys top setup, sells at target/stop rules) for debugging without GPU.

### 9. Execution rules

- **BUY:** Limit at mid or last trade; bracket stop via separate stop order (Alpaca paper supports stop/stop_limit).
- **SELL:** Market or limit at bid for rotation exits.
- **HOLD:** No order.
- Fractional shares enabled where Alpaca allows.
- Stops checked each cycle; missing stop on open position → place protective stop from store.

### 10. Market hours

- US equities regular session only (9:30–16:00 ET).
- Cycles: 9:30, 9:45, … 15:45; EOD report 16:05.
- Pre-market cycle 9:00: ingest + optional GTC limits (no trades before 9:30).

---

## Phase 1 Deliverables

- `src/finance_vibe/bot/` package (config, store, alpaca, indicators, ollama, risk, executor, runner, dashboard)
- `.env.example` with all keys
- `user.md` runbook
- Unit tests for risk guard, JSON parsing, store

## Phase 2 Operations (you)

1. **Each morning:** Start runner + dashboard before 9:30 ET.
2. **Each EOD:** Review dashboard daily report + equity curve.
3. **Tune:** Adjust watchlist, `OLLAMA_MODEL`, risk %, or prompt notes in `.env` (`BOT_STRATEGY_NOTES`).
4. **Go/no-go at day 14:** Net paper P&L positive with acceptable drawdown → plan live $500–1k on Schwab.

---

## File Layout

```
src/finance_vibe/bot/
  __init__.py
  config.py          # env + watchlist
  models.py          # dataclasses
  store.py           # SQLite
  market_hours.py    # ET session checks
  alpaca_client.py   # broker wrapper
  indicator_pack.py  # finance-vibe signals
  ollama_agent.py    # Qwen decisions
  risk_guard.py      # hard limits
  executor.py        # order placement
  runner.py          # cycle orchestration + CLI
  dashboard.py       # Flask UI
data/bot/
  trading_bot.db     # created at runtime
```

---

## Failure Modes

| Failure | Behavior |
|---------|----------|
| Ollama down | Skip LLM; log warning; optional rule-based fallback |
| Alpaca API error | Retry 3×; skip cycle; alert in dashboard |
| Invalid LLM JSON | HOLD all; log raw response |
| Daily loss halt | No new buys; allow sells/stops only |
| Outside market hours | Runner sleeps or exits `--once` with message |
