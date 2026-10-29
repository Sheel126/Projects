# Phase 4 validation report: `vol_trend_noise`

**Verdict: NO-GO.** All four pre-registered checks failed. Check 1 failed in sample, before the
lockbox was opened. Checks 2-4 failed in the lockbox, which was opened once, for information, at
the user's choice. Explanation: `docs/lessons/04-validation.md`.

| Commit | What |
|---|---|
| f2e27c4 | Pre-registration (`preregistration.md`): written before anything below ran |
| ec4cba6 | Phase 4 code and in-sample results, committed before the lockbox was opened |
| — | Lockbox opened 2026-10-29 18:55 UTC (`lockbox_opened.json`) |

## Check 1, in sample: Deflated Sharpe ≥ 0.95. FAIL

`run_phase4.py insample` (`insample.txt`, `insample.json`):

- Trial 24 reproduces to the cent: $384,832.48. An ETF-only panel gives the same result as the
  Russell 1000 panel.
- Daily after-tax Sharpe 0.0849 (1.35 a year); skew 0.28, kurtosis 8.2; 2,200 sessions;
  N = 24 trials.
- The best Sharpe 24 skill-less trials would show by luck: **3.16 a year. DSR = 0.000.**
- The bar is inflated by `orb_in_play`'s Sharpe of −6.9, from the account it wiped out. After the
  fact, labelled as such: without ORB the bar is 0.96 and DSR 0.88 (still a fail); with a robust
  MAD variance the bar is 0.46 and DSR 1.00. The pre-registered rule stands.

Reported, not gating:

| Statistic | Value |
|---|---|
| PBO (CSCV, 16 blocks, 12,870 splits) | 16.9%. The three Noise Band trials won in sample in about 90% of splits |
| Bootstrap, candidate − SPY | +1.2%/yr; P(> 0) = 60%; 90% interval −6.4% to +9.1% |

## Checks 2-4, lockbox 2024-10-01 to 2026-10-28 (521 sessions). FAIL ×3

`run_phase4.py lockbox` (`lockbox.txt`, `lockbox.json`):

| | After-tax value | CAGR | Max DD | Calmar | Sharpe | Tax paid |
|---|---|---|---|---|---|---|
| `vol_trend_noise` | $103,182 | 2.0% | −15.3% | 0.13 | 0.21 | $6,164 |
| `vol_trend` alone | $112,903 | 6.5% | −9.1% | 0.71 | 0.58 | $3,017 |
| SPY buy-and-hold | $133,167 | 17.1% | −18.8% | 0.91 | 1.05 | $431 |

| # | Check | Result |
|---|---|---|
| 2 | Beats SPY after tax | FAIL: $103,182 vs $133,167 |
| 3 | Max drawdown ≥ −15% | FAIL: −15.3% |
| 4 | Beats `vol_trend` alone | FAIL: $103,182 vs $112,903 |

After-tax returns by calendar year:

| Year | `vol_trend_noise` | `vol_trend` | SPY |
|---|---|---|---|
| 2024 (Q4) | +5.0% | +2.2% | +3.5% |
| 2025 | +1.0% | +6.1% | +17.5% |
| 2026 to date | −1.7% | +5.0% | +14.0% |

Run continuously from 2016 to 2026-10-28: $374,998 (max DD −14.9%) vs SPY's $398,321 (max DD −33.9%).

## Diagnosis (after the lockbox; changes nothing)

From `lockbox_diagnostic.py` (`lockbox_diagnostic.txt`). The Noise Band alone earned **+18.1% a
year** pre-tax in sample and **−0.6% a year** in the lockbox. It still paid on days SPY fell more
than 1% (+0.92%), and still lost the same amount on quiet days (−0.25%). The profit between those
two disappeared. That is consistent with decay after the paper came out in May 2024
(McLean & Pontiff 2016), or with a less trending market; two years can't tell the two apart.

## What is left

- 24 of 25 trials are used and the lockbox is spent. Any new candidate would be judged on data
  that has now been seen, and would face a higher Deflated Sharpe bar.
- The one result that held out of sample is the original Phase 3c finding: `vol_trend` alone cut
  the drawdown roughly in half (−9.1% vs −18.8%) at the cost of return. That fits objective B
  from Phase 3c (a risk-managed objective), not "beat SPY".
