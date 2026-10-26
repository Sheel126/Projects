"""Phase 3c research screen: the published exposure-management strategies, on history we are
allowed to look at freely (lesson 03c §3).

The in-sample window (2016-01 .. 2024-09) is where trials are spent. Everything here runs on
1960-2015 instead, from free daily series, so choosing among the papers' rules costs no trials and
cannot fit the in-sample years:

    S&P 500 total return    Vanguard 500 Index (VFINX) from 1980; ^GSPC + a 3.5% dividend before
    T-bills                 the 13-week yield (^IRX), from 1960
    Treasuries              VFITX (intermediate) from 1991, VUSTX (long) from 1986
    International           EFA from 2001, EEM from 2003 (dual momentum and VAA start there)
    2x S&P 500              synthetic before SSO (2006-06): 2 x index - (T-bill + 0.4%) - 0.9%
                            a year; calibrated against SSO in --calibrate

It is a vectorised daily model, not the engine: weights chosen at the close of day t earn day
t+1's close-to-close return, turnover costs 5 bp, and tax is not modelled (turnover and holding
period are printed instead, because the engine run is where the tax bill is computed). It
optimises nothing on 2016+ and reads nothing after 2015-12-31 unless --through is given, which is
for the lesson's illustrations only.

    python scripts/research_screen.py --fetch           # download and cache the series
    python scripts/research_screen.py                   # the screen
    python scripts/research_screen.py --calibrate       # synthetic 2x vs real SSO, 2006-2015
"""

import argparse
import math
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

CACHE = Path(__file__).resolve().parents[2] / "data" / "cache" / "research"
TICKERS = ["^GSPC", "^IRX", "VFINX", "VFITX", "VUSTX", "EFA", "EEM", "IEF", "SSO", "SPY"]
COST = 0.0005
LEVERED_SPREAD = 0.004
LEVERED_FEE = 0.009
DIVIDEND_BEFORE_1980 = 0.035


# ---- data -----------------------------------------------------------------------------------

def fetch() -> None:
    import yfinance as yf
    CACHE.mkdir(parents=True, exist_ok=True)
    for t in TICKERS:
        d = yf.download(t, start="1927-01-01", end="2026-01-01", auto_adjust=True, progress=False)
        d.columns = [c[0] if isinstance(c, tuple) else c for c in d.columns]
        d[["Close"]].to_csv(CACHE / f"{t.lstrip('^')}.csv")
        print(t, len(d), d.index[0].date())


def load(through: str) -> pd.DataFrame:
    def close(t: str) -> pd.Series:
        s = pd.read_csv(CACHE / f"{t.lstrip('^')}.csv", index_col=0, parse_dates=True)["Close"]
        return s[s.index <= through]

    gspc, vfinx = close("^GSPC"), close("VFINX")
    days = gspc.index[gspc.index >= "1960-01-04"]
    r = pd.DataFrame(index=days)
    # equity total return: VFINX from 1980, ^GSPC plus a flat dividend before
    eq = vfinx.reindex(days).pct_change()
    early = gspc.reindex(days).pct_change() + DIVIDEND_BEFORE_1980 / 252
    r["eq"] = eq.where(days >= vfinx.index[1], early)
    # T-bill: yesterday's quoted yield earned today
    r["cash"] = (close("^IRX").reindex(days).ffill().shift(1) / 100 / 252).fillna(0.0)
    for name, t in (("bond", "VFITX"), ("long", "VUSTX"), ("intl", "EFA"), ("em", "EEM")):
        r[name] = close(t).reindex(days).pct_change()
    r["eq2x"] = 2 * r["eq"] - r["cash"] - (LEVERED_SPREAD + LEVERED_FEE) / 252
    r["price"] = (1 + r["eq"].fillna(0)).cumprod()
    return r.iloc[1:]


# ---- signals --------------------------------------------------------------------------------

