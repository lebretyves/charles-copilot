import json
import sys
from pathlib import Path


ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))


from learning.llm.schemas import ExplanationTarget, LLMConversationMessage, LLMTrainingSample
from learning.pipelines.export_finetune_dataset import export_finetune_dataset
from learning.review.schemas import ReviewTask


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


def _make_sample(sample_id: str, split: str = "train") -> LLMTrainingSample:
    return LLMTrainingSample(
        sample_id=sample_id,
        case_id=1,
        segment_id=sample_id.split(":")[0],
        split=split,
        prompt_id="charles-perop-waveform-v2-local-train",
        prompt_version="2026-03-30",
        primary_problem_id="hemodynamic_instability",
        primary_severity="critical",
        source_problem_ids=["hemodynamic_instability"],
        case_complications=["major_blood_loss"],
        system_prompt="system prompt",
        user_prompt="user prompt",
        messages=[
            LLMConversationMessage(role="system", content="system prompt"),
            LLMConversationMessage(role="user", content="user prompt"),
        ],
        expected_output=ExplanationTarget(
            situation="Instabilite hemodynamique probable.",
            risks=["Hypoperfusion"],
            recommendations=["Verifier la courbe"],
            call_mar=True,
            call_mar_reason="Instabilite critique",
            confidence=0.9,
        ),
    )


def test_export_finetune_dataset_respects_review_statuses(tmp_path):
    output_dir = tmp_path / "exports"
    output_dir.mkdir()
    manifest_path = _write_manifest(tmp_path, output_dir)
    review_path = output_dir / "review_candidates.jsonl"

    approved = ReviewTask(sample=_make_sample("sample-approved:train"), review_status="approved")
    edited = ReviewTask(
        sample=_make_sample("sample-edited:eval", split="eval"),
        review_status="edited",
        corrected_output=ExplanationTarget(
            situation="Correction reviewer.",
            risks=["Risque corrige"],
            recommendations=["Reco corrigee"],
            call_mar=False,
            confidence=0.8,
        ),
        corrected_problem_id="hemorrhage_context",
    )
    rejected = ReviewTask(sample=_make_sample("sample-rejected:train"), review_status="rejected")
    pending = ReviewTask(sample=_make_sample("sample-pending:train"), review_status="pending")

    with review_path.open("w", encoding="utf-8") as handle:
        for task in [approved, edited, rejected, pending]:
            handle.write(json.dumps(task.model_dump(mode="json"), ensure_ascii=False) + "\n")

    summary = export_finetune_dataset(manifest_path=manifest_path, review_path=review_path, export_mode="gold_only")

    assert summary["samples_exported"] == 2
    assert summary["samples_skipped"] == 2
    assert summary["status_counts"]["approved"] == 1
    assert summary["status_counts"]["edited"] == 1

    chat_train = [json.loads(line) for line in (output_dir / "finetune_chat_train.jsonl").read_text(encoding="utf-8").splitlines()]
    chat_eval = [json.loads(line) for line in (output_dir / "finetune_chat_eval.jsonl").read_text(encoding="utf-8").splitlines()]
    assert len(chat_train) == 1
    assert len(chat_eval) == 1
    assert chat_eval[0]["primary_problem_id"] == "hemorrhage_context"
    assert '"situation": "Correction reviewer."' in chat_eval[0]["assistant_json"]


def test_export_finetune_dataset_bootstrap_pending_mode(tmp_path):
    output_dir = tmp_path / "exports"
    output_dir.mkdir()
    manifest_path = _write_manifest(tmp_path, output_dir)
    review_path = output_dir / "review_candidates.jsonl"

    pending = ReviewTask(sample=_make_sample("sample-pending:train"), review_status="pending")
    review_path.write_text(json.dumps(pending.model_dump(mode="json"), ensure_ascii=False) + "\n", encoding="utf-8")

    summary = export_finetune_dataset(
        manifest_path=manifest_path,
        review_path=review_path,
        export_mode="bootstrap_pending",
    )

    assert summary["samples_exported"] == 1
    assert summary["origin_counts"]["bootstrap_pending"] == 1
