# Phase 3b verification report

Generated 2026-10-18. In-sample window **2016-01-04 → 2024-09-30**, $100k start, 32% short-term /
15% long-term, quarterly estimated tax, the Phase 2 cost model, market-on-open fills. No run
touched the lockbox (2024-10-01 onward). The rules for every strategy were written down in
`docs/lessons/03b-investor-strategies.md` before the first run and were not changed afterwards.

## Verdict: none of the eight passes. The prediction held, and the reason is clear

| Strategy | After-tax value | CAGR | Max DD | Calmar | Sharpe | Trades | Avg hold (days) | Eff. tax | Gains long-term | Gate |
|---|---|---|---|---|---|---|---|---|---|---|
| **SPY buy & hold** | **$294,152** | **14.4%** | −33.9% | **0.43** | 0.85 | 1 | 3,191 | 15.0% | 100% | (benchmark) |
| Naive momentum | $196,381 | 8.9% | −38.5% | 0.23 | 0.45 | 274 | 83 | 33.9% | 7% | (benchmark) |
| `buffett_quality` | $240,694 | 11.1% | −35.7% | 0.31 | 0.60 | 173 | 348 | 21.1% | 58% | fail 3/4 |
| `greenblatt_magic` | $180,541 | 7.4% | −43.4% | 0.17 | 0.47 | 149 | 504 | 20.5% | 65% | fail 4/4 |
| `lynch_peg` | $161,743 | 5.8% | −44.3% | 0.13 | 0.38 | 382 | 158 | 27.9% | 21% | fail 4/4 |
| `canslim` | $117,158 | 2.1% | −33.5% | 0.06 | 0.21 | 397 | 73 | 31.7% | 26% | fail 4/4 |
| `templeton_value` | $143,418 | 4.2% | −59.9% | 0.07 | 0.29 | 104 | 419 | 20.5% | 80% | fail 4/4 |
| `turtle_trend` | $134,144 | 3.5% | **−10.9%** | 0.32 | 0.54 | 249 | 68 | 36.2% | 0% | fail 3/4 |
| `all_weather` | $173,440 | 6.9% | −21.8% | 0.31 | 0.85 | 5 | 3,191 | 15.3% | 100% | fail 4/4 |
| `quality_trend` | $188,568 | 7.9% | −19.9% | 0.40 | 0.69 | 424 | 183 | 24.8% | 38% | fail 3/4 |

All figures are after tax. Value is post-liquidation: everything sold and every dollar of tax paid.
Run with `python scripts/run_investors.py --save --json docs/phase3b/results.json`; every number
above is in that file.

Calendar-year returns, after tax:

| Year | SPY | Buffett | Greenblatt | Lynch | CANSLIM | Templeton | Turtle | All-Weather | Quality+Trend |
|---|---|---|---|---|---|---|---|---|---|
| 2016 | 12.7 | 13.9 | 9.9 | 5.6 | 0.0 | 12.4 | −1.7 | 6.2 | 6.8 |
| 2017 | 21.6 | 18.2 | 10.2 | 13.3 | 15.6 | 20.8 | 6.3 | 11.8 | 12.4 |
| 2018 | −5.0 | −19.3 | −13.7 | −17.6 | 0.7 | −20.9 | 0.2 | −1.8 | −9.3 |
| 2019 | 31.0 | 32.0 | 13.0 | 32.6 | −1.1 | 19.6 | 10.7 | 17.4 | 20.8 |
| 2020 | 18.2 | 12.4 | 5.6 | −5.8 | 14.5 | −9.1 | 9.1 | 19.8 | 12.0 |
| 2021 | 28.5 | 20.4 | 18.4 | 24.0 | −1.5 | 32.6 | 1.9 | 10.8 | 10.8 |
| 2022 | −18.3 | −11.7 | −7.2 | −21.5 | −14.9 | −20.2 | −5.8 | −17.9 | −8.4 |
| 2023 | 26.0 | 29.5 | 20.8 | 25.5 | −5.9 | 28.0 | 6.8 | 8.8 | 18.7 |
| 2024 (to Sep) | 21.7 | 12.9 | 12.3 | 8.7 | 15.4 | −9.3 | 4.5 | 9.8 | 9.1 |

## 1. The prediction was right

Before any run, the factor pre-screen (lesson 03b §1) said only profitability had paid in big US
stocks over this window, and that value, momentum and long-term reversal had not. The ranking came
out exactly that way:

- **Quality led.** `buffett_quality` is the best stock picker by far, and it beat SPY in 2016,
  2019, 2022 and 2023.
- **Half-quality came second.** `greenblatt_magic` is half quality, half value.
- **The pure value, growth-at-a-price and momentum methods trailed.** Lynch, Templeton and CANSLIM
  all depend on factors that delivered nothing from 2016 to 2024.

This also confirms the pre-screen is worth running *first* next time: it's free and it was right.

## 2. Why even the best one lost to SPY: equal weight vs a mega-cap market

An equal-weighted Russell 1000 (every member at the same weight, before tax and costs) compounded at
**11.4% a year** over this window, against SPY's **14.6%**. That 3.2-point gap is the "Magnificent
Seven" era: a handful of mega-caps carried the cap-weighted index. Every stock strategy here holds
equal weights, so each one starts the race 3.2 points a year behind before picking a single stock.

`buffett_quality` earned 11.1% a year **after** 21% effective tax and costs. Its pre-tax return was
therefore above the equal-weight universe's, so the selection added value. But it didn't add
enough to cover the equal-weight headwind *and* a tax bill that SPY defers until the end.

