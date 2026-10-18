# Lesson 02: The backtester and the tax engine

Phase 1 answered *"what could the bot have known at the close of day t?"*. Phase 2 answers the
next two questions, and they are the two that decide whether this project continues:

> **"If the bot had acted on that knowledge, what would have happened?"**
> **"And what would have been left after the IRS took its cut?"**

The second question is not a footnote. A momentum swing bot realises almost everything as
**short-term** capital gains, taxed as ordinary income (24–32% federal plus state), while the
benchmark — SPY held and never sold — is taxed at **15–20%, and only when you finally sell**.
That gap is roughly a third of the gross return. A backtester that reports pre-tax numbers is
measuring the wrong strategy.

---

## 1. Why event-driven on daily bars, and where the honesty comes from

A vectorised backtest ("compute signals for the whole panel, shift by one, multiply by returns")
is fast and almost always wrong for this strategy, because a bracket order's outcome depends on
the *path* the price took inside a day, not on the close. We need an event loop.

The loop runs once per session *t*, in this fixed order:

| Step | What happens | Prices it may read |
|---|---|---|
| 1. Open | Resting orders that gapped through their price fill at the open | `open[t]` |
| 2. Intrabar | Remaining brackets resolve against the bar's range | `high[t]`, `low[t]` |
| 3. Close | Time stops fire; equity is marked | `close[t]` |
| 4. Decide | The strategy sees data **up to and including t** and emits intents for *t+1* | `≤ t` |

**The entire look-ahead defence is that step 4 comes last and cannot see row *t+1*.** We do not
rely on remembering to `shift(1)`. The strategy is handed a `DataView` cursor pinned to *t*;
asking it for a later row raises. Phase 1's `assert_no_lookahead` then acts as a second,
independent check on any indicator the strategy computes.

## 2. The intrabar problem: one bar, two triggers

This is the single biggest source of fake profit in daily-bar backtests. A position with a take
profit at 110 and a stop at 95 meets this bar:

| open | high | low | close |
|---|---|---|---|
| 101 | 111 | 94 | 108 |

Both levels were touched. The bar does not say in which order. Assume the take profit and the
trade is a +9% winner; assume the stop and it is a −5% loser. Repeated over a few thousand
trades, that choice is the difference between a system and a fantasy.

**Our rule is pessimistic and unconditional: on an ambiguous bar, the stop wins.** Not because
it is likely — because any other choice is a free parameter that the optimiser in Phase 4 would
happily overfit. The full resolution order is:

```
1. open <= stop           -> exit at open      (gapped through the stop; the open is the
                                               first price that actually traded)
2. open >= target         -> exit at open      (gapped through the target)
3. low <= stop AND high >= target
                          -> exit at stop      AMBIGUOUS: counted and reported
4. low <= stop            -> exit at stop
5. high >= target         -> exit at target
6. days_held >= time_stop -> exit at close     (time stop; Phase 3 sets the horizon)
```

Gaps are checked first because on a gap the open *is* the first tradable price: a stop at 95 on a
bar that opens at 91 fills at 91, not 95. Backtests that fill stops at the stop price are
quietly assuming a liquidity that was not there on exactly the days it mattered.

The engine reports an **ambiguity rate**: the share of exits resolved by rule 3. If that rate is
high, the result is mostly an artefact of the assumption, and Phase 3's stop/target geometry is
too tight to be resolved by daily bars at all. That number is a gate on the *strategy design*,
not just a diagnostic.

## 3. The limit-entry problem: fills you only get when you are wrong

The strategy enters with a **limit buy** below the market. In the backtest, a limit at 100 fills
if `low[t+1] <= 100`, at `min(open, 100)`. That looks conservative. It is not, for a subtle
reason:

> **You are only filled when the price came down to you — which is disproportionately when it
> kept going down.** Bars that merely grazed your limit and then ran up are counted as fills at
> the best possible price, with no queue, no partial fill, and nobody ahead of you.

This is adverse selection, and daily bars cannot see it. Three defences, all of them knobs the
Phase 4 sensitivity sweep will turn:

1. **A touch buffer.** In strict mode a fill requires `low <= limit - buffer`, so a bar that only
   kissed the level does not count. Default buffer is one cent; strict mode uses a few basis
   points.
2. **A participation cap.** Position size is capped at a fraction of **trailing 20-day ADV known
   at t** — not *t+1*'s volume, which would be look-ahead, and in the *optimistic* direction.
   Default 1%. Without this, a backtest happily buys $2M of a stock that trades $5M a day.
3. **Reporting.** The engine reports what share of fills were touch-only. If the edge lives in
   those fills, there is no edge.

## 4. Costs: commission is zero, everything else is not

Alpaca charges no commission, which makes it tempting to model costs as zero. What remains:

