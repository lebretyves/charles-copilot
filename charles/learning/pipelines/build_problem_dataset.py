from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from learning.problems import infer_problem_record
from learning.waveforms.features import CaseFrameCache, extract_feature_record
from learning.waveforms.schemas import SegmentRecord
from learning.waveforms.segmenter import DEFAULT_MANIFEST_PATH, load_dataset_manifest, resolve_manifest_paths


def _default_segment_index_path(manifest_path: str | Path) -> Path:
    manifest = load_dataset_manifest(manifest_path)
    resolved = resolve_manifest_paths(manifest)
    return resolved["output_dir"] / "segment_index.jsonl"


def build_problem_dataset(
    manifest_path: str | Path = DEFAULT_MANIFEST_PATH,
    segment_index_path: str | Path | None = None,
    limit_segments: int | None = None,
) -> dict[str, object]:
    manifest = load_dataset_manifest(manifest_path)
    resolved = resolve_manifest_paths(manifest)
    output_dir = resolved["output_dir"]
    output_dir.mkdir(parents=True, exist_ok=True)

    segment_index = Path(segment_index_path) if segment_index_path else _default_segment_index_path(manifest_path)
    if not segment_index.exists():
        raise FileNotFoundError(f"Segment index not found: {segment_index}")

    feature_index_path = output_dir / "feature_index.jsonl"
    problem_index_path = output_dir / "problem_index.jsonl"
    summary_path = output_dir / "problem_summary.json"

    cache = CaseFrameCache(manifest)
    primary_problem_counts: Counter[str] = Counter()
    severity_counts: Counter[str] = Counter()
    case_complication_counts: Counter[str] = Counter()
    processed_segments = 0

    with (
        segment_index.open("r", encoding="utf-8") as source,
        feature_index_path.open("w", encoding="utf-8") as feature_handle,
        problem_index_path.open("w", encoding="utf-8") as problem_handle,
    ):
        for line in source:
            if not line.strip():
                continue
            segment = SegmentRecord.model_validate(json.loads(line))
            feature_record = extract_feature_record(segment, manifest, cache=cache)
            problem_record = infer_problem_record(feature_record)

            feature_handle.write(json.dumps(feature_record.model_dump(mode="json"), ensure_ascii=False) + "\n")
            problem_handle.write(json.dumps(problem_record.model_dump(mode="json"), ensure_ascii=False) + "\n")

            if problem_record.primary_problem_id:
                primary_problem_counts[problem_record.primary_problem_id] += 1
            if problem_record.problem_hypotheses:
                severity_counts[problem_record.problem_hypotheses[0].severity] += 1
            for complication in problem_record.case_complications:
                case_complication_counts[complication] += 1

            processed_segments += 1
            if limit_segments is not None and processed_segments >= limit_segments:
                break

    summary = {
        "dataset_id": manifest.dataset_id,
        "dataset_version": manifest.dataset_version,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "segments_processed": processed_segments,
        "primary_problem_counts": dict(sorted(primary_problem_counts.items())),
        "primary_severity_counts": dict(sorted(severity_counts.items())),
        "case_complication_counts": dict(sorted(case_complication_counts.items())),
        "feature_index_path": str(feature_index_path),
        "problem_index_path": str(problem_index_path),
    }
    summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Build feature and problem datasets from the VitalDB segment index.")
    parser.add_argument("--manifest", default=str(DEFAULT_MANIFEST_PATH), help="Path to dataset manifest YAML.")
    parser.add_argument("--segment-index", default=None, help="Optional path to segment_index.jsonl.")
    parser.add_argument("--limit-segments", type=int, default=None, help="Optional cap on processed segments.")
    args = parser.parse_args()

    summary = build_problem_dataset(
        manifest_path=args.manifest,
        segment_index_path=args.segment_index,
        limit_segments=args.limit_segments,
    )
    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
