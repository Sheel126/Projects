"""Daily-active trading rules — quality hybrid buys + quick profit-taking.

Uses Finance-Vibe research signals (setup / coiled cobra / vibe / RS) as the
buy thesis. Intraday dip/VWAP is timing only — not a standalone buy reason.
"""
from __future__ import annotations

from finance_vibe.bot import config
from finance_vibe.bot.models import AgentDecision, CycleContext, TradeAction, TickerSnapshot

# Sector tags for rotation — avoid stacking one sector
SECTOR_MAP: dict[str, str] = {
    "NVDA": "tech", "AMD": "tech", "META": "tech", "PLTR": "tech", "SOFI": "fintech",
    "AAPL": "tech", "AMZN": "tech", "NFLX": "tech", "SMCI": "tech", "GOOGL": "tech",
    "MSFT": "tech", "MU": "semis",
    "TSLA": "auto", "HOOD": "fintech", "COIN": "crypto",
    "JPM": "finance", "BAC": "finance", "XLF": "finance",
    "XOM": "energy", "OXY": "energy", "XLE": "energy",
    "GLD": "gold", "IWM": "smallcap",
    "NIO": "auto", "RIVN": "auto",
    "SPY": "index", "QQQ": "index", "SOXL": "semis",
    "XLK": "tech", "ARKK": "growth",
    "MARA": "crypto", "RIOT": "crypto",
}


def sector_for(ticker: str) -> str:
    return SECTOR_MAP.get(ticker.upper(), "other")


def compute_tight_stop(snap: TickerSnapshot) -> float | None:
    """Tighter intraday stop for quick-flip trades."""
    if snap.price <= 0:
        return None
    floor_pct = snap.price * (1 - config.ACTIVE_STOP_PCT / 100)
    if snap.atr and snap.atr > 0:
        atr_stop = snap.price - snap.atr * config.ACTIVE_ATR_MULT
        return round(max(atr_stop, floor_pct), 2)
    return round(floor_pct, 2)


def preferred_stop(snap: TickerSnapshot) -> float | None:
    """Prefer structural research stop when present; else tight intraday stop."""
    if snap.stop is not None and snap.price > 0 and snap.stop < snap.price:
        return snap.stop
    return snap.tight_stop or compute_tight_stop(snap)


def has_research_structure(snap: TickerSnapshot) -> bool:
    """Finance-Vibe quality structure (what the non-bot scanners look for)."""
    if snap.setup_type == "SETUP_LONG":
        return True
    if snap.setup_type and str(snap.setup_type).startswith("PENDING"):
        return True
    if snap.coiled_cobra_grade and (
        "A" in snap.coiled_cobra_grade or "B" in snap.coiled_cobra_grade
    ):
        return True
    return False


def has_quality_bias(snap: TickerSnapshot) -> bool:
    """Structure OR strong vibe/conviction confluence."""
    if has_research_structure(snap):
        return True
    vibe_ok = snap.vibe_score is not None and snap.vibe_score >= config.MIN_BUY_VIBE
    conv_ok = (snap.conviction or 0) >= config.MIN_BUY_CONVICTION
    return bool(vibe_ok and conv_ok)


def is_freefall(snap: TickerSnapshot) -> bool:
    """Reject catching knives that are dumping hard without A-grade coil."""
    chg = snap.change_from_open_pct or 0.0
    if chg > config.MAX_DIP_BUY_PCT:
        return False
    # Allow deep dips only for A-grade coils / confirmed SETUP_LONG
    if snap.setup_type == "SETUP_LONG":
        return False
    if snap.coiled_cobra_grade and "A" in snap.coiled_cobra_grade:
        return False
    return True


def timing_constructive_strength(snap: TickerSnapshot) -> bool:
    """Green / flat names with participation — not chase-only noise."""
    if not config.ALLOW_STRENGTH_BUYS:
        return False
    chg = snap.change_from_open_pct or 0.0
    if chg < 0:
        return False
    if chg > 2.2:
        return False  # already extended from open
    rvol = snap.rvol if snap.rvol is not None else 1.0
    if rvol < config.MIN_RVOL:
        return False
    above_vwap = snap.price_vs_vwap_pct is not None and snap.price_vs_vwap_pct >= -0.05
    orb_up = snap.orb_signal == "ORB_BREAKOUT_UP"
    return above_vwap or orb_up


