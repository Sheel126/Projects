# Lesson 03d: copying other traders, trading inside the day, and two bugs

Phase 3c ended with nothing able to beat SPY after tax, and the arithmetic said no long-only timing
rule would. This phase went looking for a *different kind* of return rather than a better timing
rule: copying people who know more (insiders, hedge funds), and trading inside the day, where a
strategy is flat every night and its profits don't move with the market.

It also found two defects that had been quietly distorting every stock strategy since Phase 3.

## 1. What was tried, and what it cost

Before any run, the user raised the trial budget from 20 to 25 (`TRIAL_BUDGET`). That is allowed,
and it isn't free. Phase 4's Deflated Sharpe ratio asks "how good would the *best of N* random
strategies look?", and N is now larger. The rules for all six trials were written into code
before the first in-sample run:

| # | Trial | The idea | Source |
|---|---|---|---|
| 18 | `noise_band` | Intraday momentum on SPY: trade only when the move from the open is bigger than usual for that time of day | Zarattini, Aziz & Barbon 2024 |
| 19 | `spy_core_noise` | SPY held as usual, with the Noise Band on top as an intraday overlay | the same, as an overlay |
| 20 | `orb_in_play` | Opening-range breakout, only on "stocks in play" (unusual opening volume) | Zarattini, Barbon & Aziz 2024 |
| 21 | `insider_cluster` | Copy insiders: buy when two or more officers or directors buy their own stock within 30 days | Cohen, Malloy & Pomorski 2012; Lakonishok & Lee 2001 |
| 22 | `clone_13f` | Copy hedge funds: the top 3 holdings of the 10 managers whose 13F picks did best over the past year | Cohen, Polk & Silli, "Best Ideas" |
| 23 | `fvg_first_candle` | The retail "first candle rule" with a fair-value-gap entry | no paper; the common recipe |
| 24 | `vol_trend_noise` | **Post-hoc**: Phase 3c's `vol_trend` held overnight, the Noise Band on top | designed *after* seeing #19 |

Trial 24 is different, and it is labelled that way everywhere. It was designed after trial 19
failed only on drawdown. That is tuning after looking, the same thing lesson 03c warned about with
trial 17. It is still worth running, because the pieces weren't fitted: `vol_trend` was chosen on
1960-2015, and the Noise Band's rules are the paper's own. But its in-sample result can't be read
as evidence. Only the lockbox can be.

## 2. Free intraday data

Alpaca's free plan serves SIP minute bars back to 2016, which covers the whole in-sample window.
`scripts/fetch_minutes.py` caches them as gzipped CSVs (about 1.8 MB per year of SPY). For the
opening-range strategy it fetches the 09:30 five-minute bar of every Russell 1000 member each day,
about 250,000 rows a year. It then fetches full minute bars only for each day's 20 selected
stocks. Nothing on or after 2024-10-01 is downloaded.

## 3. Accounting for a strategy that is flat every night

The daily engine fills at the open and marks at the close, and an intraday strategy is flat at
both. `intraday/account.py` does the minimum this needs:

- **Every intraday dollar is short-term** (32%), realized the same day, and goes into the same
  `TaxAccount` the engine uses, so netting, carryforwards and quarterly payments match.
- **Wash sales** inside a year don't change the total. A loss washed into tomorrow's shares is
  recognized when those shares are sold the same day. Only a chain crossing 31 December delays
  anything, by a year, on a few days' losses.
- **An optional SPY core** in the same account. Its correctness check: the core alone must
  reproduce the engine's SPY benchmark. It does, within 1% ($297k vs $294k). The small excess is
  because it buys on day one's open rather than day two's.
- **Margin interest.** With a fully invested core, a losing overlay day or a tax payment is paid
  for with a margin loan. That costs 8% a year here, positive cash earns nothing, and the interest
  is never deducted. All three choices go against the strategy.
- **Overlay leverage is capped by what Alpaca would actually lend.** Day-trading buying power is
  4 × (equity − maintenance margin on overnight positions). Holding SPY overnight at 1x gives
  about 2.8x, so the overlay is capped at 2.5x. Holding `vol_trend` at up to 1.5x, half of it in
  2x SSO, gives about 2.4x, so that overlay is capped at 2x.

## 4. The Noise Band

These are the rules from the paper (read from its full text, not a summary), in `intraday/noise_band.py`:

1. For each minute of the day, **sigma** = the average over the last 14 days of
   |price at that minute / that day's open − 1|. That is how far SPY normally drifts by that time.
