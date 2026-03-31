from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, field_validator


class DatasetSource(BaseModel):
    name: str
    license: str
    citation: str


class DatasetPaths(BaseModel):
    metadata_csv: str
    labs_csv: str | None = None
    cases_dir: str
    waveforms_dir: str
    output_dir: str


class SignalSpec(BaseModel):
    name: str
    file_key: str
    column: str
    sample_rate_hz: int = Field(gt=0)


class SegmentSpec(BaseModel):
    window_seconds: float = Field(default=30.0, gt=0)
    stride_seconds: float = Field(default=5.0, gt=0)
    min_signal_coverage: float = Field(default=0.75, ge=0.0, le=1.0)
    min_required_signals: int = Field(default=2, ge=1)

    @field_validator("stride_seconds")
    @classmethod
    def validate_stride(cls, value: float, info):
        window_seconds = info.data.get("window_seconds")
        if window_seconds is not None and value > window_seconds:
            raise ValueError("stride_seconds must be <= window_seconds")
        return value


class WindowSignalStats(BaseModel):
    source_column: str
    samples: int = Field(ge=0)
    expected_samples: int = Field(ge=0)
    coverage_ratio: float = Field(ge=0.0, le=1.0)


class SignalFeatureSet(BaseModel):
    source_column: str
    sample_rate_hz: int | None = Field(default=None, gt=0)
    samples: int = Field(ge=0)
    coverage_ratio: float = Field(ge=0.0, le=1.0)
    mean: float | None = None
    std: float | None = None
    min: float | None = None
    max: float | None = None
    median: float | None = None
    amplitude: float | None = None
    rms: float | None = None
    abs_mean: float | None = None
    slope_mean_abs: float | None = None
    zero_crossing_rate: float | None = None
    delta: float | None = None


class SegmentRecord(BaseModel):
    segment_id: str
    case_id: int
    start_s: float = Field(ge=0)
    end_s: float = Field(gt=0)
    weak_labels: list[str] = Field(default_factory=list)
    vitals_snapshot: dict[str, float | int | None] = Field(default_factory=dict)
    signals: dict[str, WindowSignalStats] = Field(default_factory=dict)
    source_files: dict[str, str] = Field(default_factory=dict)
    case_context: dict[str, Any] = Field(default_factory=dict)
    case_complications: list[str] = Field(default_factory=list)


class FeatureRecord(BaseModel):
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


class VitalDBDatasetManifest(BaseModel):
    dataset_id: str
    dataset_version: str
    description: str
    source: DatasetSource
    paths: DatasetPaths
    case_glob: str = "case_*.parquet"
    context_columns: list[str] = Field(default_factory=list)
    signal_specs: list[SignalSpec]
    segment_spec: SegmentSpec
