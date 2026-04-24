from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse

from learning.finetune.config import FineTuneRunConfig


def _import_mlflow():
    try:
        import mlflow  # type: ignore

        return mlflow
    except ImportError:
        return None


def resolve_tracking_store_path(tracking_uri: str | None) -> Path | None:
    if not tracking_uri:
        return None
    if tracking_uri.startswith("file://"):
        parsed = urlparse(tracking_uri)
        path = unquote(parsed.path)
        if len(path) >= 3 and path[0] == "/" and path[2] == ":":
            path = path[1:]
        return Path(path)
    if "://" in tracking_uri:
        return None
    return Path(tracking_uri)


def ensure_local_tracking_store(tracking_uri: str | None) -> Path | None:
    local_path = resolve_tracking_store_path(tracking_uri)
    if local_path is None:
        return None
    local_path.mkdir(parents=True, exist_ok=True)
    return local_path


def _sanitize_key(key: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", key).strip("_")


def _normalize_param_value(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float, str)):
        return str(value)
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def flatten_params(payload: dict[str, Any], prefix: str = "") -> dict[str, str]:
    flattened: dict[str, str] = {}
    for key, value in payload.items():
        full_key = _sanitize_key(f"{prefix}.{key}" if prefix else key)
        if isinstance(value, dict):
            flattened.update(flatten_params(value, prefix=full_key))
            continue
        flattened[full_key] = _normalize_param_value(value)
    return flattened


def collect_run_params(config: FineTuneRunConfig) -> dict[str, str]:
    payload = {
        "dataset": {
            "id": config.dataset.dataset_id,
            "version": config.dataset.dataset_version,
            "format": config.dataset.dataset_format,
            "source_train_path": config.dataset.source_train_path,
            "source_eval_path": config.dataset.source_eval_path,
            "prepared_train_path": config.dataset.prepared_train_path,
            "prepared_eval_path": config.dataset.prepared_eval_path,
        },
        "model": {
            "base_model_path": config.model.base_model_path,
            "tokenizer_path": config.model.tokenizer_path or config.model.base_model_path,
            "ollama_target_tag": config.model.ollama_target_tag,
            "family": config.model.model_family,
            "trust_remote_code": config.model.trust_remote_code,
        },
        "lora": config.lora.model_dump(mode="python"),
        "quantization": config.quantization.model_dump(mode="python"),
        "training": config.training.model_dump(mode="python"),
        "tracking": {
            "experiment_name": config.tracking.experiment_name,
            "tracking_uri": config.tracking.tracking_uri,
        },
        "run": {
            "run_id": config.run_id,
            "training_stage": config.training_stage,
        },
    }
    return flatten_params(payload)


def flatten_numeric_metrics(payload: dict[str, Any], prefix: str = "") -> dict[str, float]:
    flattened: dict[str, float] = {}
    for key, value in payload.items():
        full_key = _sanitize_key(f"{prefix}.{key}" if prefix else key)
        if isinstance(value, dict):
            flattened.update(flatten_numeric_metrics(value, prefix=full_key))
        elif isinstance(value, (int, float)) and not isinstance(value, bool):
            flattened[full_key] = float(value)
    return flattened


def default_tracking_tags(
    config: FineTuneRunConfig,
    *,
    stage: str,
    extra_tags: dict[str, str] | None = None,
) -> dict[str, str]:
    tags = {
        "charles.run_id": config.run_id,
        "charles.stage": stage,
        "charles.training_stage": config.training_stage,
        "charles.dataset_id": config.dataset.dataset_id,
        "charles.dataset_version": config.dataset.dataset_version,
        "charles.dataset_format": config.dataset.dataset_format,
        "charles.model_target": config.model.ollama_target_tag,
    }
    tags.update({key: str(value) for key, value in config.tracking.tags.items()})
    if extra_tags:
        tags.update({key: str(value) for key, value in extra_tags.items()})
    return tags