| Cost | Where it applies | Model |
|---|---|---|
| **Stop slippage** | Stops become market orders when triggered | `max(1 tick, slippage_bps × price)`, config; gap fills at the open take no extra penalty (the open is already the damage) |
| **Limit entry / take profit** | Limit orders | No slippage by construction — you get your price or better. The cost is the fill bias in §3, not the price |
| **SEC Section 31 fee** | **Sells only**, on proceeds | A per-$1M-of-proceeds rate. The rate is reset annually, so it is a config value, never a constant in code |
| **FINRA TAF** | **Sells only**, per share | A per-share rate with a per-trade cap; also config |
| **Spread** | Every entry | Implicit in the limit price. Small for large liquid names — which is what Phase 3's liquidity floor is for |

Both regulatory fees are sell-side only and tiny per trade, which is exactly why a high-turnover
bot must model them: they scale with the number of round trips, and this strategy's whole premise
is a lot of round trips. They are also **deductible from proceeds**, so they belong inside the
tax engine's basis and proceeds arithmetic, not bolted on afterwards.

---

## 5. Tax, part one: lots and holding periods

A share is not fungible for tax purposes. Every buy fill creates a **tax lot**: quantity,
acquisition date, and cost basis (price × qty + fees). Every sell fill **disposes of** lots in a
defined order and realises a gain or loss per lot.

- **Lot selection is FIFO**, matching Alpaca's default. Specific-lot identification could reduce
  tax, but it needs broker support and per-order lot instructions; it is not on the table for
  Phase 2, and pretending otherwise would overstate after-tax returns.
- **The holding period** starts the **day after** acquisition and includes the disposal date.
  Long term requires *more than* one year, so a lot bought 2026-03-02 is short term if sold on
  2027-03-02 and long term on 2027-03-03. Off by one here is a 10–17 percentage-point error in
  the tax rate on that trade. This bot should produce almost no long-term gains at all, which is
  precisely why the boundary needs a test: it is the case nobody exercises by accident.
- **All money is `Decimal`, rounded half-up to cents at defined points.** Floats in a tax ledger
  accumulate error that later surfaces as a penny of disagreement with the Java engine, and there
  is no way to tell a rounding penny from a logic bug. The schema already declares `NUMERIC`;
  the Python engine matches it.

## 6. Tax, part two: wash sales (IRC §1091), the rule that shapes the strategy

**The rule.** If you sell at a loss and acquire substantially identical stock within **30 days
before or 30 days after** the sale, the loss is **disallowed**. The window is 61 days wide and
centred on the sale. The disallowed amount is not destroyed: it is **added to the cost basis of
the replacement shares**, and the replacement lot **inherits the holding period** of the washed
shares (§1091(d)).

So a wash sale is a **deferral**, not a penalty — the loss comes back when you finally exit
without re-entering. Three things make it cost real money anyway:

1. **It moves deductions into a later tax year.** A loss washed in December becomes a next-year
   loss. You pay tax this year on gains you did not actually keep.
2. **A chain can roll forward indefinitely.** Sell at a loss, rebuy, sell at a loss, rebuy: the
   deferral compounds and only unwinds on a clean 31-day absence.
3. **It interacts badly with a tax reserve.** The reserve must set aside cash for a gain that the
   paper loss *appeared* to offset but legally did not.

**Matching is share for share, not trade for trade.** Sell 100 at a $500 loss and buy 40
replacement shares, and exactly 40% of the loss — $200 — is disallowed. The other $300 is
deductible now. This proportional split is the part naive implementations get wrong.

**The 31-day blacklist is necessary but not sufficient.** After any loss sale the bot blacklists
the symbol until `sale_date + 31`, which kills the "after" side of the window. The "before" side
survives, and the strategy's own **tranche scaling creates it routinely**:

```
day 1   buy 50 AAPL          <- lot A
day 5   buy 50 AAPL          <- lot B (second tranche; the position is working)
day 10  the stop hits; FIFO sells lot A at a loss
        -> lot B was acquired 5 days BEFORE the loss sale, inside the window
        -> lot A's loss is disallowed and lands in lot B's basis
```

No blacklist can prevent that, because the replacement purchase happened before the loss existed.
The ledger has to handle it and the backtester has to charge the strategy for it. This is the
concrete reason the tax engine is built in Phase 2 alongside the backtester instead of waiting
for the live system in Phase 6: **tranching changes the after-tax result, so Phase 3 cannot
choose a tranche policy without it.**

**What makes this tractable.** The general wash-sale problem is genuinely hard. Ours is not,
because of four scope decisions already baked in: long only, one taxable account, **no options
ever**, and "substantially identical" defined as **the same symbol**. That removes short sales,
§1256 contracts, constructive sales, IRA-triggered washes (permanently disallowed rather than
deferred), and the SPY-versus-VOO judgement call. The residual risk is holding two near-identical
ETFs at once, which Phase 3's portfolio construction avoids.

