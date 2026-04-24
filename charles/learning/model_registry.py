from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from learning.dvc_tracking import read_dvc_snapshot_metadata
from learning.finetune.config import FineTuneRunConfig


STATUS_VALUES = {"draft", "reviewed", "validated", "runtime-ready"}


@dataclass
class ExistingCardMetadata:
    status: str | None = None
    human_review_status: str | None = None
    approved_for_runtime: str | None = None
    clinical_caution: str | None = None


def _read_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def _count_jsonl_rows(path: str | Path | None) -> int:
    if not path:
        return 0
    source = Path(path)
    if not source.exists():
        return 0
    return sum(1 for line in source.read_text(encoding="utf-8").splitlines() if line.strip())


def _find_latest_trainer_state(adapter_dir: Path) -> dict[str, Any] | None:
    if not adapter_dir.exists():
        return None
    trainer_states = list(adapter_dir.rglob("trainer_state.json"))
    if not trainer_states:
        return None

    def _state_key(path: Path) -> tuple[int, str]:
        payload = _read_json(path) or {}
        return int(payload.get("global_step", 0)), str(path)

    selected_path = max(trainer_states, key=_state_key)
    return _read_json(selected_path)


def _latest_eval_metrics(trainer_state: dict[str, Any] | None) -> dict[str, float]:
    if not trainer_state:
        return {}
    log_history = trainer_state.get("log_history", [])
    eval_rows = [row for row in log_history if isinstance(row, dict) and any(key.startswith("eval_") for key in row)]
    if not eval_rows:
        return {}
    latest = max(eval_rows, key=lambda row: row.get("step", 0))
    metrics: dict[str, float] = {}
    for key, value in latest.items():
        if key.startswith("eval_") and isinstance(value, (int, float)) and not isinstance(value, bool):
            metrics[key] = float(value)
    return metrics


def _relative_repo_path(path: str | Path | None, workspace_root: Path) -> str | None:
    if not path:
        return None
    source = Path(path)
    repo_root = workspace_root.parent
    try:
        return source.resolve().relative_to(repo_root.resolve()).as_posix()
    except Exception:
        return source.as_posix()


def _format_optional_metric(metrics: dict[str, float], key: str) -> str | None:
    if key not in metrics:
        return None
    return f"`{key} = {metrics[key]:.4f}`"


def _parse_existing_card(card_path: Path) -> ExistingCardMetadata:
    if not card_path.exists():
        return ExistingCardMetadata()
    text = card_path.read_text(encoding="utf-8")

    def _extract(pattern: str) -> str | None:
        match = re.search(pattern, text, flags=re.MULTILINE)
        return match.group(1).strip() if match else None

    status = _extract(r"- Status:\s*`([^`]+)`")
    if status not in STATUS_VALUES:
        status = None
    return ExistingCardMetadata(
        status=status,
        human_review_status=_extract(r"- Human review status:\s*(.+)"),
        approved_for_runtime=_extract(r"- Approved for runtime:\s*(.+)"),
        clinical_caution=_extract(r"- Clinical caution:\s*(.+)"),
    )


def _derive_version_label(run_id: str, dataset_id: str, dataset_version: str) -> str:
    prefix = f"{dataset_id}_{dataset_version}_"
    if run_id.startswith(prefix):
        return run_id[len(prefix):]
    return run_id


def _derive_status(existing: ExistingCardMetadata, has_training: bool, has_comparison: bool) -> str:
    if existing.status in STATUS_VALUES:
        return existing.status
    if has_comparison:
        return "validated"
    if has_training:
        return "draft"
    return "draft"


def _derive_human_review(existing: ExistingCardMetadata, status: str) -> str:
    if existing.human_review_status:
        return existing.human_review_status
    if status == "validated":
        return "validated offline"
    if status == "reviewed":
        return "reviewed from artifacts"
    return "not reviewed"


def _derive_runtime_approval(existing: ExistingCardMetadata, status: str) -> str:
    if existing.approved_for_runtime:
        return existing.approved_for_runtime
    return "yes" if status == "runtime-ready" else "no"


