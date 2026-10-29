# Liquid ATM

A tax-aware, momentum swing-trading bot for highly liquid US equities and large ETFs, run through Alpaca.

**The funnel:** regime filter → screener (from about 1,000 names down to about 10) → local-LLM catalyst veto → limit entry with an ATR-sized bracket (TP/SL).
**Built into the core:** a 31-day wash-sale blacklist, a tax-lot ledger, a tax-reserve bucket, and a December flush.
**Running cost:** zero. Market data comes from free sources (Alpaca free tier, yfinance, SEC EDGAR), and the LLM is Qwen running locally through Ollama.

> This is research software. Paper trading only until the Phase 4 validation gate and at least one month of paper trading (Phase 8) pass.

## Layout

| Path | What | Language |
|---|---|---|
| `quant/` | data, signals, `backtest/` (event loop, fills, metrics), `tax/` (lots, wash sales, reserve), `baselines/`, and the LLM gateway. Emits **trade intents** | Python 3.12, FastAPI |
| `orchestrator/` | owns the DB schema (Flyway), and later the OMS, tax ledger and kill switches. The **only** component that moves money | Java 17, Spring Boot 3.5 |
| `db/init/` | one-time Postgres init (pgvector) | SQL |
| `quant/.../strategy/` | Phase 3 funnel: params, causal indicators, regime, screener, book | Python |
| `quant/.../investors/` | Phase 3b: eight famous-investor methods as rules, on point-in-time SEC fundamentals; Phase 3d: insider and 13F copying | Python |
| `quant/.../intraday/` | Phase 3d: minute bars, the after-tax intraday account, Noise Band, ORB, first-candle FVG | Python |
| `shared/tax-fixtures/` | 13 golden test vectors that both tax engines must pass | JSON |
| `docs/lessons/` | the *why* behind each phase; read these first | Markdown |

### Data jobs (Phase 1)

```bash
cd quant
.venv/Scripts/python -m liquid_atm_quant.data.cli sync-calendar --start 2005-01-01
.venv/Scripts/python -m liquid_atm_quant.data.cli sync-assets        # Alpaca assets, incl. delisted
.venv/Scripts/python -m liquid_atm_quant.data.cli universe-live      # today's Russell 1000 (iShares IWB)
.venv/Scripts/python -m liquid_atm_quant.data.cli universe-history   # Wayback IWB snapshots + S&P 500 history
.venv/Scripts/python -m liquid_atm_quant.data.cli bars               # SIP daily bars (raw + adj_factor)
.venv/Scripts/python -m liquid_atm_quant.data.cli yf-backfill        # ^VIX + pre-2016 ETF history
.venv/Scripts/python -m liquid_atm_quant.data.cli edgar              # 8-K/10-Q/10-K/Form 4 index
.venv/Scripts/python -m liquid_atm_quant.data.cli dq                 # data quality (exit 1 on errors)
.venv/Scripts/python -m liquid_atm_quant.data.cli coverage           # survivorship coverage by year
.venv/Scripts/python -m liquid_atm_quant.data.cli crosscheck         # Alpaca vs Yahoo returns
.venv/Scripts/python -m liquid_atm_quant.data.cli daily              # the incremental daily run
```

### Backtests and the tax engine (Phase 2)

```bash
cd quant
.venv/Scripts/python scripts/tax_fixtures.py          # 13/13 golden vectors, exit 1 on failure
.venv/Scripts/python scripts/run_backtest.py          # SPY buy-and-hold + naive momentum
.venv/Scripts/python scripts/run_backtest.py --strategy spy --cash 1000000.00
.venv/Scripts/python scripts/run_backtest.py --save    # store into backtest_runs (V5)
.venv/Scripts/python scripts/run_backtest.py --december-flush --json
```

A full 2016-2026 run over 1,781 symbols takes about 20 seconds, most of it loading the panel from
Postgres; the loop itself is under a second, because Phase 4 has to run it hundreds of times.

Headline results and the gate are in `docs/lessons/02-backtester-and-tax.md` §12.

### Strategy (Phase 3)

```bash
cd quant
.venv/Scripts/python scripts/run_backtest.py --strategy phase3 --save     # gate: SPY, momentum, funnel
.venv/Scripts/python scripts/run_backtest.py --strategy funnel --param stop_atr=2.5 --save   # a counted trial
.venv/Scripts/python scripts/funnel_forward_returns.py --horizon 21       # drift per screener stage
.venv/Scripts/python scripts/screen_today.py                              # tomorrow's intents, same code path
```

