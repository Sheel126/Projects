"""Ollama (Qwen) portfolio agent — structured trade decisions."""
from __future__ import annotations

import json
import logging
import re
from typing import Any

import requests

from finance_vibe.bot import config
from finance_vibe.bot.daily_activity import build_daily_decision, merge_llm_with_daily
from finance_vibe.bot.models import AgentDecision, CycleContext, TradeAction, TickerSnapshot
from finance_vibe.bot.signal_engine import compute_conviction

logger = logging.getLogger(__name__)

# Tight algorithmic prompt for smaller / coder models — follow steps literally.
SYSTEM_PROMPT = """You are a trading decision engine. Output ONLY valid JSON. No markdown.

STRICT ALGORITHM (follow in order):

STEP 1 — CHECK HALTS
- If account.halted=true: every ticker gets HOLD or SELL only. STOP.

STEP 2 — SELL REVIEW (for each ticker where in_position=true)
SELL 100% if ANY true:
  (a) rsi > 72
  (b) change_from_open_pct > 2.0
  (c) price >= target1 (when target1 is a number)
  (d) position_pnl_pct >= 3.0
SELL 50% if price >= target1 and not already selling 100%.
Otherwise HOLD positions.

STEP 3 — BUY REVIEW (only if not halted)
Count open positions. Max 3 total.
Skip BUY if: has_open_buy_order=true, in_position=true, stop is null, or open positions >= 3.

A ticker is BUY-ELIGIBLE only if ALL true:
  (1) setup_type is exactly "SETUP_LONG" OR coiled_cobra_grade contains "A" or "B"
  (2) conviction >= 40
  (3) vibe_score is null OR vibe_score >= 5 OR coiled_cobra_grade contains "A"
  (4) stop field is a number below current price

Pick at most 2 BUY-ELIGIBLE tickers with HIGHEST conviction from conviction_ranking.
- If market_regime.regime_bull_ok is false: max 1 BUY, use pct=10 only.
- If regime_bull_ok is true: use pct=15 if conviction 40-59, pct=20 if 60-74, pct=25 if >=75.
- BUY stop MUST equal the stop field from watchlist data. Never invent prices.

STEP 4 — EVERYONE ELSE
Any ticker not assigned BUY or SELL in steps 2-3: action=HOLD, pct=0, stop=null.

OUTPUT FORMAT (exact keys):
{
  "summary": "max 20 words",
  "actions": [
    {"ticker": "TICKER", "action": "BUY|SELL|HOLD", "pct": 0, "stop": null, "reason": "cite conviction and rule"}
  ]
}

RULES:
- One action per ticker in watchlist. Use ONLY tickers provided.
- Never BUY without stop. Never duplicate open orders.
- Do not invent numbers — copy stop/conviction/vibe from input.
- When unsure, HOLD.

EXAMPLE (illustrative):
{"summary":"Sell extended SOFI, buy PLTR setup","actions":[
  {"ticker":"PLTR","action":"BUY","pct":20,"stop":23.5,"reason":"conv 72 SETUP_LONG vibe 7 rule step3"},
  {"ticker":"SOFI","action":"SELL","pct":100,"stop":null,"reason":"rsi 74 step2a"},
  {"ticker":"NVDA","action":"HOLD","pct":0,"stop":null,"reason":"conv 30 below threshold"}
]}"""


