from __future__ import annotations

import argparse
import json
import subprocess
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from learning.finetune.config import (
    FineTuneArtifactsConfig,
    FineTuneDatasetConfig,
    FineTuneModelConfig,
    FineTuneRunConfig,
)
from learning.finetune.runtime import inspect_run_environment, write_prepared_text_dataset
from learning.waveforms.segmenter import DEFAULT_MANIFEST_PATH, load_dataset_manifest, resolve_manifest_paths


def _default_source_paths(output_dir: Path, dataset_format: str) -> tuple[Path, Path]:
    if dataset_format == "chat":
        return output_dir / "finetune_chat_train.jsonl", output_dir / "finetune_chat_eval.jsonl"
    if dataset_format == "instruction":
        return output_dir / "finetune_instruction_train.jsonl", output_dir / "finetune_instruction_eval.jsonl"
    raise ValueError(f"Unsupported dataset format: {dataset_format}")


def _count_prepared_metadata(path: Path) -> dict[str, dict[str, int]]:
    problem_counts: Counter[str] = Counter()
    complication_counts: Counter[str] = Counter()
    variant_counts: Counter[str] = Counter()
    rows = 0
    if not path.exists():
        return {
            "rows": 0,
            "primary_problem_counts": {},
            "case_complication_counts": {},
            "input_variant_counts": {},
        }

    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        payload = json.loads(line)
        rows += 1
        if payload.get("primary_problem_id"):
            problem_counts[payload["primary_problem_id"]] += 1
        variant_counts[payload.get("input_variant", "full_wave")] += 1
        for complication in payload.get("case_complications", []):
            complication_counts[complication] += 1
    return {
        "rows": rows,
        "primary_problem_counts": dict(sorted(problem_counts.items())),
        "case_complication_counts": dict(sorted(complication_counts.items())),
        "input_variant_counts": dict(sorted(variant_counts.items())),
    }


def _write_instructions(run_dir: Path, config_path: Path, environment_report_path: Path, python_executable: str) -> Path:
    instructions_path = run_dir / "README.md"
    instructions_path.write_text(
        "\n".join(
            [
                "# Fine-Tuning Run Pack",
                "",
                "1. Put the local Meditron base model in Transformers format at the configured `base_model_path`.",
                "   Important: an Ollama tag like `meditron:7b` is not enough for LoRA training.",
                "2. Install the local training stack:",
                "   `learning/finetune/bootstrap_env.ps1` or an equivalent local setup",
                "3. If you need the official Meditron weights, make sure the Hugging Face repo access has been approved and log in locally with `hf auth login` before downloading.",
                "4. Validate the environment before training:",
                f"   `& \"{python_executable}\" -m learning.finetune.train_local_sft --config \"{config_path}\" --validate-only`",
                "5. Inspect the generated environment report and resolve any blocking issues.",
                f"6. Launch training when the run is ready: `& \"{python_executable}\" -m learning.finetune.train_local_sft --config \"{config_path}\"`",
                "",
                "Artifacts written by this run pack:",
                f"- config: `{config_path.name}`",
                f"- environment report: `{environment_report_path.name}`",
                "- prepared text datasets for SFT (`prepared_*` JSONL)",
                "- adapter outputs and logs under `artifacts/` once training starts",
            ]
        ),
        encoding="utf-8",
    )
    return instructions_path


