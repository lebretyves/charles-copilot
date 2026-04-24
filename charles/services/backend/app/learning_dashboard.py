from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from app.config import settings


STATUS_VALUES = ("draft", "reviewed", "validated", "runtime-ready")


def resolve_learning_root() -> Path:
    root = Path(settings.learning_root)
    if root.is_absolute():
        return root
    return Path(__file__).resolve().parent.parent.parent.parent / settings.learning_root


def _display_path(path: str | Path | None, learning_root: Path) -> str | None:
    if not path:
        return None
    source = Path(path)
    try:
        relative = source.resolve().relative_to(learning_root.resolve())
        return f"learning/{relative.as_posix()}"
    except Exception:
        return source.as_posix()


def _read_json(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def _count_jsonl_rows(path: Path) -> int:
    if not path.is_file():
        return 0
    return sum(1 for line in path.read_text(encoding="utf-8").splitlines() if line.strip())


def _iso_timestamp(value: str | None) -> str | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc).isoformat()
    except ValueError:
        return value


def _mtime_iso(path: Path) -> str | None:
    if not path.exists():
        return None
    return datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).isoformat()


def _parse_model_card(card_path: Path) -> dict[str, Any]:
    if not card_path.is_file():
        return {
            "exists": False,
            "status": None,
            "human_review_status": None,
            "approved_for_runtime": "no",
            "clinical_caution": None,
        }

    text = card_path.read_text(encoding="utf-8")

    def extract(pattern: str) -> str | None:
        match = re.search(pattern, text, flags=re.MULTILINE)
        return match.group(1).strip() if match else None

    status = extract(r"- Status:\s*`([^`]+)`")
    if status not in STATUS_VALUES:
        status = None

    approved_for_runtime = (extract(r"- Approved for runtime:\s*(.+)") or "no").strip().lower()

    return {
        "exists": True,
        "status": status,
        "human_review_status": extract(r"- Human review status:\s*(.+)"),
        "approved_for_runtime": "yes" if approved_for_runtime == "yes" else "no",
        "clinical_caution": extract(r"- Clinical caution:\s*(.+)"),
    }


def _read_dvc_snapshot(snapshot_path: Path, learning_root: Path) -> dict[str, Any] | None:
    if not snapshot_path.is_file():
        return None
    payload = yaml.safe_load(snapshot_path.read_text(encoding="utf-8")) or {}
    outs = payload.get("outs") or []
    first = outs[0] if outs else {}
    tracked_path_value = first.get("path")
    tracked_path = (snapshot_path.parent / tracked_path_value).resolve() if tracked_path_value else None
    dataset_summary = _read_json((tracked_path / "dataset_summary.json")) if tracked_path else None
    export_summary = _read_json((tracked_path / "finetune_export_summary.json")) if tracked_path else None
    runs_root = tracked_path / "runs" if tracked_path else None
    run_dirs = sorted(path for path in runs_root.iterdir() if path.is_dir()) if runs_root and runs_root.exists() else []
    latest_run = max(run_dirs, key=lambda path: path.stat().st_mtime) if run_dirs else None

    dataset_id = tracked_path.name if tracked_path else snapshot_path.stem
    return {
        "dataset_id": dataset_id,
        "snapshot_path": _display_path(snapshot_path, learning_root),
        "tracked_path": _display_path(tracked_path, learning_root) if tracked_path else None,
        "md5": first.get("md5"),
        "size_bytes": first.get("size"),
        "file_count": first.get("nfiles"),
        "cases_scanned": (dataset_summary or {}).get("cases_scanned"),
        "cases_with_segments": (dataset_summary or {}).get("cases_with_segments"),
        "segments_written": (dataset_summary or {}).get("segments_written"),
        "samples_exported": (export_summary or {}).get("samples_exported"),
        "export_mode": (export_summary or {}).get("export_mode"),
        "run_count": len(run_dirs),
        "latest_run_id": latest_run.name if latest_run else None,
        "latest_run_at": _mtime_iso(latest_run) if latest_run else None,
    }


def _discover_dvc_snapshots(learning_root: Path) -> dict[str, dict[str, Any]]:
    exports_root = learning_root / "datasets" / "exports"
    snapshots: dict[str, dict[str, Any]] = {}
    if not exports_root.exists():
        return snapshots
    for snapshot_path in sorted(exports_root.glob("*.dvc")):
        metadata = _read_dvc_snapshot(snapshot_path, learning_root)
        if metadata is not None:
            snapshots[metadata["dataset_id"]] = metadata
    return snapshots


