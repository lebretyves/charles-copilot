from __future__ import annotations

import importlib.metadata
import json
from pathlib import Path
from typing import Any

from learning.finetune.config import FineTuneRunConfig
from learning.finetune.schemas import FineTuneChatSample, FineTuneInstructionSample, PreparedTextSample


TOKENIZER_CANDIDATES = [
    "tokenizer.json",
    "tokenizer.model",
    "tokenizer_config.json",
    "spiece.model",
    "vocab.json",
]


def _read_jsonl(path: str | Path) -> list[dict[str, Any]]:
    source = Path(path)
    if not source.exists():
        raise FileNotFoundError(f"JSONL source not found: {source}")
    rows: list[dict[str, Any]] = []
    for line in source.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def render_chat_training_text(sample: FineTuneChatSample) -> str:
    blocks: list[str] = []
    has_assistant_message = False
    for message in sample.messages:
        role = message.role.strip().upper()
        content = message.content.strip()
        blocks.append(f"[{role}]\n{content}")
        if role == "ASSISTANT":
            has_assistant_message = True
    if not has_assistant_message:
        blocks.append(f"[ASSISTANT]\n{sample.assistant_json.strip()}")
    return "\n\n".join(blocks).strip() + "\n"


def render_instruction_training_text(sample: FineTuneInstructionSample) -> str:
    blocks = [
        f"[SYSTEM]\n{sample.system.strip()}",
        f"[USER]\n{sample.instruction.strip()}",
        f"[ASSISTANT]\n{sample.output_json.strip()}",
    ]
    return "\n\n".join(blocks).strip() + "\n"


def prepare_text_samples(dataset_path: str | Path, dataset_format: str) -> list[PreparedTextSample]:
    rows = _read_jsonl(dataset_path)
    prepared: list[PreparedTextSample] = []
    for row in rows:
        if dataset_format == "chat":
            sample = FineTuneChatSample.model_validate(row)
            text = render_chat_training_text(sample)
        elif dataset_format == "instruction":
            sample = FineTuneInstructionSample.model_validate(row)
            text = render_instruction_training_text(sample)
        else:
            raise ValueError(f"Unsupported dataset format: {dataset_format}")

        prepared.append(
            PreparedTextSample(
                sample_id=sample.sample_id,
                split=sample.split,
                input_variant=getattr(sample, "input_variant", "full_wave"),
                target_origin=sample.target_origin,
                primary_problem_id=sample.primary_problem_id,
                primary_severity=sample.primary_severity,
                case_complications=list(sample.case_complications),
                masked_signals=list(getattr(sample, "masked_signals", [])),
                text=text,
            )
        )
    return prepared


def write_prepared_text_dataset(
    source_path: str | Path,
    output_path: str | Path,
    *,
    dataset_format: str,
) -> dict[str, object]:
    prepared = prepare_text_samples(source_path, dataset_format)
    target = Path(output_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w", encoding="utf-8") as handle:
        for sample in prepared:
            handle.write(json.dumps(sample.model_dump(mode="json"), ensure_ascii=False) + "\n")
    return {
        "path": str(target),
        "samples_written": len(prepared),
        "dataset_format": dataset_format,
    }


def _package_version(name: str) -> str | None:
    try:
        return importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError:
        return None


def _detect_torch_runtime() -> dict[str, Any]:
    version = _package_version("torch")
    info: dict[str, Any] = {"installed": version is not None, "version": version}
    if version is None:
        return info
    try:
        import torch  # type: ignore
    except Exception as exc:  # pragma: no cover - defensive import guard
        info["import_error"] = str(exc)
        return info

    info["cuda_available"] = bool(torch.cuda.is_available())
    info["cuda_device_count"] = int(torch.cuda.device_count()) if torch.cuda.is_available() else 0
    if torch.cuda.is_available():
        info["cuda_device_names"] = [torch.cuda.get_device_name(i) for i in range(torch.cuda.device_count())]
        try:
            info["bf16_supported"] = bool(torch.cuda.is_bf16_supported())
        except AttributeError:
            info["bf16_supported"] = False
    return info


def inspect_run_environment(config: FineTuneRunConfig) -> dict[str, Any]:
    required_packages = ["torch", "transformers", "trl", "peft", "accelerate", "datasets"]
    if config.quantization.enabled:
        required_packages.append("bitsandbytes")

    package_versions = {name: _package_version(name) for name in required_packages}

    base_model_dir = Path(config.model.base_model_path)
    tokenizer_dir = Path(config.model.tokenizer_path) if config.model.tokenizer_path else base_model_dir

    train_path = Path(config.dataset.source_train_path)
    eval_path = Path(config.dataset.source_eval_path) if config.dataset.source_eval_path else None
    prepared_train_path = Path(config.dataset.prepared_train_path)
    prepared_eval_path = Path(config.dataset.prepared_eval_path) if config.dataset.prepared_eval_path else None

    model_files = {
        "base_model_exists": base_model_dir.exists(),
        "config_json": str(base_model_dir / "config.json"),
        "config_json_exists": (base_model_dir / "config.json").exists(),
        "tokenizer_dir": str(tokenizer_dir),
        "tokenizer_files_present": [
            name for name in TOKENIZER_CANDIDATES if (tokenizer_dir / name).exists()
        ],
    }

    dataset_checks = {
        "source_train_exists": train_path.exists(),
        "source_eval_exists": eval_path.exists() if eval_path else None,
        "prepared_train_exists": prepared_train_path.exists(),
        "prepared_eval_exists": prepared_eval_path.exists() if prepared_eval_path else None,
        "dataset_format": config.dataset.dataset_format,
    }

    blocking_issues: list[str] = []
    if not dataset_checks["source_train_exists"]:
        blocking_issues.append("Missing source train dataset.")
    if prepared_train_path and not prepared_train_path.exists():
        blocking_issues.append("Missing prepared train dataset.")
    if not model_files["base_model_exists"]:
        blocking_issues.append("Missing local base model directory.")
    elif not model_files["config_json_exists"]:
        blocking_issues.append("Base model directory does not contain config.json.")
    if not model_files["tokenizer_files_present"]:
        blocking_issues.append("Tokenizer files not found in the configured tokenizer/base model directory.")
    for name, version in package_versions.items():
        if version is None:
            blocking_issues.append(f"Missing Python package: {name}")

    gpu = _detect_torch_runtime()
    if gpu.get("installed") and not gpu.get("cuda_available"):
        blocking_issues.append("Torch is installed but CUDA is not available for local fine-tuning.")

    return {
        "run_id": config.run_id,
        "dataset_checks": dataset_checks,
        "model_checks": model_files,
        "package_versions": package_versions,
        "gpu": gpu,
        "blocking_issues": blocking_issues,
        "launch_ready": not blocking_issues,
    }
