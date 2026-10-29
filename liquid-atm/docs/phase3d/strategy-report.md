# Phase 3d verification report

Generated 2026-10-29. In-sample window **2016-01-04 → 2024-09-30**, $100k start, 32% short-term /
15% long-term, quarterly estimated tax, after-tax and post-liquidation. **The lockbox
(2024-10-01 onward) was neither downloaded nor read.** Lesson:
`docs/lessons/03d-copying-and-intraday.md`.

## Verdict

**One trial passes all four checks of the in-sample gate: `vol_trend_noise`** (trial 24), Phase
3c's `vol_trend` held overnight with the Noise Band intraday overlay on top. It is the first pass
in 24 trials. It turned $100k into **$384,832 after tax**, against SPY's $294,152, with a
**−14.9% max drawdown** (SPY −33.9%) and an after-tax **Calmar of 1.13** (SPY 0.43). That also
clears Phase 4's stricter bar (Calmar ≥ 1.0, drawdown ≤ 15%), barely.

**It is a candidate, not proof.** Trial 24 was designed *after* trial 19 failed only on drawdown,
and the Noise Band paper's sample contains this window. The lockbox is the test that counts (§6).

| # | Trial | After-tax value | CAGR | Max DD | Calmar | Sharpe | Gate |
|---|---|---|---|---|---|---|---|
| | **SPY buy & hold** | **$294,152** | 14.4% | −33.9% | 0.43 | 0.85 | (benchmark) |
| | Naive momentum | $239,660 | 11.6% | −38.2% | 0.30 | 0.54 | (benchmark) |
| 18 | `noise_band` | $273,879 | 12.2% | −24.7% | 0.49 | 1.05 | fail 2/4 |
| 19 | `spy_core_noise` | **$749,302** | 26.8% | −33.3% | 0.81 | 1.31 | fail 1/4 (drawdown) |
| 20 | `orb_in_play` | $84 | −55.6% | −99.9% | −0.56 | −6.92 | fail 4/4 |
| 21 | `insider_cluster` | $211,189 | 9.3% | −54.4% | 0.17 | 0.49 | fail 4/4 |
| 22 | `clone_13f` | $305,315 | 14.2% | −39.5% | 0.36 | 0.68 | fail 2/4 |
| 23 | `fvg_first_candle` | $46,516 | −8.3% | −56.7% | −0.15 | −0.69 | fail 4/4 |
| **24** | **`vol_trend_noise`** (post-hoc) | **$384,832** | **16.8%** | **−14.9%** | **1.13** | **1.35** | **PASS** |

The naive-momentum benchmark is $239,660, not Phase 3c's $196,381: two bugs fixed in this phase
changed it (§5). Runs: `run_phase3d.py --save --json`; every number is in `results.json`, and the
printed run is `results.txt`.

Calendar years, after tax:

| Year | SPY | 18 noise | 19 SPY+noise | 21 insider | 22 13F | **24 vol_trend+noise** |
|---|---|---|---|---|---|---|
| 2016 | 12.7 | −12.7 | 3.1 | 18.8 | 16.6 | −0.6 |
| 2017 | 21.6 | −9.3 | 15.8 | 11.2 | 11.3 | **30.3** |
| 2018 | −5.0 | 45.1 | 30.0 | −8.9 | −2.7 | **22.3** |
| 2019 | 31.0 | 4.4 | 32.8 | 17.2 | 20.4 | 9.8 |
| 2020 | 18.2 | 17.2 | 36.4 | 6.7 | 76.8 | 14.8 |
| 2021 | 28.5 | 19.2 | 49.1 | 20.6 | −1.0 | 26.2 |
| 2022 | −18.3 | 15.9 | −5.2 | −13.2 | −15.3 | **9.2** |
| 2023 | 26.0 | 25.2 | 51.3 | 32.8 | 13.7 | 23.9 |
| 2024 (to Sep) | 21.7 | 12.8 | 32.4 | 3.5 | 24.0 | 14.0 |

## 1. The Noise Band (18, 19, 24)

**The code reproduces the paper.** Pre-tax, year by year, it is within about 2 points of the
paper's own table in seven of eight years: 2016 −12.8% vs −12.8%, 2018 +59.1% vs +61.1%, 2023
+38.8% vs +37.2%. The one exception is 2021, which comes out at +29.0% against +34.8%
(lesson §4).

