# Phase 3 verification report

Generated 2026-10-14. In-sample window **2016-01-04 → 2024-09-30**, $100k start, 32% short-term /
15% long-term, quarterly estimates, the Phase 2 cost model. The lockbox (2024-10-01 onward) was not
touched by any funnel run. The reasoning behind every number is in `docs/lessons/03-strategy.md`.

## Verdict: the gate fails, and the reason is clear

The funnel ran with its pre-registered defaults, unchanged. It loses money in sample, so **Phase 3
does not pass**. The engine and the screener are doing what they were built to do; the *idea* (a
10-day breakout bracket on 6-month momentum leaders) has no edge in Russell 1000 stocks over this
period. §3 shows why, without the engine in the way.

| Gate criterion (lesson 03 §9) | Result | |
|---|---|---|
| Post-liquidation value beats SPY buy & hold | **FAIL** | $56,511 vs $294,152 |
| Post-liquidation value beats naive momentum | **FAIL** | $56,511 vs $196,381 |
| Max drawdown (after tax) ≤ 20% | **FAIL** | −50.79% |
| Calmar (after tax) beats SPY's | **FAIL** | −0.12 vs 0.43 |
| Survives strict fills | not run, cannot change anything | 0 touch-only fills, so strict mode rejects nothing |

## 1. The headline run (trial 2 of 20)

```
$ python scripts/run_backtest.py --strategy phase3 --save

=== buy_and_hold_spy  2016-01-04 .. 2024-09-30
  after-tax  CAGR  14.43%   vol 17.67%   Sharpe  0.85   maxDD -33.86%   Calmar  0.43
  post-liquidation value      294,152.01

=== naive_momentum  2016-01-04 .. 2024-09-30
  after-tax  CAGR   8.92%   vol 26.71%   Sharpe  0.45   maxDD -38.45%   Calmar  0.23
  post-liquidation value      196,381.20   effective tax 33.9%, 60 wash sales

=== momentum_funnel  [64d9da1cf06547d7]  2016-01-04 .. 2024-09-30
  after-tax  CAGR  -6.33%   vol 10.78%   Sharpe -0.55   maxDD -50.79%   Calmar -0.12
  post-liquidation value       56,511.45
  trades  1257   hit 45.7%   avg hold 9.5d
  exits  stop 580 · time 505 · target 158 · delisted 8 · terminal 6
  R: expectancy -0.119R   avg win +1.16R   avg loss -1.19R
  fills: rate 95.7%  touch-only 0.0%  ambiguous exits 0.0%   expired entries 56
  regime days  risk_on 1084 · caution 565 · risk_off 550 (incl. the first 200 with no SMA200)
  funnel/day   universe 921 → eligible 783 → trend 345 → momentum 69 → trigger 4.0 → extension 2.1
  book skips   pacing 680 · heat 522 · slots 435 · sector 267
```

**Why trial 2 and not 1:** trial 1 ran on an engine with the zombie-position defect (§4). Its rows
are kept in `backtest_runs` under the label `phase3_zombie_defect` rather than deleted. Fixing the
engine added a config field, which changed the hash, so the honest count is 2.

## 2. Reading the diagnostics

- **Expectancy is −0.12R, and it is steady.** 1,257 trades × −0.12R × 0.75% risk is roughly −110% of
  cumulative risk. That is a slow bleed, not a crash, which is why the regime filter could not help:
  the losses come from the trades, not from the market.
- **The exit mix says "no drift".** Only 12.6% of trades reach the 3-ATR target, and 40% time out.
  For a driftless walk the 3:2 bracket wins 40% of the decided trades (lesson 03 §5). Here it wins
  158 of 738 decided trades (21%), with most of the rest timing out.
- **Average loss is −1.19R, not −1.0R.** Stops gap. Earnings is the obvious suspect (lesson 03,
  limitations). That 0.19R of gap slippage on the losers is roughly the whole expectancy.
- **The fill model is not the problem.** There were 0 touch-only fills and 0 ambiguous exits. The
  entry design worked as intended: fills happen at the open, with no adverse selection. The two
  assumptions most capable of making a backtest lie are not carrying this result in either
  direction.
- **The book is not the problem either.** Heat, pacing and sector caps all bind regularly, which is
  what they are for. They limit size; they cannot change the sign.

## 3. Where the drift is, measured without the engine

`scripts/funnel_forward_returns.py` takes every session the regime allows and every name that
survives each screener stage. It measures the return from the next open over *h* sessions, minus the
average eligible name over the same window. This is research, not a trial: nothing is optimised.

| Stage | 5 sessions | 10 sessions | 21 sessions | 63 sessions |
|---|---|---|---|---|
| trend (close > SMA50 > SMA200) | −0.004% | +0.003% | +0.018% | **+0.187%** |
| momentum (top 20%, risk-adjusted) | −0.024% | −0.007% | +0.051% | **+0.236%** |
| trigger (20-day high, RVOL ≥ 1.5) | **−0.138%** | **−0.094%** | **−0.293%** | −0.311% |
| extension (≤ 3 ATR above SMA20) | **−0.209%** | **−0.200%** | −0.245% | +0.104% |

(The figures are mean excess returns. t-stats are in the script output, but they overstate
significance because the windows overlap and the cross-section is correlated.)

