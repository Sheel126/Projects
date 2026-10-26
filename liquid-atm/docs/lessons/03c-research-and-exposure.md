# Lesson 03c: what the research says, and what a taxable account does to it

Phase 3b ended with eight famous-investor strategies failing the in-sample gate and three proposed
follow-ups. This phase ran those three, then went to the literature for the published strategies
that target exactly our problem: keep most of the stock market's return while cutting its
drawdowns. It tested them on history we are allowed to look at freely, spent trials only on the
winners, diagnosed the best one and tried a fix.

The short version: **one strategy, `vol_trend`, passed three of the four gate checks** (drawdown,
Calmar, naive momentum). Nothing beat SPY after tax, and the arithmetic in §7 says nothing of this
kind is likely to.

## 1. Three ways to look at data, and what each one costs

| Look | Example | Costs a trial? |
|---|---|---|
| Published research | Faber (2007), Moreira & Muir (2017) | No. Someone else's data, someone else's choices |
| **Our own data outside the in-sample window** | the research screen, 1960-2015 | **No.** Choosing on it cannot fit 2016-2024 |
| Our in-sample window, 2016-2024 | `run_investors.py --save` | **Yes.** Every distinct configuration is one of 20 |
| The lockbox, 2024-10 onward | Phase 4 | Opened once, for one strategy |

The research screen (`scripts/research_screen.py`) is the new tool. It's a vectorised daily model
on free series going back to 1960: the Vanguard 500 fund (total return from 1980), ^GSPC with a
3.5% dividend before that, T-bill yields, and Vanguard Treasury funds. It has no tax and only a
5 bp cost, so it ranks ideas; the engine prices them.

A 2x leveraged ETF didn't exist before 2006, so the screen builds one: 2 × index − (T-bill + 0.4%)
− 0.9% fee, reset daily. Against the real SSO over 2006-2015 it compounds at 7.92% vs 7.83%, with
a daily correlation of 0.993 (`--calibrate`). Daily reset matters: the fund rebalances to exactly
2x every night, which costs money in choppy markets ("volatility decay") and is why SSO lost more
than 40% in 2022 while the S&P lost about 25%.

**Caveat:** I already know roughly what markets did in 2016-2024, like anyone who lived through
it. Choosing on 1960-2015 removes the *fitting*, not that background knowledge. The lockbox is the
only test free of both.

## 2. The three proposed trials, and why cap weighting didn't save quality

| # | Trial | Rule | Result |
|---|---|---|---|
| 11 | `buffett_quality_cw` | Phase 3b's screen, weights ∝ market cap, cap 10% | 7.8%/yr, −37.5%. Worse than equal weight |
| 12 | `spy_trend` | Faber: SPY above its 200-day average on the first session of the month, else SHY | 6.4%/yr, −37.5%. Worse drawdown than SPY |
| 13 | `quality_cw_trend` | 11 + turtle trend, 50/50 | 6.3%/yr, −20.7% |