def _derive_clinical_caution(existing: ExistingCardMetadata) -> str:
    if existing.clinical_caution:
        return existing.clinical_caution
    return "decision support research artifact, not a stand-alone clinical system"


def _dataset_notes(run_summary: dict[str, Any] | None, export_summary: dict[str, Any] | None) -> list[str]:
    notes: list[str] = []
    if export_summary:
        if export_summary.get("samples_exported") is not None:
            notes.append(f"`{export_summary['samples_exported']}` exported samples in the dataset release")
        if export_summary.get("export_mode"):
            notes.append(f"export mode: `{export_summary['export_mode']}`")
    if run_summary:
        train_variants = run_summary.get("train_profile", {}).get("input_variant_counts", {})
        if train_variants:
            variant_summary = ", ".join(f"{key}={value}" for key, value in sorted(train_variants.items()))
            notes.append(f"train variants: {variant_summary}")
        complication_counts = run_summary.get("train_profile", {}).get("case_complication_counts", {})
        if complication_counts:
            top_complications = list(sorted(complication_counts.items(), key=lambda item: (-item[1], item[0])))[:5]
            notes.append(
                "top train complications: "
                + ", ".join(f"{key}={value}" for key, value in top_complications)
            )
    return notes


def _training_method(config: FineTuneRunConfig) -> str:
    return "QLoRA / local SFT scaffold" if config.quantization.enabled else "LoRA / local SFT scaffold"


def _hardware_label(environment_report: dict[str, Any] | None) -> str:
    gpu_names = ((environment_report or {}).get("gpu") or {}).get("cuda_device_names") or []
    if gpu_names:
        return ", ".join(str(name) for name in gpu_names)
    return "local GPU workflow"


def _comparison_takeaway(comparison_summary: dict[str, Any] | None) -> str:
    if not comparison_summary:
        return "No downstream comparison artifact available yet."
    adapter = comparison_summary.get("adapter") or {}
    overall = adapter.get("overall_score")
    if isinstance(overall, (int, float)) and overall >= 0.95:
        return "Strong offline structured-output performance on the available evaluation slice."
    if isinstance(overall, (int, float)):
        return "Offline evaluation exists, but the adapter still needs stronger downstream validation."
    return "Offline comparison artifact present, but no adapter score was captured."


