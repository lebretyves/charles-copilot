from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import pandas as pd

from .schemas import FeatureRecord, SegmentRecord, SignalFeatureSet, VitalDBDatasetManifest
from .segmenter import (
    NUMERIC_VITAL_COLUMNS,
    TIME_COLUMN_CANDIDATES,
    build_waveform_file_map,
    resolve_manifest_paths,
)


def _find_time_column(frame: pd.DataFrame) -> str:
    for name in TIME_COLUMN_CANDIDATES:
        if name in frame.columns:
            return name
    raise ValueError(f"No supported time column found in dataframe columns: {list(frame.columns)}")


def _slice_window(frame: pd.DataFrame, time_col: str, start_s: float, end_s: float) -> pd.DataFrame:
    time_series = pd.to_numeric(frame[time_col], errors="coerce")
    window = frame[(time_series >= start_s) & (time_series < end_s)]
    if window.empty and not frame.empty:
        midpoint = (start_s + end_s) / 2.0
        nearest_idx = (time_series - midpoint).abs().idxmin()
        window = frame.loc[[nearest_idx]]
    return window


def _to_numeric_array(frame: pd.DataFrame, column: str) -> np.ndarray:
    if column not in frame.columns:
        return np.array([], dtype="float64")
    series = pd.to_numeric(frame[column], errors="coerce").dropna()
    if series.empty:
        return np.array([], dtype="float64")
    return series.to_numpy(dtype="float64")


def _round_or_none(value: float | None) -> float | None:
    if value is None or math.isnan(value):
        return None
    return round(float(value), 6)


def compute_signal_feature_set(
    values: np.ndarray,
    *,
    source_column: str,
    sample_rate_hz: int,
    coverage_ratio: float,
) -> SignalFeatureSet:
    if values.size == 0:
        return SignalFeatureSet(
            source_column=source_column,
            sample_rate_hz=sample_rate_hz,
            samples=0,
            coverage_ratio=round(float(coverage_ratio), 6),
        )

    centered = values - float(values.mean())
    diffs = np.diff(values)
    zero_crossings = None
    if centered.size >= 2:
        zero_crossings = np.count_nonzero(np.diff(np.signbit(centered))) / max(centered.size - 1, 1)

    return SignalFeatureSet(
        source_column=source_column,
        sample_rate_hz=sample_rate_hz,
        samples=int(values.size),
        coverage_ratio=round(float(coverage_ratio), 6),
        mean=_round_or_none(float(values.mean())),
        std=_round_or_none(float(values.std())),
        min=_round_or_none(float(values.min())),
        max=_round_or_none(float(values.max())),
        median=_round_or_none(float(np.median(values))),
        amplitude=_round_or_none(float(values.max() - values.min())),
        rms=_round_or_none(float(np.sqrt(np.mean(np.square(values))))),
        abs_mean=_round_or_none(float(np.mean(np.abs(values)))),
        slope_mean_abs=_round_or_none(float(np.mean(np.abs(diffs)))) if diffs.size else None,
        zero_crossing_rate=_round_or_none(float(zero_crossings)) if zero_crossings is not None else None,
        delta=_round_or_none(float(values[-1] - values[0])) if values.size >= 2 else None,
    )


def _compute_numeric_window_features(window: pd.DataFrame) -> dict[str, float | int | None]:
    features: dict[str, float | int | None] = {}
    for alias, candidates in NUMERIC_VITAL_COLUMNS.items():
        series = np.array([], dtype="float64")
        for column in candidates:
            series = _to_numeric_array(window, column)
            if series.size:
                break
        if not series.size:
            features[f"{alias}_mean"] = None
            features[f"{alias}_delta"] = None
            continue
        features[f"{alias}_mean"] = _round_or_none(float(series.mean()))
        features[f"{alias}_delta"] = _round_or_none(float(series[-1] - series[0])) if series.size >= 2 else 0.0
    return features


class CaseFrameCache:
    def __init__(self, manifest: VitalDBDatasetManifest):
        self.manifest = manifest
        self.paths = resolve_manifest_paths(manifest)
        self.numeric_frames: dict[int, tuple[pd.DataFrame, str]] = {}
        self.waveform_frames: dict[int, dict[str, tuple[pd.DataFrame, str]]] = {}

    def get_numeric_frame(self, case_id: int) -> tuple[pd.DataFrame, str]:
        if case_id not in self.numeric_frames:
            case_path = Path(self.paths["cases_dir"]) / f"case_{case_id:05d}.parquet"
            frame = pd.read_parquet(case_path)
            self.numeric_frames[case_id] = (frame, _find_time_column(frame))
        return self.numeric_frames[case_id]

    def get_waveform_frames(self, case_id: int) -> dict[str, tuple[pd.DataFrame, str]]:
        if case_id not in self.waveform_frames:
            loaded: dict[str, tuple[pd.DataFrame, str]] = {}
            for key, path in build_waveform_file_map(case_id, self.paths["waveforms_dir"]).items():
                if not path.exists():
                    continue
                frame = pd.read_parquet(path)
                loaded[key] = (frame, _find_time_column(frame))
            self.waveform_frames[case_id] = loaded
        return self.waveform_frames[case_id]


def extract_feature_record(
    segment: SegmentRecord,
    manifest: VitalDBDatasetManifest,
    cache: CaseFrameCache | None = None,
) -> FeatureRecord:
    cache = cache or CaseFrameCache(manifest)
    numeric_frame, numeric_time_col = cache.get_numeric_frame(segment.case_id)
    numeric_window = _slice_window(numeric_frame, numeric_time_col, segment.start_s, segment.end_s)
    numeric_features = _compute_numeric_window_features(numeric_window)

    signal_features: dict[str, SignalFeatureSet] = {}
    waveform_frames = cache.get_waveform_frames(segment.case_id)
    for signal_spec in manifest.signal_specs:
        frame_info = waveform_frames.get(signal_spec.file_key)
        if frame_info is None:
            continue
        frame, time_col = frame_info
        window = _slice_window(frame, time_col, segment.start_s, segment.end_s)
        values = _to_numeric_array(window, signal_spec.column)
        coverage = segment.signals.get(signal_spec.name).coverage_ratio if signal_spec.name in segment.signals else 0.0
        signal_features[signal_spec.name] = compute_signal_feature_set(
            values,
            source_column=signal_spec.column,
            sample_rate_hz=signal_spec.sample_rate_hz,
            coverage_ratio=coverage,
        )

    return FeatureRecord(
        segment_id=segment.segment_id,
        case_id=segment.case_id,
        start_s=segment.start_s,
        end_s=segment.end_s,
        weak_labels=list(segment.weak_labels),
        vitals_snapshot=dict(segment.vitals_snapshot),
        numeric_features=numeric_features,
        signal_features=signal_features,
        source_files=dict(segment.source_files),
        case_context=dict(segment.case_context),
        case_complications=list(segment.case_complications),
    )