def timing_quality_pullback(snap: TickerSnapshot) -> bool:
    """Mild red into structure / value — timing for research setups."""
    chg = snap.change_from_open_pct or 0.0
    if chg < config.MAX_DIP_BUY_PCT or chg > 0.35:
        return False
    if not has_research_structure(snap) and (snap.conviction or 0) < config.MIN_BUY_CONVICTION:
        return False
    # Prefer reclaim / near value: below or near VWAP, not collapsing IBS
    if snap.ibs is not None and snap.ibs < 0.08:
        return False
    return True


def has_valid_timing(snap: TickerSnapshot) -> bool:
    return timing_constructive_strength(snap) or timing_quality_pullback(snap)


def compute_active_score(snap: TickerSnapshot) -> float:
    """Quality hybrid score (0–100+). Higher = better buy candidate.

    Rewards research structure / RS / vibe / volume.
    Mild timing bonus for pullbacks OR constructive strength.
    Penalizes freefalls and extended chases.
    """
    score = 0.0

    # Research conviction (already packs vibe/setup/cobra/ML)
    score += min(40.0, (snap.conviction or 0) * 0.40)

    if snap.setup_type == "SETUP_LONG":
        score += 22.0
    elif snap.setup_type and str(snap.setup_type).startswith("PENDING"):
        score += 12.0

    if snap.coiled_cobra_grade:
        if "A" in snap.coiled_cobra_grade:
            score += 20.0
        elif "B" in snap.coiled_cobra_grade:
            score += 12.0
    elif snap.coiled_cobra_score:
        score += min(12.0, float(snap.coiled_cobra_score) / 10.0)

    if snap.vibe_score is not None:
        if snap.vibe_score >= 7:
            score += 14.0
        elif snap.vibe_score >= 5:
            score += 8.0
        elif snap.vibe_score <= 2:
            score -= 10.0

    # Relative strength vs QQQ (research core; was unused by bot)
    if snap.rs_63d is not None:
        if snap.rs_63d > 0:
            score += min(18.0, snap.rs_63d * 80.0)
        else:
            score -= min(12.0, abs(snap.rs_63d) * 40.0)

    if snap.vs_qqq_pct is not None and snap.vs_qqq_pct > 0:
        score += min(8.0, snap.vs_qqq_pct * 2.0)

    # Relative volume participation
    rvol = snap.rvol
    if rvol is not None:
        if rvol >= 1.5:
            score += 14.0
        elif rvol >= 1.2:
            score += 10.0
        elif rvol >= config.MIN_RVOL:
            score += 5.0
        elif rvol < 0.6:
            score -= 8.0

    if snap.ml_rank is not None and snap.ml_rank <= 5:
        score += max(0.0, 10.0 - snap.ml_rank * 1.5)

    # Timing — pullback into quality OR constructive strength
    chg = snap.change_from_open_pct or 0.0
    if timing_quality_pullback(snap):
        score += 10.0
        if chg <= -0.25:
            score += min(8.0, abs(chg) * 3.0)  # mild dip bonus only
    elif timing_constructive_strength(snap):
        score += 12.0
        if snap.price_vs_vwap_pct is not None and snap.price_vs_vwap_pct >= 0:
            score += 4.0

    # Penalties
    if is_freefall(snap):
        score -= 25.0
    if chg <= -4.0:
        score -= 15.0
    if chg >= 3.0:
        score -= 12.0  # chase
    rsi = snap.rsi
    if rsi is not None:
        if rsi > 72:
            score -= 15.0
        elif rsi < 28:
            score -= 12.0
        elif 40 <= rsi <= 62:
            score += 6.0

    if snap.regime_ok is False:
        score -= 8.0

    return round(max(0.0, score), 1)