def _render_card(record: dict[str, Any]) -> str:
    dataset_notes = record["dataset_notes"] or ["No additional dataset notes captured."]
    trainer_lines = record["trainer_metric_lines"] or ["Trainer metrics unavailable."]
    comparison_lines = record["comparison_metric_lines"] or ["No downstream comparison artifact available."]

    return "\n".join(
        [
            f"# Model Card: {record['run_id']}",
            "",
            "## Identity",
            "",
            f"- Adapter name: `{record['run_id']}`",
            f"- Version: `{record['version_label']}`",
            f"- Date: `{record['date_label']}`",
            f"- Status: `{record['status']}`",
            "",
            "## Base model",
            "",
            f"- Canonical base model: `{record['canonical_base_model']}`",
            f"- Local training path: `{record['base_model_path']}`",
            f"- Runtime target tag: `{record['runtime_target_tag']}`",
            f"- Model family: `{record['model_family']}`",
            "",
            "## Intended use",
            "",
            f"- Primary purpose: {record['primary_purpose']}",
            f"- Expected inputs: {record['expected_inputs']}",
            f"- Expected outputs: {record['expected_outputs']}",
            f"- Explicit non-goals: {record['explicit_non_goals']}",
            "",
            "## Dataset lineage",
            "",
            f"- Dataset id: `{record['dataset_id']}`",
            f"- Dataset version: `{record['dataset_version']}`",
            f"- Train samples: `{record['train_rows']}`",
            f"- Eval samples: `{record['eval_rows']}`",
            f"- Input variants: {record['input_variants_label']}",
            "- Dataset notes:",
            *[f"  - {line}" for line in dataset_notes],
            f"- DVC snapshot: `{record['dataset_dvc_snapshot_path'] or 'not tracked'}`",
            f"- DVC md5: `{record['dataset_dvc_md5'] or 'unknown'}`",
            "",
            "## Training configuration",
            "",
            f"- Method: {record['training_method']}",
            f"- LoRA / QLoRA parameters: {record['lora_label']}",
            f"- Target modules: {record['target_modules_label']}",
            f"- Quantization: {record['quantization_label']}",
            f"- Sequence length: `{record['sequence_length']}`",
            f"- Batch size: `{record['batch_size']}`",
            f"- Gradient accumulation: `{record['gradient_accumulation']}`",
            f"- Learning rate: `{record['learning_rate']}`",
            f"- Epochs: `{record['epochs']}`",
            f"- Seed: `{record['seed']}`",
            f"- Hardware: {record['hardware_label']}",
            "",
            "## Evaluation",
            "",
            "- Trainer metrics:",
            *[f"  - {line}" for line in trainer_lines],
            "- Downstream comparison metrics:",
            *[f"  - {line}" for line in comparison_lines],
            f"- Main takeaways: {record['comparison_takeaway']}",
            "",
            "## Limitations",
            "",
            f"- Data limitations: {record['data_limitations']}",
            f"- Model limitations: {record['model_limitations']}",
            f"- Deployment limitations: {record['deployment_limitations']}",
            "",
            "## Safety and review",
            "",
            f"- Human review status: {record['human_review_status']}",
            f"- Approved for runtime: {record['approved_for_runtime']}",
            f"- Clinical caution: {record['clinical_caution']}",
            "",
            "## Linked artifacts",
            "",
            f"- Run config: `{record['run_config_path']}`",
            f"- Training summary: `{record['training_summary_path']}`",
            f"- Evaluation summary: `{record['evaluation_summary_path']}`",
            f"- Adapter path: `{record['adapter_path']}`",
        ]
    ) + "\n"


