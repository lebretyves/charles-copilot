import json
import sys
from pathlib import Path


ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))


from learning.finetune.runtime import prepare_text_samples
from learning.llm.schemas import ExplanationTarget, LLMConversationMessage
from learning.finetune.schemas import FineTuneChatSample, FineTuneInstructionSample
from learning.pipelines.build_finetune_run import build_finetune_run


def _write_manifest(tmp_path: Path, output_dir: Path) -> Path:
    manifest_path = tmp_path / "manifest.yaml"
    manifest_path.write_text(
        "\n".join(
            [
                "dataset_id: test_vitaldb",
                'dataset_version: "v1"',
                "description: test dataset",
                "source:",
                "  name: VitalDB",
                "  license: test",
                "  citation: test",
                "paths:",
                f"  metadata_csv: {(tmp_path / 'clinical_metadata.csv').as_posix()}",
                f"  cases_dir: {(tmp_path / 'cases').as_posix()}",
                f"  waveforms_dir: {(tmp_path / 'waveforms').as_posix()}",
                f"  output_dir: {output_dir.as_posix()}",
                "signal_specs:",
                "  - name: ecg",
                "    file_key: 500hz",
                "    column: SNUADC/ECG_II",
                "    sample_rate_hz: 2",
                "segment_spec:",
                "  window_seconds: 2.0",
                "  stride_seconds: 1.0",
                "  min_signal_coverage: 0.5",
                "  min_required_signals: 1",
            ]
        ),
        encoding="utf-8",
    )
    (tmp_path / "clinical_metadata.csv").write_text("caseid\n1\n", encoding="utf-8")
    (tmp_path / "cases").mkdir(exist_ok=True)
    (tmp_path / "waveforms").mkdir(exist_ok=True)
    return manifest_path


def _make_chat_sample(sample_id: str, split: str = "train") -> FineTuneChatSample:
    return FineTuneChatSample(
        sample_id=sample_id,
        split=split,
        source_status="pending",
        target_origin="bootstrap_pending",
        prompt_id="charles-perop-waveform-v2-local-train",
        prompt_version="2026-03-30",
        primary_problem_id="hemodynamic_instability",
        primary_severity="critical",
        case_complications=["major_blood_loss"],
        messages=[
            LLMConversationMessage(role="system", content="system prompt"),
            LLMConversationMessage(role="user", content="user prompt"),
        ],
        assistant_json=json.dumps(
            ExplanationTarget(
                situation="Instabilite hemodynamique probable.",
                risks=["Hypoperfusion"],
                recommendations=["Verifier la courbe"],
                call_mar=True,
                call_mar_reason="Instabilite critique",
                confidence=0.9,
            ).model_dump(mode="json"),
            ensure_ascii=False,
        ),
    )


def _make_instruction_sample(sample_id: str, split: str = "train") -> FineTuneInstructionSample:
    return FineTuneInstructionSample(
        sample_id=sample_id,
        split=split,
        source_status="pending",
        target_origin="bootstrap_pending",
        prompt_id="charles-perop-waveform-v2-local-train",
        prompt_version="2026-03-30",
        primary_problem_id="metabolic_derangement_context",
        primary_severity="critical",
        case_complications=["intraop_acidemia_lab"],
        system="system prompt",
        instruction="user prompt",
        output_json=json.dumps(
            {
                "situation": "Contexte metabolique critique.",
                "risks": ["Acidose"],
                "recommendations": ["Verifier les gaz"],
                "call_mar": True,
                "confidence": 0.85,
            },
            ensure_ascii=False,
        ),
    )


def test_prepare_text_samples_renders_chat_blocks(tmp_path):
    dataset_path = tmp_path / "finetune_chat_train.jsonl"
    dataset_path.write_text(
        json.dumps(_make_chat_sample("sample-chat:train").model_dump(mode="json"), ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    prepared = prepare_text_samples(dataset_path, "chat")

    assert len(prepared) == 1
    assert "[SYSTEM]" in prepared[0].text
    assert "[USER]" in prepared[0].text
    assert prepared[0].text.count("[ASSISTANT]") == 1


def test_build_finetune_run_creates_launch_ready_pack_with_fake_local_model(tmp_path):
    output_dir = tmp_path / "exports"
    output_dir.mkdir()
    manifest_path = _write_manifest(tmp_path, output_dir)

    train_path = output_dir / "finetune_chat_train.jsonl"
    eval_path = output_dir / "finetune_chat_eval.jsonl"
    train_path.write_text(
        json.dumps(_make_chat_sample("sample-train:train").model_dump(mode="json"), ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    eval_path.write_text(
        json.dumps(_make_chat_sample("sample-eval:eval", split="eval").model_dump(mode="json"), ensure_ascii=False)
        + "\n",
        encoding="utf-8",
    )
    (output_dir / "finetune_export_summary.json").write_text("{}", encoding="utf-8")

    model_dir = tmp_path / "models" / "meditron-7b-transformers"
    model_dir.mkdir(parents=True)
    (model_dir / "config.json").write_text("{}", encoding="utf-8")
    (model_dir / "tokenizer.json").write_text("{}", encoding="utf-8")

    summary = build_finetune_run(
        manifest_path=manifest_path,
        dataset_format="chat",
        run_name="test_run_ready",
        base_model_path=str(model_dir),
    )

    run_dir = output_dir / "runs" / "test_run_ready"
    assert Path(summary["prepared_train_path"]).exists()
    assert Path(summary["config_path"]).exists()
    assert Path(summary["environment_report_path"]).exists()
    assert (run_dir / "run_local.ps1").exists()
    assert (run_dir / "README.md").exists()

    environment = json.loads(Path(summary["environment_report_path"]).read_text(encoding="utf-8"))
    assert environment["model_checks"]["config_json_exists"] is True
    assert "tokenizer.json" in environment["model_checks"]["tokenizer_files_present"]
    assert "Missing local base model directory." not in environment["blocking_issues"]


def test_build_finetune_run_reports_missing_model_blockers(tmp_path):
    output_dir = tmp_path / "exports"
    output_dir.mkdir()
    manifest_path = _write_manifest(tmp_path, output_dir)

    train_path = output_dir / "finetune_instruction_train.jsonl"
    eval_path = output_dir / "finetune_instruction_eval.jsonl"
    train_path.write_text(
        json.dumps(_make_instruction_sample("sample-train:train").model_dump(mode="json"), ensure_ascii=False)
        + "\n",
        encoding="utf-8",
    )
    eval_path.write_text(
        json.dumps(_make_instruction_sample("sample-eval:eval", split="eval").model_dump(mode="json"), ensure_ascii=False)
        + "\n",
        encoding="utf-8",
    )

    summary = build_finetune_run(
        manifest_path=manifest_path,
        dataset_format="instruction",
        run_name="test_run_missing_model",
        base_model_path=str(tmp_path / "missing-model"),
    )

    assert summary["launch_ready"] is False
    assert "Missing local base model directory." in summary["blocking_issues"]