def _discover_mlflow(learning_root: Path) -> dict[str, Any]:
    store = learning_root / "mlruns"
    experiments: list[str] = []
    runs_count = 0
    latest_update_at: str | None = None

    if store.exists():
        for experiment_dir in sorted(path for path in store.iterdir() if path.is_dir()):
            if experiment_dir.name.startswith(".") or experiment_dir.name in {"models", ".trash"}:
                continue
            experiments.append(experiment_dir.name)
            for run_dir in sorted(path for path in experiment_dir.iterdir() if path.is_dir()):
                if (run_dir / "meta.yaml").exists():
                    runs_count += 1
                    current_time = _mtime_iso(run_dir)
                    if current_time and (latest_update_at is None or current_time > latest_update_at):
                        latest_update_at = current_time

    return {
        "store_path": _display_path(store, learning_root),
        "exists": store.exists(),
        "experiment_count": len(experiments),
        "run_count": runs_count,
        "latest_update_at": latest_update_at,
    }


def _derive_status(card_metadata: dict[str, Any], training_summary: dict[str, Any] | None, comparison_summary: dict[str, Any] | None) -> str:
    status = card_metadata.get("status")
    if status in STATUS_VALUES:
        return status
    if comparison_summary:
        return "validated"
    if training_summary:
        return "draft"
    return "draft"


def _build_adapter_record(run_dir: Path, learning_root: Path, dvc_snapshots: dict[str, dict[str, Any]]) -> dict[str, Any] | None:
    run_config = _read_json(run_dir / "run_config.json")
    if not run_config:
        return None

    run_id = str(run_config.get("run_id") or run_dir.name)
    dataset_dir = run_dir.parent.parent
    dataset_id = dataset_dir.name
    dvc_metadata = dvc_snapshots.get(dataset_id, {})
    run_summary = _read_json(run_dir / "run_summary.json")
    training_summary = _read_json(run_dir / "artifacts" / "training_summary.json")
    comparison_summary = _read_json(run_dir / "artifacts" / "evaluation" / "comparison_summary.json")
    model_card = _parse_model_card(learning_root / "model_cards" / f"{run_id}.md")

    train_rows = (run_summary or {}).get("train_profile", {}).get("rows")
    eval_rows = (run_summary or {}).get("eval_profile", {}).get("rows")
    if train_rows is None:
        train_rows = _count_jsonl_rows(run_dir / "prepared" / "prepared_train.jsonl")
    if eval_rows is None:
        eval_rows = _count_jsonl_rows(run_dir / "prepared" / "prepared_eval.jsonl")

    input_variant_counts = (run_summary or {}).get("train_profile", {}).get("input_variant_counts") or {}
    comparison_adapter = (comparison_summary or {}).get("adapter") or {}
    status = _derive_status(model_card, training_summary, comparison_summary)
    approved_for_runtime = model_card.get("approved_for_runtime", "no")
    latest_update_at = (
        _iso_timestamp((comparison_summary or {}).get("evaluated_at"))
        or _iso_timestamp((training_summary or {}).get("trained_at"))
        or _iso_timestamp(run_config.get("created_at"))
        or _mtime_iso(run_dir)
    )

    train_metrics = (training_summary or {}).get("train_metrics") or {}
    base_model_tag = ((run_config.get("model") or {}).get("ollama_target_tag") or "").strip()
    if not base_model_tag:
        base_model_tag = Path(((run_config.get("model") or {}).get("base_model_path") or "unknown")).name

    return {
        "run_id": run_id,
        "dataset_id": dataset_id,
        "base_model": "epfl-llm/meditron-7b" if "meditron" in base_model_tag.lower() else base_model_tag,
        "runtime_target_tag": base_model_tag,
        "status": status,
        "human_review_status": model_card.get("human_review_status"),
        "approved_for_runtime": approved_for_runtime,
        "train_rows": train_rows,
        "eval_rows": eval_rows,
        "input_variants": sorted(input_variant_counts.keys()),
        "input_variant_counts": input_variant_counts,
        "train_loss": train_metrics.get("train_loss"),
        "train_runtime_s": train_metrics.get("train_runtime"),
        "overall_score": comparison_adapter.get("overall_score"),
        "json_parse_ok": comparison_adapter.get("json_parse_ok"),
        "schema_valid": comparison_adapter.get("schema_valid"),
        "call_mar_accuracy": comparison_adapter.get("call_mar_accuracy"),
        "samples_evaluated": (comparison_summary or {}).get("samples_evaluated"),
        "updated_at": latest_update_at,
        "run_path": _display_path(run_dir, learning_root),
        "model_card_path": _display_path(learning_root / "model_cards" / f"{run_id}.md", learning_root),
        "comparison_path": _display_path(run_dir / "artifacts" / "evaluation" / "comparison_summary.json", learning_root),
        "training_summary_path": _display_path(run_dir / "artifacts" / "training_summary.json", learning_root),
        "dataset_dvc_md5": dvc_metadata.get("md5"),
        "dataset_snapshot_path": dvc_metadata.get("snapshot_path"),
    }