def _render_registry(records: list[dict[str, Any]]) -> str:
    lines = [
        "# CHARLES Model Registry",
        "",
        "Central registry for locally trained adapters used by the CHARLES learning pipeline.",
        "",
        "## Status vocabulary",
        "",
        "- `draft`: initial run, incomplete downstream validation",
        "- `reviewed`: training artifacts reviewed, but not yet validated offline end to end",
        "- `validated`: offline evaluation available and considered usable for research benchmarking",
        "- `runtime-ready`: explicitly approved for runtime integration",
        "",
        "## Current adapters",
        "",
        "| Adapter | Base model | Dataset | Train / Eval | Status | Latest eval | Runtime |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for record in records:
        lines.append(
            f"| `{record['run_id']}` | `{record['canonical_base_model']}` | "
            f"`{record['dataset_id']}_{record['dataset_version']}` | `{record['train_rows']} / {record['eval_rows']}` | "
            f"`{record['status']}` | {record['latest_eval_label']} | `{record['approved_for_runtime']}` |"
        )

    lines.extend(
        [
            "",
            "## Promotion rules",
            "",
            "An adapter can move to `runtime-ready` only if:",
            "",
            "1. The base model is explicitly identified.",
            "2. Dataset lineage is documented.",
            "3. Training parameters are documented.",
            "4. Offline evaluation artifacts are present.",
            "5. Limits and intended use are written clearly.",
            "6. A human review confirms that runtime integration is desired.",
            "",
            "## Linked model cards",
            "",
        ]
    )
    for record in records:
        lines.append(f"- [{record['run_id']}](./model_cards/{record['run_id']}.md)")
    return "\n".join(lines) + "\n"


def _build_record(workspace_root: Path, run_dir: Path) -> dict[str, Any] | None:
    run_config_path = run_dir / "run_config.json"
    config_payload = _read_json(run_config_path)
    if not config_payload:
        return None
    config = FineTuneRunConfig.model_validate(config_payload)

    run_summary = _read_json(run_dir / "run_summary.json")
    training_summary = _read_json(Path(config.artifacts.training_summary_path))
    environment_report = _read_json(Path(config.artifacts.environment_report_path))
    comparison_summary = _read_json(run_dir / "artifacts" / "evaluation" / "comparison_summary.json")
    export_summary_path = Path(config.dataset.export_summary_path) if config.dataset.export_summary_path else None
    export_summary = _read_json(export_summary_path) if export_summary_path else None
    dvc_metadata = read_dvc_snapshot_metadata(run_dir.parent.parent)
    trainer_state = _find_latest_trainer_state(Path(config.artifacts.adapter_output_dir))
    trainer_eval_metrics = _latest_eval_metrics(trainer_state)

    card_path = workspace_root / "model_cards" / f"{config.run_id}.md"
    existing = _parse_existing_card(card_path)
    status = _derive_status(existing, training_summary is not None, comparison_summary is not None)
    train_rows = (run_summary or {}).get("train_profile", {}).get("rows") or _count_jsonl_rows(config.dataset.prepared_train_path)
    eval_rows = (run_summary or {}).get("eval_profile", {}).get("rows") or _count_jsonl_rows(config.dataset.prepared_eval_path)
    input_variants = list(((run_summary or {}).get("train_profile", {}).get("input_variant_counts") or {}).keys())
    if not input_variants:
        input_variants = list(((export_summary or {}).get("input_variant_counts") or {}).keys())

    trainer_metric_lines = []
    train_metrics = (training_summary or {}).get("train_metrics", {})
    train_loss = _format_optional_metric(train_metrics, "train_loss")
    train_runtime = _format_optional_metric(train_metrics, "train_runtime")
    if train_loss:
        trainer_metric_lines.append(train_loss)
    if train_runtime:
        trainer_metric_lines.append(train_runtime)
    eval_loss = _format_optional_metric(trainer_eval_metrics, "eval_loss")
    eval_token_accuracy = _format_optional_metric(trainer_eval_metrics, "eval_mean_token_accuracy")
    if eval_loss:
        trainer_metric_lines.append(eval_loss)
    if eval_token_accuracy:
        trainer_metric_lines.append(eval_token_accuracy)

    adapter_metrics = ((comparison_summary or {}).get("adapter") or {})
    comparison_metric_lines = []
    for key in ("json_parse_ok", "schema_valid", "call_mar_accuracy", "overall_score"):
        formatted = _format_optional_metric(adapter_metrics, key)
        if formatted:
            comparison_metric_lines.append(formatted)

    overall_score = adapter_metrics.get("overall_score")
    if isinstance(overall_score, (int, float)):
        latest_eval_label = f"`overall_score={overall_score:.4f}`"
    elif eval_loss:
        latest_eval_label = eval_loss
    else:
        latest_eval_label = "trainer eval unavailable"

    created_at = training_summary.get("trained_at") if training_summary else None
    if comparison_summary and comparison_summary.get("evaluated_at"):
        created_at = comparison_summary["evaluated_at"]
    elif not created_at:
        created_at = config.created_at
    try:
        date_label = datetime.fromisoformat(str(created_at).replace("Z", "+00:00")).date().isoformat()
    except Exception:
        date_label = str(created_at)

    canonical_base_model = "epfl-llm/meditron-7b" if "meditron" in config.model.ollama_target_tag.lower() else config.model.ollama_target_tag

    return {
        "run_id": config.run_id,
        "version_label": _derive_version_label(config.run_id, config.dataset.dataset_id, config.dataset.dataset_version),
        "date_label": date_label,
        "status": status,
        "canonical_base_model": canonical_base_model,
        "base_model_path": _relative_repo_path(config.model.base_model_path, workspace_root),
        "runtime_target_tag": config.model.ollama_target_tag,
        "model_family": config.model.model_family,
        "primary_purpose": f"local structured perioperative interpretation for `{config.dataset.dataset_format}`-format CHARLES samples",
        "expected_inputs": "CHARLES structured train/eval samples generated from VitalDB-derived features, alerts, and context",
        "expected_outputs": "structured JSON analyses for the CHARLES worker / review pipeline",
        "explicit_non_goals": "raw waveform primary detection, unsupervised online learning, autonomous clinical use",
        "dataset_id": config.dataset.dataset_id,
        "dataset_version": config.dataset.dataset_version,
        "train_rows": train_rows,
        "eval_rows": eval_rows,
        "input_variants_label": ", ".join(f"`{variant}`" for variant in input_variants) if input_variants else "`full_wave`",
        "dataset_notes": _dataset_notes(run_summary, export_summary),
        "dataset_dvc_snapshot_path": _relative_repo_path((dvc_metadata or {}).get("snapshot_path"), workspace_root),
        "dataset_dvc_md5": (dvc_metadata or {}).get("md5"),
        "training_method": _training_method(config),
        "lora_label": f"`r={config.lora.r}` , `alpha={config.lora.alpha}` , `dropout={config.lora.dropout}` , `bias={config.lora.bias}`".replace("` ,", "`,"),
        "target_modules_label": ", ".join(f"`{module}`" for module in config.lora.target_modules),
        "quantization_label": (
            f"4-bit `{config.quantization.quant_type}`, `{config.quantization.compute_dtype}`, "
            f"double quantization {'enabled' if config.quantization.use_double_quant else 'disabled'}"
            if config.quantization.enabled
            else "disabled"
        ),
        "sequence_length": config.training.max_seq_length,
        "batch_size": config.training.per_device_train_batch_size,
        "gradient_accumulation": config.training.gradient_accumulation_steps,
        "learning_rate": config.training.learning_rate,
        "epochs": config.training.num_train_epochs,
        "seed": config.training.seed,
        "hardware_label": _hardware_label(environment_report),
        "trainer_metric_lines": trainer_metric_lines,
        "comparison_metric_lines": comparison_metric_lines,
        "comparison_takeaway": _comparison_takeaway(comparison_summary),
        "data_limitations": "trained on public anonymized VitalDB-derived structured data, not on live hospital data",
        "model_limitations": "reasons over structured features, alerts, and context; it does not replace a dedicated raw-waveform signal model",
        "deployment_limitations": "validated offline only; runtime integration still requires an explicit promotion step",
        "human_review_status": _derive_human_review(existing, status),
        "approved_for_runtime": _derive_runtime_approval(existing, status),
        "clinical_caution": _derive_clinical_caution(existing),
        "run_config_path": _relative_repo_path(run_config_path, workspace_root),
        "training_summary_path": _relative_repo_path(config.artifacts.training_summary_path, workspace_root),
        "evaluation_summary_path": _relative_repo_path(run_dir / "artifacts" / "evaluation" / "comparison_summary.json", workspace_root) or "not available",
        "adapter_path": _relative_repo_path(config.artifacts.adapter_output_dir, workspace_root),
        "latest_eval_label": latest_eval_label,
        "card_path": card_path,
    }


def sync_model_registry(workspace_root: str | Path | None = None) -> dict[str, Any]:
    workspace = Path(workspace_root) if workspace_root else Path(__file__).resolve().parent
    model_cards_dir = workspace / "model_cards"
    model_cards_dir.mkdir(parents=True, exist_ok=True)

    runs_root = workspace / "datasets" / "exports"
    run_dirs: list[Path] = []
    if runs_root.exists():
        for dataset_dir in sorted(path for path in runs_root.iterdir() if path.is_dir()):
            candidate = dataset_dir / "runs"
            if not candidate.exists():
                continue
            run_dirs.extend(sorted(path for path in candidate.iterdir() if path.is_dir()))

    records = [record for record in (_build_record(workspace, run_dir) for run_dir in run_dirs) if record is not None]
    records = sorted(records, key=lambda item: item["run_id"])

    for record in records:
        card_path: Path = record["card_path"]
        card_path.write_text(_render_card(record), encoding="utf-8")

    registry_path = workspace / "MODEL_REGISTRY.md"
    registry_path.write_text(_render_registry(records), encoding="utf-8")

    return {
        "workspace_root": str(workspace),
        "runs_discovered": len(run_dirs),
        "records_written": len(records),
        "registry_path": str(registry_path),
        "model_cards_dir": str(model_cards_dir),
    }
