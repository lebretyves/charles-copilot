from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from learning.finetune import FineTuneChatSample, FineTuneInstructionSample
from learning.llm.schemas import ExplanationTarget, LLMConversationMessage
from learning.review.schemas import ReviewTask
from learning.waveforms.segmenter import DEFAULT_MANIFEST_PATH, load_dataset_manifest, resolve_manifest_paths


def _default_review_path(manifest_path: str | Path) -> Path:
    manifest = load_dataset_manifest(manifest_path)
    resolved = resolve_manifest_paths(manifest)
    return resolved["output_dir"] / "review_candidates.jsonl"


def _target_from_review(task: ReviewTask, export_mode: str) -> tuple[ExplanationTarget | None, str | None]:
    if task.review_status == "rejected":
        return None, None
    if task.review_status == "edited":
        if task.corrected_output is None:
            return None, None
        return task.corrected_output, "gold_edited"
    if task.review_status == "approved":
        return task.sample.expected_output, "gold_approved"
    if export_mode == "bootstrap_pending" and task.review_status == "pending":
        return task.sample.expected_output, "bootstrap_pending"
    return None, None


def export_finetune_dataset(
    manifest_path: str | Path = DEFAULT_MANIFEST_PATH,
    review_path: str | Path | None = None,
    export_mode: str = "gold_only",
) -> dict[str, object]:
    manifest = load_dataset_manifest(manifest_path)
    resolved = resolve_manifest_paths(manifest)
    output_dir = resolved["output_dir"]
    output_dir.mkdir(parents=True, exist_ok=True)

    source_path = Path(review_path) if review_path else _default_review_path(manifest_path)
    if not source_path.exists():
        raise FileNotFoundError(f"Review dataset not found: {source_path}")

    chat_train_path = output_dir / "finetune_chat_train.jsonl"
    chat_eval_path = output_dir / "finetune_chat_eval.jsonl"
    instruction_train_path = output_dir / "finetune_instruction_train.jsonl"
    instruction_eval_path = output_dir / "finetune_instruction_eval.jsonl"
    gold_reference_path = output_dir / "gold_reference.jsonl"
    summary_path = output_dir / "finetune_export_summary.json"

    split_counts: Counter[str] = Counter()
    status_counts: Counter[str] = Counter()
    origin_counts: Counter[str] = Counter()
    problem_counts: Counter[str] = Counter()
    variant_counts: Counter[str] = Counter()
    exported = 0
    skipped = 0

    with (
        source_path.open("r", encoding="utf-8") as source,
        chat_train_path.open("w", encoding="utf-8") as chat_train,
        chat_eval_path.open("w", encoding="utf-8") as chat_eval,
        instruction_train_path.open("w", encoding="utf-8") as instruction_train,
        instruction_eval_path.open("w", encoding="utf-8") as instruction_eval,
        gold_reference_path.open("w", encoding="utf-8") as gold_reference,
    ):
        for line in source:
            if not line.strip():
                continue
            task = ReviewTask.model_validate(json.loads(line))
            target, target_origin = _target_from_review(task, export_mode=export_mode)
            if target is None or target_origin is None:
                skipped += 1
                continue

            assistant_json = json.dumps(target.model_dump(mode="json"), ensure_ascii=False)
            chat_messages = [
                *task.sample.messages,
                LLMConversationMessage(role="assistant", content=assistant_json),
            ]

            chat_sample = FineTuneChatSample(
                sample_id=task.sample.sample_id,
                split=task.sample.split,
                input_variant=task.sample.input_variant,
                source_status=task.review_status,
                target_origin=target_origin,
                prompt_id=task.sample.prompt_id,
                prompt_version=task.sample.prompt_version,
                primary_problem_id=task.corrected_problem_id or task.sample.primary_problem_id,
                primary_severity=task.sample.primary_severity,
                case_complications=list(task.sample.case_complications),
                masked_signals=list(task.sample.masked_signals),
                messages=chat_messages,
                assistant_json=assistant_json,
            )
            instruction_sample = FineTuneInstructionSample(
                sample_id=task.sample.sample_id,
                split=task.sample.split,
                input_variant=task.sample.input_variant,
                source_status=task.review_status,
                target_origin=target_origin,
                prompt_id=task.sample.prompt_id,
                prompt_version=task.sample.prompt_version,
                primary_problem_id=task.corrected_problem_id or task.sample.primary_problem_id,
                primary_severity=task.sample.primary_severity,
                case_complications=list(task.sample.case_complications),
                masked_signals=list(task.sample.masked_signals),
                system=task.sample.system_prompt,
                instruction=task.sample.user_prompt,
                output_json=assistant_json,
            )

            payload_chat = json.dumps(chat_sample.model_dump(mode="json"), ensure_ascii=False)
            payload_instruction = json.dumps(instruction_sample.model_dump(mode="json"), ensure_ascii=False)
            payload_gold = json.dumps(
                {
                    "sample_id": task.sample.sample_id,
                    "split": task.sample.split,
                    "input_variant": task.sample.input_variant,
                    "review_status": task.review_status,
                    "target_origin": target_origin,
                    "expected_output": target.model_dump(mode="json"),
                },
                ensure_ascii=False,
            )

            if task.sample.split == "eval":
                chat_eval.write(payload_chat + "\n")
                instruction_eval.write(payload_instruction + "\n")
            else:
                chat_train.write(payload_chat + "\n")
                instruction_train.write(payload_instruction + "\n")
            gold_reference.write(payload_gold + "\n")

            split_counts[task.sample.split] += 1
            status_counts[task.review_status] += 1
            origin_counts[target_origin] += 1
            if chat_sample.primary_problem_id:
                problem_counts[chat_sample.primary_problem_id] += 1
            variant_counts[chat_sample.input_variant] += 1
            exported += 1

    summary = {
        "dataset_id": manifest.dataset_id,
        "dataset_version": manifest.dataset_version,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "export_mode": export_mode,
        "source_review_path": str(source_path),
        "samples_exported": exported,
        "samples_skipped": skipped,
        "split_counts": dict(sorted(split_counts.items())),
        "status_counts": dict(sorted(status_counts.items())),
        "origin_counts": dict(sorted(origin_counts.items())),
        "primary_problem_counts": dict(sorted(problem_counts.items())),
        "input_variant_counts": dict(sorted(variant_counts.items())),
        "chat_train_path": str(chat_train_path),
        "chat_eval_path": str(chat_eval_path),
        "instruction_train_path": str(instruction_train_path),
        "instruction_eval_path": str(instruction_eval_path),
        "gold_reference_path": str(gold_reference_path),
    }
    summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Export reviewed CHARLES samples to local fine-tuning formats.")
    parser.add_argument("--manifest", default=str(DEFAULT_MANIFEST_PATH), help="Path to dataset manifest YAML.")
    parser.add_argument("--review-path", default=None, help="Optional path to review_candidates.jsonl.")
    parser.add_argument(
        "--export-mode",
        default="gold_only",
        choices=["gold_only", "bootstrap_pending"],
        help="gold_only exports only approved/edited samples; bootstrap_pending also exports pending ones.",
    )
    args = parser.parse_args()

    summary = export_finetune_dataset(
        manifest_path=args.manifest,
        review_path=args.review_path,
        export_mode=args.export_mode,
    )
    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
