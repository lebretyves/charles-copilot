from __future__ import annotations

from pydantic import BaseModel, Field


class SignalDatasetRecord(BaseModel):
    sample_id: str
    case_id: int
    segment_id: str
    split: str
    primary_problem_id: str
    primary_severity: str | None = None
    case_complications: list[str] = Field(default_factory=list)
    weak_labels: list[str] = Field(default_factory=list)
    array_path: str
    channel_names: list[str] = Field(default_factory=list)
    target_length: int = Field(gt=0)
    availability: list[float] = Field(default_factory=list)
