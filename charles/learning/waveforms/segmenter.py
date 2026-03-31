from __future__ import annotations

import math
from pathlib import Path
from typing import Iterable

import pandas as pd
import yaml

from .labels import infer_weak_labels
from .schemas import (
    SegmentRecord,
    SegmentSpec,
    VitalDBDatasetManifest,
    WindowSignalStats,
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MANIFEST_PATH = PROJECT_ROOT / "learning" / "datasets" / "manifests" / "vitaldb_waveforms.yaml"
TIME_COLUMN_CANDIDATES = ("time_sec", "time", "t")
NUMERIC_VITAL_COLUMNS = {
    "hr": ["Solar8000/HR"],
    "spo2": ["Solar8000/PLETH_SPO2"],
    "pas": ["Solar8000/ART_SBP", "Solar8000/NIBP_SBP"],
    "pad": ["Solar8000/ART_DBP", "Solar8000/NIBP_DBP"],
    "pam": ["Solar8000/ART_MBP", "Solar8000/NIBP_MBP"],
    "etco2": ["Solar8000/ETCO2"],
    "fr": ["Solar8000/RR", "Solar8000/RR_CO2"],
    "bis": ["BIS/BIS"],
}


def load_dataset_manifest(path: str | Path = DEFAULT_MANIFEST_PATH) -> VitalDBDatasetManifest:
    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    return VitalDBDatasetManifest.model_validate(raw)


def resolve_manifest_paths(manifest: VitalDBDatasetManifest) -> dict[str, Path]:
    def _resolve(value: str) -> Path:
        path = Path(value)
        if path.is_absolute():
            return path
        return (PROJECT_ROOT / path).resolve()

    return {
        "metadata_csv": _resolve(manifest.paths.metadata_csv),
        "labs_csv": _resolve(manifest.paths.labs_csv) if manifest.paths.labs_csv else None,
        "cases_dir": _resolve(manifest.paths.cases_dir),
        "waveforms_dir": _resolve(manifest.paths.waveforms_dir),
        "output_dir": _resolve(manifest.paths.output_dir),
    }


def find_case_files(cases_dir: str | Path, case_glob: str = "case_*.parquet") -> list[Path]:
    return sorted(Path(cases_dir).glob(case_glob))


def build_waveform_file_map(case_id: int, waveforms_dir: str | Path) -> dict[str, Path]:
    waves_dir = Path(waveforms_dir)
    case_tag = f"{case_id:05d}"
    return {
        "500hz": waves_dir / f"wave_{case_tag}_500hz.parquet",
        "25hz": waves_dir / f"wave_{case_tag}_25hz.parquet",
        "128hz": waves_dir / f"wave_{case_tag}_128hz.parquet",
    }


def _find_time_column(frame: pd.DataFrame) -> str:
    for name in TIME_COLUMN_CANDIDATES:
        if name in frame.columns:
            return name
    raise ValueError(f"No supported time column found in dataframe columns: {list(frame.columns)}")


def _clean_numeric_series(frame: pd.DataFrame, candidates: list[str]) -> pd.Series:
    for column in candidates:
        if column in frame.columns:
            series = pd.to_numeric(frame[column], errors="coerce").dropna()
            if not series.empty:
                return series
    return pd.Series(dtype="float64")


def _summarize_numeric_window(frame: pd.DataFrame, start_s: float, end_s: float) -> dict[str, float | int | None]:
    time_col = _find_time_column(frame)
    time_series = pd.to_numeric(frame[time_col], errors="coerce")
    window = frame[(time_series >= start_s) & (time_series < end_s)]

    if window.empty and not frame.empty:
        midpoint = (start_s + end_s) / 2.0
        nearest_idx = (time_series - midpoint).abs().idxmin()
        window = frame.loc[[nearest_idx]]

    summary: dict[str, float | int | None] = {}
    for alias, candidates in NUMERIC_VITAL_COLUMNS.items():
        series = _clean_numeric_series(window, candidates)
        if series.empty:
            summary[alias] = None
            summary[f"{alias}_min"] = None
            summary[f"{alias}_max"] = None
            continue
        summary[alias] = round(float(series.iloc[-1]), 3)
        summary[f"{alias}_min"] = round(float(series.min()), 3)
        summary[f"{alias}_max"] = round(float(series.max()), 3)
    return summary


def _extract_signal_stats(
    frame: pd.DataFrame,
    time_col: str,
    column: str,
    sample_rate_hz: int,
    start_s: float,
    end_s: float,
) -> WindowSignalStats | None:
    if column not in frame.columns:
        return None

    time_series = pd.to_numeric(frame[time_col], errors="coerce")
    mask = (time_series >= start_s) & (time_series < end_s)
    window = pd.to_numeric(frame.loc[mask, column], errors="coerce").dropna()

    duration_s = max(end_s - start_s, 0.0)
    expected_samples = max(int(round(duration_s * sample_rate_hz)), 1)
    samples = int(window.shape[0])
    coverage_ratio = min(samples / expected_samples, 1.0)

    return WindowSignalStats(
        source_column=column,
        samples=samples,
        expected_samples=expected_samples,
        coverage_ratio=round(float(coverage_ratio), 4),
    )


def _iter_segment_starts(total_duration_s: float, spec: SegmentSpec) -> Iterable[float]:
    if total_duration_s <= 0:
        return []
    if total_duration_s <= spec.window_seconds:
        return [0.0]

    starts: list[float] = []
    cursor = 0.0
    max_start = total_duration_s - spec.window_seconds
    while cursor <= max_start + 1e-9:
        starts.append(round(cursor, 6))
        cursor += spec.stride_seconds
    return starts


def iter_case_segments(
    case_path: str | Path,
    waveforms_dir: str | Path,
    manifest: VitalDBDatasetManifest,
    max_segments_per_case: int | None = None,
) -> list[SegmentRecord]:
    case_path = Path(case_path)
    case_id = int(case_path.stem.replace("case_", ""))
    numeric_frame = pd.read_parquet(case_path)
    numeric_time_col = _find_time_column(numeric_frame)
    total_duration_s = float(pd.to_numeric(numeric_frame[numeric_time_col], errors="coerce").dropna().max())

    waveform_paths = build_waveform_file_map(case_id, waveforms_dir)
    waveform_frames: dict[str, tuple[pd.DataFrame, str]] = {}
    for key, path in waveform_paths.items():
        if not path.exists():
            continue
        frame = pd.read_parquet(path)
        waveform_frames[key] = (frame, _find_time_column(frame))

    if not waveform_frames:
        return []

    records: list[SegmentRecord] = []
    for index, start_s in enumerate(_iter_segment_starts(total_duration_s, manifest.segment_spec)):
        end_s = min(start_s + manifest.segment_spec.window_seconds, total_duration_s)
        if end_s <= start_s:
            continue

        signals: dict[str, WindowSignalStats] = {}
        covered_signals = 0
        for signal_spec in manifest.signal_specs:
            frame_info = waveform_frames.get(signal_spec.file_key)
            if frame_info is None:
                continue
            frame, time_col = frame_info
            stats = _extract_signal_stats(
                frame=frame,
                time_col=time_col,
                column=signal_spec.column,
                sample_rate_hz=signal_spec.sample_rate_hz,
                start_s=start_s,
                end_s=end_s,
            )
            if stats is None:
                continue
            signals[signal_spec.name] = stats
            if stats.coverage_ratio >= manifest.segment_spec.min_signal_coverage:
                covered_signals += 1

        if covered_signals < manifest.segment_spec.min_required_signals:
            continue

        vitals_snapshot = _summarize_numeric_window(numeric_frame, start_s, end_s)
        weak_labels = infer_weak_labels(vitals_snapshot)
        source_files = {
            "numeric": case_path.name,
            **{key: path.name for key, path in waveform_paths.items() if path.exists()},
        }
        record = SegmentRecord(
            segment_id=f"case{case_id:05d}_{index:05d}_{int(math.floor(start_s * 1000)):010d}",
            case_id=case_id,
            start_s=round(start_s, 3),
            end_s=round(end_s, 3),
            weak_labels=weak_labels,
            vitals_snapshot=vitals_snapshot,
            signals=signals,
            source_files=source_files,
        )
        records.append(record)

        if max_segments_per_case is not None and len(records) >= max_segments_per_case:
            break

    return records