**Alone (18), tax kills it.** It made 18% a year pre-tax, but every dollar is short-term, so it
compounds at 12.2% after tax. It also lost money in 2016 and 2017.

**As an overlay (19, 24), it works,** because of *when* it makes money (daily, 2016-2024):

| SPY that day | Days | Noise Band, mean |
|---|---|---|
| down more than 1% | 242 | **+0.83%** |
| up more than 1% | 294 | +0.53% |
| within ±0.5% | 1,109 | −0.22% |

It pays on big days in either direction and bleeds on quiet ones: it behaves like owning
volatility. Its correlation is −0.08 with SPY and −0.13 with `vol_trend`. Held alongside a book
whose losses come from large moves, it fills in exactly those days. That is why trial 24's worst
drawdown is a quiet stretch in 2016, not a crash. In 2022 it made +9.2% while SPY lost 18%.

**Trial 19 fails only on drawdown.** The SPY core still fell 33% in March 2020, and the overlay
didn't offset enough of that in a month. Swapping the core for `vol_trend`, which steps aside below
the 200-day average, is what trial 24 does.

**Robustness** (`noise_sensitivity.txt`; diagnostics, not trials):

| Trial 24 variant | After-tax value | Max DD | Calmar | Passes gate? |
|---|---|---|---|---|
| as registered | $384,832 | −14.9% | 1.13 | yes |
| costs ×2 | $363,876 | −16.0% | 1.00 | yes |
| costs ×4 | $324,727 | −18.2% | 0.80 | yes |
| Alpaca's real costs ($0 commission) | $401,777 | −13.9% | 1.25 | yes |
| 2020-2024 only | $232,545 from $100k | −13.3% | 1.49 | yes |

It survives quadrupled costs, which matters because cost is the usual reason an intraday edge
disappears. Trial 19 also beats SPY in both halves of the window (2016-19: $198k vs $163k;
2020-24: $362k vs $177k).

**The costs it pays, and the reasons to doubt it:**
- **Margin interest.** 8% on any negative overnight cash: $1,382 over the window for trial 24.
- **Overlay leverage capped by Alpaca's real buying power.** 2x for trial 24, 2.5x for trial 19.
- **Wash sales across 31 December** are not modelled (lesson §3).
- **Taxes are figured as two separate ledgers**, so the overlay's losses never offset the core's
  gains. That overstates tax slightly.
- **The paper's 2007-2024 sample contains this window**, so the authors chose the rules knowing
  how these years went.
- **Trial 24 is post-hoc.**
- **It is a single mechanism on a single instrument.** If dealer-gamma intraday trends have been
  crowded since the paper was published (May 2024), the lockbox will show it.

## 2. Opening-range breakout on stocks in play (20): the edge lives inside one minute

It lost almost everything: −0.62R per trade, a 7.9% hit rate. The diagnostic
(`orb_diagnostic.txt`) shows why. It re-scores the same 35,421 trades under different fill
assumptions, gross:

| Assumption | Mean R | Hit rate |
|---|---|---|
| Registered: 5 bp slippage on both stop orders, the entry minute can stop out | −0.62R | 7.9% |
| The paper's: no slippage, the entry minute can stop out | −0.23R | 10.7% |
| Most generous: no slippage, the entry minute never stops out | **+0.18R** | 15.0% |

The stop sits 10% of a day's ATR from the entry, often less than one minute's range in a stock
having its biggest day of the year. With 1-minute bars, whether the stop was hit before or after
the entry in that minute cannot be known, and 54% of triggers had both in the same minute. The
strategy only shows a profit if every one of those resolves in its favour *and* stop orders fill
at the exact price. **Its result is an execution assumption, not a finding.** It would need tick
data to evaluate, and real fills would include the slippage the paper left out. An independent
replication on index futures reached the same "gross yes, net no".

## 3. Copying insiders (21) and funds (22)

**Insiders failed (−54% drawdown).** Clusters of insider buying arrive when stocks have already
fallen: energy and REITs in 2019, then COVID. The book filled with 20 of them at 5% each and fell
48% in a month in March 2020. It also tops up any name that halves (the shared no-trade-band rule
in `investors/base.py`), which averaged down into GoHealth from $11.84 to $0.66. In the Russell
1000, at least, the signal is weak, as the one post-2010 out-of-sample study predicted.

