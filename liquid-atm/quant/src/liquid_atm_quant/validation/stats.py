"""Overfitting statistics for Phase 4 (lesson 04 §2-§4).

Everything here works on *per-period* returns (one row per session) and per-period Sharpe ratios.
Annualizing first would be wrong: the Deflated Sharpe's standard error is in the units of the
observations, and multiplying by sqrt(252) on one side only is the classic way to make it lie.
"""

import itertools
import math
from dataclasses import asdict, dataclass
from statistics import NormalDist

import numpy as np

EULER_GAMMA = 0.5772156649015329
_N = NormalDist()


def sharpe(returns: np.ndarray) -> float:
    """Per-period Sharpe, zero risk-free rate (the gate's convention, lesson 02 §10)."""
    r = np.asarray(returns, dtype=float)
    sd = r.std(ddof=1)
    return float(r.mean() / sd) if sd > 0 else 0.0


def moments(returns: np.ndarray) -> tuple[float, float]:
    """Skewness and *raw* (not excess) kurtosis: a normal distribution gives (0, 3)."""
    r = np.asarray(returns, dtype=float)
    z = (r - r.mean()) / r.std(ddof=0)
    return float(np.mean(z ** 3)), float(np.mean(z ** 4))


def probabilistic_sharpe(sr: float, benchmark: float, n: int, skew: float, kurt: float) -> float:
    """P(true Sharpe > benchmark) given an estimate from n observations (Bailey & López de Prado
    2012). Fat tails and negative skew widen the estimate's error, so they lower the probability."""
    denom = 1.0 - skew * sr + (kurt - 1.0) / 4.0 * sr ** 2
    if denom <= 0:
        return float("nan")
    return _N.cdf((sr - benchmark) * math.sqrt(n - 1) / math.sqrt(denom))


def expected_max_sharpe(variance: float, n_trials: int) -> float:
    """The Sharpe the best of n_trials skill-less strategies is expected to show, given how much
    their Sharpes vary (the False Strategy Theorem, Bailey & López de Prado 2014, eq. 2)."""
    if n_trials < 2:
        return 0.0
    return math.sqrt(variance) * ((1 - EULER_GAMMA) * _N.inv_cdf(1 - 1 / n_trials)
                                  + EULER_GAMMA * _N.inv_cdf(1 - 1 / (n_trials * math.e)))


@dataclass(frozen=True)
class DeflatedSharpe:
    sharpe: float
    sharpe_annual: float
    n_obs: int
    skew: float
    kurtosis: float
    n_trials: int
    trial_sharpe_variance: float
    expected_max_sharpe: float
    expected_max_sharpe_annual: float
    dsr: float

    def as_dict(self) -> dict:
        return asdict(self)


def deflated_sharpe(returns: np.ndarray, trial_sharpes: np.ndarray, n_trials: int) -> DeflatedSharpe:
    """DSR = PSR against the expected maximum Sharpe of `n_trials` skill-less trials.

    `trial_sharpes` are the per-period Sharpes of the trials actually run (candidate included);
    their variance sets how far luck alone could push the best one."""
    r = np.asarray(returns, dtype=float)
    sr = sharpe(r)
    skew, kurt = moments(r)
    var = float(np.var(np.asarray(trial_sharpes, dtype=float), ddof=1))
    sr0 = expected_max_sharpe(var, n_trials)
    return DeflatedSharpe(sr, sr * math.sqrt(252), len(r), skew, kurt, n_trials, var, sr0,
                          sr0 * math.sqrt(252), probabilistic_sharpe(sr, sr0, len(r), skew, kurt))


@dataclass(frozen=True)
class Pbo:
    pbo: float
    n_splits: int
    median_logit: float
    in_sample_winners: dict[str, int]
    """How often each trial was the in-sample winner."""

    def as_dict(self) -> dict:
        return asdict(self)


def cscv_pbo(matrix: np.ndarray, names: list[str], blocks: int = 16) -> Pbo:
    """Probability of Backtest Overfitting by combinatorially symmetric cross-validation
    (Bailey, Borwein, López de Prado & Zhu 2017).

    The T x N return matrix is cut into `blocks` contiguous blocks. For every way of choosing half
    of them as "in sample", the trial with the best in-sample Sharpe is located in the
    out-of-sample ranking. PBO is the share of splits where it lands at or below the median: the
    probability that picking the best backtest picks a below-average strategy."""
    m = np.asarray(matrix, dtype=float)
    t, n = m.shape
    edges = np.linspace(0, t, blocks + 1).astype(int)
    parts = [m[edges[i]:edges[i + 1]] for i in range(blocks)]
    logits, wins = [], dict.fromkeys(names, 0)
    for chosen in itertools.combinations(range(blocks), blocks // 2):
        ins = np.vstack([parts[i] for i in chosen])
        oos = np.vstack([parts[i] for i in range(blocks) if i not in chosen])
        best = int(np.argmax(_sharpes(ins)))
        wins[names[best]] += 1
        oos_sr = _sharpes(oos)
        rank = int(np.sum(oos_sr < oos_sr[best])) + 1      # 1 = worst, n = best
        w = rank / (n + 1)
        logits.append(math.log(w / (1 - w)))
    logits = np.array(logits)
    return Pbo(float(np.mean(logits <= 0)), len(logits), float(np.median(logits)),
               {k: v for k, v in sorted(wins.items(), key=lambda kv: -kv[1]) if v})


def _sharpes(m: np.ndarray) -> np.ndarray:
    sd = m.std(axis=0, ddof=1)
    return np.where(sd > 0, m.mean(axis=0) / np.where(sd > 0, sd, 1), 0.0)


def stationary_bootstrap(excess: np.ndarray, mean_block: int = 21, draws: int = 10_000,
                         seed: int = 4) -> dict:
    """Politis & Romano (1994) resampling of a daily return difference: blocks of geometric length
    keep volatility clustering, which an i.i.d. bootstrap would destroy. Returns the probability
    that the annualized mean difference is positive, and a 90% interval for it."""
    x = np.asarray(excess, dtype=float)
    t = len(x)
    rng = np.random.default_rng(seed)
    p = 1.0 / mean_block
    pos = np.arange(t)
    means = np.empty(draws)
    for d in range(draws):
        jump = rng.random(t) < p
        jump[0] = True                                   # every path starts a block
        block = np.cumsum(jump) - 1
        starts = pos[jump]
        offsets = rng.integers(t, size=len(starts))      # each block starts at a random session
        idx = (offsets[block] + pos - starts[block]) % t  # then walks forward, wrapping around
        means[d] = x[idx].mean()
    annual = means * 252
    return {"p_positive": float(np.mean(annual > 0)),
            "annual_mean": float(x.mean() * 252),
            "ci90": [float(np.quantile(annual, 0.05)), float(np.quantile(annual, 0.95))],
            "mean_block": mean_block, "draws": draws, "seed": seed}
