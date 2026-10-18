"""Does each screener stage pick stocks that go up? A check that bypasses the engine (lesson 03 §5).

    python scripts/funnel_forward_returns.py                 # 2016-01-04 .. 2024-09-30
    python scripts/funnel_forward_returns.py --horizon 5

For every session the regime allows (not RISK_OFF) and every name that survives each screener
stage, measure the return from the next session's open to the close `horizon` sessions later, minus
the equal-weighted average of every eligible name over the same window. Positive mean excess
return = that stage selects drift in our favour; negative = it selects reversal.

This is the bracket math made empirical: brackets only shape outcomes, so if the stocks the
screener picks do not drift up, no stop/target choice can rescue the strategy. It reads data the
strategy is allowed to see at `t` to *select*, and future bars only to *score*, which is the point
of the exercise and the reason it never feeds back into a decision.

It is research on in-sample data, not a backtest, so it is not saved as a trial. It still counts as
looking: anything changed because of what it shows must be run as a new, counted trial.
"""

import argparse
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import numpy as np  # noqa: E402
import psycopg  # noqa: E402

from liquid_atm_quant.backtest.panel import Panel  # noqa: E402
from liquid_atm_quant.config import get_settings  # noqa: E402
from liquid_atm_quant.strategy import FunnelParams, LOCKBOX_START, assert_outside_lockbox  # noqa: E402
from liquid_atm_quant.strategy.indicators import Indicators  # noqa: E402
from liquid_atm_quant.strategy.regime import Regime, RegimeFilter  # noqa: E402

STAGES = ("eligible", "trend", "momentum", "trigger", "extension")


def stage_masks(ind: Indicators, member: np.ndarray, t: int, p: FunnelParams) -> dict:
    """The screener's five masks at session `t`, mirroring `Screener.screen` stage by stage."""
    close, ac = ind.close[t], ind.adj_close[t]
    with np.errstate(invalid="ignore"):
        eligible = member[t] & np.isfinite(close) & (close >= p.min_price) & \
            (ind.adv[t] >= p.min_adv) & (ind.run[t] >= p.history)
        trend = eligible & (ac > ind.sma_fast[t]) & (ind.sma_fast[t] > ind.sma_slow[t])
        momentum = ind.momentum[t]
        ranked = np.flatnonzero(trend & np.isfinite(momentum))
        top = np.zeros_like(trend)
        if ranked.size:
            keep = max(1, int(np.ceil(ranked.size * p.momentum_top)))
            top[ranked[np.argsort(-momentum[ranked], kind="stable")[:keep]]] = True
        trigger = top & (ac > ind.prior_high[t]) & (ind.rvol[t] >= p.rvol_min)
        extension = trigger & np.isfinite(ind.atr_adj[t]) & \
            ((ac - ind.sma_short[t]) <= p.max_extension_atr * ind.atr_adj[t])
    return {"eligible": eligible, "trend": trend, "momentum": top, "trigger": trigger,
            "extension": extension}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--start", type=date.fromisoformat, default=date(2016, 1, 4))
    parser.add_argument("--end", type=date.fromisoformat, default=date(2024, 9, 30))
    parser.add_argument("--horizon", type=int, default=10)
    parser.add_argument("--index", default="russell1000")
    args = parser.parse_args()
    assert_outside_lockbox(args.end)

    p = FunnelParams()
    with psycopg.connect(get_settings().database_url) as conn:
        panel = Panel.from_db(conn, args.start, args.end, index_name=args.index)
    ind = Indicators.compute(panel, p)
    regime = RegimeFilter(ind, p)

    # Same-identity forward return, next open -> close at t + horizon, on adjusted prices.
    ao, ac, seg = panel.adjusted("open"), panel.adjusted("close"), panel.segment_id
    h = args.horizon
    excess: dict[str, list[float]] = {s: [] for s in STAGES}
    raw: dict[str, list[float]] = {s: [] for s in STAGES}
    for t in range(len(panel.sessions) - h - 1):
        if regime.at(t).state is Regime.RISK_OFF:
            continue
        with np.errstate(invalid="ignore", divide="ignore"):
            fwd = ac[t + 1 + h - 1] / ao[t + 1] - 1.0
        same = (seg[t + 1] == seg[t]) & (seg[t + h] == seg[t])
        fwd = np.where(same, fwd, np.nan)
        masks = stage_masks(ind, panel.member, t, p)
        base = np.nanmean(fwd[masks["eligible"]]) if masks["eligible"].any() else np.nan
        if not np.isfinite(base):
            continue
        for stage, mask in masks.items():
            values = fwd[mask & np.isfinite(fwd)]
            raw[stage].extend(values.tolist())
            excess[stage].extend((values - base).tolist())

    print(f"forward {h}-session return from the next open, {args.start} .. {args.end}, "
          f"regime not risk_off (lockbox starts {LOCKBOX_START})\n")
    print(f"{'stage':<10} {'obs':>9} {'mean':>8} {'excess':>8} {'t-stat':>7} {'hit>0':>6}")
    for stage in STAGES:
        r, e = np.array(raw[stage]), np.array(excess[stage])
        if not e.size:
            continue
        tstat = e.mean() / (e.std(ddof=1) / np.sqrt(e.size)) if e.size > 1 else float("nan")
        print(f"{stage:<10} {e.size:>9,} {r.mean():>8.3%} {e.mean():>+8.3%} {tstat:>7.2f} "
              f"{(r > 0).mean():>6.1%}")
    print("\nt-stats overstate significance: overlapping windows and cross-sectional correlation "
          "make observations far from independent.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
