# Day 5 Runbook — the frozen two-week run

The point of this run is **not** to make money. It is to collect enough trades
that the nine remaining parameters can be judged honestly. Four days and 28
trades cannot tell signal from luck; roughly 270 trades can.

**The rule for the next two weeks: change nothing.** If something looks wrong,
write it down and let it run. The only exception is a crash or a wrong-way
order, which is a bug, not a strategy opinion.

---

## Starting the day

```powershell
.\start-paper-bot.ps1            # fresh session: cancels orders, flattens, resets baseline
.\start-paper-bot.ps1 -Resume    # after a crash or restart: KEEPS positions and day P&L
```

Use `-Resume` after any interruption. A plain start flattens live positions.

The launcher also starts `scripts/watchdog.ps1`, which relaunches the runner
with `-Resume` if it dies while the market is open (capped at 5 restarts/day).

Dashboard: <http://127.0.0.1:5001> — the banner at the top reads
`RUNNER: ALIVE / STALE / OFF`. If it says STALE or OFF during market hours,
positions are unmanaged; restart with `-Resume`.

### Day 5 one-off: verify the watchdog

Once, after the open, kill the runner window and confirm it comes back with
positions intact. This is the only planned intervention of the whole run.

```powershell
PYTHONPATH=src python -m finance_vibe.bot.runner watchdog-check   # exit 10 = market open, runner gone
```

---

## What the bot does, in plain terms

Every 20 minutes it looks at 14 stocks and asks three questions about each:

1. **Has it moved too far already today?** It will only buy something between
   2.5% below and 3.5% above where it opened. Below that it is falling too
   fast; above that the move has already happened.
2. **Is it stretched above its average price for the day?** More than 1% above
   VWAP means it is being chased. Skip.
3. **Is it good enough?** One quality score, built from the research signals,
   must be at least 38.

If all three pass, it buys 13% of the account, up to 5 positions, at most 2 new
ones per cycle.

**Exits are the change you asked for.** Instead of always selling at +1.2%,
each stock gets its own target and stop, set to half its normal daily range
(ATR). Today that means:

| Stock | Daily range | Target and stop |
|---|---|---|
| GLD | 1.95% | ±0.97% |
| XOM | 2.06% | ±1.03% |
| NVDA | 3.25% | ±1.62% |
| PLTR | 4.62% | ±2.31% |
| HOOD | 5.34% | ±2.67% |
| SMCI | 6.07% | ±3.04% |

A quiet stock no longer has to travel an impossible distance, and a fast one
is no longer sold while it is still moving. Anything that hits neither band is
sold at 3:55 PM. Nothing is held overnight.

**Brakes:** no new buys once the day is down 1.0%, or when QQQ is down 0.4%
from its open. Trading halts entirely at -5%.

**The AI no longer decides trades.** It writes the summary you see on the
dashboard and nothing more. See below for why.

---

## How to judge the run

```powershell
python scripts/benchmark.py --alpha
```

**One question decides it: is the alpha positive?**

Green days and beating QQQ are both misleading here, and it is worth knowing
exactly why before the run starts. The watchlist moves about **2.53x as much
as QQQ**. Over the four recorded days the 14 names gained **+4.16%** equal
weighted while QQQ gained +1.64%. So a monkey holding this basket beats QQQ
in any rising market, and green days in a rising market are nearly free.

The only honest test is the bot against the same basket at the same capital:

| Four recorded days | Return |
|---|---|
| Watchlist basket, equal weight, open to close | +4.16% |
| Same basket at the bot's 48% deployment | +1.99% |
| Bot, new config, replayed | +2.09% |
| **Alpha — skill above simply holding it** | **+0.10%** |

**+0.10% over four days is statistically zero.** Per trade the 95% confidence
interval runs -0.08% to +1.27%, which includes zero. Everything the bot earned
was market exposure, not selection or timing.

For context the config that actually ran live scored **-1.66%** alpha, so this
rewrite moved it from destroying value to neutral. That is a real improvement,
and neutral is still neutral.

**What this bot actually is:** a de-risked long position on a high-beta
basket. It captures roughly half the basket's move with far smaller drawdowns
(-0.11% max over four days) and no overnight gap risk. It makes money when
tech drifts up and loses money when tech drifts down. It has no mechanism that
profits from a falling market.

Three outcomes after two weeks:

- **Alpha clearly positive** — there is something here worth funding.
- **Alpha near zero** — you own a complicated way to hold half a tech basket.
  Decide whether the drawdown protection alone justifies running it.
- **Alpha negative** — stop.

Do not judge a single day, and do not read a green week in a rising market as
success. That is exactly what misled us over the first four days.

---

## What was measured, and what was not

Run the harness yourself:

```powershell
python scripts/replay.py                          # current config
python scripts/replay.py --holdout 2026-09-02     # in-sample vs holdout
python scripts/replay.py --verbose                # every trade
```

**Measured and believed:**

- The parameter cut is the big win, and it is a mechanical one. The old gates
  rejected 94.4% of all observations, so the bot sat in cash: 21% of capital
  deployed, 3.2 trades a day. Now it deploys 48% and makes 6.8 trades a day.
  On the stored cycles that is +2.09% against +0.68%.
