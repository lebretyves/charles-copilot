import json
import sys
from pathlib import Path


ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))


from learning.pipelines import evaluate_finetune_run as pipeline


def _write_config(tmp_path: Path) -> Path:
    run_dir = tmp_path / "run"
    config = {
        "run_id": "test-run",
        "created_at": "2026-03-30T00:00:00+00:00",
        "dataset": {
            "dataset_id": "dataset",
            "dataset_version": "v1",
            "dataset_format": "chat",
            "source_train_path": str(tmp_path / "train.jsonl"),
            "source_eval_path": str(tmp_path / "eval.jsonl"),
            "prepared_train_path": str(tmp_path / "prepared_train.jsonl"),
            "prepared_eval_path": str(tmp_path / "prepared_eval.jsonl"),
        },
        "model": {
            "base_model_path": str(tmp_path / "model"),
            "tokenizer_path": str(tmp_path / "tokenizer"),
        },
        "artifacts": {
            "run_dir": str(run_dir),
            "output_dir": str(run_dir / "output"),
            "logging_dir": str(run_dir / "logs"),
            "adapter_output_dir": str(run_dir / "adapter"),
            "environment_report_path": str(run_dir / "environment_report.json"),
            "training_summary_path": str(run_dir / "training_summary.json"),
        },
    }
    config_path = tmp_path / "run_config.json"
    config_path.write_text(json.dumps(config), encoding="utf-8")
    return config_path


def test_evaluate_finetune_run_can_skip_base_and_emit_adapter_only_summary(tmp_path, monkeypatch):
    config_path = _write_config(tmp_path)
    calls = []

    monkeypatch.setattr(pipeline, "load_evaluation_targets", lambda *_args, **_kwargs: ["sample-a", "sample-b"])
    monkeypatch.setattr(pipeline, "_load_generation_stack", lambda _config: ("torch", "tok", "base-model", type("FakePeft", (), {"from_pretrained": staticmethod(lambda base, path: f"adapter:{base}:{path}")})))

    def fake_evaluate_variant(*, variant_name, targets, torch_module, tokenizer, model, max_new_tokens, run_dir):
        calls.append({"variant": variant_name, "targets": list(targets), "model": model})
        return {
            "variant": variant_name,
            "samples_evaluated": len(targets),
            "overall_score": 0.75 if variant_name == "adapter" else 0.25,
            "records_path": str(run_dir / "artifacts" / "evaluation" / f"{variant_name}_records.jsonl"),
        }

    monkeypatch.setattr(pipeline, "_evaluate_variant", fake_evaluate_variant)

    summary = pipeline.evaluate_finetune_run(config_path, variants="adapter", max_samples=1)

    assert [call["variant"] for call in calls] == ["adapter"]
    assert calls[0]["targets"] == ["sample-a"]
    assert summary["base"] is None
    assert summary["adapter"]["overall_score"] == 0.75
    assert summary["delta"] is None
    assert summary["variants"] == "adapter"


def test_evaluate_finetune_run_computes_delta_when_both_variants_run(tmp_path, monkeypatch):
    config_path = _write_config(tmp_path)

    monkeypatch.setattr(pipeline, "load_evaluation_targets", lambda *_args, **_kwargs: ["sample-a"])
    monkeypatch.setattr(pipeline, "_load_generation_stack", lambda _config: ("torch", "tok", "base-model", type("FakePeft", (), {"from_pretrained": staticmethod(lambda base, path: f"adapter:{base}:{path}")})))

    def fake_evaluate_variant(*, variant_name, targets, torch_module, tokenizer, model, max_new_tokens, run_dir):
        return {
            "variant": variant_name,
            "samples_evaluated": len(targets),
            "json_parse_ok": 0.2 if variant_name == "base" else 0.8,
            "schema_valid": 0.2 if variant_name == "base" else 0.8,
            "call_mar_accuracy": 0.2 if variant_name == "base" else 0.8,
            "confidence_score": 0.2 if variant_name == "base" else 0.8,
            "situation_similarity": 0.2 if variant_name == "base" else 0.8,
            "call_mar_reason_similarity": 0.2 if variant_name == "base" else 0.8,
            "risks_f1": 0.2 if variant_name == "base" else 0.8,
            "recommendations_f1": 0.2 if variant_name == "base" else 0.8,
            "overall_score": 0.2 if variant_name == "base" else 0.8,
            "records_path": str(run_dir / "artifacts" / "evaluation" / f"{variant_name}_records.jsonl"),
        }

    monkeypatch.setattr(pipeline, "_evaluate_variant", fake_evaluate_variant)

    summary = pipeline.evaluate_finetune_run(config_path, variants="both")

    assert summary["base"]["overall_score"] == 0.2
    assert summary["adapter"]["overall_score"] == 0.8
    assert summary["delta"]["overall_score_delta"] == 0.6
