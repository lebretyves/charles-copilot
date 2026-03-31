import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))


from learning.pipelines.build_problem_dataset import build_problem_dataset
from learning.pipelines.build_signal_dataset import build_signal_dataset
from learning.pipelines.build_vitaldb_dataset import build_segment_index


def _write_test_case_dataset(base_dir: Path) -> tuple[Path, Path, Path]:
    cases_dir = base_dir / "cases"
    waves_dir = base_dir / "waveforms"
    output_dir = base_dir / "exports"
    cases_dir.mkdir(parents=True, exist_ok=True)
    waves_dir.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)

    numeric = pd.DataFrame(
        {
            "time_sec": [0.0, 1.0, 2.0, 3.0],
            "Solar8000/HR": [72.0, 118.0, 116.0, 115.0],
            "Solar8000/PLETH_SPO2": [98.0, 97.0, 91.0, 87.0],
            "Solar8000/ART_MBP": [78.0, 62.0, 58.0, 52.0],
            "Solar8000/ART_SBP": [120.0, 95.0, 88.0, 84.0],
            "Solar8000/ART_DBP": [70.0, 55.0, 50.0, 48.0],
            "Solar8000/ETCO2": [35.0, 34.0, 29.0, 28.0],
            "Solar8000/RR": [14.0, 18.0, 26.0, 27.0],
            "BIS/BIS": [48.0, 42.0, 35.0, 32.0],
        }
    )
    numeric.to_parquet(cases_dir / "case_00001.parquet", index=False)

    wave_500 = pd.DataFrame(
        {
            "time_sec": [0.0, 0.5, 1.0, 1.5, 2.0, 2.5],
            "SNUADC/ECG_II": [0.1, 0.2, -0.3, 0.4, -0.2, 0.1],
            "SNUADC/ART": [80.0, 79.0, 60.0, 58.0, 54.0, 52.0],
        }
    )
    wave_500.to_parquet(waves_dir / "wave_00001_500hz.parquet", index=False)

    wave_25 = pd.DataFrame(
        {
            "time_sec": [0.0, 1.0, 2.0, 3.0],
            "Primus/CO2": [35.0, 34.0, 29.0, 28.0],
            "Primus/AWP": [10.0, 11.0, 22.0, 24.0],
        }
    )
    wave_25.to_parquet(waves_dir / "wave_00001_25hz.parquet", index=False)

    metadata = pd.DataFrame({"caseid": [1], "age": [64], "sex": ["M"], "asa": [3]})
    metadata_path = base_dir / "clinical_metadata.csv"
    metadata.to_csv(metadata_path, index=False)
    return metadata_path, cases_dir, output_dir


def _write_manifest(tmp_path: Path, metadata_path: Path, cases_dir: Path, output_dir: Path) -> Path:
    manifest_path = tmp_path / "manifest.yaml"
    manifest_path.write_text(
        "\n".join(
            [
                "dataset_id: test_vitaldb",
                'dataset_version: "v1"',
                "description: test dataset",
                "source:",
                "  name: VitalDB",
                "  license: test",
                "  citation: test",
                "paths:",
                f"  metadata_csv: {metadata_path.as_posix()}",
                f"  cases_dir: {cases_dir.as_posix()}",
                f"  waveforms_dir: {(tmp_path / 'waveforms').as_posix()}",
                f"  output_dir: {output_dir.as_posix()}",
                "context_columns:",
                "  - age",
                "signal_specs:",
                "  - name: ecg",
                "    file_key: 500hz",
                "    column: SNUADC/ECG_II",
                "    sample_rate_hz: 2",
                "  - name: art",
                "    file_key: 500hz",
                "    column: SNUADC/ART",
                "    sample_rate_hz: 2",
                "  - name: co2",
                "    file_key: 25hz",
                "    column: Primus/CO2",
                "    sample_rate_hz: 1",
                "  - name: awp",
                "    file_key: 25hz",
                "    column: Primus/AWP",
                "    sample_rate_hz: 1",
                "segment_spec:",
                "  window_seconds: 2.0",
                "  stride_seconds: 1.0",
                "  min_signal_coverage: 0.5",
                "  min_required_signals: 2",
            ]
        ),
        encoding="utf-8",
    )
    return manifest_path


def test_build_signal_dataset_exports_npz_windows(tmp_path):
    metadata_path, cases_dir, output_dir = _write_test_case_dataset(tmp_path)
    manifest_path = _write_manifest(tmp_path, metadata_path, cases_dir, output_dir)

    build_segment_index(manifest_path=manifest_path, limit_cases=1, max_segments_per_case=2)
    build_problem_dataset(manifest_path=manifest_path, limit_segments=2)
    summary = build_signal_dataset(manifest_path=manifest_path, target_length=16, limit_segments=2)

    assert summary["samples_written"] == 2
    index_path = Path(summary["index_path"])
    assert index_path.exists()

    rows = [json.loads(line) for line in index_path.read_text(encoding="utf-8").splitlines()]
    assert len(rows) == 2
    payload = np.load(rows[0]["array_path"], allow_pickle=True)
    assert payload["channels"].shape == (4, 16)
    assert payload["availability"].shape == (4,)
