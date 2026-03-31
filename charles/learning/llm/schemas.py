from __future__ import annotations

from pydantic import BaseModel, Field, field_validator


class ExplanationTarget(BaseModel):
    situation: str = Field(..., min_length=1, max_length=400)
    risks: list[str] = Field(default_factory=list, max_length=6)
    recommendations: list[str] = Field(default_factory=list, max_length=6)
    call_mar: bool = False
    call_mar_reason: str | None = Field(default=None, max_length=240)
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)

    @field_validator("risks", "recommendations", mode="before")
    @classmethod
    def _normalize_list(cls, value):
        if value is None:
            return []
        if isinstance(value, str):
            return [value[:180]]
        if not isinstance(value, (list, tuple)):
            return []
        items: list[str] = []
        for item in value:
            text = str(item).strip()
            if text:
                items.append(text[:180])
        return items[:6]


class LLMConversationMessage(BaseModel):
    role: str
    content: str


class LLMTrainingSample(BaseModel):
    sample_id: str
    case_id: int
    segment_id: str
    split: str
    input_variant: str = "full_wave"
    prompt_id: str
    prompt_version: str
    primary_problem_id: str | None = None
    primary_severity: str | None = None
    target_origin: str = "heuristic_bootstrap"
    source_problem_ids: list[str] = Field(default_factory=list)
    case_complications: list[str] = Field(default_factory=list)
    masked_signals: list[str] = Field(default_factory=list)
    system_prompt: str
    user_prompt: str
    messages: list[LLMConversationMessage]
    expected_output: ExplanationTarget
