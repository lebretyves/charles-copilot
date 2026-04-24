import json
import sys
from pathlib import Path


ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))


from learning.model_registry import sync_model_registry


def _write_run_artifacts(workspace_root: Path, run_id: str) -> Path:
    dataset_export_dir = workspace_root / "datasets" / "exports" / "test_dataset_v1"
    run_dir = dataset_export_dir / "runs" / run_id
    adapter_dir = run_dir / "artifacts" / "adapter" / "checkpoint-4"
    eval_dir = run_dir / "artifacts" / "evaluation"
    adapter_dir.mkdir(parents=True, exist_ok=True)
    eval_dir.mkdir(parents=True, exist_ok=True)
    (workspace_root / "model_cards").mkdir(parents=True, exist_ok=True)

    prepared_train = run_dir / "prepared" / "prepared_train.jsonl"
    prepared_eval = run_dir / "prepared" / "prepared_eval.jsonl"
    prepared_train.parent.mkdir(parents=True, exist_ok=True)
    prepared_train.write_text('{"sample_id":"a"}\n{"sample_id":"b"}\n', encoding="utf-8")
    prepared_eval.write_text('{"sample_id":"c"}\n', encoding="utf-8")

    export_summary_path = dataset_export_dir / "finetune_export_summary.json"
    export_summary_path.write_text(
        json.dumps(
            {
                "dataset_id": "test_dataset",
                "dataset_version": "v1",
                "samples_exported": 3,
                "export_mode": "bootstrap_pending",
                "input_variant_counts": {"full_wave": 1, "no_wave": 1, "partial_wave": 1},
            }
        ),
        encoding="utf-8",
    )
    (dataset_export_dir.parent / "test_dataset_v1.dvc").write_text(
        "\n".join(
            [
                "outs:",
                "- md5: fake-dataset-md5.dir",
                "  size: 456",
                "  nfiles: 3",
                "  hash: md5",
                "  path: test_dataset_v1",
            ]
        ),
        encoding="utf-8",
    )

    run_config = {
        "run_id": run_id,
        "created_at": "2026-03-31T00:00:00+00:00",
        "dataset": {
            "dataset_id": "test_dataset",
            "dataset_version": "v1",
            "dataset_format": "chat",
            "source_train_path": str(dataset_export_dir / "finetune_chat_train.jsonl"),
            "source_eval_path": str(dataset_export_dir / "finetune_chat_eval.jsonl"),
            "prepared_train_path": str(prepared_train),
            "prepared_eval_path": str(prepared_eval),
            "export_summary_path": str(export_summary_path),
        },
        "model": {
            "base_model_path": str(workspace_root / "local_models" / "meditron-7b-transformers"),
            "ollama_target_tag": "meditron:7b",
            "model_family": "llama_like",
            "trust_remote_code": False,
        },
        "lora": {
            "r": 16,
            "alpha": 32,
            "dropout": 0.05,
            "bias": "none",
            "target_modules": ["q_proj", "k_proj"],
        },
        "quantization": {
            "enabled": True,
            "load_in_4bit": True,
            "quant_type": "nf4",
            "compute_dtype": "bfloat16",
            "use_double_quant": True,
        },
        "training": {
            "max_seq_length": 2048,
            "learning_rate": 0.0001,
            "num_train_epochs": 2.0,
            "per_device_train_batch_size": 1,
            "per_device_eval_batch_size": 1,
            "gradient_accumulation_steps": 8,
            "warmup_ratio": 0.03,
            "weight_decay": 0.0,
            "logging_steps": 10,
            "save_steps": 50,
            "eval_steps": 50,
            "save_total_limit": 2,
            "gradient_checkpointing": True,
            "packing": False,
            "seed": 42,
            "optim": "paged_adamw_8bit",
            "lr_scheduler_type": "cosine",
        },
        "artifacts": {
            "run_dir": str(run_dir),
            "output_dir": str(run_dir / "artifacts" / "adapter"),
            "logging_dir": str(run_dir / "artifacts" / "logs"),
            "adapter_output_dir": str(run_dir / "artifacts" / "adapter"),
            "environment_report_path": str(run_dir / "artifacts" / "environment_report.json"),
            "training_summary_path": str(run_dir / "artifacts" / "training_summary.json"),
        },
    }
    (run_dir / "run_config.json").write_text(json.dumps(run_config), encoding="utf-8")

    (run_dir / "run_summary.json").write_text(
        json.dumps(
            {
                "train_profile": {
                    "rows": 2,
                    "input_variant_counts": {"full_wave": 1, "partial_wave": 1},
                    "case_complication_counts": {"major_blood_loss": 1, "vasopressor_support": 2},
                },
                "eval_profile": {
                    "rows": 1,
                },
            }
        ),
        encoding="utf-8",
    )

    (run_dir / "artifacts" / "training_summary.json").write_text(
        json.dumps(
            {
                "run_id": run_id,
                "trained_at": "2026-03-31T10:00:00+00:00",
                "train_metrics": {
                    "train_loss": 0.42,
                    "train_runtime": 123.0,
                },
                "adapter_output_dir": str(run_dir / "artifacts" / "adapter"),
            }
        ),
        encoding="utf-8",
    )

    (run_dir / "artifacts" / "environment_report.json").write_text(
        json.dumps(
            {
                "gpu": {
                    "cuda_device_names": ["RTX Test GPU"],
                }
            }
        ),
        encoding="utf-8",
    )

    (eval_dir / "comparison_summary.json").write_text(
        json.dumps(
            {
                "run_id": run_id,
                "evaluated_at": "2026-03-31T11:00:00+00:00",
                "samples_evaluated": 1,
                "adapter": {
                    "overall_score": 0.91,
                    "json_parse_ok": 1.0,
                    "schema_valid": 1.0,
                    "call_mar_accuracy": 1.0,
                },
            }
        ),
        encoding="utf-8",
    )

    (adapter_dir / "trainer_state.json").write_text(
        json.dumps(
            {
                "global_step": 4,
                "log_history": [
                    {
                        "step": 4,
                        "eval_loss": 0.33,
                        "eval_mean_token_accuracy": 0.88,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    return run_dir


def test_sync_model_registry_generates_registry_and_card(tmp_path):
    workspace_root = tmp_path / "learning"
    run_id = "test_dataset_v1_chat_meditron_lora_auto"
    _write_run_artifacts(workspace_root, run_id)

    summary = sync_model_registry(workspace_root)

    assert summary["records_written"] == 1
    registry_text = (workspace_root / "MODEL_REGISTRY.md").read_text(encoding="utf-8")
    card_text = (workspace_root / "model_cards" / f"{run_id}.md").read_text(encoding="utf-8")

    assert f"`{run_id}`" in registry_text
    assert "`validated`" in registry_text
    assert "overall_score=0.9100" in registry_text
    assert f"# Model Card: {run_id}" in card_text
    assert "- Status: `validated`" in card_text
    assert "`eval_loss = 0.3300`" in card_text
    assert "`overall_score = 0.9100`" in card_text
    assert "RTX Test GPU" in card_text
    assert "test_dataset_v1.dvc" in card_text
    assert "fake-dataset-md5.dir" in card_text


def test_sync_model_registry_preserves_manual_runtime_status(tmp_path):
    workspace_root = tmp_path / "learning"
    run_id = "test_dataset_v1_chat_meditron_lora_runtime"
    _write_run_artifacts(workspace_root, run_id)
    existing_card = workspace_root / "model_cards" / f"{run_id}.md"
    existing_card.parent.mkdir(parents=True, exist_ok=True)
    existing_card.write_text(
        "\n".join(
            [
                f"# Model Card: {run_id}",
                "",
                "## Identity",
                "",
                "- Status: `runtime-ready`",
                "",
                "## Safety and review",
                "",
                "- Human review status: approved for runtime use",
                "- Approved for runtime: yes",
                "- Clinical caution: keep human supervision",
            ]
        ),
        encoding="utf-8",
    )

    sync_model_registry(workspace_root)
    card_text = existing_card.read_text(encoding="utf-8")
    registry_text = (workspace_root / "MODEL_REGISTRY.md").read_text(encoding="utf-8")

    assert "- Status: `runtime-ready`" in card_text
    assert "- Approved for runtime: yes" in card_text
    assert "keep human supervision" in card_text
    assert "`runtime-ready`" in registry_text
    assert "`yes`" in registry_text
