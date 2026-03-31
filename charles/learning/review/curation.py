from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

from learning.llm.schemas import LLMTrainingSample
from learning.review.schemas import ReviewTask


FOCUS_GROUP_RULES: dict[str, dict[str, set[str]]] = {
    "respiratory": {
        "problem_ids": {"respiratory_instability", "airway_mechanics_issue"},
        "complications": {"intraop_hypercapnia_lab"},
    },
    "airway": {
        "problem_ids": {"airway_mechanics_issue"},
        "complications": {"difficult_airway_proxy"},
    },
    "metabolic": {
        "problem_ids": {"metabolic_derangement_context"},
        "complications": {
            "intraop_acidemia_lab",
            "severe_intraop_acidemia_lab",
            "intraop_hyperglycemia_lab",
            "intraop_hyperkalemia_lab",
            "intraop_hypokalemia_lab",
            "renal_dysfunction_lab",
        },
    },
}


def infer_focus_groups(sample: LLMTrainingSample) -> list[str]:
    source_problem_ids = set(sample.source_problem_ids)
    complications = set(sample.case_complications)
    matched: list[str] = []
    for focus_name, rules in FOCUS_GROUP_RULES.items():
        if source_problem_ids.intersection(rules["problem_ids"]) or complications.intersection(rules["complications"]):
            matched.append(focus_name)
    return matched


def _focus_rank(sample: LLMTrainingSample, focus_name: str) -> tuple[int, int, int, str]:
    rules = FOCUS_GROUP_RULES[focus_name]
    primary_match = int((sample.primary_problem_id or "") in rules["problem_ids"])
    source_match = sum(1 for item in sample.source_problem_ids if item in rules["problem_ids"])
    complication_match = sum(1 for item in sample.case_complications if item in rules["complications"])
    return (-primary_match, -source_match, -complication_match, sample.sample_id)


def load_reference_samples(path: str | Path) -> list[LLMTrainingSample]:
    source = Path(path)
    if not source.exists():
        raise FileNotFoundError(f"Reference dataset not found: {source}")

    samples: list[LLMTrainingSample] = []
    for line in source.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        samples.append(LLMTrainingSample.model_validate(json.loads(line)))
    return samples


def materialize_review_task(sample: LLMTrainingSample) -> ReviewTask:
    tags: list[str] = []
    priority = "normal"
    tags.append(f"input_{sample.input_variant}")
    if sample.expected_output.call_mar:
        tags.append("call_mar")
        priority = "high"
    if sample.primary_severity == "critical":
        tags.append("critical")
        priority = "high"
    if sample.primary_problem_id:
        tags.append(sample.primary_problem_id)
    for focus_name in infer_focus_groups(sample):
        tags.append(f"focus_{focus_name}")

    return ReviewTask(
        sample=sample,
        review_priority=priority,
        review_tags=tags,
    )


def choose_review_tasks(
    samples: list[LLMTrainingSample],
    *,
    per_problem_limit: int = 20,
    per_focus_limit: int = 6,
    limit_total: int | None = None,
) -> list[ReviewTask]:
    ordered_samples = sorted(samples, key=lambda item: (item.primary_problem_id or "", item.split, item.sample_id))
    grouped: dict[tuple[str | None, str], list[LLMTrainingSample]] = defaultdict(list)
    for sample in ordered_samples:
        grouped[(sample.primary_problem_id, sample.split)].append(sample)

    selected: list[ReviewTask] = []
    selected_ids: set[str] = set()

    if per_focus_limit > 0:
        for focus_name in FOCUS_GROUP_RULES:
            focus_bucket = [
                sample
                for sample in ordered_samples
                if sample.sample_id not in selected_ids and focus_name in infer_focus_groups(sample)
            ]
            focus_bucket.sort(key=lambda item: _focus_rank(item, focus_name))
            picked = 0
            for sample in focus_bucket:
                selected.append(materialize_review_task(sample))
                selected_ids.add(sample.sample_id)
                picked += 1
                if limit_total is not None and len(selected) >= limit_total:
                    return selected
                if picked >= per_focus_limit:
                    break

    for key in sorted(grouped, key=lambda item: ((item[0] or ""), item[1])):
        bucket = grouped[key]
        picked = 0
        for sample in bucket:
            if sample.sample_id in selected_ids:
                continue
            selected.append(materialize_review_task(sample))
            selected_ids.add(sample.sample_id)
            picked += 1
            if limit_total is not None and len(selected) >= limit_total:
                return selected
            if picked >= per_problem_limit:
                break
    return selected
