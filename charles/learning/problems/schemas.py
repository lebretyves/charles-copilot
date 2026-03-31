from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from learning.waveforms.schemas import SignalFeatureSet


class ProblemHypothesis(BaseModel):
    problem_id: str
    severity: str
    score: float = Field(ge=0.0, le=1.0)
    reasons: list[str] = Field(default_factory=list)
    evidence: dict[str, Any] = Field(default_factory=dict)


class ProblemAnalysisRecord(BaseModel):
    segment_id: str
    case_id: int
    start_s: float = Field(ge=0)
    end_s: float = Field(gt=0)
    weak_labels: list[str] = Field(default_factory=list)
    vitals_snapshot: dict[str, float | int | None] = Field(default_factory=dict)
    numeric_features: dict[str, float | int | None] = Field(default_factory=dict)
    signal_features: dict[str, SignalFeatureSet] = Field(default_factory=dict)
    source_files: dict[str, str] = Field(default_factory=dict)
    case_context: dict[str, Any] = Field(default_factory=dict)
    case_complications: list[str] = Field(default_factory=list)
    feature_version: str = "v1"
    problem_version: str = "v1"
    primary_problem_id: str | None = None
    problem_hypotheses: list[ProblemHypothesis] = Field(default_factory=list)