def _write_launch_script(run_dir: Path, config_path: Path, python_executable: str) -> Path:
    script_path = run_dir / "run_local.ps1"
    script_path.write_text(
        "\n".join(
            [
                f'$config = "{config_path}"',
                f'$python = "{python_executable}"',
                "& $python -m learning.finetune.train_local_sft --config $config --validate-only",
                "& $python -m learning.finetune.train_local_sft --config $config",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    return script_path


def _collect_environment_report(
    config: FineTuneRunConfig,
    config_path: Path,
    repo_root: Path,
) -> dict[str, object]:
    python_candidate = config.python_executable
    if python_candidate and python_candidate != "py" and Path(python_candidate).exists():
        result = subprocess.run(
            [python_candidate, "-m", "learning.finetune.train_local_sft", "--config", str(config_path), "--validate-only"],
            cwd=repo_root,
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode == 0:
            report_path = Path(config.artifacts.environment_report_path)
            if report_path.exists():
                try:
                    return json.loads(report_path.read_text(encoding="utf-8"))
                except json.JSONDecodeError:
                    pass
            try:
                return json.loads(result.stdout)
            except json.JSONDecodeError:
                pass
    return inspect_run_environment(config)


def build_finetune_run(
    manifest_path: str | Path = DEFAULT_MANIFEST_PATH,
    *,
    dataset_format: str = "chat",
    run_name: str | None = None,
    base_model_path: str | None = None,
    tokenizer_path: str | None = None,
    ollama_target_tag: str = "meditron:7b",
) -> dict[str, object]:
    manifest = load_dataset_manifest(manifest_path)
    resolved = resolve_manifest_paths(manifest)
    output_dir: Path = resolved["output_dir"]
    output_dir.mkdir(parents=True, exist_ok=True)

    source_train_path, source_eval_path = _default_source_paths(output_dir, dataset_format)
    if run_name is None:
        run_name = f"{manifest.dataset_id}_{manifest.dataset_version}_{dataset_format}_meditron_lora"

    runs_dir = output_dir / "runs"
    run_dir = runs_dir / run_name
    prepared_dir = run_dir / "prepared"
    artifacts_dir = run_dir / "artifacts"
    logs_dir = artifacts_dir / "logs"
    adapter_output_dir = artifacts_dir / "adapter"
    for directory in [run_dir, prepared_dir, artifacts_dir, logs_dir, adapter_output_dir]:
        directory.mkdir(parents=True, exist_ok=True)

    prepared_train_path = prepared_dir / "prepared_train.jsonl"
    prepared_eval_path = prepared_dir / "prepared_eval.jsonl"
    write_prepared_text_dataset(source_train_path, prepared_train_path, dataset_format=dataset_format)
    if source_eval_path.exists():
        write_prepared_text_dataset(source_eval_path, prepared_eval_path, dataset_format=dataset_format)

    config_path = run_dir / "run_config.json"
    environment_report_path = artifacts_dir / "environment_report.json"
    training_summary_path = artifacts_dir / "training_summary.json"
    export_summary_path = output_dir / "finetune_export_summary.json"
    workspace_root = Path(manifest_path).resolve().parent.parent.parent
    repo_root = workspace_root.parent
    venv_python = workspace_root / ".venv-finetune" / "Scripts" / "python.exe"
    python_executable = str(venv_python) if venv_python.exists() else "py"

    configured_model_path = base_model_path or str(
        (workspace_root / "local_models" / "meditron-7b-transformers")
    )
    config = FineTuneRunConfig(
        run_id=run_name,
        created_at=datetime.now(timezone.utc).isoformat(),
        python_executable=python_executable,
        dataset=FineTuneDatasetConfig(
            dataset_id=manifest.dataset_id,
            dataset_version=manifest.dataset_version,
            dataset_format=dataset_format,
            source_train_path=str(source_train_path),
            source_eval_path=str(source_eval_path) if source_eval_path.exists() else None,
            prepared_train_path=str(prepared_train_path),
            prepared_eval_path=str(prepared_eval_path) if prepared_eval_path.exists() else None,
            export_summary_path=str(export_summary_path) if export_summary_path.exists() else None,
        ),
        model=FineTuneModelConfig(
            base_model_path=configured_model_path,
            tokenizer_path=tokenizer_path,
            ollama_target_tag=ollama_target_tag,
        ),
        artifacts=FineTuneArtifactsConfig(
            run_dir=str(run_dir),
            output_dir=str(adapter_output_dir),
            logging_dir=str(logs_dir),
            adapter_output_dir=str(adapter_output_dir),
            environment_report_path=str(environment_report_path),
            training_summary_path=str(training_summary_path),
        ),
        notes=[
            "This scaffold assumes a local Transformers-compatible base model directory.",
            "Ollama remains the runtime target after fine-tuning, not the training input format.",
        ],
    )

    config_path.write_text(json.dumps(config.model_dump(mode="json"), indent=2, ensure_ascii=False), encoding="utf-8")
    environment = _collect_environment_report(config, config_path, repo_root)
    environment_report_path.write_text(json.dumps(environment, indent=2, ensure_ascii=False), encoding="utf-8")

    instructions_path = _write_instructions(run_dir, config_path, environment_report_path, python_executable)
    launch_script_path = _write_launch_script(run_dir, config_path, python_executable)

    train_profile = _count_prepared_metadata(prepared_train_path)
    eval_profile = _count_prepared_metadata(prepared_eval_path) if prepared_eval_path.exists() else {
        "rows": 0,
        "primary_problem_counts": {},
        "case_complication_counts": {},
    }

    summary = {
        "dataset_id": manifest.dataset_id,
        "dataset_version": manifest.dataset_version,
        "run_id": run_name,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "dataset_format": dataset_format,
        "source_train_path": str(source_train_path),
        "source_eval_path": str(source_eval_path) if source_eval_path.exists() else None,
        "prepared_train_path": str(prepared_train_path),
        "prepared_eval_path": str(prepared_eval_path) if prepared_eval_path.exists() else None,
        "train_profile": train_profile,
        "eval_profile": eval_profile,
        "launch_ready": environment["launch_ready"],
        "blocking_issues": environment["blocking_issues"],
        "config_path": str(config_path),
        "environment_report_path": str(environment_report_path),
        "instructions_path": str(instructions_path),
        "launch_script_path": str(launch_script_path),
        "python_executable": python_executable,
    }
    (run_dir / "run_summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a local Meditron fine-tuning run scaffold.")
    parser.add_argument("--manifest", default=str(DEFAULT_MANIFEST_PATH), help="Path to dataset manifest YAML.")
    parser.add_argument("--dataset-format", choices=["chat", "instruction"], default="chat")
    parser.add_argument("--run-name", default=None, help="Optional run folder name.")
    parser.add_argument("--base-model-path", default=None, help="Local Transformers model directory.")
    parser.add_argument("--tokenizer-path", default=None, help="Optional tokenizer directory.")
    parser.add_argument("--ollama-tag", default="meditron:7b", help="Target Ollama tag after local fine-tuning.")
    args = parser.parse_args()

    summary = build_finetune_run(
        manifest_path=args.manifest,
        dataset_format=args.dataset_format,
        run_name=args.run_name,
        base_model_path=args.base_model_path,
        tokenizer_path=args.tokenizer_path,
        ollama_target_tag=args.ollama_tag,
    )
    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