def _held_sectors(ctx: CycleContext) -> set[str]:
    sectors: set[str] = set()
    for p in ctx.open_positions:
        sectors.add(sector_for(str(p.get("symbol", ""))))
    for t in ctx.watchlist:
        if t.in_position:
            sectors.add(sector_for(t.ticker))
    return sectors


def _action_map(actions: list[TradeAction]) -> dict[str, TradeAction]:
    return {a.ticker: a for a in actions}


def should_quick_sell(snap: TickerSnapshot) -> tuple[bool, str, float]:
    """Return (sell?, reason, sell_pct)."""
    if not snap.in_position:
        return False, "", 0.0

    pnl = snap.position_pnl_pct or 0.0
    if pnl >= config.QUICK_PROFIT_PCT:
        return True, f"quick profit {pnl:.2f}%", 100.0
    if pnl <= -config.QUICK_STOP_LOSS_PCT:
        return True, f"cut loss {pnl:.2f}%", 100.0
    if snap.rsi is not None and snap.rsi > config.ACTIVE_SELL_RSI:
        return True, f"rsi {snap.rsi:.0f} extended", 100.0
    if (snap.change_from_open_pct or 0) >= config.ACTIVE_SELL_FROM_OPEN_PCT:
        return True, f"+{snap.change_from_open_pct:.1f}% from open", 100.0
    if snap.target1 and snap.price >= snap.target1:
        return True, "hit target1", 100.0
    if (
        snap.price_vs_vwap_pct is not None
        and snap.price_vs_vwap_pct >= 0.35
        and pnl >= config.QUICK_PROFIT_PCT * 0.6
    ):
        return True, f"above VWAP +{snap.price_vs_vwap_pct:.2f}%", 100.0
    return False, "", 0.0


def _buy_eligible(snap: TickerSnapshot, ctx: CycleContext, open_count: int) -> bool:
    """Quality hybrid eligibility — research thesis + timing, not any red candle."""
    if ctx.halted or snap.in_position or snap.has_open_buy_order:
        return False
    if open_count >= config.MAX_POSITIONS:
        return False
    if snap.price <= 0:
        return False

    stop = preferred_stop(snap)
    if stop is None or stop >= snap.price:
        return False

    rsi = snap.rsi
    if rsi is not None and (rsi < config.ACTIVE_MIN_RSI or rsi > config.ACTIVE_MAX_RSI):
        return False

    if config.BUY_MODE == "dip":
        # Legacy knife mode (explicit opt-in only)
        chg = snap.change_from_open_pct or 0.0
        score = snap.active_score or compute_active_score(snap)
        return chg <= config.DIP_BUY_FROM_OPEN_PCT or score >= config.ACTIVE_MIN_BUY_SCORE

    # --- quality mode (default) ---
    if config.REQUIRE_STRUCTURE and not has_quality_bias(snap):
        return False

    if is_freefall(snap):
        return False

    if not has_valid_timing(snap):
        return False

    # Soft participation filter (skip ultra-dead names)
    if snap.rvol is not None and snap.rvol < (config.MIN_RVOL * 0.7):
        return False

    score = snap.active_score or compute_active_score(snap)
    if score < config.ACTIVE_MIN_BUY_SCORE:
        return False

    return True


def _pick_buys(
    snapshots: list[TickerSnapshot],
    ctx: CycleContext,
    open_count: int,
    max_buys: int,
) -> list[TickerSnapshot]:
    held = _held_sectors(ctx)
    candidates = [
        s for s in snapshots
        if _buy_eligible(s, ctx, open_count)
    ]
    # Prefer quality score, then stronger RS, then less of a freefall
    candidates.sort(
        key=lambda s: (
            s.active_score or compute_active_score(s),
            s.rs_63d or 0.0,
            s.change_from_open_pct or 0.0,
        ),
        reverse=True,
    )

    picked: list[TickerSnapshot] = []
    used_sectors: set[str] = set()
    for snap in candidates:
        if len(picked) >= max_buys:
            break
        sec = sector_for(snap.ticker)
        if sec in held or sec in used_sectors:
            continue
        picked.append(snap)
        used_sectors.add(sec)
        open_count += 1

    if len(picked) < max_buys:
        for snap in candidates:
            if snap in picked:
                continue
            if len(picked) >= max_buys:
                break
            picked.append(snap)
            open_count += 1
    return picked


