# Datasets

This folder stores dataset contracts for the learning side of CHARLES.

For the current step, the key idea is simple:
- keep VitalDB as the validated source dataset
- cut it into reusable waveform windows
- attach weak labels from numeric trends
- preserve enough provenance to rebuild the same segment later

Contents:
- `manifests/`: source and segmentation definitions
- `exports/`: generated JSONL/JSON outputs from builders

Weak-label caveat:
- labels such as `hypotension` or `desaturation` are heuristic labels inferred from numeric windows
- they are suitable for bootstrapping and eval preparation
- they should not be promoted to final clinical truth without later review
