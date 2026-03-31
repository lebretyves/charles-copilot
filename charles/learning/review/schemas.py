from __future__ import annotations

from pydantic import BaseModel, Field

from learning.llm.schemas import ExplanationTarget, LLMTrainingSample


class ReviewTask(BaseModel):
    sample: LLMTrainingSample
    review_status: str = "pending"
    reviewer: str | None = None
    review_notes: str | None = None
    corrected_output: ExplanationTarget | None = None
    corrected_problem_id: str | None = None
    review_priority: str = "normal"
    review_tags: list[str] = Field(default_factory=list)