@dataclass
class MLflowTrackingSession:
    active: bool
    tracking_uri: str | None = None
    experiment_name: str | None = None
    run_name: str | None = None
    run_id: str | None = None
    reason: str | None = None
    warnings: list[str] = field(default_factory=list)
    _mlflow: Any = None

    def status_payload(self) -> dict[str, Any]:
        return {
            "active": self.active,
            "tracking_uri": self.tracking_uri,
            "experiment_name": self.experiment_name,
            "run_name": self.run_name,
            "mlflow_run_id": self.run_id,
            "reason": self.reason,
            "warnings": list(self.warnings),
        }

    def _capture(self, action: str, func) -> None:
        if not self.active or self._mlflow is None:
            return
        try:
            func()
        except Exception as exc:  # pragma: no cover - defensive path for local environments
            self.warnings.append(f"{action}: {exc}")

    def log_params(self, params: dict[str, Any]) -> None:
        flattened = flatten_params(params)
        for key, value in flattened.items():
            self._capture(f"log_param:{key}", lambda key=key, value=value: self._mlflow.log_param(key, value))

    def log_metrics(self, metrics: dict[str, float]) -> None:
        for key, value in metrics.items():
            self._capture(f"log_metric:{key}", lambda key=key, value=value: self._mlflow.log_metric(key, value))

    def log_json(self, payload: dict[str, Any], artifact_file: str) -> None:
        self._capture(
            f"log_json:{artifact_file}",
            lambda: self._mlflow.log_text(json.dumps(payload, indent=2, ensure_ascii=False), artifact_file),
        )

    def log_text(self, text: str, artifact_file: str) -> None:
        self._capture(f"log_text:{artifact_file}", lambda: self._mlflow.log_text(text, artifact_file))

    def log_artifact(self, path: str | Path, artifact_path: str | None = None) -> None:
        source = Path(path)
        if not source.exists():
            self.warnings.append(f"log_artifact_missing:{source}")
            return
        self._capture(
            f"log_artifact:{source.name}",
            lambda: self._mlflow.log_artifact(str(source), artifact_path=artifact_path),
        )

    def log_artifacts(self, path: str | Path, artifact_path: str | None = None) -> None:
        source = Path(path)
        if not source.exists():
            self.warnings.append(f"log_artifacts_missing:{source}")
            return
        self._capture(
            f"log_artifacts:{source.name}",
            lambda: self._mlflow.log_artifacts(str(source), artifact_path=artifact_path),
        )

    def set_tags(self, tags: dict[str, Any]) -> None:
        normalized = {str(key): str(value) for key, value in tags.items()}
        self._capture("set_tags", lambda: self._mlflow.set_tags(normalized))

    def finish(self, status: str = "FINISHED") -> None:
        self._capture("end_run", lambda: self._mlflow.end_run(status=status))


def start_tracking_session(
    config: FineTuneRunConfig,
    *,
    stage: str,
    extra_tags: dict[str, str] | None = None,
) -> MLflowTrackingSession:
    tracking = config.tracking
    if not tracking.enabled:
        return MLflowTrackingSession(active=False, reason="tracking_disabled")

    mlflow = _import_mlflow()
    if mlflow is None:
        return MLflowTrackingSession(
            active=False,
            tracking_uri=tracking.tracking_uri,
            experiment_name=tracking.experiment_name,
            reason="mlflow_not_installed",
        )

    run_name = f"{tracking.run_name_prefix}-{config.run_id}-{stage}"
    try:
        ensure_local_tracking_store(tracking.tracking_uri)
        if tracking.tracking_uri:
            mlflow.set_tracking_uri(tracking.tracking_uri)
        mlflow.set_experiment(tracking.experiment_name)
        active_run = mlflow.start_run(run_name=run_name)
        session = MLflowTrackingSession(
            active=True,
            tracking_uri=tracking.tracking_uri,
            experiment_name=tracking.experiment_name,
            run_name=run_name,
            run_id=getattr(getattr(active_run, "info", None), "run_id", None),
            reason="started",
            _mlflow=mlflow,
        )
        session.set_tags(default_tracking_tags(config, stage=stage, extra_tags=extra_tags))
        return session
    except Exception as exc:  # pragma: no cover - defensive path for local environments
        return MLflowTrackingSession(
            active=False,
            tracking_uri=tracking.tracking_uri,
            experiment_name=tracking.experiment_name,
            run_name=run_name,
            reason=f"mlflow_start_failed: {exc}",
        )