**The matching algorithm**, stated precisely because two engines have to agree on it:

```
process disposals in chronological order (date, then fill id)
for each disposal with gain < 0:
    candidates = lots of the same symbol acquired in [d-30, d+30] (calendar days),
                 excluding the disposed lot itself,
                 that were still open at the sale or were acquired after it
    sort candidates by acquired_on, then lot id
    for each candidate while unmatched shares remain:
        m          = min(unmatched_qty, candidate.qty_original - qty_already_used)
        disallowed = round_cents(|gain| * m / disposal.qty)
        candidate.cost_basis += disallowed
        candidate.holding_period_start = min(candidate.holding_period_start,
                                             candidate.acquired_on - washed_holding_days)
        record a wash_sale_adjustment row
    any unmatched share fraction keeps its loss deductible now
```

One deliberate simplification sits in that candidate filter: a lot acquired inside the window and
*already sold before* the loss sale is technically still a replacement, which would mean
retroactively adjusting an earlier disposal. We exclude it, log an `info` event, and record it as
a known limitation — under FIFO it is rare, and the alternative is a ledger that rewrites
history. If the fixtures show it firing in practice, it gets built properly.

## 7. Tax, part three: the reserve, carryforwards, and cash drag

The reserve is what turns "the account is up $40k" into "you may withdraw $28k".

- Realised short-term gains and losses **net within the tax year**. The reserve holds
  `rate × max(0, net_short_term_gain_ytd)` and is **recomputed** after every disposal rather than
  accrued trade by trade — otherwise a winning January followed by a losing February
  over-reserves.
- **A net loss year does not refund cash.** Capital losses offset capital gains without limit,
  but only **$3,000** of a net loss is deductible against ordinary income per year; the rest
  **carries forward indefinitely**. The engine therefore carries a `loss_carryforward` across
  years, and a bad year shows up as a future tax shield rather than a rebate. Modelling it as a
  rebate would flatter every multi-year backtest.
- **Available to withdraw = equity − reserve.** The reserve sits in cash, counts toward equity,
  and is **not** available for position sizing. It is a genuine drag: money the strategy earned
  but cannot compound. The backtest models that rather than assuming tax gets paid from an
  outside wallet.
- **Estimated taxes (1040-ES)** are due quarterly, and the safe harbour is the lesser of 90% of
  the current year's tax or 100% of last year's (110% above $150k AGI). Phase 6 produces the
  report; Phase 2 only has to make the reserve big enough and correctly timed.
- **The December flush** harvests losses before year end — and if the bot re-enters within 30
  days, §1091 disallows exactly the loss it was harvesting. So a flush implies a 31-day absence,
  which means sitting out a historically strong stretch of the calendar. That is a real cost, it
  is configurable, and Phase 4 measures it. Phase 2 only has to make it *measurable*.

## 8. Why two engines and a fixture file

The Python engine drives backtests; the Java engine (Phase 6) drives the live ledger and the tax
report. Two implementations of the same law will diverge, and the divergence will be a single
cent somewhere in a basis adjustment. `shared/tax-fixtures/` is the contract: a JSON scenario in,
an exact expected ledger out, and **both engines must pass every file**. When they disagree, one
of them is wrong and the fixture says which.

Determinism requirements, so the two can agree at all: `Decimal` arithmetic, half-up rounding to
cents at named points, FIFO with `(date, fill_id)` tie-breaks, and disposals processed in a
defined order.

## 9. Baselines: the bar Phase 4 has to clear

The strategy is not competing against zero. It is competing against **what you would otherwise do
with the money**, and that comparison is harder than it looks:

- **SPY buy and hold.** Bought once, never sold. Gains are **unrealised and untaxed** for the
  whole period; qualified dividends are taxed annually at 15%. To compare fairly we report
  **both** the running after-tax NAV *and* the **post-liquidation** value, where every strategy
  pays tax on everything it still holds at the end. Without the terminal liquidation, SPY's
  deferred tax bill is invisible and the benchmark looks better than it is. Without the running
  curve, drawdowns are wrong.
- **Naive momentum.** Top-decile 12-month total return, monthly rebalance, no regime filter, no
  LLM, taxed short term. This isolates what the Phase 3 machinery actually adds. If the funnel
  cannot beat a screen anyone could run in an afternoon, the funnel is not the edge.

Baselines do double duty: they are also **the backtester's self-test**. SPY buy-and-hold run
through our engine has to reproduce SPY's known CAGR and max drawdown for the period to within
rounding. If it does not, the engine is broken and nothing downstream means anything. That is the
Phase 2 gate, and it is checkable before any strategy exists.