SYSTEM_PROMPT_DAILY_ACTIVE = """You are a daily-active trading engine. Output ONLY valid JSON. No markdown.

GOAL: Buy QUALITY Finance-Vibe setups (structure/cobra/vibe/RS), not free-falling dips.
Mild pullbacks OR constructive green with volume are OK. Target ~TARGET% wins. Flat by EOD.

STRICT ALGORITHM (follow in order):

STEP 1 — HALTS / EOD
If account.halted=true OR account.entries_blocked=true: SELL or HOLD only. No new BUYs.

STEP 2 — SELL (every in_position=true ticker)
SELL 100% if ANY:
  (a) position_pnl_pct >= {tp}
  (b) change_from_open_pct >= {sell_open}
  (c) rsi >= {sell_rsi}
  (d) position_pnl_pct <= -{sl} (cut loss)
Otherwise HOLD position.

STEP 3 — BUY QUALITY (only if not halted and entries_blocked=false)
Max open positions: {max_pos}. Max {max_buys} new BUYs this cycle.
Skip if: in_position, has_open_buy_order=true, or positions full.

BUY-ELIGIBLE only if ALL true:
  (1) QUALITY: setup_type is SETUP_LONG or PENDING_* OR coiled_cobra_grade has A/B
      OR (vibe_score >= {min_vibe} AND conviction >= {min_conv})
  (2) NOT FREEFALL: change_from_open_pct > {max_dip} (unless SETUP_LONG or cobra A)
  (3) TIMING: either
      (a) mild pullback into quality (open% between {max_dip} and +0.35), OR
      (b) constructive strength (open% 0 to +2.2, rvol>={min_rvol}, above/near VWAP or ORB_BREAKOUT_UP)
  (4) active_score >= {min_score}
  (5) stop/tight_stop is a number below price

Prefer HIGHEST active_score then rs_63d. Spread across sectors.
NEVER buy just because a stock is red. NEVER buy IBS/VWAP oversold alone without quality.
- pct={pos_pct} default; pct={pos_mid} if active_score 55-69; pct={pos_hi} if active_score >= 70
- stop MUST use stop or tight_stop from watchlist. Never invent.

STEP 4 — Prefer quality over activity. HOLD is OK when no setup.

STEP 5 — ELSE HOLD

OUTPUT FORMAT:
{{"summary":"max 20 words","actions":[{{"ticker":"X","action":"BUY|SELL|HOLD","pct":0,"stop":null,"reason":"rule cite"}}]}}

RULES: One action per ticker. Never BUY without stop below price. Never BUY when entries_blocked."""


def get_system_prompt() -> str:
    if config.TRADING_MODE == "daily_active":
        pos = config.ACTIVE_POSITION_PCT
        return SYSTEM_PROMPT_DAILY_ACTIVE.format(
            tp=config.QUICK_PROFIT_PCT,
            sell_open=config.ACTIVE_SELL_FROM_OPEN_PCT,
            sell_rsi=config.ACTIVE_SELL_RSI,
            sl=config.QUICK_STOP_LOSS_PCT,
            max_pos=config.MAX_POSITIONS,
            max_buys=config.ACTIVE_MAX_BUYS_PER_CYCLE,
            max_dip=config.MAX_DIP_BUY_PCT,
            min_score=config.ACTIVE_MIN_BUY_SCORE,
            min_vibe=int(config.MIN_BUY_VIBE),
            min_conv=int(config.MIN_BUY_CONVICTION),
            min_rvol=config.MIN_RVOL,
            pos_pct=pos,
            pos_mid=round(pos * 1.15, 1),
            pos_hi=round(min(pos * 1.35, config.MAX_POSITION_PCT * 100), 1),
        )
    return SYSTEM_PROMPT


def build_decision_brief(ctx: CycleContext) -> str:
    """Compress context for weaker LLMs — scannable text before JSON."""
    acct = ctx.to_prompt_dict()["account"]
    regime = ctx.market_regime.get("regime_bull_ok", "?")
    lines = [
        "=== TRADING BRIEF ===",
        f"Mode: {ctx.trading_mode} | Equity ${acct['equity']} | Cash ${acct['cash']} | Day P&L {acct['day_pnl_pct']}% | Halted {acct['halted']}",
        f"Market regime bull_ok: {regime}",
        f"Open positions: {len(ctx.open_positions)} | Open orders: {len(ctx.open_orders)}",
        "",
    ]
    if ctx.trading_mode == "daily_active":
        lines.append("QUALITY SCORE RANKING (setup/cobra/vibe/RS — not knife dips):")
        ranked = sorted(ctx.watchlist, key=lambda t: t.active_score, reverse=True)
        for i, r in enumerate(ranked[:10], 1):
            lines.append(
                f"  #{i} {r.ticker} [{r.sector}]: quality={r.active_score} conv={r.conviction} "
                f"setup={r.setup_type} vibe={r.vibe_score} cobra={r.coiled_cobra_grade} "
                f"rs={r.rs_63d} rvol={r.rvol} open={r.change_from_open_pct}% "
                f"vwap%={r.price_vs_vwap_pct} held={r.in_position}"
            )
    else:
        lines.append("CONVICTION RANKING (trade top names first):")
        for r in ctx.conviction_ranking[:8]:
            lines.append(
                f"  #{r['rank']} {r['ticker']}: conviction={r['conviction']} "
                f"setup={r.get('setup')} vibe={r.get('vibe_score')} cobra={r.get('cobra_grade')} "
                f"held={r.get('in_position')}"
            )
    lines.extend(["", "PER-TICKER SIGNALS:"])
    for t in ctx.watchlist:
        lines.append(
            f"  {t.ticker} [{t.sector}]: price={t.price} chg%={t.change_pct} open%={t.change_from_open_pct} "
            f"rsi={t.rsi} quality={t.active_score} conviction={t.conviction} setup={t.setup_type} "
            f"vibe={t.vibe_score} cobra={t.coiled_cobra_grade} rs={t.rs_63d} rvol={t.rvol} "
            f"vwap%={t.price_vs_vwap_pct} tight_stop={t.tight_stop} "
            f"stop={t.stop} t1={t.target1} in_pos={t.in_position} pnl%={t.position_pnl_pct} "
            f"open_buy_ord={t.has_open_buy_order}"
        )
    if ctx.open_positions:
        lines.append("")
        lines.append("POSITIONS:")
        for p in ctx.open_positions:
            lines.append(f"  {p.get('symbol')}: qty={p.get('qty')} pnl%={p.get('pnl_pct')}")
    if ctx.open_orders:
        lines.append("")
        lines.append("OPEN ORDERS (do not duplicate):")
        for o in ctx.open_orders:
            lines.append(f"  {o.get('symbol')}: {o.get('side')} {o.get('status')}")
    lines.append("")
    lines.append("Apply SYSTEM algorithm. Return JSON only.")
    return "\n".join(lines)


