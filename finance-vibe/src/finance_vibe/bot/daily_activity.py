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
    """Intraday stop price, one ATR band below entry (same band as the exit)."""
    if snap.price <= 0:
        return None
    return round(snap.price * (1 - exit_band_pct(snap) / 100.0), 2)


def preferred_stop(snap: TickerSnapshot) -> float | None:
    """Prefer structural research stop when present; else tight intraday stop."""
    if snap.stop is not None and snap.price > 0 and snap.stop < snap.price:
        return snap.stop
    return snap.tight_stop or compute_tight_stop(snap)


def in_entry_band(snap: TickerSnapshot) -> bool:
    """One timing gate: is the move from the open still worth joining?

    Replaces the old strength/pullback split. Those were two code paths with
    four thresholds between them, all fitted to four days, and they rejected
    88% of snapshots. The band alone expresses the same idea: do not catch a
    knife, do not chase something that has already run.
    """
    chg = snap.change_from_open_pct or 0.0
    return config.ENTRY_MIN_FROM_OPEN_PCT <= chg <= config.ENTRY_MAX_FROM_OPEN_PCT


def compute_active_score(snap: TickerSnapshot) -> float:
    """Quality hybrid score (0–100+). Higher = better buy candidate.

    Rewards research structure / RS / vibe / volume.
    Mild timing bonus for pullbacks OR constructive strength.
    Penalizes freefalls and extended chases. RVOL boosts score only.
    """
    score = 0.0

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

    if snap.rs_63d is not None:
        if snap.rs_63d > 0:
            score += min(18.0, snap.rs_63d * 80.0)
        else:
            score -= min(12.0, abs(snap.rs_63d) * 40.0)

    if snap.vs_qqq_pct is not None and snap.vs_qqq_pct > 0:
        score += min(8.0, snap.vs_qqq_pct * 2.0)

    # Volume interest, as a score input only. The old MIN_RVOL / hard-floor
    # pair was a hard gate and silently blocked every buy on Day 4.
    rvol = snap.rvol
    if rvol is not None:
        if rvol >= 1.5:
            score += 14.0
        elif rvol >= 1.2:
            score += 10.0
        elif rvol >= 0.75:
            score += 5.0

    # ml_rank bonus lives in signal_engine only — applying it here too was
    # double-counting it.

    chg = snap.change_from_open_pct or 0.0
    # Mild timing preference: buying a pullback beats buying a run-up.
    if chg <= 0:
        score += 10.0
        score += min(8.0, abs(chg) * 3.0)
    else:
        score += 12.0
        if snap.price_vs_vwap_pct is not None and snap.price_vs_vwap_pct >= 0:
            score += 4.0

    if chg <= -4.0:
        score -= 15.0
    if chg >= 3.0:
        score -= 12.0
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


def exit_band_pct(snap: TickerSnapshot) -> float:
    """Take-profit / stop distance, scaled to the stock's own daily range.

    A single fixed target cannot fit this watchlist: daily ATR runs from ~2%
    (GLD) to ~6.8% (COIN), so 1.2% is most of a quiet name's whole day and
    noise on a fast one. The clamps are safety rails, not tuned values.
    """
    if snap.atr and snap.price > 0:
        band = config.ATR_EXIT_MULT * (snap.atr / snap.price * 100.0)
    else:
        band = config.ATR_EXIT_MULT * 4.0      # no ATR: assume a middling 4% name
    return round(min(max(band, 0.6), 4.0), 2)


def should_quick_sell(snap: TickerSnapshot) -> tuple[bool, str, float]:
    """Return (sell?, reason, sell_pct).

    Take-profit and stop-loss only, both at +/- one ATR band. Discretionary
    exits (RSI, % from open, target1, VWAP profit-take) were measured to cut
    winners early; anything that hits neither band rides to the EOD flatten.
    """
    if not snap.in_position:
        return False, "", 0.0

    pnl = snap.position_pnl_pct or 0.0
    band = exit_band_pct(snap)
    if pnl >= band:
        return True, f"target +{pnl:.2f}% (band {band:.2f}%)", 100.0
    if pnl <= -band:
        return True, f"stop {pnl:.2f}% (band {band:.2f}%)", 100.0
    return False, "", 0.0


def hold_reason(snap: TickerSnapshot) -> str:
    """Why this ticker was left alone, phrased for whichever side applies.

    An open position that is not being sold is a *sell*-side outcome, so it
    reports its distance from the exit bands. Reporting the buy-side "no
    quality setup" for a held position reads as though the exit never ran,
    which is what turned HOOD into a false alarm on Day 5.
    """
    if not snap.in_position:
        return "no quality setup"
    pnl = snap.position_pnl_pct or 0.0
    band = exit_band_pct(snap)
    return (
        f"holding {pnl:+.2f}% | exits at +/-{band:.2f}% "
        f"({band - pnl:+.2f}% to target, {-band - pnl:+.2f}% to stop)"
    )


