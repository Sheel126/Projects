# Lesson 03b: Famous investors as testable rules

Phase 3's funnel failed its gate (−0.12R a trade, `docs/phase3/strategy-report.md`). The forward-
return study showed why: buying a breakout day picks short-term *reversal* in large caps, and the
momentum edge that does exist is slow, measured in months. So Phase 3b asks a different question:
**do the methods of famous long-horizon investors survive our engine, our taxes and our costs?**

The investors come from `questflowai/investorskills`, a set of prompt files describing how each
investor thinks. Those files are prose with no numbers ("demand a margin of safety"), so they can't
be backtested as written. This lesson turns each one into exact rules **before** any of them is
run. Everything in §4 is fixed now. Changing a number afterwards is a new trial (§5).

---

## 1. Why a pre-screen, and what it said

Testing many strategies manufactures winners. Run eight, and the best one looks good partly by
luck. Before spending engine runs we can ask a cheaper question with better data: **did the factor
behind each style pay in big US stocks over our window?** Ken French's data library publishes
monthly returns for portfolios sorted by size and by each characteristic. It is built from CRSP,
which includes every delisted stock, so it is better data than ours. We keep only the big-stock
half, because our universe is the Russell 1000 and most published anomalies are much weaker among
large caps.

`scripts/factor_prescreen.py --history`, 2016-01 → 2024-09 (the lockbox is not read):

| Factor, big stocks | 1963–2015 long side − market | **2016–2024 long side − market** | Stands in for |
|---|---|---|---|
| Profitability (robust − weak) | +0.9%/yr (t 1.7) | **+2.7%/yr (t 2.2)** | Buffett, Greenblatt |
| Investment (conservative − aggressive) | +1.8%/yr (t 2.4) | −0.0%/yr (t 0.0) | Buffett |
| Value (high − low book/market) | +2.3%/yr (t 2.1) | −0.1%/yr (t 0.0) | Greenblatt, Lynch, Templeton |
| Momentum (12-2) | +3.1%/yr (t 3.4) | −0.8%/yr (t −0.4) | CANSLIM |
| Long-term reversal | +2.5%/yr (t 2.4) | −1.0%/yr (t −0.3) | Templeton |

**The prediction, written down before any Phase 3b run:** only quality/profitability paid in large
caps over this window. Value, momentum and reversal all worked for fifty years and then did
nothing. So we expect `buffett_quality` to have the best odds, Greenblatt (half quality, half
value) to sit in between, and Lynch, CANSLIM and Templeton to struggle. The ETF strategies don't
depend on these factors and are judged on drawdown control.

This is the McLean & Pontiff (2016) effect in action: anomaly returns fall by about half after
publication, and some disappear.

## 2. The new data: point-in-time fundamentals

Five of the eight strategies need company financials. They come from **SEC XBRL company facts**
(`companyfacts.zip`, free, every 10-K and 10-Q figure since 2009 with its filing date).
`data/fundamentals.py` loads them and `backtest/fundamentals.py` serves them to strategies. Five
rules keep this honest:

1. **First report wins.** Every 10-K repeats last year's numbers, and restatements rewrite old ones.
   We keep the value from the *earliest* filing, the only one the market had at the time.
2. **Known means filed before today.** A fact filed on day D is usable from the close of D+1. The
   filing date carries no time of day, and an after-close filing isn't tradable until the next
   session.
3. **Quarters from year-to-date figures.** Cash flow is reported year-to-date only, and nobody files
   a Q4 10-Q. A quarter is either a reported ~3-month figure or the difference of two cumulative
   ones (9M − 6M; FY − 9M = Q4), known only once *both* filings are out. TTM (trailing twelve
   months) is the sum of four **consecutive** quarters; a gap means no TTM.
4. **Stale means dead.** If a company's newest quarter is more than 200 days old, it has stopped
   filing (acquired, delisted, or the ticker now belongs to someone else), and it gets no snapshot.