class OllamaAgent:
    def __init__(
        self,
        base_url: str | None = None,
        model: str | None = None,
        enabled: bool | None = None,
    ) -> None:
        self.base_url = (base_url or config.OLLAMA_BASE_URL).rstrip("/")
        self.model = model or config.OLLAMA_MODEL
        self.enabled = config.OLLAMA_ENABLED if enabled is None else enabled
        self.timeout = config.OLLAMA_TIMEOUT_SEC

    def decide(self, ctx: CycleContext) -> AgentDecision:
        if config.TRADING_MODE == "daily_active" and not self.enabled:
            return build_daily_decision(ctx)

        if not self.enabled:
            return self._rule_based_fallback(ctx)

        brief = build_decision_brief(ctx)
        user_prompt = brief + "\n\n=== RAW JSON ===\n" + json.dumps(
            ctx.to_prompt_dict(), indent=2
        )
        try:
            raw = self._chat(user_prompt)
            parsed = self._parse_json(raw)
            actions = self._parse_actions(parsed.get("actions", []), ctx.watchlist)
            actions = self._sanitize_actions(actions, ctx)
            llm_decision = AgentDecision(
                actions=actions,
                summary=str(parsed.get("summary", "")),
                raw_response=raw,
                model=self.model,
            )
            if config.TRADING_MODE == "daily_active":
                return merge_llm_with_daily(llm_decision, ctx)
            return llm_decision
        except Exception as exc:
            logger.error("Ollama decision failed: %s", exc)
            if config.TRADING_MODE == "daily_active":
                fb = build_daily_decision(ctx)
                fb.summary = f"Ollama failed ({exc}); daily rules."
                return fb
            fb = self._rule_based_fallback(ctx)
            fb.summary = f"Ollama failed ({exc}); rule-based fallback."
            fb.used_fallback = True
            return fb

    def _sanitize_actions(
        self, actions: list[TradeAction], ctx: CycleContext
    ) -> list[TradeAction]:
        """Clamp obvious LLM mistakes; risk_guard is still final gate."""
        snap = {t.ticker: t for t in ctx.watchlist}
        out: list[TradeAction] = []
        for a in actions:
            act = a.normalized_action()
            s = snap.get(a.ticker)
            if act == "BUY":
                if ctx.halted:
                    a = TradeAction(a.ticker, "HOLD", reason="halted")
                elif s and s.has_open_buy_order:
                    a = TradeAction(a.ticker, "HOLD", reason="open order exists")
                elif s and s.in_position:
                    a = TradeAction(a.ticker, "HOLD", reason="already in position")
                elif not a.stop and s and (s.tight_stop or s.stop):
                    stop = s.tight_stop or s.stop
                    a = TradeAction(
                        a.ticker, "BUY", pct=a.pct, stop=stop, reason=a.reason,
                    )
                elif not a.stop:
                    a = TradeAction(a.ticker, "HOLD", reason="missing stop")
                elif s and a.stop and a.stop >= s.price:
                    a = TradeAction(a.ticker, "HOLD", reason="invalid stop")
                else:
                    a.pct = max(5.0, min(35.0, a.pct or 15.0))
            elif act == "SELL":
                if s and not s.in_position:
                    a = TradeAction(a.ticker, "HOLD", reason="no position")
                else:
                    a.pct = max(25.0, min(100.0, a.pct or 100.0))
            out.append(a)
        return out

    def _chat(self, user_prompt: str) -> str:
        url = f"{self.base_url}/api/chat"
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": get_system_prompt()},
                {"role": "user", "content": user_prompt},
            ],
            "stream": False,
            "format": "json",
            "options": {"temperature": 0.05, "num_predict": 1024},
        }
        resp = requests.post(url, json=payload, timeout=self.timeout)
        resp.raise_for_status()
        data = resp.json()
        return data.get("message", {}).get("content", "")

    @staticmethod
    def _parse_json(text: str) -> dict[str, Any]:
        text = text.strip()
        if text.startswith("```"):
            text = re.sub(r"^```(?:json)?\s*", "", text)
            text = re.sub(r"\s*```$", "", text)
        return json.loads(text)

    def _parse_actions(
        self, actions: list[dict], watchlist: list[TickerSnapshot]
    ) -> list[TradeAction]:
        valid_tickers = {t.ticker for t in watchlist}
        out: list[TradeAction] = []
        seen = set()
        for a in actions:
            ticker = str(a.get("ticker", "")).upper()
            if ticker not in valid_tickers or ticker in seen:
                continue
            seen.add(ticker)
            stop_val = a.get("stop")
            stop = float(stop_val) if stop_val not in (None, "", "null") else None
            out.append(TradeAction(
                ticker=ticker,
                action=str(a.get("action", "HOLD")),
                pct=float(a.get("pct", 0) or 0),
                stop=stop,
                reason=str(a.get("reason", "")),
            ))
        for t in watchlist:
            if t.ticker not in seen:
                out.append(TradeAction(ticker=t.ticker, action="HOLD", reason="default"))
        return out

    def _rule_based_fallback(self, ctx: CycleContext) -> AgentDecision:
        """Same rules as SYSTEM_PROMPT step 2-3 — deterministic backup."""
        ranked = sorted(
            ctx.watchlist, key=lambda t: t.conviction or compute_conviction(t), reverse=True,
        )
        actions: list[TradeAction] = []
        open_count = len(ctx.open_positions)
        regime_ok = ctx.market_regime.get("regime_bull_ok", True)
        buys_placed = 0
        max_buys = 1 if not regime_ok else 2

        for t in ranked:
            if t.in_position:
                if (t.rsi and t.rsi > 72) or t.change_from_open_pct > 2.0:
                    actions.append(TradeAction(
                        t.ticker, "SELL", 100, reason="rule step2 extended",
                    ))
                elif t.target1 and t.price >= t.target1:
                    actions.append(TradeAction(
                        t.ticker, "SELL", 50, reason="rule step2 target1",
                    ))
                else:
                    actions.append(TradeAction(t.ticker, "HOLD", reason="hold position"))
            elif (
                not ctx.halted
                and buys_placed < max_buys
                and t.stop
                and not t.has_open_buy_order
                and open_count < config.MAX_POSITIONS
                and (t.conviction or 0) >= 40
                and (
                    t.setup_type == "SETUP_LONG"
                    or (t.coiled_cobra_grade and ("A" in t.coiled_cobra_grade or "B" in t.coiled_cobra_grade))
                )
                and (t.vibe_score is None or t.vibe_score >= 5 or (t.coiled_cobra_grade and "A" in t.coiled_cobra_grade))
            ):
                conv = t.conviction or 0
                pct = 25 if conv >= 75 else (20 if conv >= 60 else 15)
                if not regime_ok:
                    pct = 10
                actions.append(TradeAction(
                    t.ticker, "BUY", pct, stop=t.stop,
                    reason=f"fallback conv={conv}",
                ))
                buys_placed += 1
                open_count += 1
            else:
                actions.append(TradeAction(t.ticker, "HOLD", reason="no setup"))

        return AgentDecision(
            actions=actions,
            summary="Rule-based fallback (same algorithm as prompt)",
            used_fallback=True,
            model="rules",
        )
