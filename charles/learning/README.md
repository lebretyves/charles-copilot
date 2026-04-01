# Learning Pipelines

This directory hosts the learning scaffolding for CHARLES.

The target architecture is intentionally split into three layers:

1. `waveforms/`
   Segment and describe VitalDB waveform windows.
2. `pipelines/`
   Build reusable dataset indexes and later feature/problem datasets.
3. `datasets/`
   Store manifests, exports, and dataset-level documentation.

After dataset generation, the next local fine-tuning phase starts with:
4. `review/`
   Prepare review packs and gold candidates before any local model training.
5. `finetune/`
   Export local SFT formats, prepare training text datasets, and build Meditron run packs.

Current status:
- Step 1 implemented: dataset manifest + weak-label segmentation/indexing.
- Step 2 implemented: feature extraction and baseline problem scoring pipeline.
- Step 3 implemented: explanatory LLM train/eval pipeline fed by structured problem outputs.
- Fine-tuning step 1 implemented: review/gold pack generation.
- Fine-tuning step 2 implemented: local chat/instruction export for SFT.
- Fine-tuning step 3 implemented: local Meditron LoRA/QLoRA run scaffold and environment validation.

Why step 1 comes first:
- it keeps VitalDB as the validated source of truth for now
- it creates a stable dataset contract for later models
- it avoids training directly on raw replay logic

Typical command for the first stage:

```bash
python -m learning.pipelines.build_vitaldb_dataset --manifest learning/datasets/manifests/vitaldb_waveforms.yaml --limit-cases 10
```

Typical commands for the fine-tuning scaffold:

```bash
python -m learning.pipelines.export_finetune_dataset --manifest learning/datasets/manifests/vitaldb_waveforms.yaml --export-mode bootstrap_pending
python -m learning.pipelines.build_finetune_run --manifest learning/datasets/manifests/vitaldb_waveforms.yaml --dataset-format chat
python -m learning.finetune.train_local_sft --config learning/datasets/exports/vitaldb_waveforms_v1/runs/vitaldb_waveforms_v1_chat_meditron_lora/run_config.json --validate-only
python -m learning.pipelines.sync_model_registry
```

Outputs created by step 1:
- a JSONL segment index
- a JSON summary
- weak labels derived from windowed vitals, not from final human interpretation
- case-level complication tags derived from VitalDB metadata and intraoperative labs

Outputs created by step 2:
- a JSONL feature index for each segment
- a JSONL problem index with ranked baseline hypotheses
- a problem summary to track what the baseline engine sees in the corpus
- contextual hypotheses enriched by VitalDB complications such as blood loss, transfusion, vasopressor support, ICU outcome, difficult airway, and metabolic derangement
- a robust sidecar hypotension engine with:
  - double baseline `t0` / `stable_phase`
  - recursive episode memory
  - cause profiles
  - contradiction handling
  - confidence scoring
  - optional waveform and multi-curve analysis

Hypotension workbench:
- model module: `learning/problems/hypotension_model.py`
- evaluation script: `learning/pipelines/evaluate_hypotension_model.py`
- synthetic tests: `tests/test_learning_hypotension_model.py`
- latest detailed evaluation report: `learning/evaluation/hypotension_model_precise_cases/hypotension_evaluation_report.md`

Typical command for the hypotension evaluator:

```bash
python -m learning.pipelines.evaluate_hypotension_model --with-waveforms 3 46 --without-waveforms 52 97
```

Outputs created by step 3:
- `llm_train.jsonl` for local fine-tuning
- `llm_eval.jsonl` for repeatable local evaluation
- `llm_reference.jsonl` with the full structured reference set
- prompts aligned with CHARLES structured-output expectations

Outputs created by fine-tuning step 2:
- `finetune_chat_train.jsonl` / `finetune_chat_eval.jsonl`
- `finetune_instruction_train.jsonl` / `finetune_instruction_eval.jsonl`
- `gold_reference.jsonl` to keep reviewer-aligned targets visible

Outputs created by fine-tuning step 3:
- a run folder under `datasets/exports/<dataset>/runs/`
- `prepared_train.jsonl` / `prepared_eval.jsonl` ready for SFT
- `run_config.json` with local training settings
- `environment_report.json` to confirm whether the machine is ready
- `run_local.ps1` and a run-specific README
- local MLflow tracking metadata pointing to `learning/mlruns` by default
- DVC snapshot metadata linking the run back to the tracked export directory when a `.dvc` snapshot exists

Model governance:
- `MODEL_REGISTRY.md` tracks adapter status across draft, reviewed, validated, and runtime-ready states
- `model_cards/` contains the CHARLES adapter model card template plus filled cards for existing Meditron runs
- new adapters should not be considered runtime-ready until both the registry entry and model card are complete
- MLflow local tracking is now the recommended trace for new fine-tuning and evaluation runs; when `mlflow` is available, train/eval artifacts are copied into the configured local experiment store
- train and eval now trigger a local model-registry sync automatically so the registry and model cards stay aligned with run artifacts
- DVC snapshots now cover the main generated dataset exports; see [DVC_DATASETS.md](/d:/projet%20Iade/charles/docs/DVC_DATASETS.md)

Important:
- weak labels are scaffolding, not final diagnoses
- once CHARLES is connected to live non-public data, later retraining should happen only after review/validation
- a local Ollama tag such as `meditron:7b` is a runtime target, not a LoRA training input; step 3 expects a local Transformers-compatible model directory
- the official `epfl-llm/meditron-7b` repository currently requires Hugging Face approval/authentication before the real weights can be downloaded locally
- MLflow is intentionally non-blocking by default in the scaffold: missing `mlflow` does not stop training unless `tracking.strict=true` is explicitly enabled in `run_config.json`
