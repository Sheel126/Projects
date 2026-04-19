from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Literal, Optional, Dict, Any


RecommendationType = Literal["TAKE", "WATCH", "SKIP"]
SetupType = Literal["SETUP_LONG", "SETUP_SHORT"]


@dataclass
class NewsHeadline:
    title: str
    url: str
    sentiment: Literal["positive", "negative", "mixed", "unknown"] = "unknown"


@dataclass
class AIAnalysisResult:
    symbol: str
    setup_type: SetupType
    recommendation: RecommendationType
    time_horizon: str
    confidence: float
    risk_flags: List[str] = field(default_factory=list)
    rationale_bullets: List[str] = field(default_factory=list)
    invalidations: List[str] = field(default_factory=list)
    news_headlines: List[NewsHeadline] = field(default_factory=list)
    action_plan: List[str] = field(default_factory=list)
    beginner_notes: List[str] = field(default_factory=list)
    position_size_hint: str = "Start small (for example 25% of your intended position)"
    buy_timing: str = "Wait for entry confirmation near the planned entry level."
    sell_timing: str = "Scale out near targets and exit early if invalidation is hit."
    status: Literal["ok", "ai_unavailable", "validation_failed"] = "ok"
    raw_model_output: Optional[str] = None


def validate_ai_payload(obj: Dict[str, Any]) -> AIAnalysisResult:
    """
    Lightweight runtime validator to convert a dict (from JSON) into an
    AIAnalysisResult. This intentionally stays permissive but guards
    against missing / badly-typed fields, so a single bad record does
    not crash the whole batch.
    """
    symbol = str(obj.get("symbol", "")).strip()
    setup_type = obj.get("setup_type", "")
    recommendation = obj.get("recommendation", "")

    if setup_type not in ("SETUP_LONG", "SETUP_SHORT"):
        setup_type = "SETUP_LONG"

    if recommendation not in ("TAKE", "WATCH", "SKIP"):
        recommendation = "WATCH"

    time_horizon = str(obj.get("time_horizon", "1-3 weeks"))

    try:
        confidence = float(obj.get("confidence", 0.5))
    except (TypeError, ValueError):
        confidence = 0.5

    def _coerce_str_list(value: Any) -> List[str]:
        if isinstance(value, list):
            return [str(v) for v in value if isinstance(v, (str, int, float))]
        if isinstance(value, (str, int, float)):
            return [str(value)]
        return []

    risk_flags = _coerce_str_list(obj.get("risk_flags", []))
    rationale_bullets = _coerce_str_list(obj.get("rationale_bullets", []))
    invalidations = _coerce_str_list(obj.get("invalidations", []))
    action_plan = _coerce_str_list(obj.get("action_plan", []))
    beginner_notes = _coerce_str_list(obj.get("beginner_notes", []))
    position_size_hint = str(
        obj.get(
            "position_size_hint",
            "Start small (for example 25% of your intended position)",
        )
    ).strip()
    if not position_size_hint:
        position_size_hint = "Start small (for example 25% of your intended position)"
    buy_timing = str(
        obj.get(
            "buy_timing",
            "Wait for entry confirmation near the planned entry level.",
        )
    ).strip() or "Wait for entry confirmation near the planned entry level."
    sell_timing = str(
        obj.get(
            "sell_timing",
            "Scale out near targets and exit early if invalidation is hit.",
        )
    ).strip() or "Scale out near targets and exit early if invalidation is hit."

    headlines_raw = obj.get("news_headlines", [])
    headlines: List[NewsHeadline] = []
    if isinstance(headlines_raw, list):
        for item in headlines_raw:
            if not isinstance(item, dict):
                continue
            title = str(item.get("title", "")).strip()
            url = str(item.get("url", "")).strip()
            sentiment = str(item.get("sentiment", "unknown")).lower()
            if sentiment not in ("positive", "negative", "mixed", "unknown"):
                sentiment = "unknown"
            if title and url:
                headlines.append(
                    NewsHeadline(title=title, url=url, sentiment=sentiment)
                )

    return AIAnalysisResult(
        symbol=symbol,
        setup_type=setup_type,  # type: ignore[arg-type]
        recommendation=recommendation,  # type: ignore[arg-type]
        time_horizon=time_horizon,
        confidence=confidence,
        risk_flags=risk_flags,
        rationale_bullets=rationale_bullets,
        invalidations=invalidations,
        news_headlines=headlines,
        action_plan=action_plan,
        beginner_notes=beginner_notes,
        position_size_hint=position_size_hint,
        buy_timing=buy_timing,
        sell_timing=sell_timing,
    )