**The 13F clone beat SPY after tax ($305k), but with a −39.5% drawdown.** The managers its rule
picked ran concentrated, aggressive books: +77% in 2020, then −1% and −15%. It chose managers on
the past year only, with no hindsight, which is why this is a fair result. It is a riskier SPY,
not a better one.

## 4. The first candle rule (23) and its placebo

It lost 8% a year. More telling than the loss is the placebo. Moving each day's real setup to a
random minute and a random direction did *better* than the real rule in 65% of 200 runs (real
−0.085R, placebo median −0.065R). **The fair value gap carries no information** here; what the
rule does is pay a 3R bracket's costs on noise. That matches the independent placebo test in the
lesson's sources.

## 5. Two defects found and fixed

1. **Stock splits** were not applied to held positions. A split looked like a crash, the
   rebalancer bought the "dip", and a sale booked a false tax loss. Fixed in `engine.py` (step 0)
   and `LotBook.split`, with a check that a non-clean jump is a special dividend (Albertsons, 2023).
2. **An empty universe snapshot.** The Russell 1000 snapshot of 2017-01-31 had zero members, which
   emptied the universe from February to July 2017. The panel now skips empty snapshots, and the
   data-quality job flags them (`empty_snapshot`).

Every earlier strategy was re-run on the corrected engine and data (`rerun_phase3b3c.json/.txt`):

| | Before | After |
|---|---|---|
| Naive momentum (benchmark) | $196,381 | $239,660 |
| `buffett_quality` | 11.1%/yr | 12.6%/yr |
| `vol_trend_v2` | $190,683 | $217,506 |
| `momentum_funnel` | −0.12R | −0.02R |
| `vol_trend` | $201,932 | $201,932 (holds no splitting stocks) |

**No earlier trial passes on the corrected numbers.** `vol_trend` now fails two checks instead of
one, because the higher momentum benchmark beats it.

## 6. What Phase 4 has to do with trial 24

- **Deflated Sharpe with N = 24.** Trial 24's Sharpe is 1.35 over 8.7 years. Phase 4 asks how
  likely the best of 24 tries is to look this good by luck. This is the first trial where that
  question isn't moot.
- **Walk-forward** isn't very informative for a rule with no fitted parameters. The useful
  version is a stability check: rolling one- and two-year windows, and how often it trails SPY.
- **The lockbox (2024-10 → now): about two years, all after the paper was published.** It is opened
  once, for this one strategy, with the pass/fail criteria written down before it is read.
  Suggested criteria, for you to approve: after-tax return above SPY's, max drawdown within 15%,
  and the overlay's own contribution positive. If any fails, the answer is SPY plus the tax tooling.
- **Phase 6 requirements this creates:** overlay lots must be sold by specific identification,
  never FIFO out of the core. Margin and day-trading buying power must be checked before every
  overlay order. The pattern-day-trader rule needs at least $25k in the account at all times.

## Tests

```
$ cd quant && .venv/Scripts/pytest -q
242 passed
```

New: `test_phase3d.py` (19). It covers the Noise Band (a trend day, **unchanged by the future**,
leverage sizing, early closes), the after-tax account (short-term tax, the core's long-term exit),
ORB fills (trigger, same-minute stop, relative volume from prior days only), the fair-value-gap
detector, routine insiders and clusters, the Form 4 parser, CUSIP matching by price and name, the
13F clone's use of only public filings, and splits (value kept, special dividend not a split,
ledger basis kept).

## Trial ledger

| # | Hash | What | Result |
|---|---|---|---|
| 1-17 | | Phases 3, 3b, 3c | see `docs/phase3c/strategy-report.md`; re-scored in §5 |
| 18 | bf39fa723a41c86b | `noise_band` | fail 2/4 |
| 19 | cff9e47ef8c7217d | `spy_core_noise` | fail 1/4 (drawdown) |
| 20 | f7d07635627a6ffa | `orb_in_play` | fail 4/4 |
| 21 | a184336be91ab325 | `insider_cluster` | fail 4/4 |
| 22 | 59386f2314c6345f | `clone_13f` | fail 2/4 |
| 23 | ef64a44fdd1e4f02 | `fvg_first_candle` | fail 4/4 |
| **24** | 025b6455f4fec66e | **`vol_trend_noise`** (post-hoc) | **PASS** |

**24 of 25 used.** The budget was raised from 20 to 25 before any Phase 3d run.