## 10. Metrics, and the ones that decide the gate

Computed on both the pre-tax and after-tax equity curves: CAGR, annualised volatility, Sharpe,
Sortino, max drawdown, **Calmar** (CAGR ÷ max DD), hit rate, average win versus average loss,
exposure, turnover — plus the tax-specific ones: effective tax rate, deferred loss balance, and
the flush's cost.

Two choices worth stating:

- **Calmar is the headline, not Sharpe.** The Phase 4 gate is drawdown constrained (max DD ≤
  15%), and Sharpe is indifferent to whether the volatility arrived as a smooth grind or as one
  30% hole.
- **The risk-free rate is a config value, default 0, and identical for the bot and every
  baseline.** T-bills paid ~0% in 2021 and ~5% in 2024. Quoting a Sharpe without saying which
  rate was used, or using different rates for strategy and benchmark, is how backtests win
  arguments they should lose.

Deflated Sharpe and PBO belong to Phase 4, but they need the number of parameter trials, so
`metrics` records the run's configuration hash from the start.

## 11. Performance, because Phase 4 needs hundreds of runs

Walk-forward plus CPCV means running this engine hundreds of times over 2016–2026: ~2,450
sessions × ~1,800 symbols. So the panel is loaded **once** from `bar_segments` into dense `numpy`
arrays indexed `[session, symbol]` (raw OHLCV, `adj_factor`, `segment_id`), and the
point-in-time `DataView` is nothing more than a row limit on those arrays. That is a few hundred
megabytes of RAM, and it turns a run into seconds instead of minutes — the difference between
Phase 4 being a week of compute and an afternoon.

Indicators are computed **within a single `(symbol, segment_id)`**, never across one: Phase 1
found ~70 reused tickers, and an ATR window that spans Contura Energy and Coterra Energy is
measuring a corporate action, not volatility.

---

## 12. What the baselines actually show

Run on the Phase 1 data (2,698 sessions x 1,781 symbols, 2016-01-04 to 2026-09-25), $1M start,
32% short-term / 15% long-term, quarterly estimated payments:

| | SPY buy & hold | Naive momentum (top 10, monthly) |
|---|---|---|
| CAGR (pre-tax) | **14.85%** | 12.21% |
| Volatility | 17.47% | 28.12% |
| Sharpe (rf = 0) | 0.88 | 0.55 |
| Max drawdown | **-33.81%** | -36.90% |
| Calmar | 0.44 | 0.33 |
| Round trips | 1 | 288 |
| Hit rate | - | 50.3% |
| **Effective tax rate** | **15.0%** | **31.5%** |
| Wash sales | 0 | 66 |
| Tax paid during the run | $52,820 | $775,643 |
| **Post-liquidation value** | **$3,935,398** | $3,195,954 |

**The gate passes.** SPY's own total-return series computed straight from `bar_segments`, with no
backtester involved, gives CAGR 15.02% and max drawdown **-33.79%**, peaking 2020-02-19 and
troughing 2020-03-23. The engine reproduces the drawdown to two decimal places and the correct
crash dates, and the CAGR to within 0.2 percentage points - the residual being whole-share
rounding and the one-session delay between deciding and filling. At $1M, where share granularity
is immaterial, the engine gives 15.05%.

Two things this table settles before Phase 3 starts:

1. **The benchmark is hard.** SPY returned 14.85% a year with a 15.0% effective tax rate, because
   nothing is realized until the end and only dividends are taxed along the way. Naive momentum
   earned less, in a deeper drawdown, and handed over **twice the tax rate** on the way.
   Most of that gap is not skill, it is tax treatment.
2. **The tax engine changes the ranking, not just the reported number.** Pre-tax, momentum trails
   SPY by 2.6 percentage points of CAGR. After tax and liquidation it trails by $739,000 on a $1M
   account. A pre-tax backtest would have understated the gap by more than half.

The December flush works and is measurable, which is all Phase 2 owed it:

| | post-liquidation | effective tax | wash sales | flush exits |
|---|---|---|---|---|
| flush off | $3,195,954 | 31.5% | 66 | 0 |
| flush on | $3,505,359 | 31.3% | 88 | 28 |

Harvesting beat not harvesting here, and it created 22 extra wash sales doing it - the blacklist
kept the re-entry outside the window often enough for the deferral to be worth more than the
disallowances cost. Whether that holds out of sample is a Phase 4 question, not a Phase 2 one.

**A note on what these baselines do *not* exercise.** Neither uses a bracket, so both report a 0%
ambiguity rate and a 0% touch-only fill rate. The two assumptions from §2 and §3 - the ones most
likely to make a backtest lie - are covered by unit tests here and will get their first real
workout in Phase 3, when the strategy that depends on them exists. Watch those two numbers first
when it does.
