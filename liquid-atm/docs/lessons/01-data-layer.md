# Lesson 01: The free data layer

A backtest can't be more honest than its data. This phase builds data that answers one question correctly for any past date *t*:

> **"What could the bot have known at the close of day *t*?"**

Nothing from *t+1* can leak in, and nothing that later disappeared can be missing.

---

## 1. What we found by probing the free sources (Phase 1, step 0)

| Source | What it gives us | Limits |
|---|---|---|
| **Alpaca SIP daily bars** (free) | Consolidated-tape OHLCV from 2016, **including delisted names** (SIVB up to 2023-03-09, FRC, CELG, TWTR, ATVI all present) | Starts 2016; the latest 15 minutes are embargoed on the free plan |
| **iShares IWB holdings** (`latest-holdings.csv`) | Today's Russell 1000, about 1,000 names, with sector and weight | Today only: the `asOfDate` parameter is ignored now |
| **Wayback Machine snapshots of IWB** | 65 historical holdings files, **2006–2025**, 2–11 per year | Sparse; the gaps are filled forward (see §3) |
| **`fja05680/sp500` (GitHub)** | Every S&P 500 membership change since 1996 (about 2,700 dates) | S&P 500 instead of Russell 1000, but dense and exact |
| **SEC EDGAR** | Every filing, with its **acceptance timestamp** | 10 requests/sec; requires a User-Agent header |
| **yfinance** | `^VIX`, and ETF history before 2016 | Unofficial; no delisted stocks; prices are split-adjusted, not raw |

**Scope decision:** because Alpaca includes delisted stocks, **the stock backtest window is 2016 to today, from Alpaca only.** yfinance is kept for `^VIX`, for ETF history before 2016 (so the regime filter can study 2008), and for cross-checking. Stock data from yfinance before 2016 would reintroduce exactly the survivorship bias we're trying to remove, so we don't use it.

That window still covers the 2018 Q4 selloff, the 2020 crash, the 2022 bear market and the 2025 volatility: four very different regimes.

## 2. Raw vs. adjusted prices: why we store both

On 2020-08-31, Apple split 4-for-1:

| date | raw close | fully adjusted close |
|---|---|---|
| 2020-08-28 | 499.23 | 120.96 |
| 2020-08-31 | 129.04 | 125.06 |

- **Raw** is what actually traded, which is what the order book saw. **Orders must use raw prices.** A stop at "$121" computed from adjusted history, sent to the market on 2020-08-28, would have been meaningless against a $499 stock.
- **Adjusted** removes splits and dividends, so returns are continuous. **Indicators and returns must use adjusted prices.** Otherwise, AAPL "fell 74%" in one day, and every breakout and ATR calculation breaks.
- We store raw OHLCV plus `adj_factor = adjusted_close / raw_close`. Any adjusted price is `raw × adj_factor`, with no need to duplicate columns.

**A subtle look-ahead trap:** adjustment factors are computed *backwards from today*. A dividend paid in 2024 changes the "adjusted" 2019 prices. So adjusted *levels* contain future information. Adjusted *returns* are safe, and comparing an adjusted price level to a fixed threshold, like "price > $10", is not. Our rule: filters on **levels** use raw prices (liquidity floor, minimum price), and **returns and indicators** use adjusted prices.

## 3. Point-in-time universes, and filling gaps between snapshots

`universe_membership(index_name, as_of_date, symbol)` stores *snapshots*. To answer "who was in the index on date *t*?":

```
members(t) = the snapshot with the largest as_of_date <= t
```

That's the *latest snapshot that existed at time t*, and **never** a later one, even if the later one is closer in time. Picking "the nearest snapshot" is a classic look-ahead bug: a June 2020 snapshot used on 2020-05-01 contains companies that were only added to the index *because* they had already gone up.

With Russell snapshots 2–11 per year, a company added between snapshots is missed until the next one. That's a small, **conservative** error: we trade a slightly stale universe and never a future one. The S&P 500 history has exact change dates, so it serves as a second, precise universe for cross-checking results.

## 4. Survivorship coverage: measuring what we can't fix

For every historical snapshot, **coverage** is the share of its members that have price bars near that date.

```
coverage(snapshot) = |members with a bar within ±5 trading days| / |members|
```

- Coverage near 100% for 2016 onward means Alpaca's delisted history really works.
- Coverage well below 100% means missing names, which are most likely the ones that died. Phase 4 **haircuts** backtest returns in proportion to what's missing.
- The report breaks coverage down by year. Declining coverage in older years is expected and tells you how far back to trust the backtest.

## 5. Two traps we only found by loading the data

### 5a. Frozen padding: dead companies that keep "trading"

Alpaca does not stop emitting bars when a company disappears. It repeats the last real trade forever, with zero volume:

| date | open | high | low | close | volume |
|---|---|---|---|---|---|
| 2016-09-06 | 28.75 | 29.13 | 28.65 | 29.05 | 124,088,225 |
| 2016-09-07 | 29.05 | 29.05 | 29.05 | 29.05 | **0** |
| ... every session since ... | 29.05 | 29.05 | 29.05 | 29.05 | **0** |

EMC was acquired by Dell on 2016-09-07 and still "prints" 29.05 today. Across our universe there are about 328 such runs, covering roughly 37,000 bars. Left alone, a backtest could buy a dead company, hold it forever at a frozen price, and never take the loss.