def realized_vol(ret: pd.Series, window: int) -> pd.Series:
    return np.sqrt(252 * (ret ** 2).rolling(window).mean())


def month_starts(index: pd.DatetimeIndex) -> np.ndarray:
    m = index.to_period("M")
    return np.r_[True, m[1:] != m[:-1]]


def trailing(price: pd.Series, days: int) -> pd.Series:
    return price / price.shift(days) - 1


@dataclass
class Spec:
    name: str
    paper: str
    weights: Callable[[pd.DataFrame], pd.DataFrame]
    band: float = 0.0
    """Skip a rebalance unless total |weight change| exceeds this: the tax-aware no-trade band."""


def hold(r: pd.DataFrame) -> pd.DataFrame:
    return pd.DataFrame({"eq": 1.0}, index=r.index)


def binary(signal: pd.Series, risk: str = "eq", lever: float = 1.0) -> pd.DataFrame:
    on = signal.astype(float)
    if lever == 2.0:
        return pd.DataFrame({"eq2x": on, "cash": 1 - on})
    return pd.DataFrame({risk: on * lever, "cash": 1 - on * min(lever, 1.0)})


def sma_signal(r: pd.DataFrame, days: int = 200, monthly: bool = False,
               buffer: float = 0.0) -> pd.Series:
    """Close above its `days` average. With `buffer`, exit only once the close is `buffer` below
    the average (enter as soon as it is above): a whipsaw filter."""
    sma = r["price"].rolling(days).mean()
    if buffer:
        on, out = False, []
        for px, avg in zip(r["price"].to_numpy(), sma.to_numpy()):
            if np.isfinite(avg):
                on = px > avg if not on else px >= avg * (1 - buffer)
            out.append(on)
        above = pd.Series(out, index=r.index)
    else:
        above = r["price"] > sma
    if not monthly:
        return above
    held = above.where(month_starts(r.index))
    return held.ffill().fillna(False).astype(bool)


def fast_momentum(r: pd.DataFrame) -> pd.Series:
    """Keller's 13612W score of the index above zero, checked daily: reacts within weeks, where a
    200-day average takes months to turn."""
    p = r["price"]
    score = (12 * trailing(p, 21) + 4 * trailing(p, 63) + 2 * trailing(p, 126) + trailing(p, 252))
    return score > 0


def exposure_weights(e: pd.Series) -> pd.DataFrame:
    """Exposure 0..2 to the index, as SPY + SSO + T-bills, fully invested in [1, 2]."""
    e = e.clip(0, 2)
    return pd.DataFrame({"eq": np.where(e <= 1, e, 2 - e), "eq2x": np.where(e <= 1, 0, e - 1),
                         "cash": np.where(e <= 1, 1 - e, 0)}, index=e.index)


def vol_target(r: pd.DataFrame, target: float, cap: float, window: int = 20,
               slow: int | None = None) -> pd.Series:
    """Moreira & Muir (2017) / Harvey et al. (2018): exposure = target vol / forecast vol.

    With `slow`, the forecast is the larger of the fast and slow estimate: quick to cut when
    volatility jumps, slow to re-lever after it falls (the asymmetric version practitioners use)."""
    vol = realized_vol(r["eq"], window)
    if slow:
        vol = np.maximum(vol, realized_vol(r["eq"], slow))
    return (target / vol).clip(upper=cap)


def stepped(e: pd.Series, step: float) -> pd.Series:
    """Tax-aware exposure: whole steps with hysteresis. Up once the raw target reaches the next
    step; down only once it is half a step below the current one (or straight to zero when the
    trend filter is off). Fewer, larger trades; no trimming a lot every week."""
    out = np.full(len(e), np.nan)
    level = None
    for i, x in enumerate(e.to_numpy()):
        if not np.isfinite(x):
            continue
        floor = np.floor(x / step + 1e-9) * step
        if level is None or x <= 0 or x >= level + step or x < level - step / 2:
            level = floor
        out[i] = level
    return pd.Series(out, index=e.index)