5. **Symbols are tied to companies carefully.** SEC's ticker list is current-only. Delisted
   companies are recovered by matching Alpaca's company name to the XBRL entity name. When the two
   methods disagree, the company with more reported history wins (that's how XOM survives its 2026
   holding-company reorganisation). A symbol's company applies only to the symbol's *latest*
   identity segment, so a reused ticker never borrows the old company's books.

Coverage: 1,455 of 1,879 symbols that were ever in the index since 2014 are resolved (1,165 by
ticker, 290 by name). The unresolved 424 are mostly delisted names whose ticker was reused and whose
old company name we no longer have. **That's a survivorship bias in the optimistic direction**:
companies that died are more likely to be missing, so the stock strategies can't pick them. Phase 4's
haircut has to cover it.

Market cap = shares outstanding × price, with one fix: the price is the raw close on the day the
share count became known, carried forward by the adjusted return since. Otherwise a split after the
filing would make the cap wrong by the split ratio.

## 3. How every strategy trades (the shared plumbing)

Each strategy only answers "what should I own, and how much?" `investors/base.py` turns that into
orders, using four rules that matter more for after-tax money than any stock-picking detail:

1. **Sells before buys**, so the cash from a sale arrives before the purchase that needs it.
2. **The tax reserve isn't investable.** Weights are scaled by (equity − reserve) / equity × 98%.
3. **A no-trade band.** A holding that's still wanted is resized only when it's more than `band`
   (relative) off target. Trimming a winner every month realizes short-term gains at 32%; letting
   it drift can let the gain age past a year and be taxed at 15%.
4. **Hysteresis.** A stock-picker's holding stays while it ranks within `hold_rank` (twice the
   portfolio size), and new names only fill the empty slots. Otherwise a name hovering at the
   cut-off is bought and sold every month: pure turnover, pure short-term tax.

All orders are market-on-open the next session, through the same engine, cost model and tax ledger
as Phases 2 and 3.

## 4. The eight strategies, exactly

Universe for the stock strategies: point-in-time Russell 1000 members that traded today, price at
least $10, 20-day average dollar volume at least $10M, at least 63 sessions as one corporate
identity. "Operating sectors" excludes Financials, Utilities and Real Estate, where EBIT, ROIC and
EV don't mean what they mean for an operating business.

