from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any, Literal

from learning.finetune.schemas import FineTuneChatSample, FineTuneInstructionSample
from learning.llm.schemas import ExplanationTarget


def normalize_text(value: str | None) -> str:
    if not value:
        return ""
    text = unicodedata.normalize("NFKD", value)
    text = "".join(char for char in text if not unicodedata.combining(char))
    text = text.lower()
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def sequence_similarity(left: str | None, right: str | None) -> float:
    a = normalize_text(left)
    b = normalize_text(right)
    if not a and not b:
        return 1.0
    return SequenceMatcher(a=a, b=b).ratio()


def list_f1_score(predicted: list[str], expected: list[str]) -> float:
    predicted_set = {normalize_text(item) for item in predicted if normalize_text(item)}
    expected_set = {normalize_text(item) for item in expected if normalize_text(item)}
    if not predicted_set and not expected_set:
        return 1.0
    if not predicted_set or not expected_set:
        return 0.0
    overlap = len(predicted_set.intersection(expected_set))
    precision = overlap / len(predicted_set)
    recall = overlap / len(expected_set)
    if precision + recall == 0:
        return 0.0
    return 2 * precision * recall / (precision + recall)


def extract_first_json_object(raw_text: str) -> tuple[dict[str, Any] | None, str | None]:
    start = raw_text.find("{")
    if start < 0:
        return None, None

    depth = 0
    in_string = False
    escaped = False
    for index in range(start, len(raw_text)):
        char = raw_text[index]
        if escaped:
            escaped = False
            continue
        if char == "\\":
            escaped = True
            continue
        if char == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                candidate = raw_text[start : index + 1]
                try:
                    return json.loads(candidate), candidate
                except json.JSONDecodeError:
                    return None, candidate
    return None, None


@dataclass
class EvaluationTarget:
    sample_id: str
    prompt: str
    expected_output: ExplanationTarget
    expected_output_json: str
    primary_problem_id: str | None
    primary_severity: str | None
    case_complications: list[str]


def _render_chat_prompt(messages: list[dict[str, str]] | list[Any]) -> str:
    blocks: list[str] = []
    for message in messages:
        role = getattr(message, "role", None) if not isinstance(message, dict) else message["role"]
        content = getattr(message, "content", None) if not isinstance(message, dict) else message["content"]
        if role == "assistant":
            continue
        blocks.append(f"[{str(role).strip().upper()}]\n{str(content).strip()}")
    blocks.append("[ASSISTANT]\n")
    return "\n\n".join(blocks)


def _render_instruction_prompt(sample: FineTuneInstructionSample) -> str:
    return "\n\n".join(
        [
            f"[SYSTEM]\n{sample.system.strip()}",
            f"[USER]\n{sample.instruction.strip()}",
            "[ASSISTANT]\n",
        ]
    )


def load_evaluation_targets(path: str | Path, dataset_format: Literal["chat", "instruction"]) -> list[EvaluationTarget]:
    source = Path(path)
    if not source.exists():
        raise FileNotFoundError(f"Evaluation dataset not found: {source}")

    targets: list[EvaluationTarget] = []
    for line in source.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        payload = json.loads(line)
        if dataset_format == "chat":
            sample = FineTuneChatSample.model_validate(payload)
            expected = ExplanationTarget.model_validate_json(sample.assistant_json)
            prompt = _render_chat_prompt(sample.messages)
        elif dataset_format == "instruction":
            sample = FineTuneInstructionSample.model_validate(payload)
            expected = ExplanationTarget.model_validate_json(sample.output_json)
            prompt = _render_instruction_prompt(sample)
        else:  # pragma: no cover - guarded by CLI/config
            raise ValueError(f"Unsupported dataset format: {dataset_format}")

        targets.append(
            EvaluationTarget(
                sample_id=sample.sample_id,
                prompt=prompt,
                expected_output=expected,
                expected_output_json=sample.assistant_json if dataset_format == "chat" else sample.output_json,
                primary_problem_id=sample.primary_problem_id,
                primary_severity=sample.primary_severity,
                case_complications=list(sample.case_complications),
            )
        )
    return targets


def score_prediction(
    prediction: ExplanationTarget | None,
    expected: ExplanationTarget,
    *,
    parse_ok: bool,
    schema_ok: bool,
) -> dict[str, float]:
    metrics: dict[str, float] = {
        "json_parse_ok": 1.0 if parse_ok else 0.0,
        "schema_valid": 1.0 if schema_ok else 0.0,
        "call_mar_accuracy": 0.0,
        "confidence_score": 0.0,
        "situation_similarity": 0.0,
        "call_mar_reason_similarity": 0.0,
        "risks_f1": 0.0,
        "recommendations_f1": 0.0,
        "overall_score": 0.0,
    }
    if prediction is None:
        return metrics

    metrics["call_mar_accuracy"] = 1.0 if prediction.call_mar == expected.call_mar else 0.0
    metrics["confidence_score"] = max(0.0, 1.0 - abs(prediction.confidence - expected.confidence))
    metrics["situation_similarity"] = sequence_similarity(prediction.situation, expected.situation)
    metrics["call_mar_reason_similarity"] = sequence_similarity(prediction.call_mar_reason, expected.call_mar_reason)
    metrics["risks_f1"] = list_f1_score(prediction.risks, expected.risks)
    metrics["recommendations_f1"] = list_f1_score(prediction.recommendations, expected.recommendations)

    weighted_components = [
        metrics["json_parse_ok"],
        metrics["schema_valid"],
        metrics["call_mar_accuracy"],
        metrics["confidence_score"],
        metrics["situation_similarity"],
        metrics["call_mar_reason_similarity"],
        metrics["risks_f1"],
        metrics["recommendations_f1"],
    ]
    metrics["overall_score"] = sum(weighted_components) / len(weighted_components)
    return metrics


def aggregate_record_metrics(records: list[dict[str, Any]]) -> dict[str, Any]:
    totals = len(records)
    metric_names = [
        "json_parse_ok",
        "schema_valid",
        "call_mar_accuracy",
        "confidence_score",
        "situation_similarity",
        "call_mar_reason_similarity",
        "risks_f1",
        "recommendations_f1",
        "overall_score",
    ]
    averages = {
        metric_name: (sum(record["metrics"][metric_name] for record in records) / totals if totals else 0.0)
        for metric_name in metric_names
    }
    return {
        "samples_evaluated": totals,
        **averages,
    }


def comparison_delta(base_summary: dict[str, Any], adapter_summary: dict[str, Any]) -> dict[str, float]:
    deltas: dict[str, float] = {}
    for key, value in adapter_summary.items():
        if key == "samples_evaluated":
            continue
        if not isinstance(value, (int, float)):
            continue
        base_value = base_summary.get(key, 0.0)
        if not isinstance(base_value, (int, float)):
            continue
        deltas[f"{key}_delta"] = round(float(value) - float(base_value), 6)
    return deltas