def _position_pct(snap: TickerSnapshot, regime_ok: bool) -> float:
    score = snap.active_score or compute_active_score(snap)
    if not regime_ok:
        return config.ACTIVE_POSITION_PCT * 0.75
    if score >= 70:
        return min(config.ACTIVE_POSITION_PCT * 1.35, config.MAX_POSITION_PCT * 100)
    if score >= 55:
        return config.ACTIVE_POSITION_PCT * 1.15
    return config.ACTIVE_POSITION_PCT


def _buy_reason(snap: TickerSnapshot) -> str:
    parts = [f"quality={snap.active_score:.0f}"]
    if snap.setup_type:
        parts.append(str(snap.setup_type))
    if snap.coiled_cobra_grade:
        parts.append(f"cobra={snap.coiled_cobra_grade[:12]}")
    if snap.vibe_score is not None:
        parts.append(f"vibe={snap.vibe_score}")
    if snap.rs_63d is not None:
        parts.append(f"rs={snap.rs_63d:.3f}")
    if snap.rvol is not None:
        parts.append(f"rvol={snap.rvol:.2f}")
    chg = snap.change_from_open_pct
    if chg is not None:
        parts.append(f"open={chg:+.2f}%")
    if timing_constructive_strength(snap):
        parts.append("strength")
    elif timing_quality_pullback(snap):
        parts.append("pullback")
    return " ".join(parts)


def build_daily_decision(ctx: CycleContext) -> AgentDecision:
    """Deterministic daily-active decision (primary fallback)."""
    regime_ok = ctx.market_regime.get("regime_bull_ok", True)
    open_count = len(ctx.open_positions)
    max_buys = config.ACTIVE_MAX_BUYS_PER_CYCLE if regime_ok else 1

    actions_by_ticker: dict[str, TradeAction] = {}
    sells = 0

    for snap in ctx.watchlist:
        do_sell, reason, pct = should_quick_sell(snap)
        if do_sell:
            actions_by_ticker[snap.ticker] = TradeAction(
                snap.ticker, "SELL", pct, reason=f"daily {reason}",
            )
            sells += 1
            if snap.in_position:
                open_count = max(0, open_count - 1)

    buys = _pick_buys(ctx.watchlist, ctx, open_count, max_buys)
    for snap in buys:
        stop = preferred_stop(snap)
        pct = _position_pct(snap, regime_ok)
        actions_by_ticker[snap.ticker] = TradeAction(
            snap.ticker, "BUY", pct, stop=stop,
            reason=_buy_reason(snap),
        )

    actions: list[TradeAction] = []
    for snap in ctx.watchlist:
        if snap.ticker in actions_by_ticker:
            actions.append(actions_by_ticker[snap.ticker])
        else:
            actions.append(TradeAction(snap.ticker, "HOLD", reason="no quality setup"))

    summary_parts = []
    if sells:
        summary_parts.append(f"{sells} sells")
    if buys:
        summary_parts.append(f"{len(buys)} quality buys")
    summary = ", ".join(summary_parts) if summary_parts else "scanning for quality setups"

    return AgentDecision(
        actions=actions,
        summary=summary,
        used_fallback=True,
        model="daily_quality_rules",
    )


