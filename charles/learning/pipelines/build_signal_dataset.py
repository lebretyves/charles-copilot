from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from learning.llm import choose_split
from learning.problems.schemas import ProblemAnalysisRecord
from learning.signal.schemas import SignalDatasetRecord
from learning.waveforms.segmenter import (
    DEFAULT_MANIFEST_PATH,
    build_waveform_file_map,
    load_dataset_manifest,
    resolve_manifest_paths,
)


def _default_problem_index_path(manifest_path: str | Path) -> Path:
    manifest = load_dataset_manifest(manifest_path)
    resolved = resolve_manifest_paths(manifest)
    return resolved["output_dir"] / "problem_index.jsonl"


def _find_time_column(frame: pd.DataFrame) -> str:
    for name in ("time_sec", "time", "t"):
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
        return np.array([], dtype="float32")
    series = pd.to_numeric(frame[column], errors="coerce").dropna()
    if series.empty:
        return np.array([], dtype="float32")
    return series.to_numpy(dtype="float32")


def _resample_signal(values: np.ndarray, target_length: int) -> np.ndarray:
    if target_length <= 0:
        raise ValueError("target_length must be > 0")
    if values.size == 0:
        return np.zeros(target_length, dtype=np.float32)
    if values.size == 1:
        return np.full(target_length, float(values[0]), dtype=np.float32)

    x_original = np.linspace(0.0, 1.0, num=values.size, dtype=np.float32)
    x_target = np.linspace(0.0, 1.0, num=target_length, dtype=np.float32)
    resampled = np.interp(x_target, x_original, values).astype(np.float32)
    mean = float(resampled.mean())
    std = float(resampled.std())
    if std > 1e-6:
        resampled = (resampled - mean) / std
    else:
        resampled = resampled - mean
    return resampled.astype(np.float32)


def build_signal_dataset(
    manifest_path: str | Path = DEFAULT_MANIFEST_PATH,
    problem_index_path: str | Path | None = None,
    *,
    target_length: int = 256,
    limit_segments: int | None = None,
) -> dict[str, object]:
    manifest = load_dataset_manifest(manifest_path)
    resolved = resolve_manifest_paths(manifest)
    output_dir = resolved["output_dir"]
    output_dir.mkdir(parents=True, exist_ok=True)

    problem_index = Path(problem_index_path) if problem_index_path else _default_problem_index_path(manifest_path)
    if not problem_index.exists():
        raise FileNotFoundError(f"Problem index not found: {problem_index}")

    arrays_dir = output_dir / "signal_dataset" / "arrays"
    arrays_dir.mkdir(parents=True, exist_ok=True)
    index_path = output_dir / "signal_dataset" / "signal_index.jsonl"
    summary_path = output_dir / "signal_dataset" / "signal_summary.json"

    signal_specs = list(manifest.signal_specs)
    channel_names = [spec.name for spec in signal_specs]
    waveform_cache: dict[tuple[int, str], tuple[pd.DataFrame, str]] = {}
    split_counts: Counter[str] = Counter()
    label_counts: Counter[str] = Counter()
    severity_counts: Counter[str] = Counter()
    written = 0

    with problem_index.open("r", encoding="utf-8") as source, index_path.open("w", encoding="utf-8") as handle:
        for line in source:
            if not line.strip():
                continue
            record = ProblemAnalysisRecord.model_validate(json.loads(line))
            primary_problem_id = record.primary_problem_id or "stable_segment"
            split = choose_split(f"case:{record.case_id}", eval_ratio=0.2)

            channels: list[np.ndarray] = []
            availability: list[float] = []
            waveform_paths = build_waveform_file_map(record.case_id, resolved["waveforms_dir"])
            for signal_spec in signal_specs:
                cache_key = (record.case_id, signal_spec.file_key)
                if cache_key not in waveform_cache:
                    path = waveform_paths[signal_spec.file_key]
                    if path.exists():
                        frame = pd.read_parquet(path)
                        waveform_cache[cache_key] = (frame, _find_time_column(frame))
                    else:
                        waveform_cache[cache_key] = (pd.DataFrame(), "time_sec")

                frame, time_col = waveform_cache[cache_key]
                if frame.empty:
                    channels.append(np.zeros(target_length, dtype=np.float32))
                    availability.append(0.0)
                    continue

                window = _slice_window(frame, time_col, record.start_s, record.end_s)
                values = _to_numeric_array(window, signal_spec.column)
                channels.append(_resample_signal(values, target_length))
                availability.append(1.0 if values.size else 0.0)

            array_path = arrays_dir / f"{record.segment_id}.npz"
            np.savez_compressed(
                array_path,
                channels=np.stack(channels, axis=0).astype(np.float32),
                availability=np.array(availability, dtype=np.float32),
                channel_names=np.array(channel_names, dtype=object),
            )

            dataset_record = SignalDatasetRecord(
                sample_id=f"{record.segment_id}:signal:{split}",
                case_id=record.case_id,
                segment_id=record.segment_id,
                split=split,
                primary_problem_id=primary_problem_id,
                primary_severity=record.problem_hypotheses[0].severity if record.problem_hypotheses else None,
                case_complications=list(record.case_complications),
                weak_labels=list(record.weak_labels),
                array_path=str(array_path),
                channel_names=channel_names,
                target_length=target_length,
                availability=availability,
            )
            handle.write(json.dumps(dataset_record.model_dump(mode="json"), ensure_ascii=False) + "\n")

            split_counts[split] += 1
            label_counts[primary_problem_id] += 1
            if dataset_record.primary_severity:
                severity_counts[dataset_record.primary_severity] += 1
            written += 1
            if limit_segments is not None and written >= limit_segments:
                break

    summary = {
        "dataset_id": manifest.dataset_id,
        "dataset_version": manifest.dataset_version,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "samples_written": written,
        "target_length": target_length,
        "channel_names": channel_names,
        "split_counts": dict(sorted(split_counts.items())),
        "primary_problem_counts": dict(sorted(label_counts.items())),
        "primary_severity_counts": dict(sorted(severity_counts.items())),
        "index_path": str(index_path),
        "arrays_dir": str(arrays_dir),
    }
    summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Export raw waveform windows for signal-model training.")
    parser.add_argument("--manifest", default=str(DEFAULT_MANIFEST_PATH), help="Path to dataset manifest YAML.")
    parser.add_argument("--problem-index", default=None, help="Optional path to problem_index.jsonl.")
    parser.add_argument("--target-length", type=int, default=256, help="Resampled points per signal channel.")
    parser.add_argument("--limit-segments", type=int, default=None, help="Optional cap on processed segments.")
    args = parser.parse_args()

    summary = build_signal_dataset(
        manifest_path=args.manifest,
        problem_index_path=args.problem_index,
        target_length=args.target_length,
        limit_segments=args.limit_segments,
    )
    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