| # | Strategy | Investor | Rules |
|---|---|---|---|
| 1 | `buffett_quality` | Buffett / Munger | Operating sectors. ROIC = TTM EBIT × (1 − 21%) / (equity + debt − cash) ≥ 15%; debt/equity ≤ 1.0; net income positive in ≥ 7 of the last 8 quarters and on a TTM basis; TTM free cash flow > 0. Rank by earnings yield (EBIT / EV). Hold 20, equal weight, max 5 per sector, keep while rank ≤ 40. Monthly; band 50%. |
| 2 | `greenblatt_magic` | Joel Greenblatt | Operating sectors, EBIT > 0. Rank on return on capital (EBIT / (net working capital ex-cash + net PP&E)) plus rank on earnings yield; buy the best combined rank. Hold 25, keep while rank ≤ 50. **Quarterly**; band 50%. |
| 3 | `lynch_peg` | Peter Lynch | Ex-Financials. P/E (market cap / TTM net income) in (0, 40]; growth = TTM net income vs a year earlier between 10% and 50%; debt/equity ≤ 0.8; PEG = P/E ÷ growth% ≤ 1.0 to enter, ≤ 1.5 to stay. Lowest PEG first. Hold 20, max 5 per sector, keep while rank ≤ 40. Monthly; band 50%. |
| 4 | `canslim` | William O'Neil | **C** latest quarter's net income +25% y/y; **A** TTM net income +25% y/y; **N** within 15% of the 52-week high; **L** 12-month return in the top 20% of the universe; **M** SPY above its 200-day average, else everything to cash. **S** = the liquidity floor; **I** skipped (13F data isn't free). New names monthly, strongest first, up to 15 at 1/15 each. Exit at −8% from the selection price (checked daily), or at the monthly refresh if relative strength < 70% or the price is > 25% below its high. No resizing. |
| 5 | `templeton_value` | John Templeton | Price ≤ 60% of its 2-year high; TTM net income > 0; P/E ≤ 15; debt/equity ≤ 1.5. Deepest drawdown first, into up to 20 slots of 5%, monthly. Unfilled slots sit in SPY. Exit when earnings turn negative (any time), or after a year and a day once the price is back within 15% of its high or 3 years have passed. |
| 6 | `turtle_trend` | Turtles / Seykota / Tudor Jones | 12 ETFs: SPY QQQ IWM EFA EEM TLT IEF TIP LQD GLD DBC VNQ. Long when the close beats the prior 55-day high; out when it breaks the prior 20-day low. Weight = 0.25% / (20-day ATR / price), capped at 20%, set once at entry; the book is scaled down if it sums past 100%. The rest sits in SHY (T-bill-like) instead of earning the engine's 0% on cash. Checked daily. |
| 7 | `all_weather` | Ray Dalio | 30% SPY, 40% TLT, 15% IEF, 7.5% GLD, 7.5% DBC (the published retail version). Checked quarterly; band 20%. |
| 8 | `quality_trend` | Combination | 50% `buffett_quality` + 50% `turtle_trend`, each on its own schedule; band 50%. Stock picking for the long run, trend-following for the crashes. |

Some honest deviations from the investors' own practice, all forced by the data:

- **Net income growth, not EPS growth** (Lynch, CANSLIM). First-reported EPS history is broken by
  every split. Net income growth understates EPS growth only for companies buying back stock,
  which is a conservative error.
- **No judgement.** Buffett reads annual reports and Templeton travelled; these rules only see the
  numbers. That's the point of the test: does the *systematic* part of each method work on its own?
- **Monthly or quarterly decisions**, so every strategy runs on the same footing. O'Neil would act
  daily on new buy points; here only exits are daily.

Why the ETF strategies are here at all. The Turtle rules on single stocks are what Phase 3 tested
and failed. Across asset classes they're a different strategy: the documented edge of trend-following
lives in diversified markets (Moskowitz, Ooi & Pedersen 2012; Hurst, Ooi & Pedersen 2017), and its
job here is to own bonds and gold while stocks fall. That's the lever for the drawdown gate.

## 5. Trial accounting and the gate

- **Trials.** Each strategy's default configuration is one trial, so Phase 3b spends **8 of the
  remaining 18**. After it, 10 are left for Phase 4 or for fixes. `scripts/run_investors.py --save`
  counts them in `backtest_runs`.
- **The gate** is lesson 03 §9's, unchanged: the after-tax post-liquidation value beats SPY
  buy-and-hold **and** naive momentum; the after-tax max drawdown stays within 20%; the after-tax
  Calmar ratio beats SPY's. All of it is in-sample, 2016-01-04 → 2024-09-30.
- **Phase 4's gate** is harder: Calmar ≥ 1.0, max drawdown ≤ 15%, Deflated Sharpe > 0.95 out of
  sample. Passing here only earns the right to take that exam.
- **What happens next depends on the result.** A strategy that passes goes to Phase 4. If none
  passes, the next trials are combinations or variations of the closest misses, each counted.
  If nothing works within budget, the honest answer is SPY held long-term.

## 6. Limitations to carry into Phase 4

1. **Survivorship in fundamentals** (§2): about a fifth of historical index members have no
   fundamentals, disproportionately the dead ones.
2. **Sector labels are current, not point-in-time** (as in Phase 3). They feed the sector cap and
   the operating-sector filter, never a ranking.
3. **First-reported XBRL starts in 2009-2011** for most companies. Our window starts in 2016, so
   eight quarters of history are always available. Earlier tests would not have it.
4. **Price history starts in 2016** (Alpaca). Strategies with long lookbacks start trading later:
   CANSLIM and naive momentum need a year, Templeton two (2018). Their idle months sit in cash (or
   SPY, for Templeton), which counts against them.
5. **ETF history before 2016 comes from Yahoo** and is not used by these runs; the panel starts in
   2016 for every strategy.
