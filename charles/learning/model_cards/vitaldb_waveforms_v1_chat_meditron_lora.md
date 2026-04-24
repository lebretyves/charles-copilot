# Model Card: vitaldb_waveforms_v1_chat_meditron_lora

## Identity

- Adapter name: `vitaldb_waveforms_v1_chat_meditron_lora`
- Version: `chat_meditron_lora`
- Date: `2026-03-30`
- Status: `draft`

## Base model

- Canonical base model: `epfl-llm/meditron-7b`
- Local training path: `learning/local_models/meditron-7b-transformers`
- Runtime target tag: `meditron:7b`
- Model family: `llama_like`

## Intended use

- Primary purpose: local structured perioperative interpretation for `chat`-format CHARLES samples
- Expected inputs: CHARLES structured train/eval samples generated from VitalDB-derived features, alerts, and context
- Expected outputs: structured JSON analyses for the CHARLES worker / review pipeline
- Explicit non-goals: raw waveform primary detection, unsupervised online learning, autonomous clinical use

## Dataset lineage

- Dataset id: `vitaldb_waveforms`
- Dataset version: `v1`
- Train samples: `21`
- Eval samples: `11`
- Input variants: `full_wave`, `no_wave`, `partial_wave`
- Dataset notes:
  - `333` exported samples in the dataset release
  - export mode: `bootstrap_pending`
  - top train complications: ephedrine_support=17, vasopressor_support=17, intraop_acidemia_lab=12, postop_icu_admission=9, intraop_anemia_lab=8
- DVC snapshot: `learning/datasets/exports/vitaldb_waveforms_v1.dvc`
- DVC md5: `33cf19ccdb9971ae6a62eff07e5c3637.dir`

## Training configuration

- Method: QLoRA / local SFT scaffold
- LoRA / QLoRA parameters: `r=16`, `alpha=32`, `dropout=0.05`, `bias=none`
- Target modules: `q_proj`, `k_proj`, `v_proj`, `o_proj`, `gate_proj`, `up_proj`, `down_proj`
- Quantization: 4-bit `nf4`, `bfloat16`, double quantization enabled
- Sequence length: `2048`
- Batch size: `1`
- Gradient accumulation: `8`
- Learning rate: `0.0001`
- Epochs: `2.0`
- Seed: `42`
- Hardware: NVIDIA GeForce RTX 5060 Laptop GPU

## Evaluation

- Trainer metrics:
  - `train_loss = 1.3735`
  - `train_runtime = 246.8033`
  - `eval_loss = 1.2746`
  - `eval_mean_token_accuracy = 0.7234`
- Downstream comparison metrics:
  - No downstream comparison artifact available.
- Main takeaways: No downstream comparison artifact available yet.

## Limitations

- Data limitations: trained on public anonymized VitalDB-derived structured data, not on live hospital data
- Model limitations: reasons over structured features, alerts, and context; it does not replace a dedicated raw-waveform signal model
- Deployment limitations: validated offline only; runtime integration still requires an explicit promotion step

## Safety and review

- Human review status: reviewed as a historical bootstrap run
- Approved for runtime: no
- Clinical caution: for research and offline comparison only

## Linked artifacts

- Run config: `learning/datasets/exports/vitaldb_waveforms_v1/runs/vitaldb_waveforms_v1_chat_meditron_lora/run_config.json`
- Training summary: `learning/datasets/exports/vitaldb_waveforms_v1/runs/vitaldb_waveforms_v1_chat_meditron_lora/artifacts/training_summary.json`
- Evaluation summary: `learning/datasets/exports/vitaldb_waveforms_v1/runs/vitaldb_waveforms_v1_chat_meditron_lora/artifacts/evaluation/comparison_summary.json`
- Adapter path: `learning/datasets/exports/vitaldb_waveforms_v1/runs/vitaldb_waveforms_v1_chat_meditron_lora/artifacts/adapter`
