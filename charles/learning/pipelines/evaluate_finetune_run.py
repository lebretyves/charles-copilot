from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from learning.finetune import (
    aggregate_record_metrics,
    comparison_delta,
    extract_first_json_object,
    load_evaluation_targets,
    score_prediction,
)
from learning.finetune.config import FineTuneRunConfig
from learning.llm.schemas import ExplanationTarget


def _load_config(path: str | Path) -> FineTuneRunConfig:
    source = Path(path)
    return FineTuneRunConfig.model_validate_json(source.read_text(encoding="utf-8"))


def _default_eval_source(config: FineTuneRunConfig) -> Path:
    if config.dataset.source_eval_path:
        return Path(config.dataset.source_eval_path)
    raise FileNotFoundError("No source eval dataset configured in run_config.json.")


def _variant_artifact_paths(run_dir: Path, variant_name: str) -> tuple[Path, Path]:
    eval_dir = run_dir / "artifacts" / "evaluation"
    eval_dir.mkdir(parents=True, exist_ok=True)
    return eval_dir / f"{variant_name}_records.jsonl", eval_dir / f"{variant_name}_summary.json"


def _load_generation_stack(config: FineTuneRunConfig):
    try:
        import torch  # type: ignore
        from peft import PeftModel  # type: ignore
        from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig  # type: ignore
    except ImportError as exc:  # pragma: no cover - depends on local env
        raise RuntimeError("Evaluation requires the local fine-tuning environment packages.") from exc

    model_kwargs: dict[str, Any] = {
        "trust_remote_code": config.model.trust_remote_code,
    }
    if config.quantization.enabled:
        model_kwargs["quantization_config"] = BitsAndBytesConfig(
            load_in_4bit=config.quantization.load_in_4bit,
            bnb_4bit_quant_type=config.quantization.quant_type,
            bnb_4bit_compute_dtype=getattr(torch, config.quantization.compute_dtype),
            bnb_4bit_use_double_quant=config.quantization.use_double_quant,
        )
        model_kwargs["device_map"] = "auto"

    tokenizer_path = config.model.tokenizer_path or config.model.base_model_path
    tokenizer = AutoTokenizer.from_pretrained(tokenizer_path, trust_remote_code=config.model.trust_remote_code)
    if tokenizer.pad_token is None and tokenizer.eos_token is not None:
        tokenizer.pad_token = tokenizer.eos_token
    tokenizer.padding_side = "right"

    model = AutoModelForCausalLM.from_pretrained(config.model.base_model_path, **model_kwargs)
    return torch, tokenizer, model, PeftModel


def _generate_response(torch_module, tokenizer, model, prompt: str, max_new_tokens: int) -> str:
    encoded = tokenizer(prompt, return_tensors="pt")
    device = model.device
    encoded = {key: value.to(device) for key, value in encoded.items()}
    with torch_module.inference_mode():
        generated = model.generate(
            **encoded,
            do_sample=False,
            max_new_tokens=max_new_tokens,
            pad_token_id=tokenizer.pad_token_id,
            eos_token_id=tokenizer.eos_token_id,
        )
    input_length = encoded["input_ids"].shape[-1]
    new_tokens = generated[0][input_length:]
    return tokenizer.decode(new_tokens, skip_special_tokens=True).strip()


def _resolve_generation_budget(tokenizer, target, configured_max_new_tokens: int) -> int:
    expected_tokens = tokenizer(target.expected_output_json, return_tensors="pt")["input_ids"].shape[-1]
    return max(configured_max_new_tokens, int(expected_tokens) + 64)