def _discover_adapters(learning_root: Path, dvc_snapshots: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    exports_root = learning_root / "datasets" / "exports"
    adapters: list[dict[str, Any]] = []
    if not exports_root.exists():
        return adapters

    for dataset_dir in sorted(path for path in exports_root.iterdir() if path.is_dir()):
        runs_root = dataset_dir / "runs"
        if not runs_root.exists():
            continue
        for run_dir in sorted(path for path in runs_root.iterdir() if path.is_dir()):
            record = _build_adapter_record(run_dir, learning_root, dvc_snapshots)
            if record is not None:
                adapters.append(record)

    return sorted(adapters, key=lambda item: (item.get("updated_at") or "", item["run_id"]), reverse=True)


def build_learning_dashboard_payload(learning_root: str | Path | None = None) -> dict[str, Any]:
    root = Path(learning_root) if learning_root else resolve_learning_root()
    payload: dict[str, Any] = {
        "available": root.exists(),
        "learning_root": str(root),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "registry": {
            "exists": False,
            "path": _display_path(root / "MODEL_REGISTRY.md", root),
            "adapter_count": 0,
            "status_counts": {status: 0 for status in STATUS_VALUES},
            "runtime_ready_count": 0,
        },
        "dvc": {
            "snapshot_count": 0,
            "snapshots": [],
        },
        "tracking": {
            "store_path": _display_path(root / "mlruns", root),
            "exists": False,
            "experiment_count": 0,
            "run_count": 0,
            "latest_update_at": None,
        },
        "adapters": [],
        "notes": [],
    }

    if not root.exists():
        payload["notes"].append("Learning workspace not found from backend runtime.")
        return payload

    dvc_snapshots = _discover_dvc_snapshots(root)
    adapters = _discover_adapters(root, dvc_snapshots)
    tracking = _discover_mlflow(root)

    status_counts = {status: 0 for status in STATUS_VALUES}
    runtime_ready_count = 0
    for adapter in adapters:
        status_counts[adapter["status"]] = status_counts.get(adapter["status"], 0) + 1
        if adapter["approved_for_runtime"] == "yes":
            runtime_ready_count += 1

    payload["registry"] = {
        "exists": (root / "MODEL_REGISTRY.md").is_file(),
        "path": _display_path(root / "MODEL_REGISTRY.md", root),
        "adapter_count": len(adapters),
        "status_counts": status_counts,
        "runtime_ready_count": runtime_ready_count,
    }
    payload["dvc"] = {
        "snapshot_count": len(dvc_snapshots),
        "snapshots": sorted(dvc_snapshots.values(), key=lambda item: item["dataset_id"]),
    }
    payload["tracking"] = tracking
    payload["adapters"] = adapters

    if not dvc_snapshots:
        payload["notes"].append("No DVC snapshot found for learning exports.")
    if not tracking["exists"]:
        payload["notes"].append("MLflow local store missing or not initialized on this runtime.")
    elif tracking["run_count"] == 0:
        payload["notes"].append("MLflow store is present but no tracked runs were detected yet.")
    if not adapters:
        payload["notes"].append("No fine-tuning run discovered under learning/datasets/exports.")
    elif runtime_ready_count == 0:
        payload["notes"].append("Adapters are tracked, but none is approved for runtime yet.")

    return payload
