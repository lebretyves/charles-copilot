from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from learning.llm import (
    INPUT_VARIANTS,
    PROMPT_ID,
    PROMPT_VERSION,
    SYSTEM_PROMPT,
    LLMConversationMessage,
    LLMTrainingSample,
    build_reference_target,
    build_prompt_variants,
    choose_split,
)
from learning.problems.schemas import ProblemAnalysisRecord
from learning.waveforms.segmenter import DEFAULT_MANIFEST_PATH, load_dataset_manifest, resolve_manifest_paths


def _default_problem_index_path(manifest_path: str | Path) -> Path:
    manifest = load_dataset_manifest(manifest_path)
    resolved = resolve_manifest_paths(manifest)
    return resolved["output_dir"] / "problem_index.jsonl"


def build_llm_dataset(
    manifest_path: str | Path = DEFAULT_MANIFEST_PATH,
    problem_index_path: str | Path | None = None,
    limit_samples: int | None = None,
    eval_ratio: float = 0.2,
) -> dict[str, object]:
    manifest = load_dataset_manifest(manifest_path)
    resolved = resolve_manifest_paths(manifest)
    output_dir = resolved["output_dir"]
    output_dir.mkdir(parents=True, exist_ok=True)

    problem_index = Path(problem_index_path) if problem_index_path else _default_problem_index_path(manifest_path)
    if not problem_index.exists():
        raise FileNotFoundError(f"Problem index not found: {problem_index}")

    train_path = output_dir / "llm_train.jsonl"
    eval_path = output_dir / "llm_eval.jsonl"
    reference_path = output_dir / "llm_reference.jsonl"
    summary_path = output_dir / "llm_summary.json"
    variant_paths = {
        variant: {
            "train": output_dir / f"llm_train_{variant}.jsonl",
            "eval": output_dir / f"llm_eval_{variant}.jsonl",
            "reference": output_dir / f"llm_reference_{variant}.jsonl",
        }
        for variant in INPUT_VARIANTS
    }

    split_counts: Counter[str] = Counter()
    problem_counts: Counter[str] = Counter()
    call_mar_counts: Counter[str] = Counter()
    case_complication_counts: Counter[str] = Counter()
    input_variant_counts: Counter[str] = Counter()
    written = 0
    processed_records = 0

    with problem_index.open("r", encoding="utf-8") as source:
        handles = {
            "train": train_path.open("w", encoding="utf-8"),
            "eval": eval_path.open("w", encoding="utf-8"),
            "reference": reference_path.open("w", encoding="utf-8"),
        }
        variant_handles = {
            variant: {
                split_name: path.open("w", encoding="utf-8")
                for split_name, path in mapping.items()
            }
            for variant, mapping in variant_paths.items()
        }
        try:
            for line in source:
                if not line.strip():
                    continue
                record = ProblemAnalysisRecord.model_validate(json.loads(line))
                split = choose_split(f"case:{record.case_id}", eval_ratio=eval_ratio)
                expected_output = build_reference_target(record)
                prompt_variants = build_prompt_variants(record)
                for input_variant, user_prompt, masked_signals in prompt_variants:
                    sample = LLMTrainingSample(
                        sample_id=f"{record.segment_id}:{input_variant}:{split}",
                        case_id=record.case_id,
                        segment_id=record.segment_id,
                        split=split,
                        input_variant=input_variant,
                        prompt_id=PROMPT_ID,
                        prompt_version=PROMPT_VERSION,
                        primary_problem_id=record.primary_problem_id,
                        primary_severity=record.problem_hypotheses[0].severity if record.problem_hypotheses else None,
                        source_problem_ids=[item.problem_id for item in record.problem_hypotheses],
                        case_complications=list(record.case_complications),
                        masked_signals=list(masked_signals),
                        system_prompt=SYSTEM_PROMPT,
                        user_prompt=user_prompt,
                        messages=[
                            LLMConversationMessage(role="system", content=SYSTEM_PROMPT),
                            LLMConversationMessage(role="user", content=user_prompt),
                        ],
                        expected_output=expected_output,
                    )

                    payload = json.dumps(sample.model_dump(mode="json"), ensure_ascii=False)
                    handles["reference"].write(payload + "\n")
                    variant_handles[input_variant]["reference"].write(payload + "\n")
                    if split == "eval":
                        handles["eval"].write(payload + "\n")
                        variant_handles[input_variant]["eval"].write(payload + "\n")
                    else:
                        handles["train"].write(payload + "\n")
                        variant_handles[input_variant]["train"].write(payload + "\n")

                    split_counts[split] += 1
                    input_variant_counts[input_variant] += 1
                    if record.primary_problem_id:
                        problem_counts[record.primary_problem_id] += 1
                    call_mar_counts["true" if expected_output.call_mar else "false"] += 1
                    for complication in record.case_complications:
                        case_complication_counts[complication] += 1

                    written += 1
                processed_records += 1
                if limit_samples is not None and processed_records >= limit_samples:
                    break
        finally:
            for handle in handles.values():
                handle.close()
            for mapping in variant_handles.values():
                for handle in mapping.values():
                    handle.close()

    summary = {
        "dataset_id": manifest.dataset_id,
        "dataset_version": manifest.dataset_version,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "prompt_id": PROMPT_ID,
        "prompt_version": PROMPT_VERSION,
        "samples_written": written,
        "split_counts": dict(sorted(split_counts.items())),
        "input_variant_counts": dict(sorted(input_variant_counts.items())),
        "primary_problem_counts": dict(sorted(problem_counts.items())),
        "case_complication_counts": dict(sorted(case_complication_counts.items())),
        "call_mar_counts": dict(sorted(call_mar_counts.items())),
        "train_path": str(train_path),
        "eval_path": str(eval_path),
        "reference_path": str(reference_path),
        "variant_paths": {
            variant: {kind: str(path) for kind, path in mapping.items()}
            for variant, mapping in variant_paths.items()
        },
    }
    summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the structured LLM train/eval dataset from problem outputs.")
    parser.add_argument("--manifest", default=str(DEFAULT_MANIFEST_PATH), help="Path to dataset manifest YAML.")
    parser.add_argument("--problem-index", default=None, help="Optional path to problem_index.jsonl.")
    parser.add_argument("--limit-samples", type=int, default=None, help="Optional cap on processed samples.")
    parser.add_argument("--eval-ratio", type=float, default=0.2, help="Fraction routed to eval split.")
    args = parser.parse_args()

    summary = build_llm_dataset(
        manifest_path=args.manifest,
        problem_index_path=args.problem_index,
        limit_samples=args.limit_samples,
        eval_ratio=args.eval_ratio,
    )
    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
