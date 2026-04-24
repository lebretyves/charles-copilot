import json
import sys
from pathlib import Path


ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))


from learning.finetune.config import FineTuneRunConfig
from learning.finetune import mlflow_tracking as tracking


def _make_config(tmp_path: Path) -> FineTuneRunConfig:
    run_dir = tmp_path / "run"
    return FineTuneRunConfig.model_validate(
        {
            "run_id": "test-run",
            "created_at": "2026-03-31T00:00:00+00:00",
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
                "ollama_target_tag": "meditron:7b",
            },
            "artifacts": {
                "run_dir": str(run_dir),
                "output_dir": str(run_dir / "output"),
                "logging_dir": str(run_dir / "logs"),
                "adapter_output_dir": str(run_dir / "adapter"),
                "environment_report_path": str(run_dir / "environment_report.json"),
                "training_summary_path": str(run_dir / "training_summary.json"),
            },
            "tracking": {
                "enabled": True,
                "strict": False,
                "tracking_uri": str(tmp_path / "mlruns"),
                "experiment_name": "charles-local-finetune",
                "run_name_prefix": "charles",
                "tags": {
                    "charles.extra": "yes",
                },
            },
        }
    )


def test_start_tracking_session_gracefully_disables_without_mlflow(tmp_path, monkeypatch):
    config = _make_config(tmp_path)
    monkeypatch.setattr(tracking, "_import_mlflow", lambda: None)

    session = tracking.start_tracking_session(config, stage="train")

    assert session.active is False
    assert session.reason == "mlflow_not_installed"
    assert session.tracking_uri == str(tmp_path / "mlruns")


def test_start_tracking_session_logs_to_fake_mlflow(tmp_path, monkeypatch):
    config = _make_config(tmp_path)
    artifact_file = tmp_path / "artifact.json"
    artifact_file.write_text("{}", encoding="utf-8")
    artifact_dir = tmp_path / "artifact_dir"
    artifact_dir.mkdir()
    (artifact_dir / "nested.txt").write_text("ok", encoding="utf-8")

    calls: list[tuple] = []

    class FakeRunInfo:
        run_id = "mlflow-run-123"

    class FakeRun:
        info = FakeRunInfo()

    class FakeMLflow:
        def set_tracking_uri(self, uri):
            calls.append(("set_tracking_uri", uri))

        def set_experiment(self, name):
            calls.append(("set_experiment", name))

        def start_run(self, run_name):
            calls.append(("start_run", run_name))
            return FakeRun()

        def set_tags(self, tags):
            calls.append(("set_tags", dict(tags)))

        def log_param(self, key, value):
            calls.append(("log_param", key, value))

        def log_metric(self, key, value):
            calls.append(("log_metric", key, value))

        def log_text(self, text, artifact_file):
            calls.append(("log_text", artifact_file, text))

        def log_artifact(self, path, artifact_path=None):
            calls.append(("log_artifact", Path(path).name, artifact_path))

        def log_artifacts(self, path, artifact_path=None):
            calls.append(("log_artifacts", Path(path).name, artifact_path))

        def end_run(self, status="FINISHED"):
            calls.append(("end_run", status))

    monkeypatch.setattr(tracking, "_import_mlflow", lambda: FakeMLflow())

    session = tracking.start_tracking_session(config, stage="train", extra_tags={"charles.task": "fine_tuning"})
    session.log_params({"alpha": 32, "nested": {"beta": True}})
    session.log_metrics({"train_loss": 0.42})
    session.log_json({"status": "ok"}, "reports/summary.json")
    session.log_artifact(artifact_file, artifact_path="reports")
    session.log_artifacts(artifact_dir, artifact_path="adapter")
    session.finish()

    assert session.active is True
    assert session.run_id == "mlflow-run-123"
    assert ("set_tracking_uri", str(tmp_path / "mlruns")) in calls
    assert any(call[0] == "set_experiment" and call[1] == "charles-local-finetune" for call in calls)
    assert any(call[0] == "log_param" and call[1] == "nested.beta" and call[2] == "true" for call in calls)
    assert any(call[0] == "log_metric" and call[1] == "train_loss" and call[2] == 0.42 for call in calls)
    assert any(call[0] == "log_text" and call[1] == "reports/summary.json" for call in calls)
    assert any(call[0] == "log_artifact" and call[1] == "artifact.json" and call[2] == "reports" for call in calls)
    assert any(call[0] == "log_artifacts" and call[1] == "artifact_dir" and call[2] == "adapter" for call in calls)
    assert any(call[0] == "end_run" and call[1] == "FINISHED" for call in calls)
