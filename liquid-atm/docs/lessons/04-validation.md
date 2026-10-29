# Lesson 04: validation, or how a winning backtest gets checked

Phase 3d ended with the first strategy to pass all four in-sample checks: `vol_trend_noise`,
$384,832 after tax against SPY's $294,152, with a −14.9% max drawdown. Phase 4 asks the only
question that matters about a number like that: **was it skill, or was it the best of many
tries?** Two tools answer it. One is statistics on the data we already looked at; the other is
data we never looked at.

The short answer: it was not skill we can rely on. The statistics said so before the lockbox was
opened, and the lockbox agreed, by a wide margin.

## 1. Write the rules down first

Every check in this phase was written into `docs/phase4/preregistration.md` and committed
(f2e27c4) *before* any of them was computed. That order is the whole point. Once you have seen a
result, every choice you make afterwards, like which statistic, which threshold, or which outlier
to drop, quietly bends toward the answer you want. A commit timestamp is a cheap way to prove you
didn't.

The rules were: Deflated Sharpe ≥ 0.95 in sample; then, in the lockbox, beat SPY after tax, keep
the drawdown within 15%, and beat `vol_trend` without the overlay. All four had to pass.

## 2. The Deflated Sharpe Ratio

Run 24 strategies that have no edge at all, and the best of them will still show a good Sharpe
ratio, by luck. Bailey & López de Prado (2014) estimate how good: if the trials' Sharpes vary
with variance V, the best of N is expected to reach about

    E[max SR] ≈ √V · ((1 − γ)·Φ⁻¹(1 − 1/N) + γ·Φ⁻¹(1 − 1/(N·e)))      γ ≈ 0.577

The DSR is then the probability that the candidate's true Sharpe is above that bar. It allows for
how many days of data there are, and for skew and fat tails, which make a Sharpe estimate less
reliable. Everything is computed on daily returns. Annualizing first is a classic way to make the
statistic lie.

**Our result: DSR 0.00.** The candidate's after-tax Sharpe was 1.35. The bar from 24 trials was
3.16. That bar is high because one trial, `orb_in_play`, lost almost the whole account and has a
Sharpe of −6.9. A single trial that extreme makes the spread of Sharpes, and so the bar, enormous.

That is a weakness in our pre-registered rule: a catastrophic loser shouldn't make luck on the
*upside* look bigger. So we checked how much it mattered, clearly labelled as after the fact:

| How the trials' variance is measured | Bar (best of 24, by luck) | DSR |
|---|---|---|
| As pre-registered (all 24 trials) | 3.16 | 0.00 |
| ORB left out | 0.96 | 0.88 |
| Robust (median absolute deviation) | 0.46 | 1.00 |

Two of the three fail. The one that passes is the most favourable choice, picked after seeing the
result, and adopting it would be exactly the kind of after-the-fact choice §1 exists to stop.
**The rule stands: check 1 failed, and the verdict was NO-GO before the lockbox was opened.**

The lesson for next time: pre-register a *robust* variance estimate, or drop trials that ruined
their account, and decide that before looking.

## 3. Probability of Backtest Overfitting (reported, not gating)

CSCV (Bailey, Borwein, López de Prado & Zhu 2017) cuts the 2,200 sessions into 16 blocks. It then
tries all 12,870 ways of calling half of them "in sample". Each time, it picks the best trial on
that half and checks where the pick ranks on the other half. PBO is how often the pick lands in
the bottom half.

**Ours: 16.9%.** That sounds reassuring, but read what it measures: whether the *ranking among
our 24 trials* holds up across 2016-2024. The Noise Band trials were the in-sample winner in 89%
of the splits, and they stayed near the top on the other half. PBO can't detect an edge that was
real in the whole sample and then stopped. Only new data can. Reporting it, not gating on it, was
the right call.

## 4. The bootstrap (reported, not gating)

A stationary block bootstrap resamples the daily return *difference* (candidate minus SPY) in
blocks of about 21 days, which keeps calm and stormy stretches intact. It answers: given the noise
in 8.7 years of returns, how sure are we that the candidate beats SPY at all?

**P(beats SPY) = 60%, with a 90% interval of −6.4% to +9.1% a year.** Most of the candidate's
in-sample advantage was a better drawdown, not a higher return. Its expected return edge was
+1.2% a year, well within noise. This number already said that "beats SPY" was close to a coin
flip.

