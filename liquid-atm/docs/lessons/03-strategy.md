# Lesson 03: The strategy (regime → screener → bracket → book)

Phase 2 built an honest referee. Phase 3 builds the first player worth refereeing. The bar it has
to clear is already on the wall (`docs/phase2/baseline-report.md`):

| | SPY buy & hold | Naive momentum |
|---|---|---|
| Post-liquidation value ($1M start, 2016–2026) | **$3.94M** | $3.20M |
| Max drawdown | −33.8% | −36.9% |
| Effective tax rate | 15.0% | 31.5% |

Naive momentum lost to SPY on every axis, and half the gap was tax. So the funnel has to do two
things naive momentum did not: **avoid the deep drawdowns** (that is what the regime filter is
for) and **make each short-term trade earn enough to pay roughly double the tax rate** (that is
what the screener and the bracket are for). If it cannot, the honest result is "stop at Phase 4",
and Phase 3 is how we find that out cheaply.

---

## 1. The most important rule of Phase 3: we are not allowed to look at everything

Every configuration we run against history is a *trial*. Run 200 trials, keep the best, and you
have mostly measured luck. Phase 4's **Deflated Sharpe Ratio** corrects for this, but only if we
tell it honestly how many trials there were. So Phase 3 works under three constraints:

1. **A lockbox.** The last two years (**2024-10-01 → today**) are never run during Phase 3. The
   backtest script refuses to touch them without an explicit `--unlock-lockbox` flag, which only
   Phase 4's final run uses. Everything below is tuned on **2016-01 → 2024-09** only.
2. **Pre-registered defaults.** The parameters in §§2–6 are written down *now*, chosen from the
   literature and from first principles, before any backtest of the funnel exists. The first run
   uses them unchanged.
3. **A trial budget of 20.** Each run is identified by `BacktestConfig.fingerprint()` plus the
   strategy's own parameter hash, and saved to `backtest_runs`. Phase 4 reads that count. If we
   blow through 20, that is itself a finding: the idea needs too much fitting to work.

The in-sample gate is deliberately a *weak* test. Beating the baselines on data we were allowed
to stare at is necessary, nowhere near sufficient. Phase 4 is the real exam.

## 2. The regime filter: why, and why it must not be a light switch

Momentum's worst losses are not random. Daniel & Moskowitz ("Momentum Crashes", 2016) show they
cluster in **rebounds after bear markets**: the losers that fell hardest bounce hardest, and a
long-only momentum book is holding last year's winners, which lag. Separately, a trend filter on
the index cuts the left tail of almost any long-only equity strategy, because the biggest drawdowns
(2008, 2020, 2022) all happened below a falling 200-day average.

Our gate is **maximum drawdown ≤ 15%**. The SPY benchmark saw −33.8%. No screener can get from one
to the other while it is fully invested through a crash; the regime filter is the only component
that *can*.

Three inputs, all known at the close of day *t*:

| Input | Definition | Why |
|---|---|---|
| **Trend** | SPY adjusted close vs its 200-day SMA | The slow, well-documented one. Catches 2008/2022-style bear markets |
| **Breadth** | % of *today's* index members whose close is above their own 50-day SMA | A narrow rally (few leaders, many decliners) is fragile even when SPY looks fine. Uses point-in-time membership, so no survivorship |
| **Volatility** | SPY 20-day realized vol, annualized | Stops are sized in ATR, but correlation spikes in high vol, so ten "independent" 0.75% risks become one big one |

They combine into three states, not two:

| State | Condition | Effect |
|---|---|---|
| `RISK_ON` | trend up **and** breadth ≥ 50% **and** vol ≤ 25% | Normal risk per trade, up to 3 new entries a day |
| `CAUTION` | trend up, but breadth or vol fails | Half risk per trade, at most 1 new entry a day |
| `RISK_OFF` | trend down | **No new entries.** Open brackets run to their own exits |