def enforce_minimum_activity(
    decision: AgentDecision, ctx: CycleContext,
) -> AgentDecision:
    """If no trades proposed and activity required, force a rotation trade."""
    if not config.REQUIRE_DAILY_ACTIVITY or ctx.halted:
        return decision

    has_trade = any(
        a.normalized_action() in ("BUY", "SELL") for a in decision.actions
    )
    if has_trade:
        return decision

    if ctx.account_cash < config.MIN_ORDER_NOTIONAL * 2:
        return decision

    action_map = _action_map(decision.actions)
    open_count = len(ctx.open_positions)

    buys = _pick_buys(ctx.watchlist, ctx, open_count, 1)
    if buys:
        snap = buys[0]
        stop = preferred_stop(snap)
        action_map[snap.ticker] = TradeAction(
            snap.ticker, "BUY", config.ACTIVE_POSITION_PCT, stop=stop,
            reason=f"forced activity {_buy_reason(snap)}",
        )
        decision.actions = [
            action_map.get(t.ticker, TradeAction(t.ticker, "HOLD"))
            for t in ctx.watchlist
        ]
        decision.summary = f"Forced quality buy {snap.ticker} (no idle cycles)"
        return decision

    held = [s for s in ctx.watchlist if s.in_position]
    if not held:
        return decision

    winners = [s for s in held if (s.position_pnl_pct or 0) >= 0]
    rotate = min(winners, key=lambda s: s.position_pnl_pct or 0) if winners else min(
        held, key=lambda s: s.position_pnl_pct or 0,
    )
    action_map[rotate.ticker] = TradeAction(
        rotate.ticker, "SELL", 100.0,
        reason=f"forced rotation pnl={rotate.position_pnl_pct:.2f}%",
    )
    decision.actions = [
        action_map.get(t.ticker, TradeAction(t.ticker, "HOLD"))
        for t in ctx.watchlist
    ]
    decision.summary = f"Forced rotate sell {rotate.ticker}"
    return decision


def merge_llm_with_daily(
    llm: AgentDecision, ctx: CycleContext,
) -> AgentDecision:
    """Layer LLM on top of daily rules; daily sells win; LLM buys must pass quality."""
    base = build_daily_decision(ctx)
    base_map = _action_map(base.actions)
    llm_map = _action_map(llm.actions)
    open_count = len(ctx.open_positions)

    merged: list[TradeAction] = []
    for snap in ctx.watchlist:
        t = snap.ticker
        daily = base_map.get(t)
        agent = llm_map.get(t)
        if daily and daily.normalized_action() == "SELL":
            merged.append(daily)
        elif agent and agent.normalized_action() == "BUY":
            # LLM cannot bypass quality gates
            if _buy_eligible(snap, ctx, open_count):
                stop = agent.stop or preferred_stop(snap)
                merged.append(TradeAction(
                    t, "BUY", agent.pct or config.ACTIVE_POSITION_PCT,
                    stop=stop,
                    reason=agent.reason or (daily.reason if daily else _buy_reason(snap)),
                ))
                open_count += 1
            elif daily and daily.normalized_action() == "BUY":
                merged.append(daily)
                open_count += 1
            else:
                merged.append(TradeAction(t, "HOLD", reason="LLM buy failed quality gate"))
        elif daily and daily.normalized_action() == "BUY":
            merged.append(daily)
            open_count += 1
        elif agent and agent.normalized_action() == "SELL":
            merged.append(agent)
        else:
            merged.append(TradeAction(t, "HOLD", reason="hold"))

    out = AgentDecision(
        actions=merged,
        summary=llm.summary or base.summary,
        raw_response=llm.raw_response,
        model=llm.model,
        used_fallback=llm.used_fallback,
    )
    return enforce_minimum_activity(out, ctx)


def build_eod_flatten_decision(ctx: CycleContext) -> AgentDecision | None:
    """Force-close all positions before market close (no overnight risk)."""
    held = [s for s in ctx.watchlist if s.in_position]
    if not held:
        return None
    actions: list[TradeAction] = []
    for snap in ctx.watchlist:
        if snap.in_position:
            actions.append(TradeAction(
                snap.ticker, "SELL", 100.0,
                reason=f"EOD flat pnl={snap.position_pnl_pct or 0:.2f}%",
            ))
        else:
            actions.append(TradeAction(snap.ticker, "HOLD", reason="EOD flat window"))
    return AgentDecision(
        actions=actions,
        summary=f"EOD flatten {len(held)} positions",
        used_fallback=True,
        model="eod_flat",
    )