def dual_momentum(r: pd.DataFrame) -> pd.DataFrame:
    """Antonacci GEM: monthly, best of US / international by 12-month return if it beats T-bills,
    otherwise bonds."""
    px = (1 + r[["eq", "intl"]]).cumprod()      # NaN before inception stays NaN
    cash = (1 + r["cash"]).cumprod()
    m12 = px.apply(lambda s: trailing(s, 252))
    c12 = trailing(cash, 252)
    best = np.where(m12["eq"] >= m12["intl"], "eq", "intl")
    pick = pd.Series(np.where(np.maximum(m12["eq"], m12["intl"]) > c12, best, "bond"),
                     index=r.index).where(m12.notna().all(axis=1))
    pick = pick.where(month_starts(r.index) | pick.isna()).ffill().where(pick.notna())
    return _one_hot(pick, ["eq", "intl", "bond"])


def vaa_g4(r: pd.DataFrame) -> pd.DataFrame:
    """Keller & Keuning VAA-G4 (2017): 13612W momentum on SPY/EFA/EEM/bonds; if any is negative,
    the best defensive asset (bonds or T-bills); else the best risky asset. Monthly."""
    risky = ["eq", "intl", "em", "long"]
    px = (1 + r[risky + ["bond"]]).cumprod()
    cash = (1 + r["cash"]).cumprod()

    def score(s: pd.Series) -> pd.Series:
        return (12 * trailing(s, 21) + 4 * trailing(s, 63) + 2 * trailing(s, 126)
                + trailing(s, 252))
    sc = pd.DataFrame({c: score(px[c]) for c in risky + ["bond"]})
    sc["cash"] = score(cash)
    pick = []
    for _, row in sc.iterrows():
        if row[risky].isna().any():
            pick.append(None)
        elif (row[risky] < 0).any():
            pick.append("bond" if row["bond"] > row["cash"] else "cash")
        else:
            pick.append(row[risky].idxmax())
    pick = pd.Series(pick, index=r.index).where(month_starts(r.index)).ffill()
    return _one_hot(pick, risky + ["bond", "cash"])


def _one_hot(pick: pd.Series, columns: list[str]) -> pd.DataFrame:
    """1.0 in the picked column; NaN rows where nothing could be picked yet (no data)."""
    out = pd.get_dummies(pick).astype(float).reindex(columns=columns, fill_value=0.0)
    out[pick.isna()] = np.nan
    return out


def turn_of_month(r: pd.DataFrame) -> pd.DataFrame:
    """McConnell & Xu (2008): hold the index from the last session of the month through the third
    session of the next, T-bills otherwise."""
    starts = np.flatnonzero(month_starts(r.index))
    on = np.zeros(len(r), dtype=bool)
    for s in starts:
        on[max(0, s - 2):s + 2] = True            # weights at t earn t+1: covers days -1..+3
    return binary(pd.Series(on, index=r.index))


