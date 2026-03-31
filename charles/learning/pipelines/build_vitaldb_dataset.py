from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from learning.vitaldb import choose_diverse_case_files, load_case_contexts_with_complications
from learning.waveforms import (
    DEFAULT_MANIFEST_PATH,
    find_case_files,
    iter_case_segments,
    load_dataset_manifest,
    resolve_manifest_paths,
)


def build_segment_index(
    manifest_path: str | Path = DEFAULT_MANIFEST_PATH,
    limit_cases: int | None = None,
    max_segments_per_case: int | None = None,
    case_selection: str = "first",
    per_complication_cap: int = 20,
) -> dict[str, Any]:
    manifest = load_dataset_manifest(manifest_path)
    resolved = resolve_manifest_paths(manifest)
    output_dir = resolved["output_dir"]
    output_dir.mkdir(parents=True, exist_ok=True)

    all_cases = find_case_files(resolved["cases_dir"], manifest.case_glob)
    contexts = load_case_contexts_with_complications(
        resolved["metadata_csv"],
        manifest.context_columns,
        resolved.get("labs_csv"),
    )
    if case_selection == "diverse_complications":
        cases = choose_diverse_case_files(
            all_cases,
            contexts,
            limit_cases=limit_cases,
            per_complication_cap=per_complication_cap,
        )
    else:
        cases = all_cases[:limit_cases] if limit_cases is not None else all_cases
    segment_index_path = output_dir / "segment_index.jsonl"
    summary_path = output_dir / "dataset_summary.json"

    label_counts: Counter[str] = Counter()
    signal_counts: Counter[str] = Counter()
    case_complication_counts: Counter[str] = Counter()
    cases_with_segments = 0
    segments_written = 0

    with segment_index_path.open("w", encoding="utf-8") as handle:
        for case_path in cases:
            segments = iter_case_segments(
                case_path=case_path,
                waveforms_dir=resolved["waveforms_dir"],
                manifest=manifest,
                max_segments_per_case=max_segments_per_case,
            )
            if not segments:
                continue

            cases_with_segments += 1
            for segment in segments:
                if segment.case_id in contexts:
                    segment.case_context = contexts[segment.case_id]
                    segment.case_complications = list(contexts[segment.case_id].get("case_complications", []))
                for complication in segment.case_complications:
                    case_complication_counts[complication] += 1
                for label in segment.weak_labels:
                    label_counts[label] += 1
                for signal_name in segment.signals:
                    signal_counts[signal_name] += 1
                handle.write(json.dumps(segment.model_dump(mode="json"), ensure_ascii=False) + "\n")
                segments_written += 1

    summary = {
        "dataset_id": manifest.dataset_id,
        "dataset_version": manifest.dataset_version,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "cases_scanned": len(cases),
        "cases_with_segments": cases_with_segments,
        "segments_written": segments_written,
        "case_selection": case_selection,
        "label_counts": dict(sorted(label_counts.items())),
        "case_complication_counts": dict(sorted(case_complication_counts.items())),
        "signal_counts": dict(sorted(signal_counts.items())),
        "segment_index_path": str(segment_index_path),
    }
    summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the VitalDB waveform segment index for CHARLES.")
    parser.add_argument("--manifest", default=str(DEFAULT_MANIFEST_PATH), help="Path to dataset manifest YAML.")
    parser.add_argument("--limit-cases", type=int, default=None, help="Only scan the first N cases.")
    parser.add_argument(
        "--max-segments-per-case",
        type=int,
        default=None,
        help="Optional cap on how many segments are written per case.",
    )
    parser.add_argument(
        "--case-selection",
        default="first",
        choices=["first", "diverse_complications"],
        help="How to choose cases before segmentation.",
    )
    parser.add_argument(
        "--per-complication-cap",
        type=int,
        default=20,
        help="When using diverse_complications, max cases drawn per complication bucket.",
    )
    args = parser.parse_args()

    summary = build_segment_index(
        manifest_path=args.manifest,
        limit_cases=args.limit_cases,
        max_segments_per_case=args.max_segments_per_case,
        case_selection=args.case_selection,
        per_complication_cap=args.per_complication_cap,
    )
    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
