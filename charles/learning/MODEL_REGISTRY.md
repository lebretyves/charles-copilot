# CHARLES Model Registry

Central registry for locally trained adapters used by the CHARLES learning pipeline.

## Status vocabulary

- `draft`: initial run, incomplete downstream validation
- `reviewed`: training artifacts reviewed, but not yet validated offline end to end
- `validated`: offline evaluation available and considered usable for research benchmarking
- `runtime-ready`: explicitly approved for runtime integration

## Current adapters

| Adapter | Base model | Dataset | Train / Eval | Status | Latest eval | Runtime |
| --- | --- | --- | --- | --- | --- | --- |
| `vitaldb_waveforms_v1_chat_meditron_lora` | `epfl-llm/meditron-7b` | `vitaldb_waveforms_v1` bootstrap run | `21 / 11` | `draft` | trainer eval only | `no` |
| `vitaldb_waveforms_v1_chat_meditron_lora_cleanprompt` | `epfl-llm/meditron-7b` | `vitaldb_waveforms_v1` bootstrap run | `21 / 11` | `reviewed` | trainer eval only | `no` |
| `vitaldb_waveforms_v1_chat_meditron_lora_allvariants` | `epfl-llm/meditron-7b` | `vitaldb_waveforms_v1` all variants | `270 / 63` | `validated` | balanced12 comparison summary | `no` |

## Promotion rules

An adapter can move to `runtime-ready` only if:

1. The base model is explicitly identified.
2. Dataset lineage is documented.
3. Training parameters are documented.
4. Offline evaluation artifacts are present.
5. Limits and intended use are written clearly.
6. A human review confirms that runtime integration is desired.

## Linked model cards

- [vitaldb_waveforms_v1_chat_meditron_lora](./model_cards/vitaldb_waveforms_v1_chat_meditron_lora.md)
- [vitaldb_waveforms_v1_chat_meditron_lora_cleanprompt](./model_cards/vitaldb_waveforms_v1_chat_meditron_lora_cleanprompt.md)
- [vitaldb_waveforms_v1_chat_meditron_lora_allvariants](./model_cards/vitaldb_waveforms_v1_chat_meditron_lora_allvariants.md)