def specs() -> list[Spec]:
    out = [
        Spec("buy_hold", "benchmark", hold),
        Spec("faber_monthly", "Faber 2007/2018", lambda r: binary(sma_signal(r, monthly=True))),
        Spec("sma200_daily", "Gayed & Bilello 2016 (1x)", lambda r: binary(sma_signal(r))),
        Spec("sma200_daily_2x", "Gayed & Bilello 2016 (2x)", lambda r: binary(sma_signal(r),
                                                                             lever=2.0)),
        Spec("dual_momentum", "Antonacci 2014", dual_momentum),
        Spec("vaa_g4", "Keller & Keuning 2017", vaa_g4),
        Spec("turn_of_month", "McConnell & Xu 2008", turn_of_month),
    ]
    for target in (0.10, 0.12, 0.15):
        for cap in (1.0, 1.5, 2.0):
            for slow in (None, 60):
                tag = f"vt{int(target * 100)}_cap{cap:g}" + ("_asym" if slow else "")
                out.append(Spec(tag, "Moreira & Muir 2017; Harvey et al. 2018",
                                lambda r, t=target, c=cap, s=slow:
                                exposure_weights(vol_target(r, t, c, slow=s)), band=0.10))
                out.append(Spec(tag + "_trend", "vol target x 200-day filter (Hurst/Ooi/Pedersen)",
                                lambda r, t=target, c=cap, s=slow:
                                exposure_weights(vol_target(r, t, c, slow=s)
                                                 * sma_signal(r).astype(float)), band=0.10))
        for cap in (1.0, 1.5):
            tag = f"vt{int(target * 100)}_cap{cap:g}_asym_fast"
            out.append(Spec(tag, "vol target x 13612W absolute momentum (Keller)",
                            lambda r, t=target, c=cap:
                            exposure_weights(vol_target(r, t, c, slow=60)
                                             * fast_momentum(r).astype(float)), band=0.10))
    for target, cap in ((0.15, 1.5), (0.15, 2.0), (0.12, 1.5), (0.20, 2.0)):
        for step in (0.5, 0.25):
            out.append(Spec(f"vt{int(target * 100)}_cap{cap:g}_asym_trend_step{int(step * 100)}",
                            "vol target x trend, exposure in whole steps (tax-aware)",
                            lambda r, t=target, c=cap, st=step: exposure_weights(stepped(
                                vol_target(r, t, c, slow=60) * sma_signal(r).astype(float), st)),
                            band=0.10))
    for target, cap in ((0.12, 1.5), (0.15, 1.5), (0.15, 2.0), (0.18, 2.0)):
        for window in (20, 40):
            out.append(Spec(f"vt{int(target * 100)}_cap{cap:g}_rv{window}_trend_step25",
                            "stepped vol target x trend, symmetric vol forecast (fast re-entry)",
                            lambda r, t=target, c=cap, w=window: exposure_weights(stepped(
                                vol_target(r, t, c, window=w) * sma_signal(r).astype(float),
                                0.25)), band=0.10))
    for buffer in (0.01, 0.02, 0.03):
        out.append(Spec(f"vt15_cap1.5_asym_trend_step25_buf{int(buffer * 100)}",
                        "stepped vol target x 200-day filter with an exit buffer",
                        lambda r, b=buffer: exposure_weights(stepped(
                            vol_target(r, 0.15, 1.5, slow=60)
                            * sma_signal(r, buffer=b).astype(float), 0.25)), band=0.10))
    out.append(Spec("blend_vaa_vt15", "50/50 VAA-G4 and vt15_cap1.5_asym_trend",
                    lambda r: _blend(vaa_g4(r), exposure_weights(
                        vol_target(r, 0.15, 1.5, slow=60) * sma_signal(r).astype(float))),
                    band=0.10))
    return out


def _blend(a: pd.DataFrame, b: pd.DataFrame) -> pd.DataFrame:
    cols = sorted(set(a.columns) | set(b.columns))
    a, b = a.reindex(columns=cols, fill_value=0.0), b.reindex(columns=cols, fill_value=0.0)
    return 0.5 * a + 0.5 * b


# ---- simulation -----------------------------------------------------------------------------