**Hysteresis.** A raw "close > SMA200" flips on and off every few days when the index sits on the
line, and each flip is a round of entries and stop-outs. So trend turns *down* only when SPY
closes more than **1% below** its SMA200, and turns back *up* only when it closes more than **1%
above** it. The 2% band costs a little lag at genuine turning points; it buys a lot less churn.

**Why `RISK_OFF` does not force-sell.** Every open position already has a stop that bounds its
loss. Forcing an exit adds a sale (often a short-term gain at the full rate), creates wash-sale
exposure if the regime flips back within 30 days, and is exactly the decision most exposed to
whipsaw. Phase 4 will measure "force flat on `RISK_OFF`" as a variant; it is not the default.

## 3. The screener: 1,000 names → ~10 in five filters

Order matters only for speed; every filter uses data at or before *t*.

1. **Eligibility** (cheap, removes most names)
   - a member of the index *today* (point-in-time, from Phase 1) and traded today
   - raw close ≥ **$10**, 20-day average dollar volume ≥ **$25M**
   - one corporate identity for the whole 252-day lookback (`same_segment`, lesson 01 §5b)
   - not held, not on the wash-sale blacklist (the engine also blocks it; filtering here means a
     blocked name does not waste a slot)
2. **Trend alignment**: close > SMA50 > SMA200 on adjusted prices. A breakout in a stock that is
   below its long average is a bear-market rally, not momentum.
3. **Momentum rank**: 126-day return divided by 126-day volatility, ranked across everything that
   passed (1) and (2); keep the **top 20%**. Dividing by volatility is the single change from the
   naive baseline that matters most: raw return ranks reward whatever moved most, which is mostly
   whatever is most volatile, which is why the baseline ran at 28% vol.