Funnel runs refuse to go past 2024-09-30 (the lockbox) without `--unlock-lockbox`.

### Investor strategies (Phase 3b)

```bash
cd quant
.venv/Scripts/python -m liquid_atm_quant.data.cli fundamentals            # SEC XBRL facts (1.4 GB, cached)
.venv/Scripts/python scripts/factor_prescreen.py --history                # free big-stock factor check
.venv/Scripts/python scripts/run_investors.py --save --json ../docs/phase3b/results.json
```

### Research screen and exposure strategies (Phase 3c)

```bash
cd quant
.venv/Scripts/python scripts/research_screen.py --fetch          # free 1960+ series, cached
.venv/Scripts/python scripts/research_screen.py                  # published rules on 1960-2015: no trials
.venv/Scripts/python scripts/research_screen.py --calibrate      # synthetic 2x vs real SSO
.venv/Scripts/python scripts/run_investors.py --only vol_trend --save --label phase3c
```

### Copying and intraday strategies (Phase 3d)

```bash
cd quant
.venv/Scripts/python scripts/fetch_minutes.py SPY                # 1-minute SPY 2016..2024-09 (Alpaca, free)
.venv/Scripts/python scripts/fetch_minutes.py --orb-opening --orb-days   # stocks-in-play data
.venv/Scripts/python -m liquid_atm_quant.data.cli insiders       # SEC Form 4 open-market trades
.venv/Scripts/python -m liquid_atm_quant.data.cli form13f        # SEC 13F holdings
.venv/Scripts/python scripts/run_phase3d.py --save --json ../docs/phase3d/results.json
.venv/Scripts/python scripts/noise_sensitivity.py                # costs x2/x4, sub-periods: not trials
.venv/Scripts/python scripts/orb_diagnostic.py                   # how much of ORB is fill assumptions
```

### Validation (Phase 4)

```bash
cd quant
.venv/Scripts/python scripts/run_phase4.py fetch                 # ETFs + SPY minutes through today
.venv/Scripts/python scripts/run_phase4.py insample --json ../docs/phase4/insample.json
.venv/Scripts/python scripts/run_phase4.py lockbox --unlock-lockbox   # once: already spent
.venv/Scripts/python scripts/lockbox_diagnostic.py               # Noise Band before/after the lockbox
```

## Phase status

- [x] **Phase 0: Foundations.** Compose stack, baseline schema, Redis Lua sliding-window rate limiter, GPU semaphore, local-LLM gateway, Alpaca paper probe.
- [x] **Phase 1: Free data layer.** Point-in-time universes (Russell 1000 back to 2006 via Wayback, S&P 500 change history), Alpaca SIP bars including delisted names, EDGAR filings with acceptance timestamps, data-quality checks, survivorship coverage, look-ahead detector.
- [x] **Phase 2: Backtester and tax engine.** Event-driven daily loop with a point-in-time cursor
  that makes look-ahead structurally impossible; pessimistic intrabar bracket resolution; limit-fill
  bias controls (touch buffer, ADV participation cap); FIFO tax lots, IRC §1091 wash sales in both
  directions with holding-period tacking, the reserve with carryforwards and 1040-ES payments;
  13 cross-language fixtures; SPY and naive-momentum baselines. **Gate passed:** all fixtures pass
  and SPY buy-and-hold reproduces the real max drawdown (-33.79%, 2020-02-19 → 2020-03-23) exactly.
- [ ] **Phase 3: Strategy.** Built and tested: a three-state regime filter with hysteresis, a
  five-stage screener on causal whole-panel indicators (with a truncation-invariance test),
  ATR brackets, and a book with heat, sector and pacing caps. The lockbox and a 20-trial budget
  are enforced. **Gate failed in sample:** −0.12R per trade. The breakout trigger selects
  short-term reversal (`docs/phase3/strategy-report.md`). The phase also fixed an engine defect
  that held acquired companies forever.
- [ ] **Phase 3b: Investor strategies.** Point-in-time SEC fundamentals, cross-asset ETFs, and
  eight pre-registered strategies (Buffett, Greenblatt, Lynch, CANSLIM, Templeton, Turtle,
  All-Weather, quality + trend). **None passes the in-sample gate.** As the factor pre-screen
  predicted, quality led, but equal weighting cost about 3 points a year in the mega-cap era.
  Trend-following was the only strategy within the 15% drawdown limit. 10 of 20 trials used
  (`docs/phase3b/strategy-report.md`).
