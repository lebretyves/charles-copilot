from __future__ import annotations

import argparse
import inspect
import json
from datetime import datetime, timezone
from pathlib import Path

from learning.finetune.config import FineTuneRunConfig
from learning.finetune.mlflow_tracking import (
    collect_run_params,
    flatten_numeric_metrics,
    start_tracking_session,
)
from learning.finetune.runtime import inspect_run_environment
from learning.model_registry import sync_model_registry


def _load_config(path: str | Path) -> FineTuneRunConfig:
    source = Path(path)
    return FineTuneRunConfig.model_validate_json(source.read_text(encoding="utf-8"))


def _write_json(path: str | Path, payload: dict) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def _read_jsonl_rows(path: str | Path) -> list[dict]:
    source = Path(path)
    rows: list[dict] = []
    for line in source.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def _trace_path(config: FineTuneRunConfig) -> Path:
    return Path(config.artifacts.logging_dir) / "training_trace.jsonl"


def _trace(config: FineTuneRunConfig, stage: str, **details) -> None:
    target = _trace_path(config)
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "stage": stage,
        **details,
    }
    with target.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False) + "\n")
    print(json.dumps(payload, ensure_ascii=False), flush=True)


def validate_run(config_path: str | Path) -> dict:
    config = _load_config(config_path)
    report = inspect_run_environment(config)
    report["validated_at"] = datetime.now(timezone.utc).isoformat()
    _write_json(config.artifacts.environment_report_path, report)
    return report