def simulate(r: pd.DataFrame, w: pd.DataFrame, band: float) -> tuple[pd.Series, float, float]:
    """Daily returns, annual turnover, average days between rebalances."""
    w = w.reindex(r.index).astype(float)
    assets = [c for c in w.columns]
    target = w.fillna(0.0).to_numpy()
    valid = ~w.isna().all(axis=1).to_numpy() & np.isfinite(target).all(axis=1)
    rets = r[assets].fillna(0.0).to_numpy()
    held = np.zeros(len(assets))
    out = np.zeros(len(r))
    turnover, trades = 0.0, 0
    for t in range(len(r)):
        if t > 0:
            gross = held @ rets[t] + (1 - held.sum()) * r["cash"].iat[t]
            out[t] = gross
            drift = held * (1 + rets[t])
            total = 1 + gross
            held = drift / total if total > 0 else drift
        if valid[t]:
            delta = np.abs(target[t] - held).sum()
            if delta > max(band, 1e-9):
                turnover += delta
                trades += 1
                out[t] -= COST * delta
                held = target[t].copy()
    years = len(r) / 252
    return pd.Series(out, index=r.index), turnover / years, len(r) / max(trades, 1)


def stats(ret: pd.Series) -> dict:
    eq = (1 + ret).cumprod()
    years = len(ret) / 252
    cagr = eq.iat[-1] ** (1 / years) - 1
    dd = (eq / eq.cummax() - 1).min()
    sd = ret.std() * math.sqrt(252)
    yearly = (1 + ret).groupby(ret.index.year).prod() - 1
    return {"cagr": cagr, "maxdd": dd, "calmar": cagr / -dd if dd < 0 else float("nan"),
            "sharpe": ret.mean() * 252 / sd if sd else float("nan"), "worst_year": yearly.min()}


WINDOWS = [("1960-2015 all", "1960-01-01", "2015-12-31"),
           ("1960-1987", "1960-01-01", "1987-12-31"), ("1988-2005", "1988-01-01", "2005-12-31"),
           ("2006-2015", "2006-01-01", "2015-12-31")]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--fetch", action="store_true")
    parser.add_argument("--calibrate", action="store_true")
    parser.add_argument("--through", default="2015-12-31")
    parser.add_argument("--only", help="comma-separated spec names")
    args = parser.parse_args()
    if args.fetch:
        fetch()
        return 0
    r = load(args.through)

    if args.calibrate:
        sso = pd.read_csv(CACHE / "SSO.csv", index_col=0, parse_dates=True)["Close"].pct_change()
        both = pd.concat([r["eq2x"], sso], axis=1, keys=["synthetic", "SSO"]).dropna()
        both = both[both.index <= "2015-12-31"]
        g = (1 + both).prod() ** (252 / len(both)) - 1
        print(f"2006-06..2015: synthetic {g['synthetic']:.2%}/yr, SSO {g['SSO']:.2%}/yr, "
              f"daily correlation {both.corr().iat[0, 1]:.4f}")
        return 0

    chosen = specs()
    if args.only:
        keep = set(args.only.split(","))
        chosen = [s for s in chosen if s.name in keep]
    windows = WINDOWS if args.through <= "2015-12-31" else WINDOWS + [
        ("2016-2024*", "2016-01-01", args.through)]
    print(f"{'strategy':<26}" + "".join(f"{w:>34}" for w, _, _ in windows) + f"{'turn/yr':>9}"
          f"{'days/reb':>9}")
    print(f"{'':<26}" + "".join(f"{'CAGR':>9}{'maxDD':>8}{'Calmar':>8}{'worstYr':>9}"
                                for _ in windows))
    for spec in chosen:
        w = spec.weights(r)
        line = f"{spec.name:<26}"
        turn = gap = float("nan")
        for _, a, b in windows:
            sub = r[(r.index >= a) & (r.index <= b)]
            ws = w.reindex(sub.index)
            if ws.isna().all(axis=None) or ws.dropna(how="all").index[0] > sub.index[0] + pd.Timedelta(days=400):
                line += f"{'(no data)':>34}"
                continue
            ret, turn, gap = simulate(sub, ws, spec.band)
            s = stats(ret)
            line += (f"{s['cagr']:>9.1%}{s['maxdd']:>8.1%}{s['calmar']:>8.2f}"
                     f"{s['worst_year']:>9.1%}")
        print(line + f"{turn:>9.1f}{gap:>9.0f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
