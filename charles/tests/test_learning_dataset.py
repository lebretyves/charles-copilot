import json
import sys
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))


from learning.pipelines.build_vitaldb_dataset import build_segment_index
from learning.waveforms import iter_case_segments, load_dataset_manifest
from learning.waveforms.labels import infer_weak_labels
from learning.waveforms.schemas import SegmentSpec, SignalSpec, VitalDBDatasetManifest


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
            "Solar8000/PLETH_SPO2": [98.0, 97.0, 91.0, 89.0],
            "Solar8000/ART_MBP": [78.0, 62.0, 58.0, 57.0],
            "Solar8000/ART_SBP": [120.0, 95.0, 88.0, 86.0],
            "Solar8000/ART_DBP": [70.0, 55.0, 50.0, 48.0],
            "Solar8000/ETCO2": [35.0, 34.0, 29.0, 28.0],
            "Solar8000/RR": [14.0, 18.0, 26.0, 27.0],
            "BIS/BIS": [48.0, 42.0, 35.0, 32.0],
        }
    )
    numeric.to_parquet(cases_dir / "case_00001.parquet", index=False)

    wave_500 = pd.DataFrame(
        {
            "time_sec": [0.0, 0.5, 1.0, 1.5],
            "SNUADC/ECG_II": [0.1, 0.2, 0.3, 0.4],
            "SNUADC/PLETH": [0.5, 0.6, 0.7, 0.8],
            "SNUADC/ART": [80.0, 79.0, 60.0, 58.0],
        }
    )
    wave_500.to_parquet(waves_dir / "wave_00001_500hz.parquet", index=False)

    wave_25 = pd.DataFrame(
        {
            "time_sec": [0.0, 1.0, 2.0, 3.0],
            "Primus/CO2": [35.0, 34.0, 29.0, 28.0],
            "Primus/AWP": [10.0, 11.0, 12.0, 13.0],
        }
    )
    wave_25.to_parquet(waves_dir / "wave_00001_25hz.parquet", index=False)

    wave_128 = pd.DataFrame(
        {
            "time_sec": [0.0, 0.5, 1.0, 1.5],
            "BIS/EEG1_WAV": [0.01, 0.02, 0.03, 0.04],
        }
    )
    wave_128.to_parquet(waves_dir / "wave_00001_128hz.parquet", index=False)

    metadata = pd.DataFrame(
        {
            "caseid": [1],
            "age": [64],
            "sex": ["M"],
            "asa": [3],
            "department": ["General Surgery"],
            "ane_type": ["GA"],
        }
    )
    metadata_path = base_dir / "clinical_metadata.csv"
    metadata.to_csv(metadata_path, index=False)
    return metadata_path, cases_dir, output_dir


def test_repo_manifest_loads():
    manifest = load_dataset_manifest(ROOT / "learning" / "datasets" / "manifests" / "vitaldb_waveforms.yaml")
    assert manifest.dataset_id == "vitaldb_waveforms"
    assert manifest.segment_spec.window_seconds == 30.0
    assert any(signal.name == "ecg" for signal in manifest.signal_specs)


def test_infer_weak_labels_from_numeric_summary():
    labels = infer_weak_labels(
        {
            "pam_min": 54.0,
            "spo2_min": 87.0,
            "hr_max": 118.0,
            "hr_min": 72.0,
            "etco2_min": 28.0,
            "etco2_max": 35.0,
            "fr_max": 27.0,
            "fr_min": 14.0,
            "bis_min": 35.0,
        }
    )
    assert "hypotension_critical" in labels
    assert "desaturation_critical" in labels
    assert "tachycardia" in labels
    assert "hypocapnia" in labels
    assert "tachypnea" in labels
    assert "deep_hypnosis" in labels


def test_iter_case_segments_builds_segment_records(tmp_path):
    metadata_path, cases_dir, _output_dir = _write_test_case_dataset(tmp_path)

    manifest = VitalDBDatasetManifest(
        dataset_id="test_vitaldb",
        dataset_version="v1",
        description="test",
        source={"name": "VitalDB", "license": "test", "citation": "test"},
        paths={
            "metadata_csv": str(metadata_path),
            "cases_dir": str(cases_dir),
            "waveforms_dir": str(tmp_path / "waveforms"),
            "output_dir": str(tmp_path / "exports"),
        },
        context_columns=["age", "sex", "asa", "department", "ane_type"],
        signal_specs=[
            SignalSpec(name="ecg", file_key="500hz", column="SNUADC/ECG_II", sample_rate_hz=1),
            SignalSpec(name="art", file_key="500hz", column="SNUADC/ART", sample_rate_hz=1),
            SignalSpec(name="co2", file_key="25hz", column="Primus/CO2", sample_rate_hz=1),
            SignalSpec(name="eeg", file_key="128hz", column="BIS/EEG1_WAV", sample_rate_hz=1),
        ],
        segment_spec=SegmentSpec(window_seconds=2.0, stride_seconds=1.0, min_signal_coverage=0.5, min_required_signals=2),
    )

    segments = iter_case_segments(cases_dir / "case_00001.parquet", tmp_path / "waveforms", manifest)

    assert segments
    first = segments[0]
    assert first.case_id == 1
    assert first.start_s == 0.0
    assert "ecg" in first.signals
    assert first.signals["ecg"].coverage_ratio >= 1.0
    assert "stable_window" in first.weak_labels or "tachycardia" in first.weak_labels


def test_build_segment_index_writes_jsonl_and_summary(tmp_path):
    metadata_path, cases_dir, output_dir = _write_test_case_dataset(tmp_path)
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
                "  - sex",
                "  - asa",
                "signal_specs:",
                "  - name: ecg",
                "    file_key: 500hz",
                "    column: SNUADC/ECG_II",
                "    sample_rate_hz: 1",
                "  - name: art",
                "    file_key: 500hz",
                "    column: SNUADC/ART",
                "    sample_rate_hz: 1",
                "  - name: co2",
                "    file_key: 25hz",
                "    column: Primus/CO2",
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

    summary = build_segment_index(manifest_path=manifest_path, limit_cases=1, max_segments_per_case=2)

    index_path = output_dir / "segment_index.jsonl"
    summary_path = output_dir / "dataset_summary.json"

    assert summary["cases_scanned"] == 1
    assert summary["segments_written"] == 2
    assert index_path.exists()
    assert summary_path.exists()

    lines = [json.loads(line) for line in index_path.read_text(encoding="utf-8").splitlines()]
    assert len(lines) == 2
    assert lines[0]["case_context"]["age"] == 64