def _evaluate_variant(
    *,
    variant_name: str,
    targets,
    torch_module,
    tokenizer,
    model,
    max_new_tokens: int,
    run_dir: Path,
) -> dict[str, Any]:
    records_path, summary_path = _variant_artifact_paths(run_dir, variant_name)
    records: list[dict[str, Any]] = []
    with records_path.open("w", encoding="utf-8") as handle:
        for target in targets:
            sample_max_new_tokens = _resolve_generation_budget(tokenizer, target, max_new_tokens)
            raw_output = _generate_response(
                torch_module,
                tokenizer,
                model,
                target.prompt,
                max_new_tokens=sample_max_new_tokens,
            )
            raw_json, json_snippet = extract_first_json_object(raw_output)
            parse_ok = raw_json is not None
            prediction = None
            schema_ok = False
            validation_error = None
            if raw_json is not None:
                try:
                    prediction = ExplanationTarget.model_validate(raw_json)
                    schema_ok = True
                except Exception as exc:  # pragma: no cover - exercised in real eval
                    validation_error = str(exc)

            metrics = score_prediction(
                prediction,
                target.expected_output,
                parse_ok=parse_ok,
                schema_ok=schema_ok,
            )
            record = {
                "variant": variant_name,
                "sample_id": target.sample_id,
                "primary_problem_id": target.primary_problem_id,
                "primary_severity": target.primary_severity,
                "case_complications": target.case_complications,
                "prompt": target.prompt,
                "raw_output": raw_output,
                "json_snippet": json_snippet,
                "parse_ok": parse_ok,
                "schema_ok": schema_ok,
                "validation_error": validation_error,
                "prediction": prediction.model_dump(mode="json") if prediction else None,
                "expected_output": target.expected_output.model_dump(mode="json"),
                "metrics": metrics,
            }
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
            records.append(record)

    summary = aggregate_record_metrics(records)
    summary.update(
        {
            "variant": variant_name,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "records_path": str(records_path),
        }
    )
    summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    return summary


def evaluate_finetune_run(
    config_path: str | Path,
    *,
    eval_source_path: str | Path | None = None,
    max_samples: int | None = None,
    max_new_tokens: int = 320,
    variants: str = "both",
) -> dict[str, Any]:
    config = _load_config(config_path)
    eval_path = Path(eval_source_path) if eval_source_path else _default_eval_source(config)
    targets = load_evaluation_targets(eval_path, config.dataset.dataset_format)
    if max_samples is not None:
        targets = targets[:max_samples]

    run_dir = Path(config.artifacts.run_dir)
    torch_module, tokenizer, base_model, peft_model_cls = _load_generation_stack(config)
    base_summary = None
    adapter_summary = None

    if variants in {"base", "both"}:
        base_summary = _evaluate_variant(
            variant_name="base",
            targets=targets,
            torch_module=torch_module,
            tokenizer=tokenizer,
            model=base_model,
            max_new_tokens=max_new_tokens,
            run_dir=run_dir,
        )

    if variants in {"adapter", "both"}:
        adapter_path = Path(config.artifacts.adapter_output_dir)
        adapter_model = peft_model_cls.from_pretrained(base_model, adapter_path)
        adapter_summary = _evaluate_variant(
            variant_name="adapter",
            targets=targets,
            torch_module=torch_module,
            tokenizer=tokenizer,
            model=adapter_model,
            max_new_tokens=max_new_tokens,
            run_dir=run_dir,
        )

    comparison = {
        "run_id": config.run_id,
        "evaluated_at": datetime.now(timezone.utc).isoformat(),
        "samples_evaluated": len(targets),
        "eval_source_path": str(eval_path),
        "base": base_summary,
        "adapter": adapter_summary,
        "variants": variants,
        "delta": comparison_delta(base_summary, adapter_summary) if base_summary and adapter_summary else None,
    }
    comparison_path = run_dir / "artifacts" / "evaluation" / "comparison_summary.json"
    comparison_path.parent.mkdir(parents=True, exist_ok=True)
    comparison_path.write_text(json.dumps(comparison, indent=2, ensure_ascii=False), encoding="utf-8")
    comparison["comparison_path"] = str(comparison_path)
    return comparison


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate base Meditron vs LoRA adapter on the local eval set.")
    parser.add_argument("--config", required=True, help="Path to run_config.json.")
    parser.add_argument("--eval-source", default=None, help="Optional eval dataset path.")
    parser.add_argument("--max-samples", type=int, default=None, help="Optional cap on evaluated samples.")
    parser.add_argument("--max-new-tokens", type=int, default=320, help="Max generated tokens per sample.")
    parser.add_argument(
        "--variants",
        choices=("base", "adapter", "both"),
        default="both",
        help="Choose whether to evaluate the base model, the adapter, or both.",
    )
    args = parser.parse_args()

    summary = evaluate_finetune_run(
        args.config,
        eval_source_path=args.eval_source,
        max_samples=args.max_samples,
        max_new_tokens=args.max_new_tokens,
        variants=args.variants,
    )
    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
