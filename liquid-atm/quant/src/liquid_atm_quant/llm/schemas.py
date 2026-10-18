"""Structured outputs the local LLM must produce."""

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class CatalystType(StrEnum):
    EARNINGS_BEAT = "earnings_beat"
    EARNINGS_MISS = "earnings_miss"
    GUIDANCE_RAISE = "guidance_raise"
    GUIDANCE_CUT = "guidance_cut"
    MERGER_ACQUISITION = "merger_acquisition"
    PRODUCT_OR_CONTRACT = "product_or_contract"
    ANALYST_ACTION = "analyst_action"
    REGULATORY = "regulatory"
    INSIDER_BUYING = "insider_buying"
    MACRO_OR_SECTOR = "macro_or_sector"
    DILUTION_OR_OFFERING = "dilution_or_offering"
    MEME_OR_SOCIAL_PUMP = "meme_or_social_pump"
    NO_CLEAR_CATALYST = "no_clear_catalyst"


class CatalystVerdict(BaseModel):
    """The LLM gate's opinion on why a stock is moving. A veto input, never a buy signal."""

    model_config = ConfigDict(extra="forbid")

    catalyst_type: CatalystType
    quality: float = Field(ge=0.0, le=1.0, description="How durable/fundamental the catalyst is (1 = strong).")
    is_pump: bool = Field(description="True if the move looks driven by hype, social media or low-quality news.")
    red_flags: list[str] = Field(default_factory=list, max_length=5)
    confidence: float = Field(ge=0.0, le=1.0, description="How sure the model is, given the evidence provided.")
    rationale: str = Field(max_length=600)
