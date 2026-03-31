from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from learning.review import choose_review_tasks, load_reference_samples
from learning.waveforms.segmenter import DEFAULT_MANIFEST_PATH, load_dataset_manifest, resolve_manifest_paths


def _default_reference_path(manifest_path: str | Path) -> Path:
    manifest = load_dataset_manifest(manifest_path)
    resolved = resolve_manifest_paths(manifest)
    return resolved["output_dir"] / "llm_reference.jsonl"


def build_review_pack(
    manifest_path: str | Path = DEFAULT_MANIFEST_PATH,
    reference_path: str | Path | None = None,
    per_problem_limit: int = 20,
    per_focus_limit: int = 6,
    limit_total: int | None = None,
) -> dict[str, object]:
    manifest = load_dataset_manifest(manifest_path)
    resolved = resolve_manifest_paths(manifest)
    output_dir = resolved["output_dir"]
    output_dir.mkdir(parents=True, exist_ok=True)

    source_path = Path(reference_path) if reference_path else _default_reference_path(manifest_path)
    samples = load_reference_samples(source_path)
    review_tasks = choose_review_tasks(
        samples,
        per_problem_limit=per_problem_limit,
        per_focus_limit=per_focus_limit,
        limit_total=limit_total,
    )

    review_path = output_dir / "review_candidates.jsonl"
    summary_path = output_dir / "review_summary.json"
    instructions_path = output_dir / "review_instructions.md"

    status_counts: Counter[str] = Counter()
    priority_counts: Counter[str] = Counter()
    problem_counts: Counter[str] = Counter()
    split_counts: Counter[str] = Counter()
    focus_counts: Counter[str] = Counter()
    variant_counts: Counter[str] = Counter()

    with review_path.open("w", encoding="utf-8") as handle:
        for task in review_tasks:
            handle.write(json.dumps(task.model_dump(mode="json"), ensure_ascii=False) + "\n")
            status_counts[task.review_status] += 1
            priority_counts[task.review_priority] += 1
            split_counts[task.sample.split] += 1
            variant_counts[task.sample.input_variant] += 1
            if task.sample.primary_problem_id:
                problem_counts[task.sample.primary_problem_id] += 1
            for tag in task.review_tags:
                if tag.startswith("focus_"):
                    focus_counts[tag.removeprefix("focus_")] += 1

    instructions_path.write_text(
        "\n".join(
            [
                "# Review Pack",
                "",
                "Open `review_candidates.jsonl` and review each task.",
                "",
                "For each item:",
                "- keep `review_status` to `pending` until reviewed",
                "- set `review_status` to `approved`, `edited`, or `rejected`",
                "- fill `reviewer` and `review_notes`",
                "- if edited, provide `corrected_output`",
                "- optionally set `corrected_problem_id` if the baseline problem is wrong",
                "",
                "Goal:",
                "- build a small but trustworthy gold set before any local fine-tuning run",
            ]
        ),
        encoding="utf-8",
    )

    summary = {
        "dataset_id": manifest.dataset_id,
        "dataset_version": manifest.dataset_version,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_reference_path": str(source_path),
        "review_candidates_written": len(review_tasks),
        "status_counts": dict(sorted(status_counts.items())),
        "priority_counts": dict(sorted(priority_counts.items())),
        "problem_counts": dict(sorted(problem_counts.items())),
        "focus_counts": dict(sorted(focus_counts.items())),
        "split_counts": dict(sorted(split_counts.items())),
        "input_variant_counts": dict(sorted(variant_counts.items())),
        "review_path": str(review_path),
        "instructions_path": str(instructions_path),
    }
    summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a review/gold candidate pack from the LLM reference dataset.")
    parser.add_argument("--manifest", default=str(DEFAULT_MANIFEST_PATH), help="Path to dataset manifest YAML.")
    parser.add_argument("--reference-path", default=None, help="Optional path to llm_reference.jsonl.")
    parser.add_argument("--per-problem-limit", type=int, default=20, help="Max samples per problem and split.")
    parser.add_argument(
        "--per-focus-limit",
        type=int,
        default=6,
        help="Max samples reserved per focus family (respiratory, airway, metabolic).",
    )
    parser.add_argument("--limit-total", type=int, default=None, help="Optional overall cap.")
    args = parser.parse_args()

    summary = build_review_pack(
        manifest_path=args.manifest,
        reference_path=args.reference_path,
        per_problem_limit=args.per_problem_limit,
        per_focus_limit=args.per_focus_limit,
        limit_total=args.limit_total,
    )
    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
