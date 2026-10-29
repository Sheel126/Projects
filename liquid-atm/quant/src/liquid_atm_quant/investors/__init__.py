"""Phase 3b: famous investors' methods as testable rules (lesson 03b-investor-strategies)."""

from collections.abc import Callable

from liquid_atm_quant.backtest.fundamentals import Fundamentals
from liquid_atm_quant.investors.assets import (AllWeather, Sleeves, TrendSwitch, TurtleTrend,
                                               VigilantAssetAllocation, VolTargetTrend,
                                               VolTargetTrendV2)
from liquid_atm_quant.investors.base import PortfolioStrategy
from liquid_atm_quant.investors.stocks import (BuffettQuality, BuffettQualityCap, Canslim,
                                               GreenblattMagic, LynchPeg, TempletonValue)

Builder = Callable[[Fundamentals, dict[str, str]], PortfolioStrategy]

STRATEGIES: dict[str, Builder] = {
    "buffett_quality": lambda f, s: BuffettQuality(f, s),
    "greenblatt_magic": lambda f, s: GreenblattMagic(f, s),
    "lynch_peg": lambda f, s: LynchPeg(f, s),
    "canslim": lambda f, s: Canslim(f, s),
    "templeton_value": lambda f, s: TempletonValue(f, s),
    "turtle_trend": lambda f, s: TurtleTrend(),
    "all_weather": lambda f, s: AllWeather(),
    "quality_trend": lambda f, s: Sleeves([(BuffettQuality(f, s), 0.5), (TurtleTrend(), 0.5)],
                                          name="quality_trend"),
}
"""The eight pre-registered Phase 3b trials (lesson 03b §5). Each default configuration is one."""

STRATEGIES.update({
    "buffett_quality_cw": lambda f, s: BuffettQualityCap(f, s),
    "spy_trend": lambda f, s: TrendSwitch(),
    "quality_cw_trend": lambda f, s: Sleeves([(BuffettQualityCap(f, s), 0.5), (TurtleTrend(), 0.5)],
                                             name="quality_cw_trend"),
})
"""Phase 3c, part 1: the three trials the Phase 3b report proposed (lesson 03c §2)."""

STRATEGIES.update({
    "vaa_g4": lambda f, s: VigilantAssetAllocation(),
    "vol_trend": lambda f, s: VolTargetTrend(),
    "vaa_vol_blend": lambda f, s: Sleeves([(VigilantAssetAllocation(), 0.5),
                                           (VolTargetTrend(), 0.5)], name="vaa_vol_blend",
                                          band=0.02),
})
"""Phase 3c, part 2: the research picks, chosen on 1960-2015 (lesson 03c §3)."""

STRATEGIES["vol_trend_v2"] = lambda f, s: VolTargetTrendV2()
"""Phase 3c, part 3: the diagnosed fix of the best trial, checked on 1960-2015 first (§5)."""

PHASE3_STRATEGIES = ("momentum_funnel",)
"""Strategies whose distinct configurations count against the shared trial budget alongside
these eight. Baselines (SPY, naive momentum) are benchmarks, not trials."""

PHASE3D_STRATEGIES = ("noise_band", "spy_core_noise", "orb_in_play", "insider_cluster",
                      "clone_13f", "fvg_first_candle", "vol_trend_noise")
"""Phase 3d's six pre-registered trials plus one post-hoc (lesson 03d §1, §10): `vol_trend_noise`
was designed after `spy_core_noise` failed only on drawdown, and says so. They run outside
`run_investors.py`, but every saved configuration counts against the same budget."""


def build(name: str, fundamentals: Fundamentals, sectors: dict[str, str]) -> PortfolioStrategy:
    return STRATEGIES[name](fundamentals, sectors)


__all__ = ["PHASE3D_STRATEGIES", "PHASE3_STRATEGIES", "STRATEGIES", "build"]