The fix is the **`tradable_bars` view** (`volume > 0`), which every later phase reads instead of `daily_bars`. A price with no volume is not a price anyone could trade. (Indices such as `^VIX` report zero volume by construction and are therefore read from `daily_bars` directly.)

### 5b. Ticker reuse, and how padding hid it

A ticker can outlive the company that used it:

| ticker | first identity | reused by |
|---|---|---|
| `CTRA` | Contura Energy (to 2021-02-03) | Coterra Energy (from 2021-10-04) |
| `BBBY` | Bed Bath & Beyond (to 2023-05-02) | a new listing in 2025 |
| `CA` | CA Technologies (to 2018-11-02) | reused in 2023 |
| `EMC` | EMC Corp (to 2016-09-06) | reused later |

The first version of the gap check found only 22 gaps, because **the frozen padding filled the holes**. Measured on real bars only, there are about 75. Three defenses now work together:

1. **`bar_segments`** gives each identity its own `segment_id`, splitting at gaps of more than 20 sessions. No ATR, breakout high or momentum window may span two companies.
2. **`instruments.delisted_on`** records the last real session before a long padding run (the `delistings` job; 56 symbols marked so far).
3. **Universe scoping:** a symbol is only considered while it's a member at that date.

The `ticker_gap` check then distinguishes two cases: a gap that starts exactly at a recorded delisting is an **explained** identity change (warning), while an unexplained hole in a member's history is an **error** that blocks the gate.

## 6. The data-quality job

Each run writes to `data_quality_issues`, and the Phase 1 gate requires **zero `error` rows**:

| check | severity | why |
|---|---|---|
| `ohlc_sanity`: low ≤ open, close ≤ high; prices > 0 | error | Corrupt bars create phantom breakouts |
| `ticker_gap`: unexplained hole of more than 20 sessions while an index member | error | We would trade across missing data |
| `ticker_gap`: gap starting at a recorded delisting | warn | Explained identity change (§5b) |
| `frozen_padding`: 3+ sessions sharing one frozen OHLC with no volume | warn | Post-delisting placeholders (§5a) |
| `zero_volume` on a trading day | warn | Halted or illiquid; not tradable |
| `large_move`: \|adjusted return\| > 40% in a day | warn | Either a real event (review it) or a bad print |
| `stale`: a current member with no bar for the last completed session | warn | The daily job failed, or the stock was delisted |
| `source_disagreement`: Alpaca vs. yfinance adjusted close differ by more than 1.5% | warn | One of the sources is wrong |

Warnings are **reviewed, not auto-deleted**. Deleting a real −60% day (like SIVB's) would be survivorship bias sneaking back in.

## 7. Look-ahead bias: the truncation test

Look-ahead bias is using information at time *t* that only existed after *t*. It hides in code like `df["close"].shift(-1)`, in centered rolling windows, in `fillna(method="bfill")`, and in adjusted price levels (§2).

**The truncation test** catches all of these mechanically. For a signal function *f* and a date *t*:

```
f(data up to t)[t]  must equal  f(all data)[t]
```

If adding *future* rows changes the value at *t*, the signal is peeking at the future. `pit.assert_no_lookahead` runs this check on sampled dates. The Phase 1 gate includes a **planted** look-ahead signal that the test must catch, which proves that the detector itself works.

## 8. SEC filings: *filed* vs. *accepted*

EDGAR records `acceptanceDateTime`, the moment a filing became public. **It is true UTC**, which we verified against a filing's index page: Apple's 8-K shows `2026-07-30T20:30:28Z` in the JSON and "Accepted 2026-07-30 16:30:28" (Eastern) on the page. Reading it as Eastern would place every filing four hours late. An 8-K accepted at 16:05 ET on Tuesday is **not** knowable at Tuesday's close; it becomes usable for Wednesday's decisions. We store the acceptance timestamp and, from Phase 5, apply the rule "available from the next session after acceptance". A backtest that uses `filingDate` alone leaks about half a day of news.

## 9. Idempotent, incremental jobs

Every job can be re-run safely:
- Bars are fetched from `last stored date + 1` per symbol and written with `INSERT ... ON CONFLICT DO UPDATE`.
- Snapshots use the primary key `(index_name, as_of_date)`, so re-importing a snapshot replaces it rather than duplicating it.
- The daily run (calendar → live universe → bars → data quality) takes minutes and is safe to run twice.

---

## 10. What the loaded data actually looks like

| Measure | Value |
|---|---|
| Daily bars | 3.75M, 2016-01-04 to today |
| Symbols with prices | 1,771 (every index member since 2016, delisted included) |
| Russell 1000 snapshots | 57, from 2006-09-29 (Wayback) |
| S&P 500 snapshots | 489 change dates since 2016 |
| SEC filings | 537k (85k 8-K, 22k 10-Q, 7k 10-K, 421k Form 4) |
| Survivorship coverage | 98.7% overall; 96.9% in 2016 rising to 99.3% recently |
| Data-quality errors | 0 (75 gap warnings, 328 padding runs, 852 large moves for review) |
| Alpaca vs Yahoo | 11 symbols x 1 year: zero daily-return differences above 1.5% |

The coverage number is what Phase 4 turns into a haircut. The test that the data is honest:
**SVB Financial (SIVB) is in the S&P 500 universe on 2023-03-01, absent by 2023-06-01, and its
final session (267.83 -> 106.04 on 39M shares) is in our bars.** A survivorship-biased dataset
would contain none of that, and would quietly overstate every backtest that follows.
