from __future__ import annotations

from pydantic import BaseModel, Field

from learning.llm.schemas import LLMConversationMessage


class FineTuneChatSample(BaseModel):
    sample_id: str
    split: str
    input_variant: str = "full_wave"
    source_status: str
    target_origin: str
    prompt_id: str
    prompt_version: str
    primary_problem_id: str | None = None
    primary_severity: str | None = None
    case_complications: list[str] = Field(default_factory=list)
    masked_signals: list[str] = Field(default_factory=list)
    messages: list[LLMConversationMessage]
    assistant_json: str


class FineTuneInstructionSample(BaseModel):
    sample_id: str
    split: str
    input_variant: str = "full_wave"
    source_status: str
    target_origin: str
    prompt_id: str
    prompt_version: str
    primary_problem_id: str | None = None
    primary_severity: str | None = None
    case_complications: list[str] = Field(default_factory=list)
    masked_signals: list[str] = Field(default_factory=list)
    system: str
    instruction: str
    output_json: str


class PreparedTextSample(BaseModel):
    sample_id: str
    split: str
    input_variant: str = "full_wave"
    target_origin: str
    primary_problem_id: str | None = None
    primary_severity: str | None = None
    case_complications: list[str] = Field(default_factory=list)
    masked_signals: list[str] = Field(default_factory=list)
    text: str
