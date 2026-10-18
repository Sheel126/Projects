# Phase 2 verification report

> **Erratum (Phase 3, 2026-10-14).** The engine held positions in acquired or delisted companies
> forever (no bars, so the exit never resolved). Naive momentum was affected: over the full window
> it is **$3,928,949** post-liquidation, not $3,195,954, which is roughly level with SPY rather than
> far behind it. SPY's figures and the drawdown match are unchanged. See
> `docs/phase3/strategy-report.md` §4 for the defect, the fix and the corrected table.

Generated 2026-09-29 against the Phase 1 database (2,698 sessions × 1,781 symbols,
2016-01-04 → 2026-09-25). The reasoning behind every choice below is in
`docs/lessons/02-backtester-and-tax.md`.

## Gate 1: the tax fixtures pass

```
$ cd quant && .venv/Scripts/python scripts/tax_fixtures.py
  PASS  simple_short_term_gain
  PASS  wash_sale_basic_rebuy_within_30_days
  PASS  wash_sale_partial_replacement
  PASS  wash_sale_replacement_bought_before_the_sale
  PASS  tranche_scaling_creates_a_wash_then_recovers_it
  PASS  fifo_partial_sell_across_three_lots
  PASS  gain_and_loss_net_within_the_tax_year
  PASS  net_loss_year_carries_forward_and_shields_next_year
  PASS  long_term_boundary_is_the_day_after_the_anniversary
  PASS  washed_holding_period_tacks_on_and_flips_the_tax_rate
  PASS  wash_sale_defers_the_loss_it_does_not_destroy_it
  PASS  december_flush_undone_by_a_january_rebuy
  PASS  sell_fees_and_fractional_shares_allocate_without_losing_a_penny

13/13 fixtures pass
```

Every expected value in these files was worked out by hand from the statute *before* the engine was
run against them, so the two agree rather than one having been fitted to the other. The same files
are the contract for the Java ledger in Phase 6.

## Gate 2: the baselines reproduce reality

The backtester has to be checked against something whose answer is already known. SPY's own
total-return series, computed straight from `bar_segments` with no backtester involved:

| | From raw data | Through the engine |
|---|---|---|
| Max drawdown | **−33.79%** | **−33.79%** |
| Drawdown peak | 2020-02-19 | 2020-02-19 |
| Drawdown trough | 2020-03-23 | 2020-03-23 |
| CAGR | 15.02% | 15.05% (at $1M) / 14.85% (at $100k) |

The drawdown and both of its dates match exactly, and they are the real COVID crash dates. The
CAGR residual is whole-share rounding plus the engine's one-session delay between deciding at the
close and filling at the next open; it shrinks as account size grows, which is the signature of a
granularity effect rather than a modelling error.

### Headline comparison, $1M start, 32% short-term / 15% long-term, quarterly estimates

| | SPY buy & hold | Naive momentum |
|---|---|---|
| CAGR (pre-tax) | **14.85%** | 12.21% |
| Volatility | 17.47% | 28.12% |
| Sharpe (rf = 0) | 0.88 | 0.55 |
| Max drawdown | −33.81% | −36.90% |
| Calmar | 0.44 | 0.33 |
| Round trips | 1 | 288 |
| Hit rate | — | 50.3% |
| **Effective tax rate** | **15.0%** | **31.5%** |
| Wash sales | 0 | 66 |
| Tax paid during the run | $52,820 | $775,643 |
| **Post-liquidation value** | **$3,935,398** | $3,195,954 |

Naive momentum loses to SPY on return, on volatility, on drawdown, and then hands over twice the
tax rate. **This is the bar Phase 3 has to clear**, and it is a high one: most of the gap is tax
treatment rather than skill.

### The December flush is instrumented and measurable

| | Post-liquidation | Effective tax | Wash sales | Flush exits |
|---|---|---|---|---|
| flush off | $3,195,954 | 31.5% | 66 | 0 |
| flush on | $3,505,359 | 31.3% | 88 | 28 |

Harvesting won here and created 22 extra wash sales doing it. Whether that survives out of sample
is a Phase 4 question; Phase 2 only owed it the mechanics and the measurement.

## Tests

