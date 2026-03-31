# Model Card: vitaldb_waveforms_v1_chat_meditron_lora_cleanprompt

## Identity

- Adapter name: `vitaldb_waveforms_v1_chat_meditron_lora_cleanprompt`
- Version: `v1-cleanprompt`
- Date: `2026-03-30`
- Status: `reviewed`

## Base model

- Canonical base model: `epfl-llm/meditron-7b`
- Local training path: `learning/local_models/meditron-7b-transformers`
- Runtime target tag: `meditron:7b`
- Model family: `llama_like`

## Intended use

- Primary purpose: same structured perioperative interpretation task as the bootstrap adapter, with a corrected chat prompt format
- Expected inputs: structured chat samples from the CHARLES learning export
- Expected outputs: structured JSON analyses aligned with CHARLES runtime fields
- Explicit non-goals: raw waveform reading, autonomous diagnosis, runtime promotion by default

## Dataset lineage

- Dataset id: `vitaldb_waveforms`
- Dataset version: `v1`
- Train samples: `21`
- Eval samples: `11`
- Input variants: not explicitly persisted in this early run
- Dataset notes: same small bootstrap-sized dataset family as the initial adapter, but with corrected prompt formatting

## Training configuration

- Method: QLoRA / local SFT scaffold
- LoRA / QLoRA parameters: `r=16`, `alpha=32`, `dropout=0.05`, `bias=none`
- Target modules: `q_proj`, `k_proj`, `v_proj`, `o_proj`, `gate_proj`, `up_proj`, `down_proj`
- Quantization: 4-bit `nf4`, `bfloat16`, double quantization enabled
- Sequence length: `2048`
- Batch size: `1`
- Gradient accumulation: `8`
- Learning rate: `1e-4`
- Epochs: `2`
- Seed: `42`
- Hardware: local GPU workflow

## Evaluation

- Offline evaluation artifacts: no downstream comparison summary found for this run
- Trainer metrics:
  - `train_loss = 1.6160`
  - `eval_loss = 1.5079`
  - `eval_mean_token_accuracy = 0.6726`
- Main takeaways: prompt formatting was corrected, but this run did not outperform the later all-variants adapter and should remain a review artifact

## Limitations

- Data limitations: small dataset, incomplete variant lineage, no preserved downstream comparison report
- Model limitations: feature-driven interpretation only, not raw waveform understanding
- Deployment limitations: not approved for runtime integration

## Safety and review

- Human review status: reviewed
- Approved for runtime: no
- Clinical caution: offline research artifact only

## Linked artifacts

- Run config: `learning/datasets/exports/vitaldb_waveforms_v1/runs/vitaldb_waveforms_v1_chat_meditron_lora_cleanprompt/run_config.json`
- Training summary: `learning/datasets/exports/vitaldb_waveforms_v1/runs/vitaldb_waveforms_v1_chat_meditron_lora_cleanprompt/artifacts/training_summary.json`
- Eval trace: `learning/datasets/exports/vitaldb_waveforms_v1/runs/vitaldb_waveforms_v1_chat_meditron_lora_cleanprompt/artifacts/logs/training_trace.jsonl`
- Adapter path: `learning/datasets/exports/vitaldb_waveforms_v1/runs/vitaldb_waveforms_v1_chat_meditron_lora_cleanprompt/artifacts/adapter`
