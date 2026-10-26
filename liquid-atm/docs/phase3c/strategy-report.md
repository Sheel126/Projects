# Phase 3c verification report

Generated 2026-10-26. In-sample window **2016-01-04 → 2024-09-30**, $100k start, 32% short-term /
15% long-term, quarterly estimated tax, the Phase 2 cost model, market-on-open fills. 450 calendar
days of warm-up history are loaded before the window so a 200-day rule has its average on day one;
nothing trades or is scored before 2016-01-04. **The lockbox (2024-10-01 onward) was not read.**
Lesson: `docs/lessons/03c-research-and-exposure.md`.

## Verdict

**None of the seven trials passes. `vol_trend` (trial 15) passes three of the four checks** and is
the only strategy in 17 trials to do so. Every check failed for the same reason: nothing beat SPY's
after-tax value.

| Trial | Strategy | After-tax value | CAGR | Max DD | Calmar | Sharpe | Trades | Eff. tax | Gate |
|---|---|---|---|---|---|---|---|---|---|
| | **SPY buy & hold** | **$294,152** | **14.4%** | −33.9% | 0.43 | **0.85** | 1 | 15.0% | (benchmark) |
| | Naive momentum | $196,381 | 8.9% | −38.5% | 0.23 | 0.45 | 274 | 33.9% | (benchmark) |
| 11 | `buffett_quality_cw` | $187,988 | 7.8% | −37.5% | 0.21 | 0.47 | 164 | 23.3% | fail 4/4 |
| 12 | `spy_trend` | $167,157 | 6.4% | −37.5% | 0.17 | 0.50 | 16 | 18.7% | fail 4/4 |
| 13 | `quality_cw_trend` | $166,882 | 6.3% | −20.7% | 0.30 | 0.58 | 416 | 26.7% | fail 4/4 |
| 14 | `vaa_g4` | $151,065 | 4.8% | −20.1% | 0.24 | 0.53 | 70 | 35.0% | fail 4/4 |
| **15** | **`vol_trend`** | **$201,932** | **8.6%** | **−19.2%** | **0.45** | 0.77 | 49 | 27.0% | **fail 1/4** |
| 16 | `vaa_vol_blend` | $173,100 | 6.6% | **−14.9%** | 0.44 | 0.75 | 105 | 32.1% | fail 2/4 |
| 17 | `vol_trend_v2` | $190,683 | 7.9% | −22.4% | 0.35 | 0.63 | 60 | 33.4% | fail 4/4 |

All after tax and post-liquidation. Runs: `run_investors.py --only ... --save --label phase3c`;
every number is in `part1.json`, `part2.json` and `part3.json` here.

Calendar-year returns, after tax:

| Year | SPY | 11 quality cw | 12 spy trend | 14 VAA | **15 vol_trend** | 16 blend | 17 v2 |
|---|---|---|---|---|---|---|---|
| 2016 | 12.7 | 13.0 | 10.0 | 4.8 | 7.3 | 6.2 | 7.9 |
| 2017 | 21.6 | 14.3 | 20.8 | 10.7 | **34.0** | 20.7 | 34.1 |
| 2018 | −5.0 | −18.7 | −9.4 | 4.4 | −8.0 | −1.8 | −8.0 |
| 2019 | 31.0 | 34.7 | 7.9 | 4.4 | 11.7 | 8.2 | 12.4 |
| 2020 | 18.2 | −2.0 | −5.1 | 13.2 | 2.6 | 6.9 | −6.8 |
| 2021 | 28.5 | 18.0 | 27.6 | 0.8 | 15.6 | 9.0 | 18.1 |
| 2022 | −18.3 | −10.7 | −22.8 | −13.0 | **−9.1** | −10.8 | −9.8 |
| 2023 | 26.0 | 17.9 | 16.8 | 11.1 | 11.9 | 11.8 | 12.6 |
| 2024 (to Sep) | 21.7 | 12.2 | 21.2 | 8.3 | 15.4 | 10.8 | 16.1 |

