"""How much of the ORB result is execution assumptions? (lesson 03d §5). Not a trial.

The registered run charges stop slippage on entry and exit and, when the entry minute also reaches
the stop, assumes the stop filled. With 1-minute bars the order inside that minute is unknowable,
so this re-scores the same trades under the paper's assumptions (no slippage) and the most
generous one (an entry minute never stops out), gross of tax, to bound what the data can say.

    python scripts/orb_diagnostic.py
"""

import sys
from dataclasses import replace
from datetime import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import numpy as np  # noqa: E402
import psycopg  # noqa: E402

import run_phase3d as r  # noqa: E402
from liquid_atm_quant.config import get_settings  # noqa: E402
from liquid_atm_quant.intraday import orb  # noqa: E402


def r_multiple(bars, c, p, entry_bar_can_stop: bool) -> float | None:
    after = bars[bars.index.time >= time(9, 35)]
    o, h, low, cl = (after[k].to_numpy() for k in ("o", "h", "l", "c"))
    d = c.direction
    hit = np.flatnonzero(h >= c.level) if d > 0 else np.flatnonzero(low <= c.level)
    if hit.size == 0:
        return None
    k = int(hit[0])
    raw = max(c.level, o[k]) if d > 0 else min(c.level, o[k])
    slip = (lambda x: max(0.01, x * p.stop_slippage_bps / 1e4)) if p.stop_slippage_bps else \
        (lambda x: 0.0)
    entry = raw + d * slip(raw)
    risk = p.stop_atr * c.atr
    stop = entry - d * risk
    for i in range(k if entry_bar_can_stop else k + 1, len(o)):
        if (low[i] <= stop) if d > 0 else (h[i] >= stop):
            raw_exit = stop if i == k else (min(stop, o[i]) if d > 0 else max(stop, o[i]))
            return d * (raw_exit - d * slip(raw_exit) - entry) / risk
    return d * (cl[-1] - entry) / risk


def main() -> int:
    with psycopg.connect(get_settings().database_url, connect_timeout=5) as conn:
        runner = r.Runner(conn)
        picks = orb.select(orb.load_opening_bars(), runner.panel, orb.OrbParams())
    base = orb.OrbParams()
    cases = {"registered (5 bp slippage, entry minute can stop)": (base, True),
             "paper's costs (no slippage), entry minute can stop": (replace(base, stop_slippage_bps=0), True),
             "no slippage, entry minute never stops (most generous)": (replace(base, stop_slippage_bps=0), False)}
    results = {k: [] for k in cases}
    for day, chosen in sorted(picks.items()):
        minutes = orb.load_day_minutes(day)
        for c in chosen:
            bars = minutes.get(c.symbol)
            if bars is None or bars.empty:
                continue
            for label, (p, can_stop) in cases.items():
                rm = r_multiple(bars, c, p, can_stop)
                if rm is not None:
                    results[label].append(rm)
    for label, rs in results.items():
        a = np.array(rs)
        print(f"{label:<56} trades {len(a):6d}  mean {a.mean():+.3f}R  hit {np.mean(a > 0):5.1%}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