- The system runs a full day with no errors, and every module, the dashboard
  and the health check pass after the rewrite.

**Measured and explicitly NOT believed:**

- **The exit change is not proven.** In-sample the ATR bands beat the fixed
  1.2/1.8 (+1.87% vs +1.39%); on the holdout the fixed exits were slightly
  ahead (+0.32% vs +0.21%). At 13 trades a single position flips that. ATR was
  chosen because it is **one parameter instead of two** and because a 3.4x
  spread in daily range is a real mechanism — not because it scored higher.
- **Stock selection shows no measurable edge.** Shuffling the candidates that
  passed the gates into random order scored **+2.47% on average against
  +2.00%** for score-ranked. Ranking is worthless on this sample, which is why
  the LLM was removed from the trade path: reordering gate-passing candidates
  is the most it could ever do. The gates themselves do earn their place, but
  for a different reason — random picks with no gates ranged from -0.96% to
  +5.29%, while gated picks stayed within +1.35% to +3.67%. The gates narrow
  the outcome and cut the losing tail; they do not pick winners.
- **The strategy has never seen a falling market, and it will do WORSE than
  QQQ when it arrives, not better.** All four test days had QQQ close above
  its open. The watchlist carries 2.53x QQQ's move and the bot is long only,
  so a 1% QQQ drop implies roughly 2.5% against the basket. The brakes limit
  the damage without reversing it: new buys stop at -1.0% on the day and at
  -0.4% on QQQ, every position stopping out once costs about -1.24%, and the
  hard halt is -5%. Expect roughly **-1% to -2% on a genuinely bad day.**
  The containment does work — on the two flat days in the sample the bot lost
  only 0.11% and made 0.15% — but containment is not profit.

---

## The nine knobs

Frozen, and guarded by `TestFrozenConfig` so a stray edit fails the suite
instead of surfacing mid-session.

| Knob | Value | Why it exists |
|---|---|---|
| `ATR_EXIT_MULT` | 0.5 | Target and stop, as a fraction of daily range |
| `MIN_BUY_SCORE` | 38 | The one quality floor |
| `ENTRY_MIN_FROM_OPEN_PCT` | -2.5 | Do not catch a falling knife |
| `ENTRY_MAX_FROM_OPEN_PCT` | +3.5 | Do not chase a finished move |
| `VWAP_BUY_MAX_ABOVE_PCT` | 1.0 | Anti-chase ceiling |
| `ACTIVE_POSITION_PCT` | 13 | Flat position size |
| `MAX_POSITIONS` | 5 | Concurrency cap |
| `DAY_BLOCK_BUYS_PCT` | -1.0 | Daily brake |
| `BENCHMARK_BLOCK_PCT` | -0.4 | Regime brake |

26 parameters were deleted. `TestFrozenConfig.test_removed_knobs_stay_removed`
lists them and fails if any comes back.

---

## Known gaps — candidates for AFTER the run

Do not touch these during the two weeks. Each must first improve the replay
in-sample without degrading the holdout, then get 2-3 live days alone.

1. **Stops are not real orders.** In `daily_active` mode
   `Executor._use_broker_stops()` always returns `False`, so nothing sits at
   the broker; exits are only checked every 20 minutes. On Sep 2 a 3.19% band
   became a **3.56% realised loss** on SMCI because price moved between
   checks. Placing real stop orders would cap that. This is the highest-value
   change on the list, and it interacts with the EOD flatten, so it needs care.
2. **Dollar risk per trade is unequal.** Flat 13% sizing with volatility-scaled
   bands means COIN risks roughly 0.4% of equity per trade and GLD 0.13%.
   Risk-parity sizing would equalise it, at the cost of one parameter.
3. **Asymmetric bands.** A stop tighter than the target would cut the loss tail
   that hurt Sep 2, but it re-adds the second parameter ATR removed. Only worth
   it if the replay shows a clear, holdout-confirmed gain.
4. **The ML ranker is dead code.** No trained model ships with the repo, and
   the caller hardcoded two features to `None`, so `ml_rank` was `None` in all
   1,882 stored snapshots and its score bonus never fired. It was also being
   counted twice. Retrain and re-wire it deliberately, or leave it out.
5. **`rvol` is only present in 30% of stored snapshots**, so anything built on
   relative volume cannot yet be measured on history.

---

## If something breaks

| Symptom | Action |
|---|---|
| Dashboard banner STALE/OFF in market hours | `.\start-paper-bot.ps1 -Resume` |
| Runner will not start, claims already running | Check `data/bot/runner.pid`; a stale PID needs deleting |
| Positions open after 4:00 PM | Should not happen; `runner eod` flattens. Record it. |
| A cycle errors | Note the cycle id and keep going. One bad cycle is not a reason to stop. |
| Down more than 2% on the day | Brakes should already have stopped buying. Let it finish. |

Do not "fix" strategy behaviour mid-run. Write it in a list and bring it to
the post-run review.