2. The bands are `max(open, yesterday's close) × (1 + sigma)` and
   `min(open, yesterday's close) × (1 − sigma)`. An overnight gap widens the side it moved away from.
3. On the half hour only (10:00 … 15:30): **long** if price is above the upper band *and* VWAP,
   **short** if it is below the lower band and VWAP, otherwise flat. VWAP is the trailing stop.
4. Flat at the close, every day.
5. Size: capital × min(4, 2% / SPY's 14-day daily volatility). Quiet markets get more leverage.
6. Costs: $0.0035 per share commission plus $0.001 slippage. Alpaca charges no commission, so
   this is the conservative side.

**Replication first.** Before any trial, the code was checked against the paper's own year-by-year
table, pre-tax:

| | 2016 | 2017 | 2018 | 2019 | 2020 | 2021 | 2022 | 2023 |
|---|---|---|---|---|---|---|---|---|
| Paper | −12.8% | −6.9% | +61.1% | +6.9% | +26.8% | +34.8% | +24.4% | +37.2% |
| Ours | −12.8% | −9.3% | +59.1% | +6.7% | +25.5% | +29.0% | +24.0% | +38.8% |

The match is close, which means the rules are implemented as written. It doesn't make them good;
it rules out "the bot does something other than the paper".

**Why it might work.** Options dealers who are short gamma must buy as the market rises and sell
as it falls, which extends intraday moves. Big institutions also split their orders across the
day. Both give intraday trends a reason to persist. The paper finds it works best when VIX is
high and after the market has fallen, which is exactly when a long-only portfolio is losing. That
is the property that matters here: **its returns don't depend on the market's direction**
(beta ≈ 0).

**Why to doubt it.**
- The paper's sample (2007-2024) contains our whole in-sample window, and the authors chose the
  rules knowing how those years went. A good 2016-2024 result is partly the same data viewed twice.
- Two authors run a trading-education business.
- It is a single instrument with one mechanism.
- It lost money in 2016 and 2017. Two bad years in a row is what a decayed edge would look like
  too.

The lockbox (October 2024 onward) is after publication, so it is the first honest test.

## 5. Opening-range breakout on stocks in play

These are the paper's rules (read from its full text), in `intraday/orb.py`. Universe: price > $5,
14-day average volume ≥ 1M shares, 14-day ATR > $0.50. Relative volume = the first five-minute
bar's volume / its 14-day average, at least 1.0, top 20. The first bar's direction gives the side.
A stop order at its high (or low) enters; the stop loss is 10% of ATR; anything still open exits
at the close. Risk is 1% per trade, with 4x leverage at most.

Two departures, both written down before the run:

- **Universe.** We use the point-in-time Russell 1000, not all ~7,000 US stocks. Our survivorship-
  free price data covers index members only. The paper's edge is probably strongest in small
  caps, where a news day can mean 30x normal volume, so this is a harder test.
- **Slippage.** The paper charged commission only, with *zero* slippage, on a strategy whose
  entry and stop are both stop orders in a fast-moving stock. A stop becomes a market order, so
  we charge the engine's stop slippage (5 bp, at least a cent) on both.

## 6. Copying insiders

The SEC publishes every Form 3/4/5 since 2006 as quarterly tables (`data/insiders.py`), about 4
million open-market rows. The rules (`investors/insiders.py`):

- **Whose buys count.** Officers and directors only, open-market purchases (code P), dated by the
  *filing* date. Nobody outside knew about the trade until the filing was public.
- **Drop routine traders.** Cohen, Malloy & Pomorski's key finding: an insider who trades in the
  same month year after year (a bonus month, a plan) tells you nothing. The rest carry all the
  predictive power.
- **A cluster.** Two or more different opportunistic insiders within 30 days, $25k or more
  between them.
- **Hold.** 5% per name, up to 20, for 126 sessions. Everything else sits in SPY.

## 7. Copying hedge funds without hindsight

A list of famous funds is famous *because* those funds did well, so backtesting it reads the
answer off today's reputation. `clone_13f` picks managers every quarter using only what was public
then. Each manager's score is the return of their reported holdings over the past four quarters.
The bot then takes the top 10 managers' three largest positions, 46 days after quarter end, when
the filings are in.

**Matching CUSIPs for free.** A CUSIP-to-ticker database is sold, not given away. But a 13F gives
each holding's value *and* share count, so it reveals the price the fund marked it at on the
quarter-end date. A CUSIP is matched to the index member whose close that day is within 1% of that
price **and** whose name shares a word with the filing. 4,832 CUSIPs matched this way.

## 8. The first candle rule, and why it needed a placebo

There's no paper behind this one, only a popular recipe. Its rules are the recipe's most common
form: the first 5-minute range, a three-bar fair value gap breaking out of it, a limit order on the
retest, stop beyond the gap, 3R target.

The useful question isn't "did it make money?" but "**did the gap matter?**" The placebo keeps
every day's real geometry (how far below the market the limit sits, how far the stop is) and moves
it to a random minute with a random direction, 200 times. If the real rule doesn't beat most of
those, the pattern is decoration.

## 9. Two bugs that had distorted every stock strategy

**Stock splits.** The engine stores raw prices and an adjustment factor, and it never applied a
split to a position it held. A 4-for-1 split looked like a 75% loss overnight. The rebalancer then
"bought the dip", and a later sale booked a tax loss that never happened. The fix (`engine.py`
step 0, `LotBook.split`): when the adjustment factor jumps by a clean ratio (2, 3/2, 1/10)
overnight, the shares are multiplied and the per-share prices divided. Basis and dates don't
change; a split is not a sale (IRC §1036). A jump that isn't a clean ratio is a special dividend,
not a split: Albertsons paid a quarter of its price in January 2023.

**An empty universe.** The Wayback copy of iShares' 2017-01-31 Russell 1000 page parsed to *zero*
members. Because membership carries forward to the next snapshot, every stock strategy had an
empty universe from February to July 2017: it could hold what it had but buy nothing new. The
panel now skips snapshots with no members, and the data-quality job flags them.

**What changed.** Every Phase 3, 3b and 3c strategy was re-run (`docs/phase3d/rerun_phase3b3c.json`).
- The benchmark naive momentum rose from $196k to $240k.
- Buffett quality rose from 11.1% to 12.6% a year.
- The momentum funnel went from −0.12R to −0.02R per trade.
- **None of them now passes.** The conclusions of Phases 3-3c stand, on corrected numbers.

## 10. How to read the results

The report has the numbers. Three things to keep in mind:

1. **Pre-registration is what makes a result evidence.** Trials 18-23 had rules fixed in code
   before the first run. Trial 24 didn't, and that is why it can only *nominate* a candidate, not
   prove one.
2. **A combination of two decent things can beat either alone** when they lose at different
   times. `vol_trend` loses in V-shaped recoveries (2019, 2020), and the Noise Band loses in quiet,
   trendless years (2016-17). Their bad years mostly don't overlap.
3. **The lockbox is the test.** It holds about two years after the Noise Band paper was published.
   If the edge was real and not crowded away, it should show up there. If it doesn't, the answer
   is SPY.

## Sources

- Zarattini, Aziz & Barbon, ["Beat the Market: An Effective Intraday Momentum Strategy for S&P500 ETF (SPY)"](https://www.sfi.ch/de/publications/n-24-97-beat-the-market-an-effective-intraday-momentum-strategy-for-s-p500-etf-spy) (SFI 24-97, 2024)
- Zarattini, Barbon & Aziz, ["A Profitable Day Trading Strategy for the U.S. Equity Market"](https://ideas.repec.org/p/chf/rpseri/rp2498.html) (SFI 24-98, 2024); an [independent ORB replication](https://www.mql5.com/en/blogs/post/776235) on index futures found the gross edge but none after costs
- Cohen, Malloy & Pomorski, ["Decoding Inside Information"](https://www.nber.org/digest/apr11/decoding-inside-information) (JF 2012)
- Lakonishok & Lee (RFS 2001); Alldredge & Blank (JFR 2019), on clustered insider purchases
- Cohen, Polk & Silli, "Best Ideas" (2010); [WhaleWisdom on 13F backtests](https://whalewisdom.com/whitepapers/backtesting)
- [SEC insider transactions data sets](https://www.sec.gov/data-research/sec-markets-data/insider-transactions-data-sets) and [Form 13F data sets](https://www.sec.gov/data-research/sec-markets-data/form-13f-data-sets)
- On fair value gaps: a [placebo-controlled test](https://fr.tradingview.com/scripts/backtest/) found no edge
- Baltussen, Da, Lammers & Martens, "Hedging demand and market intraday momentum" (JFE 2021), on the gamma mechanism