def explain_buy_eligibility(
    snap: TickerSnapshot, ctx: CycleContext, open_count: int,
) -> dict:
    """Structured PASS/FAIL reasons for observability / post-day audit."""
    chg = snap.change_from_open_pct or 0.0
    path = "pullback" if chg <= 0 else "strength"

    reasons: list[str] = []
    ok = True

    if ctx.halted:
        ok = False
        reasons.append("halted")
    if getattr(ctx, "entries_blocked", False):
        ok = False
        reasons.append("entries_blocked")
    if snap.in_position:
        ok = False
        reasons.append("in_position")
    if snap.has_open_buy_order:
        ok = False
        reasons.append("open_buy_order")
    if open_count >= config.MAX_POSITIONS:
        ok = False
        reasons.append(f"max_positions_{config.MAX_POSITIONS}")
    if snap.price <= 0:
        ok = False
        reasons.append("bad_price")

    stop = preferred_stop(snap)
    if stop is None or stop >= snap.price:
        ok = False
        reasons.append("invalid_stop")

    # Anti-chase: refuse anything already stretched this far above VWAP.
    vwap_pct = snap.price_vs_vwap_pct
    if vwap_pct is not None and vwap_pct > config.VWAP_BUY_MAX_ABOVE_PCT:
        ok = False
        reasons.append(f"extended_vs_vwap_{vwap_pct:.2f}")

    # Timing: one band, replacing the strength/pullback split.
    if not in_entry_band(snap):
        ok = False
        reasons.append(f"outside_entry_band_{chg:.2f}")

    # Quality: one floor. The old RSI band, RVOL floors, vibe and conviction
    # gates all re-tested things active_score already accounts for.
    score = snap.active_score or compute_active_score(snap)
    if score < config.MIN_BUY_SCORE:
        ok = False
        reasons.append(f"score_{score:.0f}<{config.MIN_BUY_SCORE:.0f}")
    elif ok:
        reasons.append("PASS")

    return {
        "ticker": snap.ticker,
        "pass": ok and (reasons[-1] == "PASS" if reasons else False),
        "path": path,
        "open_pct": snap.change_from_open_pct,
        "price": snap.price,
        "vwap_pct": snap.price_vs_vwap_pct,
        "rvol": snap.rvol,
        "rsi": snap.rsi,
        "atr": snap.atr,
        "quality_score": score,
        "score_floor": config.MIN_BUY_SCORE,
        "setup": snap.setup_type,
        "cobra": snap.coiled_cobra_grade,
        "conviction": snap.conviction,
        "vibe_score": snap.vibe_score,
        "rs_63d": snap.rs_63d,
        "exit_band_pct": exit_band_pct(snap),
        "qqq_from_open": ctx.benchmark_change_from_open_pct,
        "in_position": snap.in_position,
        "position_count": open_count,
        "day_pnl_pct": ctx.day_pnl_pct,
        "entries_blocked": bool(getattr(ctx, "entries_blocked", False)),
        "reasons": reasons,
        "reject_reason": None if (ok and reasons and reasons[-1] == "PASS") else (
            reasons[-1] if reasons else "unknown"
        ),
    }


def _buy_eligible(snap: TickerSnapshot, ctx: CycleContext, open_count: int) -> bool:
    """Deterministic final buy authority. Three strategy gates, that is all:

      1. open% within ENTRY_MIN..ENTRY_MAX_FROM_OPEN_PCT (do not catch a
         knife, do not chase a completed move)
      2. price_vs_vwap_pct <= VWAP_BUY_MAX_ABOVE_PCT (anti-chase)
      3. active_score >= MIN_BUY_SCORE (one quality floor)

    Plus the mechanical checks: not halted, not already held, no open buy
    order, position slots free, sane price and stop.
    """
    detail = explain_buy_eligibility(snap, ctx, open_count)
    return bool(detail["pass"])


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
    """Flat size. Upsizing high-score names concentrated risk when the score
    was wrong; only the unfavourable-regime reduction is kept.
    """
    if not regime_ok:
        return config.ACTIVE_POSITION_PCT * 0.75
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
        parts.append("pullback" if chg <= 0 else "strength")
    parts.append(f"band={exit_band_pct(snap):.2f}%")
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
            actions.append(TradeAction(snap.ticker, "HOLD", reason=hold_reason(snap)))

    summary_parts = []
    if sells:
        summary_parts.append(f"{sells} sells")
    if buys:
        summary_parts.append(f"{len(buys)} quality buys")
    summary = ", ".join(summary_parts) if summary_parts else "scanning for quality setups"

    return enforce_minimum_activity(
        AgentDecision(
            actions=actions,
            summary=summary,
            used_fallback=True,
            model="daily_quality_rules",
        ),
        ctx,
    )


def enforce_minimum_activity(
    decision: AgentDecision, ctx: CycleContext,
) -> AgentDecision:
    """If no trades proposed and activity required, force one quality buy."""
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
            action_map.get(t.ticker, TradeAction(t.ticker, "HOLD", reason=hold_reason(t)))
            for t in ctx.watchlist
        ]
        decision.summary = f"Forced quality buy {snap.ticker} (no idle cycles)"
        return decision

    # No quality buy available: stay idle. Forcing a rotation sell here used to
    # dump the smallest winner, which is the exact behaviour TP/SL exits replace.
    return decision


def merge_llm_with_daily(
    llm: AgentDecision, ctx: CycleContext,
) -> AgentDecision:
    """Trades come from the rules; the LLM contributes only its summary text.

    The LLM used to be able to add buys and reorder candidates. Measured over
    the 125 stored cycles, ranking makes no difference at all: shuffling the
    gate-passing candidates into random order scored +2.47% on average against
    +2.00% for score-ranked, with the ranked result sitting inside the random
    spread. Since reordering gate-passing candidates is the *most* the LLM
    could ever do, it cannot be shown to add value on this evidence — and it
    made every cycle non-reproducible, which broke the replay harness.
    """
    base = build_daily_decision(ctx)
    return AgentDecision(
        actions=base.actions,
        summary=llm.summary or base.summary,
        raw_response=llm.raw_response,
        model=f"{llm.model} (commentary only)" if llm.model else base.model,
        used_fallback=llm.used_fallback,
    )


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