- [ ] **Phase 3c: Research and exposure management.** The three proposed follow-ups, then
  published rules (Faber, Gayed & Bilello, Moreira & Muir, Keller VAA, Antonacci) screened on
  1960-2015 at no trial cost, and the winners run in sample. **`vol_trend` (volatility target ×
  200-day filter, SPY/SSO/T-bills) passes 3 of 4 checks**: −19.2% max drawdown and a Calmar of
  0.45 vs SPY's 0.43, but 8.6%/yr after tax vs 14.4%. A taxable timing strategy pays an effective
  27-35% tax, much of it through wash sales FIFO creates. The gate needs an after-tax Calmar of
  0.72, which no published long-only rule reaches. Awaiting a decision on the objective. 17 of 20
  trials used (`docs/phase3c/strategy-report.md`).
- [ ] **Phase 3d: Copying and intraday.** Six pre-registered trials, plus one labelled post-hoc,
  with the budget raised to 25: the Noise Band (intraday SPY momentum, replicated year by year
  against its paper), an opening-range breakout on stocks in play, insider clusters (SEC Form 4),
  a hindsight-free 13F clone, and the "first candle" fair-value-gap rule with a placebo.
  **`vol_trend_noise` (Phase 3c's `vol_trend` + a Noise Band overlay) passes all four checks
  in-sample**: $384,832 after tax vs SPY's $294,152, −14.9% max drawdown, Calmar 1.13. It still
  passes at double costs. It is post-hoc, and the paper's sample overlaps ours, so it is a
  candidate for Phase 4's lockbox, not proof. The phase also fixed two defects that affected
  every stock strategy: splits were not applied to held positions, and an empty Russell 1000
  snapshot emptied the universe from Feb to Jul 2017. Phases 3-3c, re-run on the fixes, still
  fail. 24 of 25 trials used (`docs/phase3d/strategy-report.md`).
- [x] **Phase 4: Validation. NO-GO.** `vol_trend_noise`'s checks were pre-registered and
  committed before anything ran (`docs/phase4/preregistration.md`). In sample, its Deflated Sharpe
  over 24 trials was 0.00 (needs 0.95). PBO was 16.9%, and the bootstrap gave a 60% chance of
  beating SPY. The lockbox (2024-10 to 2026-10) was then opened once, for information. After tax:
  $103,182 vs SPY's $133,167, max drawdown −15.3%, and the overlay subtracted value compared with
  `vol_trend` alone. The Noise Band earned +18%/yr before its May 2024 publication and −0.6%/yr
  after. 24 of 25 trials used; the lockbox is spent (`docs/phase4/validation-report.md`).
- [ ] Phase 5: local-LLM catalyst gate
- [ ] Phase 6: Java orchestrator (OMS, ledger, blacklist, December flush)
- [ ] Phase 7: risk controls and observability
- [ ] Phase 8: paper trading (at least 1 month)
- [ ] Phase 9: live ramp

## Quick start

Prerequisites: Docker Desktop, Ollama with the model pulled (`ollama pull qwen2.5:14b-instruct`), Python 3.12, and JDK 17.

```bash
cp .env.example .env            # set POSTGRES_PASSWORD (+ Alpaca PAPER keys for the probe)
docker compose up -d --build    # postgres :5433, redis :6380, orchestrator :8082, quant :8001
docker compose ps               # everything should be "healthy"

curl localhost:8082/actuator/health
curl localhost:8001/health      # redis/postgres UP, ollama UP or DOWN (DOWN = no new entries)
```

Local development:

```bash
cd quant
py -3.12 -m venv .venv && .venv/Scripts/pip install -e ".[dev]"
.venv/Scripts/pytest                           # unit tests (fakeredis runs the real Lua)
.venv/Scripts/python scripts/llm_smoke.py      # needs Redis up: local Qwen -> validated CatalystVerdict, then a cache hit
.venv/Scripts/python scripts/alpaca_probe.py   # needs paper keys -> docs/phase0/alpaca-probe-report.md

cd ../orchestrator
./mvnw test                                    # Testcontainers: applies V1 to pgvector Postgres (needs Docker)
```

## Ports

| Service | Host port |
|---|---|
| Postgres | 5433 |
| Redis | 6380 |
| quant | 8001 |
| orchestrator | 8082 |
| Ollama (host) | 11434 |