**Cap weighting made quality worse**, which contradicts the evidence it was meant to apply. The
holdings explain it. The Buffett screen *ranks by earnings yield*, so its largest names were GM,
Delta, Intel, Humana and steel makers: cheap cyclicals that passed a quality floor. Cap weighting
concentrated the book in those value traps. The academic quality factor (Novy-Marx 2013;
Asness, Frazzini & Pedersen's "Quality Minus Junk") sorts *by profitability*, broadly (top 30%),
value-weighted. Our screen was never that factor. The lesson: **check that the implementation
matches the evidence you cite**, not just the label.

**The monthly trend switch whipsawed.** It sold and bought back higher in Nov 2018 → Dec 2018 →
Mar 2019, Jul 2019 → Apr 2020 (it stayed in through the COVID crash because the March 2 check
still showed SPY above its average), and twice in 2022. Faber's own ten-year follow-up reports the
rule lagged stocks in six of the eight years after 2009. A trend rule pays in slow bear markets
(2000-02, 2008) and charges in fast V-shaped ones, and 2016-2024 had only V-shapes.

(Data defect found on the way: YUM and GRMN have corrupt share counts, giving YUM a
$23-quadrillion market cap. They were never picked, since a huge cap means a tiny earnings yield,
but the fundamentals loader should sanity-check `shares_out`.)

## 3. The papers, and what 56 years said about them

| Paper | Rule | Screen verdict, 1960-2015 |
|---|---|---|
| Faber (2007; revisited 2018) | 10-month average, monthly | 10.0% vs 9.1% buy-and-hold, −33% DD. Monthly is too slow for crashes |
| Gayed & Bilello (2016) | 200-day average, daily, 1x or 2x | 1x: 10.1%, −21%. 2x: 13.7%, **−45%**. Leverage without risk control fails |
| Moreira & Muir (2017); Harvey et al. (2018) | exposure = target vol / forecast vol | **Alone, no better than buy-and-hold** (Calmar 0.2-0.3 in every era) |
| Cederburg et al. (2020) | critique: vol management fails out of sample in 103 strategies | Consistent with the line above |
| vol target × 200-day filter | both together | **−10% to −20% drawdowns in every era** including 1987, 2000-02 and 2008 |
| Antonacci (2014), dual momentum | US vs international vs bonds, 12-month | 7.0%, −24% (2006-15; data starts 2002) |
| Keller & Keuning (2017), VAA-G4 | breadth momentum, 13612W score | 11.8%, −15% (2006-15 only) |
| McConnell & Xu (2008), turn of month | hold days −1..+3 | **−0.1%/yr in 2006-2015.** The effect is gone |
| Keller's 13612W as the filter | faster trend signal | Worse than the 200-day: more whipsaw |

Two lessons that are in the papers but easy to miss:

- **Volatility targeting and trend filtering do different jobs.** Volatility rises *during* a
  crash, so scaling by volatility cuts exposure after the first leg down. The trend filter gets
  you out of a *slow* decline that never looks volatile (2000-02). Each alone left a hole; together
  they held drawdowns under 20% for 56 years.
- **Faster is not better.** The 13612W filter reacts in weeks and lost to the 200-day average in
  every era but one. A signal fast enough to dodge a V-shaped crash is fast enough to be shaken out
  by every 5% dip.

The rule for choosing, written before the screen ran: **highest 1960-2015 CAGR with a max drawdown
of 20% or less in every era.** It picked 15% target volatility, a 1.5x cap, the larger of the 20-
and 60-day vol estimates, the daily 200-day filter: 9.9%/yr against buy-and-hold's 9.1%, with a
−18.5% worst drawdown against −55%.

## 4. Holding exposure above 1x without margin

Exposure `e` between 0 and 1.5 is held as:

- e ≤ 1: SPY `e`, T-bills (BIL) `1 − e`
- e > 1: SPY `2 − e`, SSO `e − 1`. 1.25x is 75% SPY + 25% SSO

No margin account, no borrowing, and the most a position can lose is what was put in. The leverage
cost (the 0.9% fee and the borrowing built into SSO's price) is paid only on the slice above 1x.

## 5. What a taxable account does to a timing strategy

This was the most important engineering finding. The first engine run of the screen's winner on
2008-2015 (design window, no trial spent) came out **4 points a year below the screen**. Adding
back the tax paid closed the gap. Then:

- realized trades over 2008-2015: **−$18.4k**
- taxable gains after 187 wash sales: **+$54.5k**
- tax paid: **$28.4k**, on trades that lost money

Every weekly trim of SPY at a small loss, bought back days later when volatility eased, is a wash
sale. The loss is disallowed and added to the new lot's basis. It comes back eventually, but
meanwhile the *gains* are taxed every quarter at 32%.

Two fixes, tested on 2008-2015 in the engine:

1. **Stepped exposure with hysteresis** (in steps of 0.25x: up once the target reaches the next
   step, down once it is half a step below). Rebalances fell from every 8 days to every 18. Wash
   sales fell 187 → 57, after-tax CAGR rose 3.31% → 3.75%. Adopted.
2. **Twin-fund rotation through the blacklist** (buy VTI instead of a blacklisted SPY; wait out a
   blacklisted SSO). **It didn't help**: 34-63 wash sales either way. The blacklist only blocks
   the "after" side of the 61-day window. Most of ours were on the *before* side: a step up buys
   new SPY, a dip within 30 days cuts, and FIFO sells the *old* lot at a loss with the new lot as
   its replacement. The fix for that is **selling the newest lot first** (specific identification),
   which belongs in the Phase 6 order manager, not in a strategy rule. Left in the code, off.

Even after the fixes, the effective tax rate of every timing strategy was 27-35% against SPY's 15%:
their gains are realized inside a year. This is Jeffrey & Arnott's 1993 question, "Is your alpha
big enough to cover its taxes?", and for timing strategies in a bull market the answer was no.

## 6. Diagnosis and the tweak that made things worse

`vol_trend` lost to SPY in three years: 2019 (+12% vs +31%), 2020 (+5% vs +18%) and 2023 (+11% vs
+26%). The story: the 60-day leg of the volatility forecast stays high for three months after a
crash, so exposure stayed near 0.4x through each V-shaped recovery. The symmetric 20-day forecast
also won on 1960-2015 (10.3% vs 9.7%, drawdowns still within 20%), so it was not just a fit to
2016-2024.

Trial 17 tested it: **worse on every line** (7.9% vs 8.6%, −22.4% vs −19.2%, tax 33% vs 27%). The
faster forecast re-levered into the 2018, 2020 and 2022 whipsaws as quickly as into the
recoveries.

That's what usually happens when you tune after looking: the diagnosis fits the years you lost,
and the fix pays for them somewhere else. It is why every tweak is a counted trial, and why
Phase 4 deflates the winner's Sharpe by the number of trials.

## 7. Why the gate may be out of reach, in one line of arithmetic

The gate asks for after-tax value above SPY's (14.4%/yr) **and** a max drawdown of 20% or less.
Together those require an after-tax Calmar of at least 14.4 / 20 = **0.72**.

- The best rules in the screen reached a pre-tax Calmar of 0.5-0.9 depending on the era.
- A timing strategy loses roughly a third of its return to tax (§5).
- Leverage multiplies return and drawdown together, so it cannot raise Calmar.

So passing would need roughly twice the risk-adjusted return the best published long-only rules
achieved over 56 years, after tax, in SPY's strongest decade. `vol_trend` matched SPY's Calmar
(0.45 vs 0.43) at 60% of its return and 57% of its drawdown. That is a real result about risk. It
isn't a way to beat the index.

## Sources

- Faber, ["A Quantitative Approach to Tactical Asset Allocation"](https://www.etf.com/sections/index-investor-corner/swedroe-why-financial-trends-persist) (2007; JPM 2018 revisit)
- Gayed & Bilello, ["Leverage for the Long Run"](https://cmtassociation.org/?p=75350) (2016)
- Moreira & Muir, "Volatility-Managed Portfolios" (JF 2017); Cederburg, O'Doherty, Wang & Yan, ["On the Performance of Volatility-Managed Portfolios"](https://alphaarchitect.com/does-portfolio-timing-based-on-volatility-signals-outperform-buy-and-hold/) (JFE 2020)
- Harvey et al., ["The Impact of Volatility Targeting"](https://people.duke.edu/~charvey/Research/Published_Papers/P135_The_impact_of.pdf) (JPM 2018)
- Keller & Keuning, [VAA and DAA](https://www.cxoadvisory.com/strategic-allocation/multi-class-momentum-portfolio-with-canary-crash-protection/) (2017, 2018)
- Antonacci, [Global Equity Momentum](https://www.advisorperspectives.com/articles/2019/05/06/global-equity-momentum-a-craftsmans-perspective) (2014; ReSolve replication 2019)
- Moskowitz, Ooi & Pedersen, ["Time Series Momentum"](https://papers.ssrn.com/abstract=2089463) (JFE 2012)
- Barroso & Santa-Clara, ["Momentum Has Its Moments"](https://ciencia.ucp.pt/en/publications/momentum-has-its-moments/) (JFE 2015)
- Novy-Marx (2013); Asness, Frazzini & Pedersen, [Quality Minus Junk](https://rpc.cfainstitute.org/research/cfa-digest/2014/01/quality-minus-junk-digest-summary)
- Maberly & Waggoner, [turn-of-the-month effect after 1990](https://www.atlantafed.org/research/publications/wp/2000/11.aspx) (Atlanta Fed 2000)
- S&P DJI, [S&P 500 Low Volatility: 15 years live](https://www.spglobal.com/spdji/en/documents/education/education-sp-500-low-volatility-index-15-years-of-live-performance.pdf)
- Bailey & López de Prado, ["The Deflated Sharpe Ratio"](https://papers.ssrn.com/abstract=2460551) (2014)
- Jeffrey & Arnott, "Is Your Alpha Big Enough to Cover Its Taxes?" (JPM 1993)