## 1. Part 1: the three proposed trials (11-13)

- **Cap weighting made quality worse** (7.8% vs equal weight's 11.1%). The screen ranks by
  earnings yield, so the biggest holdings were cheap cyclicals (GM, DAL, INTC, HUM, steel), which
  the cap weights then concentrated. It isn't the profitability factor the evidence measures
  (lesson §2).
- **The monthly 200-day switch whipsawed** through five round trips that each lost 5-17%, and
  stayed invested through the COVID crash because the March 2 check still showed SPY above its
  average. Its drawdown (−37.5%) was worse than SPY's.
- **Quality + turtle** halved the drawdown (−20.7%) but compounded at 6.3%.

## 2. Part 2: research picks, chosen on 1960-2015 (14-16)

`scripts/research_screen.py` ran 60+ published rules and variants on 1960-2015 at no trial cost
(full output: `research_screen.txt`). The selection rule, fixed before the run: highest CAGR with
a max drawdown of 20% or less in every era. Before spending trials, each pick was run through the
real engine on the 2008-2015 design window:

| 2008-2015 (design window, engine, after tax) | Value | /yr | Max DD | Eff. tax |
|---|---|---|---|---|
| SPY | $155,214 | 5.65% | −52.1% | 15% |
| VAA-G4 | $181,033 | 7.70% | −13.9% | 35% |
| vol_trend, continuous | $129,694 | 3.31% | −18.0% | 49% |
| vol_trend, stepped (adopted) | $134,216 | 3.75% | −16.8% | 42% |
| 50/50 blend | $158,402 | 5.92% | −13.3% | 37% |

In-sample, **VAA collapsed** (4.8%). One negative risky asset is enough to step aside, and with
EEM and AGG in the mix that happened in 60 of 105 months. **`vol_trend` held**: 1.5x in the calm of
2017 (+34%), −9% in 2022 against SPY's −18%, max drawdown −19.2%, and a Calmar of 0.45 against
SPY's 0.43.

## 3. Part 3: diagnosis and one fix (17)

Where `vol_trend` lost to SPY, pre-tax (it compounded 10.5% before tax against SPY's 14.6%):

| | SPY | vol_trend | Cause |
|---|---|---|---|
| 2019 | 31.1% | 12.0% | Out from Dec 2018 to Feb 2019, then at reduced exposure |
| 2020 | 18.3% | 4.6% | Exited the crash, then held ~0.4x through the recovery: the 60-day vol stayed high |
| 2023 | 25.9% | 10.5% | Whipsawed Jan-Mar, under-exposed afterwards |

Tax: realized trades gained $55.7k economically, but 54 wash sales made $127k taxable.

Fix tested (trial 17): a symmetric 20-day vol forecast, which also won on 1960-2015 (10.3% vs
9.7%). **It made everything worse** (lesson §6). The faster forecast re-levered into the whipsaws
as quickly as into the recoveries.

The wash-sale fix (twin funds through the blacklist) was tested on the design window only and
didn't help, because most wash sales here are on the "before" side, which FIFO creates and the
blacklist cannot stop. **Phase 6 requirement:** the order manager should sell the newest lot first
(specific identification) when cutting a position that was just added to.

## 4. Where we are going wrong

1. **The benchmark's decade.** 2016-2024 was the mega-cap era. Equal weight trailed by 3.2 points,
   low volatility by about 3, value by more, and every correction was V-shaped, the worst case for
   a trend rule. Every source of diversification or defense cost money in this window.
2. **Taxes.** Every timing strategy paid an effective 27-35%, against SPY's 15% deferred to the
   end. Pre-tax, `vol_trend` was 10.5% against 14.6%. Tax took another 1.9 points a year, about
   half of it through wash-sale timing.
3. **The gate's arithmetic** (lesson §7). Beating 14.4% with a drawdown of 20% or less needs an
   after-tax Calmar of 0.72. The best published rules reach 0.5-0.9 *pre*-tax over 56 years, and
   leverage can't raise Calmar.
4. **Implementation vs evidence.** The quality screen wasn't the quality factor. VAA's paper
   universe behaved differently from its backtest. Check the mechanism, not the name.
5. **Tuning after looking.** Trial 17 is the cautionary example. The remaining three trials are
   held back on purpose.

## 5. Decision needed

Nothing can go to Phase 4 under the current gate. These are the options; choosing among them is a
change to the project's objective, so it's your call, and it has to be made **before** the lockbox
is read:

| | Option | What it means |
|---|---|---|
| A | Keep the gate | The honest strategy is SPY held long-term. The bot's remaining value is tax tooling (lot selection, December flush) and risk controls, not alpha |
| B | Re-define the objective as risk-managed equity: e.g. after-tax Calmar **and** Sharpe ≥ SPY's, max DD ≤ 20%, after-tax CAGR ≥ 60% of SPY's | `vol_trend` goes to Phase 4 as the one candidate: walk-forward, Deflated Sharpe for 17 trials, then the lockbox. It currently fails the Sharpe part (0.77 vs 0.85) |
| C | Run in a tax-advantaged account (IRA) | Removes the tax drag, but pre-tax `vol_trend` (10.5%) still trails SPY (14.6%). It changes the size of the gap, not the conclusion |

Phase 4's own gate (Calmar ≥ 1.0, max DD ≤ 15%) is stricter still. No era of the 1960-2015 screen
shows any long-only rule reaching it after tax.

## 6. What was built

- `investors/stocks.py`: `BuffettQualityCap` and `capped_weights` (proportional weights with a
  cap, the excess redistributed).
- `investors/assets.py`: `TrendSwitch` (Faber), `VolTargetTrend` (vol target × 200-day filter,
  stepped exposure, SPY/SSO/BIL), `VolTargetTrendV2` (symmetric forecast, optional wash-aware
  twin buying), `VigilantAssetAllocation` (VAA-G4), and a `band` argument on `Sleeves`.
- `backtest/engine.py`: `run(strategy, start)`. Warm-up sessions are readable but never traded or
  scored.
- `scripts/research_screen.py`: the 1960-2015 screen, with `--fetch` and `--calibrate`.
- Data: SSO, UPRO, BIL, AGG, VTI (Alpaca 2016+, Yahoo 2005-2015).

## Tests

```
$ cd quant && .venv/Scripts/pytest -q
223 passed
```

New: `test_phase3c.py` (10). It covers capped weights, cap-weighted selection, the trend switch,
warm-up sessions that are never traded, vol-target levels, the 200-day filter, step hysteresis,
the symmetric forecast, wash-aware filling, and VAA stepping aside.

## Trial ledger

| # | Hash | What | Result |
|---|---|---|---|
| 1-10 | | Phase 3 and 3b | see `docs/phase3b/strategy-report.md` |
| 11 | b4dacdfd0407bda1 | `buffett_quality_cw` | fail 4/4 |
| 12 | f0d0befd56c9f6b1 | `spy_trend` | fail 4/4 |
| 13 | fc72ab8b7b8c6e45 | `quality_cw_trend` | fail 4/4 |
| 14 | 0e2c950dd87beeb6 | `vaa_g4` | fail 4/4 |
| 15 | fec3b049f26cc683 | `vol_trend` | **fail 1/4** (beat momentum, DD and Calmar passed) |
| 16 | 065034ba1db8ae72 | `vaa_vol_blend` | fail 2/4 (DD and Calmar passed) |
| 17 | 2a1c005271d6e478 | `vol_trend_v2` | fail 4/4 |

**17 of 20 used.** The research screen and the 2008-2015 engine runs are not trials: they never
read 2016 or later. They are still looking, and the lesson says so.
