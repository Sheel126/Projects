# Phase 4 pre-registration: `vol_trend_noise`

Written and committed on 2026-10-29, **before** any Phase 4 statistic was computed and before any
data from the lockbox (2024-10-01 onward) was downloaded or read by a strategy. The commit that
adds this file is the proof of the order. `scripts/run_phase4.py lockbox` refuses to run unless
this file is committed and unchanged (lesson 04 §5).

## The candidate, frozen

`vol_trend_noise`, trial 24 of 25, config hash `025b6455f4fec66e` (Phase 3d, lesson 03d §10):

- **Core:** Phase 3c's `vol_trend` with its default `VolTrendParams` (15% vol target, 1.5x cap,
  200-day filter, 0.25 exposure steps, SPY/SSO/BIL), held overnight.
- **Overlay:** the Noise Band on SPY with the default `NoiseBandParams`, except
  `max_leverage = 2.0`, sized each morning from the combined after-tax equity at the prior close.
- **Costs and taxes:** unchanged. $0.0035/share commission and $0.001/share slippage on the
  overlay; the engine's costs on the core; 32% short-term, 15% long-term, quarterly estimated
  payments, wash sales, 8% margin interest on negative overnight cash, liquidation at the end.

No parameter, cost, tax rate or rule may change between this commit and the lockbox run.

## Check 1, in sample: Deflated Sharpe Ratio ≥ 0.95

Bailey & López de Prado (2014). Inputs:

- The candidate's **daily after-tax returns**, 2016-01-04 to 2024-09-30.
- **N = 24**, every configuration saved against the trial budget (`store.trial_count`), not only
  the 24 kept ones. If the count differs from 24 at run time, the run stops.
- The cross-trial variance of the 24 trials' daily after-tax Sharpe ratios on their common dates.
  For Phases 3b and 3c these come from the re-runs on the fixed engine
  (`docs/phase3d/rerun_phase3b3c.json`). The two Phase 3 funnel trials and the seven Phase 3d
  trials come from their saved equity curves.
- The candidate's own skew and kurtosis, and its number of daily observations.

Pass: DSR ≥ 0.95, i.e. at least 95% confidence that the true Sharpe exceeds the best Sharpe that
24 skill-less trials would be expected to show by luck.

## Checks 2-4, out of sample: the lockbox, opened once

Window: **2024-10-01 to the last complete session in the data on the day of the run**. The
account starts with $100,000 on 2024-10-01, with no positions. History before that date may be
read only as indicator warm-up (the 200-day average, the vol forecasts, the 14-session noise
area). The account is liquidated and taxed at the end of the window, as in every trial.

The benchmark is SPY buy-and-hold on the same engine, over the same window, also from $100,000.
Naive momentum is **not** run: its Russell 1000 universe has no point-in-time snapshots inside
the lockbox.

| # | Check | Pass if |
|---|---|---|
| 2 | Beats SPY after tax | post-liquidation value > SPY buy-and-hold's |
| 3 | Drawdown held | after-tax max drawdown ≥ −15% |
| 4 | The overlay earns its place | post-liquidation value > that of `vol_trend` alone over the same window |

**GO for Phase 5 = all four checks pass.** Any failure is NO-GO for this candidate.

## Reported but not gating (fixed now, so they cannot be chosen afterwards)

- Probability of Backtest Overfitting (CSCV, 16 blocks) over the 24 trials' daily after-tax
  returns, in sample.
- A stationary block bootstrap (mean block 21 sessions, 10,000 draws, seed 4) of the candidate's
  daily after-tax return minus SPY's, in sample: the probability that the annualized difference
  is positive.
- Calendar-year after-tax returns of the candidate, `vol_trend` alone and SPY, in sample.
- In the lockbox: CAGR, Sharpe, Calmar, the overlay's after-tax P&L, tax paid, margin interest,
  and the same strategy run continuously from 2016 through the lockbox.

## Rules for the lockbox run

1. One run. `run_phase4.py lockbox` writes `docs/phase4/lockbox_opened.json` and refuses to run
   again once that file exists.
2. No changes after opening. If a bug is found afterwards, it is fixed and disclosed, both results
   are reported, and the verdict is the **worse** of the two.
3. A NO-GO is final for this candidate. The 25th trial may not be used to "fix" it against the
   lockbox, because the lockbox is no longer unseen data.
4. A GO is weak evidence on its own. About two years is a short window: a strategy that truly
   beats SPY by 3 points a year fails check 2 in roughly a third of two-year windows, and a bad one
   passes it by luck about as often. Phase 8's month of paper trading and Phase 9's small live ramp
   are still required.
