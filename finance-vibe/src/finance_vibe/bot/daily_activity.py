"""Daily-active trading rules — frequent dip-buys and quick profit-taking.

Designed for short-hold rotation across a diversified volatile watchlist.
Cannot guarantee daily profit, but enforces regular trading when capital allows.
"""
from __future__ import annotations

from finance_vibe.bot import config
from finance_vibe.bot.intraday_signals import intraday_buy_bonus
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


def compute_active_score(snap: TickerSnapshot) -> float:
    """Higher = better dip-buy candidate for daily rotation."""
    score = 0.0
    chg_open = snap.change_from_open_pct or 0.0
    if chg_open <= config.DIP_BUY_FROM_OPEN_PCT:
        score += min(45.0, abs(chg_open) * 12.0)
    elif chg_open < 0:
        score += min(20.0, abs(chg_open) * 6.0)

    if snap.vs_qqq_pct is not None and snap.vs_qqq_pct < 0:
        score += min(18.0, abs(snap.vs_qqq_pct) * 6.0)

    rsi = snap.rsi
    if rsi is not None:
        if 32 <= rsi <= 52:
            score += 18.0
        elif 52 < rsi <= 62:
            score += 8.0
        elif rsi > 72:
            score -= 15.0
        elif rsi < 25:
            score -= 10.0

    if snap.setup_type == "SETUP_LONG":
        score += 12.0
    elif snap.setup_type and str(snap.setup_type).startswith("PENDING"):
        score += 6.0

    if snap.coiled_cobra_grade:
        if "A" in snap.coiled_cobra_grade:
            score += 14.0
        elif "B" in snap.coiled_cobra_grade:
            score += 8.0

    if snap.ml_rank is not None and snap.ml_rank <= 5:
        score += max(0.0, 12.0 - snap.ml_rank * 2)

    if config.USE_INTRADAY_SIGNALS:
        score += intraday_buy_bonus(snap)

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
        and snap.price_vs_vwap_pct >= 0.25
        and pnl >= config.QUICK_PROFIT_PCT * 0.5
    ):
        return True, f"above VWAP +{snap.price_vs_vwap_pct:.2f}%", 100.0
    return False, "", 0.0


def _buy_eligible(snap: TickerSnapshot, ctx: CycleContext, open_count: int) -> bool:
    if ctx.halted or snap.in_position or snap.has_open_buy_order:
        return False
    if open_count >= config.MAX_POSITIONS:
        return False
    if snap.price <= 0:
        return False
    stop = snap.tight_stop or compute_tight_stop(snap)
    if stop is None or stop >= snap.price:
        return False
    rsi = snap.rsi
    if rsi is not None and (rsi < config.ACTIVE_MIN_RSI or rsi > config.ACTIVE_MAX_RSI):
        return False
    chg = snap.change_from_open_pct or 0.0
    score = snap.active_score or compute_active_score(snap)
    if chg <= config.DIP_BUY_FROM_OPEN_PCT:
        return True
    if score >= config.ACTIVE_MIN_BUY_SCORE:
        return True
    if snap.setup_type == "SETUP_LONG":
        return True
    if config.USE_INTRADAY_SIGNALS:
        if snap.ibs is not None and snap.ibs <= config.IBS_OVERSOLD:
            return True
        if snap.price_vs_vwap_pct is not None and snap.price_vs_vwap_pct <= config.VWAP_BUY_BELOW_PCT:
            return True
        if snap.orb_signal == "ORB_BREAKOUT_UP":
            return True
    return False


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
    candidates.sort(
        key=lambda s: (
            s.active_score or compute_active_score(s),
            -(s.change_from_open_pct or 0),
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

    # Fill remaining slots without sector constraint if needed
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
    if score >= 50:
        return min(config.ACTIVE_POSITION_PCT * 1.4, config.MAX_POSITION_PCT * 100)
    if score >= 35:
        return config.ACTIVE_POSITION_PCT * 1.15
    return config.ACTIVE_POSITION_PCT


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
        stop = snap.tight_stop or compute_tight_stop(snap)
        pct = _position_pct(snap, regime_ok)
        actions_by_ticker[snap.ticker] = TradeAction(
            snap.ticker, "BUY", pct, stop=stop,
            reason=f"daily dip score={snap.active_score:.0f} chg={snap.change_from_open_pct}%",
        )

    actions: list[TradeAction] = []
    for snap in ctx.watchlist:
        if snap.ticker in actions_by_ticker:
            actions.append(actions_by_ticker[snap.ticker])
        else:
            actions.append(TradeAction(snap.ticker, "HOLD", reason="no daily signal"))

    summary_parts = []
    if sells:
        summary_parts.append(f"{sells} sells")
    if buys:
        summary_parts.append(f"{len(buys)} dip buys")
    summary = ", ".join(summary_parts) if summary_parts else "scanning for dips"

    return AgentDecision(
        actions=actions,
        summary=summary,
        used_fallback=True,
        model="daily_active_rules",
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
    regime_ok = ctx.market_regime.get("regime_bull_ok", True)

    # Try forced dip buy first
    buys = _pick_buys(ctx.watchlist, ctx, open_count, 1)
    if buys:
        snap = buys[0]
        stop = snap.tight_stop or compute_tight_stop(snap)
        action_map[snap.ticker] = TradeAction(
            snap.ticker, "BUY", config.ACTIVE_POSITION_PCT, stop=stop,
            reason=f"forced activity dip score={snap.active_score:.0f}",
        )
        decision.actions = [
            action_map.get(t.ticker, TradeAction(t.ticker, "HOLD"))
            for t in ctx.watchlist
        ]
        decision.summary = f"Forced dip buy {snap.ticker} (no idle cycles)"
        return decision

    # Full book — rotate: sell smallest winner or worst loser
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
    """Layer LLM on top of daily rules; daily sells win, buys merge."""
    base = build_daily_decision(ctx)
    base_map = _action_map(base.actions)
    llm_map = _action_map(llm.actions)

    merged: list[TradeAction] = []
    for snap in ctx.watchlist:
        t = snap.ticker
        daily = base_map.get(t)
        agent = llm_map.get(t)
        if daily and daily.normalized_action() == "SELL":
            merged.append(daily)
        elif agent and agent.normalized_action() == "BUY":
            stop = agent.stop or (snap.tight_stop or compute_tight_stop(snap))
            merged.append(TradeAction(
                t, "BUY", agent.pct or config.ACTIVE_POSITION_PCT,
                stop=stop, reason=agent.reason or daily.reason if daily else "",
            ))
        elif daily and daily.normalized_action() == "BUY":
            merged.append(daily)
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