## 5. The lockbox

The lockbox (2024-10-01 onward) was set aside in Phase 3 and never read. `run_phase4.py lockbox`
enforces three rules:

- It won't run unless the pre-registration is committed and unchanged.
- It writes `lockbox_opened.json` *before* computing anything, so a crash still counts as an
  opening.
- It refuses to run a second time.

The user chose to open it even though check 1 had already failed, for information. That was a
reasonable choice: with 24 of 25 trials used, the unseen years were worth more as an answer now
than as a reserve.

Window: 2024-10-01 to 2026-10-28, 521 sessions, $100,000 from scratch, after tax and
post-liquidation:

| | Value | CAGR | Max DD | Sharpe |
|---|---|---|---|---|
| `vol_trend_noise` | $103,182 | 2.0% | −15.3% | 0.21 |
| `vol_trend` alone | $112,903 | 6.5% | −9.1% | 0.58 |
| SPY | **$133,167** | 17.1% | −18.8% | 1.05 |

**All three lockbox checks failed.** It lost to SPY by $30k, its drawdown was just past −15%, and
the overlay *subtracted* about $9.7k compared with `vol_trend` alone. Run continuously from 2016,
the strategy now ends below SPY ($374,998 vs $398,321). It gave back its whole in-sample lead in
two years.

## 6. Why the overlay stopped working

`lockbox_diagnostic.py` runs the Noise Band on its own (trial 18's rules), pre-tax:

| Period | Per year | Hit rate | On days SPY fell > 1% | On quiet days |
|---|---|---|---|---|
| In sample 2016 to Sep 2024 | +18.1% | 44% | +0.83% | −0.22% |
| Lockbox Oct 2024 to Oct 2026 | **−0.6%** | 42% | +0.92% | −0.25% |

The "crash insurance" still worked: it still made money on big down days. But in-sample the
strategy earned about +18% a year in total; in the lockbox that went to zero. Every year from 2018
to 2024 was positive; 2025 was −1.4% and 2026 so far is −11.2%.

Two explanations fit, and two years can't separate them:

1. **Decay after publication.** The paper came out in May 2024. McLean & Pontiff (2016) found
   that published anomalies lose about half (58%) of their returns after publication, and
   more of them once they are easy and cheap to trade. An intraday SPY rule is about as easy to
   trade as anything gets.
2. **A quieter regime.** The strategy pays in trending, volatile sessions. If 2025-2026 had fewer
   of them, it would bleed small losses on quiet days. That is the −0.22% to −0.25% column, which
   barely changed.

Either way, the conclusion for money is the same.

## 7. What this phase teaches

- **A post-hoc winner is a hypothesis, not a result.** Phase 3d said so in its report, and the
  lockbox showed why.
- **Pre-registration protected us twice.** It stopped a "drop the outlier" fix to check 1, and the
  lockbox couldn't be re-run with a tweak.
- **Small edges are invisible in 9 years.** A +1-2%/yr edge over SPY is inside the noise of
  almost any backtest we can afford. A strategy that clearly beats SPY needs a big, cheap edge,
  and big, cheap edges don't survive being published.
- **The thing that did survive was risk control.** `vol_trend` alone had a −9.1% drawdown in
  the lockbox against SPY's −18.8%. It lagged in a strong bull market, which is what it was
  expected to do (lesson 03c).

## Sources

- Bailey, D. & López de Prado, M. (2014). *The Deflated Sharpe Ratio.* Journal of Portfolio
  Management 40(5).
- Bailey, D., Borwein, J., López de Prado, M. & Zhu, Q. (2017). *The Probability of Backtest
  Overfitting.* Journal of Computational Finance 20(4).
- Politis, D. & Romano, J. (1994). *The Stationary Bootstrap.* JASA 89(428).
- McLean, R. D. & Pontiff, J. (2016). *Does Academic Research Destroy Stock Return
  Predictability?* Journal of Finance 71(1).
- Zarattini, C., Aziz, A. & Barbon, A. (2024). *Beat the Market: An Effective Intraday Momentum
  Strategy for S&P500 ETF (SPY).* SFI Research Paper 24-97.