```
$ cd quant && .venv/Scripts/pytest -q
145 passed
```

New in Phase 2: `test_broker_sim.py` (17), `test_panel.py` (11), `test_engine.py` (14),
`test_tax_engine.py` (37, of which 13 are the fixtures), `test_metrics.py` (13),
`test_baselines.py` (8).

The one to look at first is `test_engine.py::test_a_strategy_that_reads_tomorrow_is_caught`: a
strategy that actively tries to read the next session's bar, which must raise. Phase 1 planted a
look-ahead signal to prove its detector worked; this is the same idea applied to the engine.

## Performance

A full 2016–2026 momentum run is **0.5 s** once the panel is in memory; the ~20 s a command takes
is almost entirely the Postgres load. Phase 4 needs hundreds of runs over this window, so this was
profiled rather than assumed — see the note below.

## Four defects found and fixed while building this

Each was caught by a test or a cross-check, not by reading the code.

1. **Marks were rounded to cents before being multiplied by the share count.** On 10,000 shares
   that is up to $50 of phantom P&L per mark. A mark is a *price*, not a cash amount; only the
   resulting total is quantized. Caught by the closed-form buy-and-hold test, which was off by
   $3.54 on $1.28M.
2. **Buy-and-hold left its distributions as idle cash.** Ten years of SPY dividends is well over a
   tenth of the account sitting uninvested, which dragged the benchmark's CAGR down to 13.99% and
   *cushioned its drawdown to −32.16%* — i.e. it quietly made the benchmark easier to beat. With
   reinvestment the figures became 14.83% and −33.79%, and the drawdown then matched the raw data
   exactly. This is the defect that mattered most: it biased the comparison in the bot's favour.
3. **Sortino returned 0.0 when a curve had no losing days**, which ranks a flawless curve *worst*.
   It now returns NaN — deliberately not infinity, because an infinity silently wins any `max()`
   and that is precisely how a parameter search talks itself into a curve with too little history.
4. **`Panel.adjusted()` rebuilt the entire `[session, symbol]` array on every call**, 38,676 times
   in one run: 48 s of a 73 s runtime. Now cached, and the arrays are frozen read-only so a
   strategy cannot corrupt the panel mid-run. Full run: 73 s → **0.5 s**.

Two smaller ones: a target-weight order was silently dropped in full when a gap up made it
unaffordable (it now shrinks to what the cash covers, rather than leaving a benchmark permanently
under-invested), and non-finite metrics broke the JSON write to Postgres (now stored as SQL NULL,
which is what "undefined" means in a database).

## Known limitations, carried forward deliberately

- **A replacement lot acquired inside the §1091 window but already sold before the loss sale is
  skipped.** Honouring it would mean retroactively rewriting an earlier disposal. Under FIFO it is
  rare; every occurrence is recorded in `matcher.skipped_prior_sale` and surfaced in the run
  diagnostics as `skipped_prior_sale_matches`, so it cannot pass unnoticed.
- **"Substantially identical" means the same ticker.** This removes the SPY-versus-VOO judgement
  call; Phase 3's portfolio construction has to avoid holding two near-identical ETFs at once.
- **Dividends are reconstructed from the `adj_factor` path**, not read from a dividend feed we do
  not have for free. The reconstruction errs toward *missing* distributions, which understates the
  benchmark's income and its tax drag — the conservative direction.
- **The regulatory fee rates are configuration, not constants.** Verify them against Alpaca's
  current schedule before any live P&L is trusted.
- **Both baselines report a 0% ambiguity rate and a 0% touch-only fill rate** because neither uses
  a bracket. The two assumptions most capable of making a backtest lie are covered by unit tests
  and get their first real workout in Phase 3. Watch those two numbers first.
- **SPY's last stored bar is 2026-09-18** while the calendar runs to 2026-09-25, so the final week
  marks at a stale price. Run `data.cli daily` before a run that cares about the last few sessions.

## Consult a CPA

The wash-sale, holding-period and reserve logic here is a good-faith implementation of IRC §1091
and §1222 for a single long-only taxable account with no options. It is not tax advice, and it has
not been reviewed by anyone qualified to give it. That review belongs before Phase 9, not after.
