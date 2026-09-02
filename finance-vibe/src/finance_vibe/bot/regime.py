"""Market regime helpers for entry gating."""
from __future__ import annotations

from finance_vibe.bot import config


def benchmark_blocks_new_buys(change_from_open_pct: float | None) -> bool:
    """Hard block dip-buys when benchmark is meaningfully red from open."""
    if change_from_open_pct is None:
        return False
    return change_from_open_pct <= config.BENCHMARK_BLOCK_PCT


def regime_summary(
    change_from_open_pct: float | None,
    entries_blocked: bool,
) -> str:
    if entries_blocked and benchmark_blocks_new_buys(change_from_open_pct):
        return (
            f"{config.BENCHMARK} {change_from_open_pct:.2f}% from open "
            f"(block < {config.BENCHMARK_BLOCK_PCT}%)"
        )
    return ""