The pre-screen's +2.7%/yr for profitability was measured on **value-weighted** portfolios. We
tested the screen equal-weighted, which isn't what the evidence supports. That is the most
important lesson in this report, and it points straight at the next trial (§6).

## 3. Drawdowns: diversification across assets works; stock picking doesn't

The Phase 4 gate needs a max drawdown of 15% or less. No stock strategy came close (−33% to −60%):
holding 15 to 25 stocks through 2018, 2020 and 2022 loses at least as much as the index. Only
cross-asset diversification moved the drawdown:

- **`turtle_trend`: −10.9%.** It was the only strategy inside the Phase 4 limit, but it earned just
  3.5% a year. Its 68-day average hold means every gain is short-term (36% effective tax, 0%
  long-term).
- **`quality_trend`: −19.9%,** about halfway between its two parents, with a Calmar of 0.40 against
  SPY's 0.43. It came closest to the gate on risk-adjusted terms.
- **`all_weather`: −21.8%.** 2022 broke it: stocks and long Treasuries fell together (TLT lost
  about 31%) when inflation, not recession, was the shock. 55% of the book sat in Treasuries.

## 4. Taxes: the slow strategies kept more

| | Avg hold | Gains taxed long-term | Effective tax |
|---|---|---|---|
| Templeton (1-year minimum hold) | 419 d | 80% | 20.5% |
| Greenblatt (quarterly, wide hold rank) | 504 d | 65% | 20.5% |
| Buffett (monthly, hysteresis) | 348 d | 58% | 21.1% |
| CANSLIM (8% stops) | 73 d | 26% | 31.7% |
| Turtle (trend exits) | 68 d | 0% | 36.2% |

The hysteresis and no-trade band did their job. Buffett and Greenblatt cut the effective tax rate
from naive momentum's 33.9% to about 21%. SPY's 15%, deferred to the end, is still the bar.

## 5. What was built

- **Point-in-time fundamentals** (`data/fundamentals.py`, `backtest/fundamentals.py`, Flyway V8
  `fundamental_facts`): SEC XBRL company facts, first report only, known only from the day after
  filing. Quarters are derived from year-to-date figures and staleness kills a snapshot.
  Symbol→CIK uses the ticker map plus company-name matching, picking whichever has more history.
  1,455 of 1,879 historical index members are resolved, holding 1.32M facts.
  `python -m liquid_atm_quant.data.cli fundamentals`.
- **Ten cross-asset ETFs** (TLT IEF SHY TIP LQD GLD DBC EFA EEM VNQ), from Alpaca 2016 onward plus
  Yahoo back to 2005.
- **`investors/` package:** the portfolio-to-orders adapter (sells first, tax reserve excluded,
  no-trade band, per-symbol overrides), a shared stock screen and ratio definitions, the eight
  strategies, and a sleeve combinator.
- **`scripts/run_investors.py`:** runs all of them with the gate and trial count, and writes JSON.
- **`scripts/factor_prescreen.py`:** the Ken French big-stock pre-screen.

## Tests

```
$ cd quant && .venv/Scripts/pytest -q
213 passed
```

New: `test_fundamentals.py` (10) and `test_investors.py` (14). The two to read first:

- `test_a_fact_is_invisible_on_its_filing_day_and_visible_the_day_after` and
  `test_later_facts_never_change_an_earlier_snapshot`: no look-ahead in fundamentals.
- `test_a_stock_strategy_cannot_see_the_future`: the full engine gives identical results on a
  truncated panel.

## Trial ledger

| # | Hash | What | Result |
|---|---|---|---|
| 1 | dfd6d162d05c4281 | Phase 3 funnel, engine defect | void |
| 2 | 64d9da1cf06547d7 | Phase 3 funnel, fixed engine | fail |
| 3 | bc7b15d3a26d3f46 | `buffett_quality` | fail 3/4 (beat momentum) |
| 4 | 93fc4a83b7967b2d | `greenblatt_magic` | fail |
| 5 | e5e8dee524bf5136 | `lynch_peg` | fail |
| 6 | 657c00186eb6366a | `canslim` | fail |
| 7 | 5203eecc65528d8d | `templeton_value` | fail |
| 8 | 71b8ffe126783a31 | `turtle_trend` | fail 3/4 (drawdown passed) |
| 9 | e53d8c2df0cba8f2 | `all_weather` | fail |
| 10 | faeac1c6d8698726 | `quality_trend` | fail 3/4 (drawdown passed) |

**10 of 20 used.** The factor pre-screen and the equal-weight comparison in §2 are not trials, but
they are looking. Anything designed because of them has to be counted.

## 6. Where this leaves Phase 4

Nothing has earned a Phase 4 exam yet. The two lessons above point to three candidate trials, each
a direct consequence of a finding here rather than a parameter tweak:

1. **`buffett_quality` cap-weighted.** The same screen with the same rules, but each holding weighted
   by market cap (capped at 10%), which is what the evidence measured. It removes the 3.2-point
   equal-weight headwind and keeps the quality tilt.
2. **SPY with a trend switch.** Hold SPY; move to Treasuries/T-bills when SPY closes below its
   200-day average. Long-term tax on most of the gains, and the trend rule attacks the drawdown
   gate directly.
3. **Cap-weighted quality + trend sleeve,** the `quality_trend` idea rebuilt on trial 1.

Each costs one trial (leaving 7), and Phase 4's Deflated Sharpe will discount the winner for the
13 total. The bar is SPY after tax with a 15% max drawdown. If none of the three clears even the
in-sample gate, the evidence says the honest strategy is SPY held long-term.
