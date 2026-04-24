# DVC Dataset Lineage

This project now uses DVC to snapshot generated dataset exports without putting the heavy export directories directly in Git.

## What is tracked

- `learning/datasets/exports/vitaldb_waveforms_v1`
- `learning/datasets/exports/vitaldb_waveforms_local50_dense`

Tracked snapshot files:

- [vitaldb_waveforms_v1.dvc](/d:/projet%20Iade/charles/learning/datasets/exports/vitaldb_waveforms_v1.dvc)
- [vitaldb_waveforms_local50_dense.dvc](/d:/projet%20Iade/charles/learning/datasets/exports/vitaldb_waveforms_local50_dense.dvc)

## What is intentionally excluded

- `learning/datasets/exports/vitaldb_waveforms_v1/runs/`
- `learning/datasets/exports/vitaldb_waveforms_local50_dense/logs/`

Reason:
- `runs/` contains training/evaluation/model artifacts, which are governed by MLflow and the model registry, not by dataset snapshotting.
- dense export `logs/` are operational noise, not dataset lineage.

## Local workflow

Install tooling in the local learning environment:

```powershell
& "D:\projet Iade\charles\learning\.venv-finetune\Scripts\python.exe" -m pip install -r "D:\projet Iade\charles\learning\finetune\requirements.txt"
```

Refresh the dataset snapshots after regenerating exports:

```powershell
& "D:\projet Iade\charles\learning\.venv-finetune\Scripts\python.exe" -m dvc add "charles/learning/datasets/exports/vitaldb_waveforms_v1" "charles/learning/datasets/exports/vitaldb_waveforms_local50_dense"
```

Useful checks:

```powershell
& "D:\projet Iade\charles\learning\.venv-finetune\Scripts\python.exe" -m dvc status
& "D:\projet Iade\charles\learning\.venv-finetune\Scripts\python.exe" -m dvc diff
```

## Link with runs and model cards

- `build_finetune_run.py` now reads the export snapshot metadata and stores:
  - `dataset.dvc_snapshot_path`
  - `dataset.dvc_tracked_path`
  - `dataset.dvc_md5`
- model cards and [MODEL_REGISTRY.md](/d:/projet%20Iade/charles/learning/MODEL_REGISTRY.md) can now point back to the dataset snapshot lineage.

## Current snapshot metadata

- `vitaldb_waveforms_v1`
  - md5: `33cf19ccdb9971ae6a62eff07e5c3637.dir`
  - files: `143`
  - size: `16176015`
- `vitaldb_waveforms_local50_dense`
  - md5: `cb70de4f3de660564150135b1b815ca6.dir`
  - files: `2`
  - size: `246345578`