4. **Trigger**: today's close is the highest close of the prior **20** sessions (a Donchian
   breakout) **and** relative volume (today's volume ÷ 20-day average) ≥ **1.5**. The rank says
   *this stock has momentum*; the trigger says *and it is moving now*, which is what a 10-day
   holding period needs.
5. **Not overextended**: (close − SMA20) ≤ **3 × ATR**. A stock 5 ATRs above its 20-day average has
   already had the move; buying it is buying the stop-out.

Survivors are sorted by momentum score, then by relative volume. Portfolio construction (§6) takes
from the top until it runs out of slots, sector room or risk budget.

**There is no LLM here yet.** Phase 5 adds the catalyst veto between the screener and the book. The
funnel has a pass-through hook for it now, so Phase 5 inserts a component rather than rewiring.

## 4. The entry: which limit, and why not the obvious one

Lesson 02 §3 explained the adverse-selection problem: a buy limit *below* today's close fills
precisely on the days the stock falls to it, so the fills you get are biased toward the trades
that were going wrong. A breakout strategy is especially exposed, because a breakout that
immediately retraces is usually a failed breakout.

So the entry limit sits slightly *above* the close:

```
entry_limit = close + 0.25 × ATR
```

- If tomorrow opens at or below it (most days), we fill **at the open**: no adverse selection,
  because we were not waiting for a dip.
- If tomorrow gaps up more than a quarter-ATR, we **skip** the trade. That is deliberate: the
  stop and target were computed from today's price, and a big gap has already spent part of the
  expected move while widening the real risk.

The two diagnostics from lesson 02 that "get their first real workout" here are the **touch-only
fill rate** (should be low with this design, since most fills are at the open) and the **expired
entry rate** (how often the gap filter skips a trade). Both get reported on every run.

## 5. The exit: why the bracket geometry alone is worth exactly nothing

ATR is Wilder's 14-day Average True Range. The bracket is

```
stop        = entry_limit − 2 × ATR
take_profit = entry_limit + 3 × ATR
time stop   = 10 sessions (exit at the close)
```

Here is the uncomfortable math. Treat the price as a random walk with volatility σ and drift μ per
day. The probability of hitting **+a** before **−b** is

```
                 1 − e^(k·b)
P(win) = ───────────────────────      where k = 2μ / σ²
           e^(−k·a) − e^(k·b)
```

With **no drift** this collapses to **b / (a + b)**. For our 3-ATR target and 2-ATR stop that is
2/5 = **40%**, and the expected value is 0.4 × 3 − 0.6 × 2 = **exactly zero**. This is the
optional-stopping theorem: no arrangement of stops and targets turns a fair game into a winning
one. "Let winners run, cut losers short" does not, by itself, make money. Wide-target/tight-stop
systems win less often by exactly the amount they win more when they do.

**The only thing that makes a bracket profitable is drift in your favour while you hold it.** With
a and b measured in units of daily σ:

| Daily drift μ (in σ) | ≈ annualized, for a 2%-vol stock | P(win) | Expectancy per trade |
|---|---|---|---|
| 0 | 0% | 40.0% | 0.00 R |
| 0.02 σ | ~10% | 42.4% | +0.06 R |
| 0.05 σ | ~25% | 46.1% | +0.15 R |
| 0.10 σ | ~50% | 52.2% | +0.30 R |

(R = the amount risked, the entry-to-stop distance. ATR is treated as ≈ σ here for readability; in
practice ATR runs 1.2–1.6 σ, which changes the scale, not the conclusion.)

Read that table against the costs. Every stop pays slippage; every ambiguous bar is scored as a
loss; every short-term gain pays 32% while every loss saves 32% only if there are gains to net it
against. **The screener exists to find stocks whose drift over the next 10 days is meaningfully
positive. The bracket only controls the shape of the outcome; it does not create one.** That is
why the hit rate and expectancy per trade are the first numbers to look at, before CAGR.

**Why 3:2 and not 2:1 or 1:1?** A wider target lets the trades with real drift pay for the ones
without, and a 2-ATR stop sits outside a typical day's noise (1 ATR) so ordinary wiggles do not
stop us out. A 10-day time stop matches the horizon over which breakout drift is documented and
keeps the capital turning. These are pre-registered starting points; Phase 4's stability heatmap
asks whether neighbouring values (2.5/1.5, 4/2, 7 or 15 days) give similar answers. If only 3:2
works, it is overfit.

**ATR on which prices?** Stops are real orders at real prices, so the levels must be on the *raw*
scale (lesson 01 §2). But a 14-day raw window that spans a split would see a fake 50% "true
range". So ATR is computed on *adjusted* prices, where splits are invisible, and then rescaled to
today's raw scale by `raw_close / adj_close` on day *t*. Ratios inside the window are unaffected
by how the adjustment is normalised, so this is correct whichever way the factor is anchored.

## 6. Building the book: sizing, heat, sectors and tranches

**Fixed-fractional sizing** is already in the engine (lesson 02):

```
shares = risk_fraction × equity / (entry_limit − stop)
```

With `risk_fraction = 0.75%` and a stop 2 ATR below, a stock with a 2% ATR has a 4% stop distance,
so the position is 0.75% / 4% ≈ **19% of equity**. Too big for one name. So three caps apply, in
this order:

| Cap | Default | What it protects against |
|---|---|---|
| Position notional | ≤ **15%** of equity | One stock that gaps through its stop |
| Portfolio heat (Σ open risk to stops) | ≤ **6%** of equity | Everything stopping out at once |
| Sector | ≤ **3 positions** per sector | Ten "different" semiconductor names that are one trade |

**Why heat matters for the 15% drawdown gate.** Ten positions at 0.75% each is 7.5% at risk, and
in a correlated sell-off they do all stop out together. Capping heat at 6% means the worst
everything-at-once day costs about 6% *plus gap slippage*. Gaps are the weakness: in March 2020
stops filled well below their levels, which is why heat is a floor on the bad day, not a ceiling,
and why the regime filter has to do the rest.

**Sectors** come from `instruments.sector` (iShares' own classification, stored in Phase 1). Names
with no sector go into one "Unknown" bucket, which gets the same cap. The sector ETFs (XLK, XLF, …)
are allowed through the screener and count against their own sector.

**Tranches = entry pacing, not pyramiding.** At most **3 new entries a day** (1 in `CAUTION`), so a
full book is built over 3–4 sessions instead of on one day's signals. That is time diversification:
one bad day of breakouts cannot fill the whole book. The alternative meaning of "tranches", adding
to a winner, is deliberately not used. It needs order replacement on the bracket, and the Phase 2
fixture `tranche_scaling_creates_a_wash_then_recovers_it` shows how it turns an ordinary stop-out
into a wash sale.

**`CAUTION` halves risk per trade (0.375%)**; it does not tighten the heat cap, so the book can still
fill. It just fills with smaller bets.

## 7. Speed without look-ahead: precomputed indicators and the truncation test

The naive baseline ranks once a month. The funnel screens **every day**, about 1,000 names ×
2,200 sessions. Computing SMA/ATR/rolling highs in a Python loop per name per day would turn a
0.5 s run into minutes, and Phase 4 needs hundreds of runs.

So indicators are computed **once**, as whole-panel numpy matrices, and the strategy reads row *t*.
That is only safe if every indicator is *causal* (row *t* depends on rows ≤ *t*). A rolling mean is;
a centred mean, a `fillna(method="bfill")` or a normalisation over the full sample is not, and
each of those is an easy mistake to make.

The defence is a test, not a code review: **the truncation invariance test.** For a sample of
sessions *t*, compute every indicator on the panel cut off at *t* and check that row *t* is
identical to row *t* of the full-panel computation. Any indicator that peeks at the future fails,
whatever the reason. It is the same idea as Phase 2's "a strategy that reads tomorrow is caught",
applied to the precomputed path, which bypasses the `DataView` cursor.

The funnel only reads indicator rows through `view.t`, so it still cannot ask for a later row.

Segments are handled the same way as in the baseline: a rolling window that crosses a ticker
change is masked to NaN, which simply makes that name ineligible until it has a clean history.

## 8. One code path for backtest and live

The same `MomentumFunnel.on_close()` that runs inside the backtester produces today's candidates for
live trading. `scripts/screen_today.py` loads the panel up to the latest session and prints the
trade intents the bot *would* place tomorrow, with the regime state and the reason each name passed.
There is no second "live screener" to drift away from the tested one. Phase 6 makes Java pull these
intents; Phase 3 only proves they come out of the tested code.

## 9. What "beats the baselines in sample" means, precisely

On **2016-01-04 → 2024-09-30** at $100k, with the same tax and cost settings as Phase 2, the funnel
with the pre-registered defaults passes when:

1. Its **post-liquidation value** beats both SPY buy & hold and naive momentum over the same window.
2. Its **max drawdown is ≤ 20%**. This is looser than Phase 4's 15% on purpose: in-sample is for
   finding out whether the idea is alive, not for fitting it to the gate.
3. Its **Calmar ratio beats SPY's** over the same window.
4. **The result survives strict fills**: rerun with `entry_buffer` raised so touch-only fills no
   longer count. If the edge disappears, it lived in fills that might not have happened.
5. **The diagnostics are reported**: hit rate, expectancy in R, average days held, exit-reason mix
   (target / stop / time), ambiguous-bar rate, touch-only rate, expired-entry rate, days in each
   regime, effective tax rate, wash-sale count, and the trial count so far.

**What failing looks like, and why it is fine.** 2016–2024 was a strong bull market for large caps,
which is the hardest possible period for a strategy that spends time in cash to beat buy & hold on
*return*. A likely outcome is "lower return, far lower drawdown". If so, the honest comparison is
risk-adjusted (Calmar), and Phase 4 decides whether the reduced drawdown is worth the tax cost. If
the funnel cannot even win on Calmar in sample, we have learned that cheaply and stop.

---

## Build spec

**New package `quant/src/liquid_atm_quant/strategy/`**

| File | Contents |
|---|---|
| `params.py` | `FunnelParams`: every number in this lesson as a frozen dataclass, with `fingerprint()` |
| `indicators.py` | Causal whole-panel matrices: SMA, Wilder ATR (adjusted, rescaled to raw), rolling max, relative volume, risk-adjusted momentum, segment masking. Cached per panel |
| `regime.py` | `RegimeFilter`: trend with hysteresis, breadth, realized vol → `RISK_ON` / `CAUTION` / `RISK_OFF` |
| `screener.py` | The five filters of §3, returning ranked `Candidate`s with a reason string per name |
| `book.py` | Portfolio construction: position cap, heat cap, sector cap, daily entry pacing |
| `funnel.py` | `MomentumFunnel`, which implements the `Strategy` protocol: regime → screen → (veto hook) → book → `BracketIntent`s |

**Small engine changes**

- `PortfolioSnapshot` gains each open position's entry price and stop, which the heat cap needs.
- `BracketIntent` gains an optional `max_notional`, which the engine applies alongside the ADV and
  cash caps.
- The diagnostics gain expectancy in R, the exit-reason mix and a per-regime day count.

**Scripts**

- `run_backtest.py --strategy funnel [--start --end] [--strict-fills]`, with a lockbox guard that
  refuses any `--end` after 2024-09-30 without `--unlock-lockbox`.
- `screen_today.py`: today's regime, candidates and intents, from the same code path.

**Tests**

- indicators: hand-computed ATR and SMA, segment masking, and the **truncation invariance test** (§7)
- regime: hysteresis does not flip inside the band; each state's conditions
- screener: one synthetic name that fails each filter, one that passes all five
- book: the position, heat and sector caps and the daily pacing limit, each binding in turn
- funnel end-to-end on a synthetic panel: a planted breakout produces exactly one bracket at the
  right levels, and a `RISK_OFF` regime produces none
- the lockbox guard refuses a run that reaches past 2024-09-30

**Report**: `docs/phase3/strategy-report.md` with the §9 gate table, the diagnostics, the strict-fill
rerun and the trial count.

**Known limitations, carried in deliberately**

- **No earnings calendar.** There is no free point-in-time earnings calendar, so some trades will
  hold through an earnings gap. The stop bounds the loss but cannot stop a gap. Phase 5 can estimate
  the next report from past EDGAR 8-K Item 2.02 dates (point-in-time valid) and test excluding them.
- **Sector labels are the latest known**, not point-in-time. Sector membership rarely changes for a
  large cap, and the label only feeds a diversification cap, not a signal, so the leak is small and
  biased toward *less* diversification being enforced, not toward more return.
- **Fixed brackets only.** No trailing stop or move-to-breakeven; both need order replacement, which
  is Phase 6 territory. They are candidates for Phase 4 variants once the OMS can do them.

---

## 10. What actually happened (written after the run)

The pre-registered funnel **failed** in sample: −0.12R per trade, −6.3% CAGR and a −51% drawdown
(`docs/phase3/strategy-report.md`). Three lessons are worth more than the result.

**A diagnostic that contradicts itself is a bug until proven otherwise.** The first run reported a
28-day average hold against a 10-session time stop. That number was impossible, so it was chased
before the result was believed. It led to positions in acquired companies that never left the book,
and to a reused ticker whose *new* company's price stopped out the old position. The defect had
also been flattering SPY against naive momentum since Phase 2. A test suite checks what you thought
of. A reality check on the diagnostics catches what you didn't.

**When a strategy loses, ask where the drift is, not which parameter to change.** §5 says brackets
only shape outcomes and drift decides the sign. So instead of tuning stops (the tempting move, and
the one that burns trials), the forward-return study measured each screener stage's drift directly:

- Trend and momentum have a small positive drift that grows over **months**: the textbook effect,
  just weak here.
- The breakout-on-volume trigger has **negative** drift over 5 to 21 sessions. Large caps that close
  at a 20-day high on heavy volume tend to give some of it back: short-term reversal.

The funnel was a slow, honest machine pointed at a signal with the wrong sign for its horizon. No
stop/target ratio fixes that; at best it would lose more slowly.

**The trial budget did its job.** With 18 trials left, the tempting next step is to try stop and
target combinations until one is green. With zero drift underneath, a green one would be noise, and
Phase 4's Deflated Sharpe would say so. The next change has to be a *different hypothesis*, chosen
for a reason the forward-return table supports, and counted.