Three conclusions:

1. **Trend and momentum carry an edge, but it is small and slow.** It grows with the horizon, to
   about +0.2% per quarter over the average stock. That is the published momentum effect, weak in
   2016–2024 large caps, and it lives on a horizon of months, not the 10 days a bracket holds.
2. **The breakout-on-volume trigger selects short-term reversal.** Its excess return is negative at
   every horizon to a month. Buying the close of a high-volume breakout day means buying *after* the
   move, and in large caps that move tends to partly reverse (Jegadeesh 1990, Lehmann 1990).
3. **So the bracket had nothing to work with.** Lesson 03 §5 showed that a bracket with zero drift
   is worth exactly 0R before costs. The final candidates have slightly *negative* drift, and costs
   plus gap slippage take the rest. −0.12R is what the math predicts for this input.

## 4. The zombie-position defect (engine), found by trial 1

Trial 1 reported an average hold of 28 days against a 10-session time stop, a book "full" on 1,629
days, and only 4.7% volatility. Those three numbers cannot all be true of a working engine.

**Cause:** a position in a company that stopped trading (acquired, merged or delisted) has no more
bars, so its bracket never resolves. NorthStar (NRF, NSAM, merged January 2017), Juno, Worldpay,
Legg Mason and Extended Stay all sat in the book until the end of the run, holding a slot and their
capital. Worse, **DCT** was acquired in 2018, the ticker was later reused, and in 2020 *the new
company's* price hit the old stop.

**Fix** (V7, `engine.py`):

- Each position remembers the corporate identity (segment) it bought.
- A bar from another segment never marks it, exits it or sells it.
- After 5 sessions without a bar from its own identity, the position is cashed out at its last mark,
  with exit reason `delisted`.
- A session where *nothing* printed is a gap in our own data (the store behind the calendar), so it
  does not count toward the 5.

Tests: `test_engine.py` covers an acquisition, the DCT ticker-reuse case, a short halt that resumes
and a stale-store tail.

**Known bias:** cashing out at the last close is right for a cash takeover and optimistic for a
failure (performance delistings average a large negative return). Phase 4's survivorship haircut
is where that gets paid back.

**It changes Phase 2's numbers.** Naive momentum suffered from the same defect. Over the full Phase 2
window ($1M, 2016-01-04 → 2026-09-18):

| | Phase 2 report | After the fix |
|---|---|---|
| SPY buy & hold, post-liquidation | $3,935,398 | $3,935,144 (end date moved from 09-25 to 09-18, the last stored bar) |
| Naive momentum, post-liquidation | $3,195,954 | **$3,928,949** |
| Naive momentum, max drawdown | −36.90% | −38.33% |
| Naive momentum, effective tax | 31.5% | 31.1% |

Naive momentum now roughly ties SPY after tax over the full window, with almost double the
volatility. The Phase 2 conclusion still holds (it does not beat SPY on any risk-adjusted measure),
but by much less than reported. An erratum points here from `docs/phase2/baseline-report.md`.

## 5. Other changes

- `PortfolioSnapshot.stops`: the heat cap reads each position's resting stop.
- `BacktestConfig.strict_fills`: rejects touch-only entries, for the §9 sensitivity run.
- `TradeRecord.risk_per_share` and `r_multiple`, plus `TradeStats.expectancy_r`, `avg_win_r` and
  `avg_loss_r`. Each trade's R is stored in `backtest_trades.r_multiple` (V7).
- **The run hash includes the strategy's parameters.** A strategy without parameters keeps the bare
  engine fingerprint, so stored baseline hashes stay valid.
- The strategy's own diagnostics (regime days, funnel shape, book skips) are merged into each run.
- `Panel.head(n)`: the truncated panel the look-ahead test compares against.
- **One deviation from the build spec.** The book passes an explicit `notional` on each
  `BracketIntent` (a field that already existed) rather than adding a `max_notional` field. The
  engine's ADV and cash caps still apply on top, and can only shrink a position.

## Tests

```
$ cd quant && .venv/Scripts/pytest -q
189 passed
```

New in Phase 3: `test_strategy_indicators.py` (8), `test_strategy_regime.py` (6),
`test_strategy_screener.py` (7), `test_strategy_book.py` (9), `test_strategy_funnel.py` (8), and 6
engine tests. Start with `test_every_indicator_is_truncation_invariant` and its partner
`test_the_truncation_test_catches_a_centred_window`.

`orchestrator: ./mvnw test` passes with V7 applied.

## Performance

- Panel load (2016 → 2024-09, 2,200 × 1,745): about 16 s.
- Indicator matrices: 0.8 s.
- Screening every session: 0.2 s.
- A full funnel backtest is a few seconds once the panel is loaded. Phase 4 can afford its sweeps.

## Trial ledger

| # | Hash | What | Result |
|---|---|---|---|
| 1 | dfd6d162d05c4281 | pre-registered defaults, zombie-defect engine | void (engine defect); kept as `phase3_zombie_defect` |
| 2 | 64d9da1cf06547d7 | pre-registered defaults, fixed engine | −0.12R, gate FAIL |

18 trials remain in the Phase 3 budget. The forward-return study (§3) is not a trial, but it *is*
looking. Any design changed because of it has to be run, saved and counted.