def train_run(config_path: str | Path) -> dict:
    config = _load_config(config_path)
    tracker = start_tracking_session(
        config,
        stage="train",
        extra_tags={"charles.task": "fine_tuning"},
    )
    _trace(config, "train_run_started", config_path=str(Path(config_path)))
    _trace(config, "mlflow_session_started", **tracker.status_payload())

    report = inspect_run_environment(config)
    report["validated_at"] = datetime.now(timezone.utc).isoformat()
    _write_json(config.artifacts.environment_report_path, report)
    tracker.log_params(collect_run_params(config))
    tracker.log_json(report, "reports/environment_report.json")
    tracker.log_artifact(config_path, artifact_path="reports")
    _trace(config, "environment_validated", launch_ready=report["launch_ready"], blocking_issues=report["blocking_issues"])
    if not report["launch_ready"]:
        tracker.finish(status="FAILED")
        raise RuntimeError("Training environment is not ready. Inspect environment_report.json before retrying.")

    try:
        _trace(config, "import_training_stack_started")
        from datasets import Dataset  # type: ignore
        from peft import LoraConfig, prepare_model_for_kbit_training  # type: ignore
        from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig, TrainerCallback  # type: ignore
        from trl import SFTConfig, SFTTrainer  # type: ignore

        _trace(config, "import_training_stack_completed")
    except ImportError as exc:  # pragma: no cover - depends on local training env
        tracker.log_text(str(exc), "reports/training_import_error.txt")
        tracker.finish(status="FAILED")
        raise RuntimeError(
            "Local fine-tuning dependencies are not fully installed. "
            "Install torch, transformers, trl, peft, accelerate, datasets and bitsandbytes."
        ) from exc

    model_kwargs = {
        "trust_remote_code": config.model.trust_remote_code,
    }
    if config.quantization.enabled:
        compute_dtype_name = config.quantization.compute_dtype
        try:
            import torch  # type: ignore
        except ImportError as exc:  # pragma: no cover - guarded above
            tracker.log_text(str(exc), "reports/training_torch_import_error.txt")
            tracker.finish(status="FAILED")
            raise RuntimeError("Torch is required for local training.") from exc

        model_kwargs["quantization_config"] = BitsAndBytesConfig(
            load_in_4bit=config.quantization.load_in_4bit,
            bnb_4bit_quant_type=config.quantization.quant_type,
            bnb_4bit_compute_dtype=getattr(torch, compute_dtype_name),
            bnb_4bit_use_double_quant=config.quantization.use_double_quant,
        )
        model_kwargs["device_map"] = "auto"

    tokenizer_path = config.model.tokenizer_path or config.model.base_model_path
    _trace(config, "tokenizer_load_started", tokenizer_path=tokenizer_path)
    tokenizer = AutoTokenizer.from_pretrained(tokenizer_path, trust_remote_code=config.model.trust_remote_code)
    if tokenizer.pad_token is None and tokenizer.eos_token is not None:
        tokenizer.pad_token = tokenizer.eos_token
    tokenizer.padding_side = "right"
    _trace(
        config,
        "tokenizer_load_completed",
        tokenizer_path=tokenizer_path,
        pad_token=str(tokenizer.pad_token),
        eos_token=str(tokenizer.eos_token),
    )

    _trace(config, "model_load_started", base_model_path=config.model.base_model_path)
    model = AutoModelForCausalLM.from_pretrained(config.model.base_model_path, **model_kwargs)
    if config.quantization.enabled:
        _trace(config, "prepare_model_for_kbit_training_started")
        model = prepare_model_for_kbit_training(model)
        _trace(config, "prepare_model_for_kbit_training_completed")
    _trace(config, "model_load_completed", quantized=config.quantization.enabled)

    peft_config = LoraConfig(
        r=config.lora.r,
        lora_alpha=config.lora.alpha,
        lora_dropout=config.lora.dropout,
        bias=config.lora.bias,
        target_modules=config.lora.target_modules,
        task_type="CAUSAL_LM",
    )

    dataset_files = {
        "train": config.dataset.prepared_train_path,
    }
    if config.dataset.prepared_eval_path:
        dataset_files["eval"] = config.dataset.prepared_eval_path

    _trace(config, "dataset_rows_read_started", dataset_files=dataset_files)
    train_rows = _read_jsonl_rows(config.dataset.prepared_train_path)
    eval_rows = _read_jsonl_rows(config.dataset.prepared_eval_path) if config.dataset.prepared_eval_path else []
    tracker.log_metrics(
        {
            "dataset_train_rows": float(len(train_rows)),
            "dataset_eval_rows": float(len(eval_rows)),
        }
    )
    _trace(
        config,
        "dataset_rows_read_completed",
        train_rows=len(train_rows),
        eval_rows=len(eval_rows),
    )
    _trace(config, "dataset_objects_build_started")
    train_dataset = Dataset.from_list(train_rows)
    eval_dataset = Dataset.from_list(eval_rows) if eval_rows else None
    _trace(
        config,
        "dataset_load_completed",
        train_rows=len(train_dataset),
        eval_rows=len(eval_dataset) if eval_dataset is not None else 0,
    )

    sft_signature = inspect.signature(SFTConfig)
    sft_kwargs = {
        "output_dir": config.artifacts.output_dir,
        "dataset_text_field": "text",
        "learning_rate": config.training.learning_rate,
        "num_train_epochs": config.training.num_train_epochs,
        "per_device_train_batch_size": config.training.per_device_train_batch_size,
        "per_device_eval_batch_size": config.training.per_device_eval_batch_size,
        "gradient_accumulation_steps": config.training.gradient_accumulation_steps,
        "warmup_ratio": config.training.warmup_ratio,
        "weight_decay": config.training.weight_decay,
        "logging_steps": config.training.logging_steps,
        "save_steps": config.training.save_steps,
        "eval_steps": config.training.eval_steps,
        "save_total_limit": config.training.save_total_limit,
        "gradient_checkpointing": config.training.gradient_checkpointing,
        "packing": config.training.packing,
        "seed": config.training.seed,
        "optim": config.training.optim,
        "lr_scheduler_type": config.training.lr_scheduler_type,
        "logging_dir": config.artifacts.logging_dir,
        "bf16": config.quantization.compute_dtype == "bfloat16",
        "fp16": config.quantization.compute_dtype == "float16",
        "report_to": [],
    }
    if "max_length" in sft_signature.parameters:
        sft_kwargs["max_length"] = config.training.max_seq_length
    elif "max_seq_length" in sft_signature.parameters:
        sft_kwargs["max_seq_length"] = config.training.max_seq_length
    if eval_dataset is not None:
        if "eval_strategy" in sft_signature.parameters:
            sft_kwargs["eval_strategy"] = "steps"
        elif "evaluation_strategy" in sft_signature.parameters:
            sft_kwargs["evaluation_strategy"] = "steps"
    else:
        if "eval_strategy" in sft_signature.parameters:
            sft_kwargs["eval_strategy"] = "no"
        elif "evaluation_strategy" in sft_signature.parameters:
            sft_kwargs["evaluation_strategy"] = "no"

    _trace(config, "sft_config_build_started")
    sft_args = SFTConfig(**sft_kwargs)
    _trace(config, "sft_config_build_completed")

    trainer_kwargs = {
        "model": model,
        "args": sft_args,
        "train_dataset": train_dataset,
        "eval_dataset": eval_dataset,
        "peft_config": peft_config,
    }
    trainer_signature = inspect.signature(SFTTrainer)
    if "processing_class" in trainer_signature.parameters:
        trainer_kwargs["processing_class"] = tokenizer
    elif "tokenizer" in trainer_signature.parameters:
        trainer_kwargs["tokenizer"] = tokenizer

    class TraceCallback(TrainerCallback):
        def on_train_begin(self, args, state, control, **kwargs):
            _trace(config, "trainer_on_train_begin", global_step=int(state.global_step), max_steps=int(state.max_steps))

        def on_step_end(self, args, state, control, **kwargs):
            _trace(config, "trainer_on_step_end", global_step=int(state.global_step))

        def on_log(self, args, state, control, logs=None, **kwargs):
            _trace(config, "trainer_on_log", global_step=int(state.global_step), logs=logs or {})

        def on_train_end(self, args, state, control, **kwargs):
            _trace(config, "trainer_on_train_end", global_step=int(state.global_step))

    _trace(config, "trainer_init_started")
    trainer = SFTTrainer(**trainer_kwargs)
    trainer.add_callback(TraceCallback)
    _trace(config, "trainer_init_completed")

    try:
        _trace(config, "trainer_train_started")
        train_result = trainer.train()
        train_metrics = dict(train_result.metrics)
        tracker.log_metrics(flatten_numeric_metrics({"train": train_metrics}))
        _trace(config, "trainer_train_completed", metrics=train_metrics)
        _trace(config, "save_model_started", adapter_output_dir=config.artifacts.adapter_output_dir)
        trainer.save_model(config.artifacts.adapter_output_dir)
        _trace(config, "save_model_completed", adapter_output_dir=config.artifacts.adapter_output_dir)
        _trace(config, "save_tokenizer_started", adapter_output_dir=config.artifacts.adapter_output_dir)
        tokenizer.save_pretrained(config.artifacts.adapter_output_dir)
        _trace(config, "save_tokenizer_completed", adapter_output_dir=config.artifacts.adapter_output_dir)

        summary = {
            "run_id": config.run_id,
            "trained_at": datetime.now(timezone.utc).isoformat(),
            "train_metrics": train_metrics,
            "adapter_output_dir": config.artifacts.adapter_output_dir,
            "tracking": tracker.status_payload(),
        }
        _write_json(config.artifacts.training_summary_path, summary)
        registry_sync = sync_model_registry()
        summary["registry_sync"] = registry_sync
        _write_json(config.artifacts.training_summary_path, summary)
        tracker.log_json(summary, "reports/training_summary.json")
        tracker.log_artifact(config.artifacts.training_summary_path, artifact_path="reports")
        tracker.log_artifact(_trace_path(config), artifact_path="reports")
        tracker.log_artifacts(config.artifacts.adapter_output_dir, artifact_path="adapter")
        tracker.log_json(registry_sync, "reports/model_registry_sync.json")
        _trace(config, "training_summary_written", training_summary_path=config.artifacts.training_summary_path)
        tracker.finish(status="FINISHED")
        return summary
    except Exception as exc:
        tracker.log_text(str(exc), "reports/training_failure.txt")
        tracker.log_artifact(_trace_path(config), artifact_path="reports")
        tracker.finish(status="FAILED")
        _trace(config, "trainer_train_failed", error=str(exc))
        raise


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate or launch a local Meditron fine-tuning scaffold.")
    parser.add_argument("--config", required=True, help="Path to run_config.json.")
    parser.add_argument("--validate-only", action="store_true", help="Only validate the local training environment.")
    args = parser.parse_args()

    if args.validate_only:
        report = validate_run(args.config)
        print(json.dumps(report, indent=2, ensure_ascii=False))
        return

    summary = train_run(args.config)
    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
