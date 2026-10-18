"""The bar Phase 4 has to clear, and the engine's own self-test (lesson 02 §9)."""

from liquid_atm_quant.baselines.naive_momentum import NaiveMomentum
from liquid_atm_quant.baselines.spy_hold import BuyAndHold

__all__ = ["BuyAndHold", "NaiveMomentum"]
