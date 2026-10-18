"""The regime filter (lesson 03 §2): the only component that can turn a −34% drawdown into −15%.

Three inputs, all known at the close of `t`: SPY's trend against its 200-day SMA (with a hysteresis
band, so it does not flip every few days while the index sits on the line), breadth across today's
index members, and SPY's realised volatility. They map to three states:

    RISK_ON    trend up, breadth healthy, vol calm   full risk per trade, 3 new entries a day
    CAUTION    trend up, but breadth or vol fails    half risk, 1 new entry a day
    RISK_OFF   trend down, or not enough history     no new entries; open brackets run on

The trend state depends on its own past (that is what hysteresis means), so it is computed in a
single forward pass over the whole panel. A forward pass is causal by construction, and the
truncation test checks it anyway.
"""

from dataclasses import dataclass
from enum import StrEnum

import numpy as np

from liquid_atm_quant.strategy.indicators import Indicators
from liquid_atm_quant.strategy.params import FunnelParams


class Regime(StrEnum):
    RISK_ON = "risk_on"
    CAUTION = "caution"
    RISK_OFF = "risk_off"


@dataclass(frozen=True)
class RegimeReading:
    state: Regime
    trend_up: bool
    close: float
    sma: float
    breadth: float
    vol: float

    def describe(self) -> str:
        return (f"{self.state.value}: SPY {self.close:.2f} vs SMA {self.sma:.2f} "
                f"(trend {'up' if self.trend_up else 'down'}), breadth {self.breadth:.0%}, "
                f"vol {self.vol:.0%}")


def trend_states(close: np.ndarray, sma: np.ndarray, band: float) -> np.ndarray:
    """Forward pass with hysteresis. 1 = up, 0 = down, -1 = not enough history yet.

    The first valid session starts the state with no band (there is no previous state to hold on
    to). After that, up turns down only below `sma * (1 - band)`, and down turns up only above
    `sma * (1 + band)`. A session with a missing print keeps the previous state.
    """
    out = np.full(len(close), -1, dtype=np.int8)
    state = -1
    for t in range(len(close)):
        c, s = close[t], sma[t]
        if np.isfinite(c) and np.isfinite(s):
            if state == -1:
                state = int(c > s)
            elif state == 1 and c < s * (1 - band):
                state = 0
            elif state == 0 and c > s * (1 + band):
                state = 1
        out[t] = state
    return out


class RegimeFilter:
    def __init__(self, indicators: Indicators, params: FunnelParams) -> None:
        self.ind = indicators
        self.params = params
        self.trend = trend_states(indicators.regime_close, indicators.regime_sma,
                                  params.trend_band)

    def at(self, t: int) -> RegimeReading:
        p, ind = self.params, self.ind
        trend = int(self.trend[t])
        breadth, vol = float(ind.breadth[t]), float(ind.regime_vol[t])
        if trend != 1:
            state = Regime.RISK_OFF
        # NaN fails both comparisons, so missing breadth or vol is treated as unhealthy.
        elif breadth >= p.breadth_min and vol <= p.vol_max:
            state = Regime.RISK_ON
        else:
            state = Regime.CAUTION
        return RegimeReading(state, trend == 1, float(ind.regime_close[t]),
                             float(ind.regime_sma[t]), breadth, vol)
