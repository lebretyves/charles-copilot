import json
import sys
from pathlib import Path


ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))


from learning.finetune.evaluation import (
    aggregate_record_metrics,
    comparison_delta,
    extract_first_json_object,
    load_evaluation_targets,
    score_prediction,
)
from learning.finetune.schemas import FineTuneChatSample
from learning.llm.schemas import ExplanationTarget, LLMConversationMessage


def _make_chat_sample(sample_id: str) -> FineTuneChatSample:
    expected = ExplanationTarget(
        situation="Instabilite hemodynamique probable.",
        risks=["Hypoperfusion tissulaire"],
        recommendations=["Verifier la courbe arterielle"],
        call_mar=True,
        call_mar_reason="Instabilite critique",
        confidence=0.9,
    )
    return FineTuneChatSample(
        sample_id=sample_id,
        split="eval",
        source_status="approved",
        target_origin="gold_approved",
        prompt_id="charles-perop-waveform-v2-local-train",
        prompt_version="2026-03-30",
        primary_problem_id="hemodynamic_instability",
        primary_severity="critical",
        case_complications=["major_blood_loss"],
        messages=[
            LLMConversationMessage(role="system", content="system prompt"),
            LLMConversationMessage(role="user", content="user prompt"),
            LLMConversationMessage(role="assistant", content=json.dumps(expected.model_dump(mode="json"))),
        ],
        assistant_json=json.dumps(expected.model_dump(mode="json")),
    )


def test_extract_first_json_object_ignores_surrounding_text():
    payload = 'Avant {"call_mar": true, "confidence": 0.7} apres'
    parsed, snippet = extract_first_json_object(payload)

    assert parsed == {"call_mar": True, "confidence": 0.7}
    assert snippet == '{"call_mar": true, "confidence": 0.7}'


def test_load_evaluation_targets_chat_uses_system_and_user_only(tmp_path):
    dataset_path = tmp_path / "finetune_chat_eval.jsonl"
    sample = _make_chat_sample("sample-1")
    dataset_path.write_text(json.dumps(sample.model_dump(mode="json"), ensure_ascii=False) + "\n", encoding="utf-8")

    targets = load_evaluation_targets(dataset_path, "chat")

    assert len(targets) == 1
    assert "[SYSTEM]" in targets[0].prompt
    assert "[USER]" in targets[0].prompt
    assert targets[0].prompt.rstrip().endswith("[ASSISTANT]")
    assert '"call_mar"' not in targets[0].prompt
    assert json.loads(targets[0].expected_output_json)["call_mar"] is True


def test_score_prediction_returns_perfect_match_for_identical_outputs():
    expected = ExplanationTarget(
        situation="Situation critique.",
        risks=["Risque A", "Risque B"],
        recommendations=["Reco A"],
        call_mar=True,
        call_mar_reason="Appel necessaire",
        confidence=0.8,
    )

    metrics = score_prediction(expected, expected, parse_ok=True, schema_ok=True)

    assert metrics["json_parse_ok"] == 1.0
    assert metrics["schema_valid"] == 1.0
    assert metrics["call_mar_accuracy"] == 1.0
    assert metrics["risks_f1"] == 1.0
    assert metrics["recommendations_f1"] == 1.0
    assert metrics["overall_score"] == 1.0


def test_aggregate_and_delta_metrics_are_computed():
    base_records = [
        {"metrics": {"json_parse_ok": 0.0, "schema_valid": 0.0, "call_mar_accuracy": 0.0, "confidence_score": 0.0, "situation_similarity": 0.0, "call_mar_reason_similarity": 0.0, "risks_f1": 0.0, "recommendations_f1": 0.0, "overall_score": 0.0}},
        {"metrics": {"json_parse_ok": 1.0, "schema_valid": 1.0, "call_mar_accuracy": 0.0, "confidence_score": 0.5, "situation_similarity": 0.5, "call_mar_reason_similarity": 0.5, "risks_f1": 0.5, "recommendations_f1": 0.5, "overall_score": 0.5}},
    ]
    adapter_records = [
        {"metrics": {"json_parse_ok": 1.0, "schema_valid": 1.0, "call_mar_accuracy": 1.0, "confidence_score": 1.0, "situation_similarity": 1.0, "call_mar_reason_similarity": 1.0, "risks_f1": 1.0, "recommendations_f1": 1.0, "overall_score": 1.0}},
        {"metrics": {"json_parse_ok": 1.0, "schema_valid": 1.0, "call_mar_accuracy": 1.0, "confidence_score": 1.0, "situation_similarity": 1.0, "call_mar_reason_similarity": 1.0, "risks_f1": 1.0, "recommendations_f1": 1.0, "overall_score": 1.0}},
    ]

    base_summary = aggregate_record_metrics(base_records)
    adapter_summary = aggregate_record_metrics(adapter_records)
    base_summary.update({"variant": "base", "records_path": "base.json"})
    adapter_summary.update({"variant": "adapter", "records_path": "adapter.json"})
    delta = comparison_delta(base_summary, adapter_summary)

    assert base_summary["samples_evaluated"] == 2
    assert adapter_summary["overall_score"] == 1.0
    assert delta["overall_score_delta"] > 0.0
    assert "variant_delta" not in delta
