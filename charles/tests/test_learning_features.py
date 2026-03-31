import json
import sys
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))


from learning.pipelines.build_problem_dataset import build_problem_dataset
from learning.pipelines.build_vitaldb_dataset import build_segment_index
from learning.problems import infer_problem_record
from learning.waveforms.features import CaseFrameCache, extract_feature_record
from learning.waveforms.schemas import SegmentRecord, SegmentSpec, SignalSpec, VitalDBDatasetManifest, WindowSignalStats


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
            "SNUADC/PLETH": [0.5, 0.6, 0.7, 0.8, 0.55, 0.65],
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

    wave_128 = pd.DataFrame(
        {
            "time_sec": [0.0, 0.5, 1.0, 1.5, 2.0, 2.5],
            "BIS/EEG1_WAV": [0.01, 0.02, 0.03, 0.04, 0.025, 0.015],
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


def _build_manifest(metadata_path: Path, cases_dir: Path, base_dir: Path) -> VitalDBDatasetManifest:
    return VitalDBDatasetManifest(
        dataset_id="test_vitaldb",
        dataset_version="v1",
        description="test",
        source={"name": "VitalDB", "license": "test", "citation": "test"},
        paths={
            "metadata_csv": str(metadata_path),
            "cases_dir": str(cases_dir),
            "waveforms_dir": str(base_dir / "waveforms"),
            "output_dir": str(base_dir / "exports"),
        },
        context_columns=["age", "sex", "asa", "department", "ane_type"],
        signal_specs=[
            SignalSpec(name="ecg", file_key="500hz", column="SNUADC/ECG_II", sample_rate_hz=2),
            SignalSpec(name="art", file_key="500hz", column="SNUADC/ART", sample_rate_hz=2),
            SignalSpec(name="co2", file_key="25hz", column="Primus/CO2", sample_rate_hz=1),
            SignalSpec(name="awp", file_key="25hz", column="Primus/AWP", sample_rate_hz=1),
            SignalSpec(name="eeg", file_key="128hz", column="BIS/EEG1_WAV", sample_rate_hz=2),
        ],
        segment_spec=SegmentSpec(window_seconds=2.0, stride_seconds=1.0, min_signal_coverage=0.5, min_required_signals=2),
    )


def test_extract_feature_record_computes_numeric_and_signal_metrics(tmp_path):
    metadata_path, cases_dir, _ = _write_test_case_dataset(tmp_path)
    manifest = _build_manifest(metadata_path, cases_dir, tmp_path)
    cache = CaseFrameCache(manifest)

    segment = SegmentRecord(
        segment_id="case00001_00000_0000000000",
        case_id=1,
        start_s=1.0,
        end_s=3.0,
        weak_labels=["hypotension_critical", "desaturation_critical", "deep_hypnosis"],
        vitals_snapshot={"pam_min": 52.0, "spo2_min": 87.0, "hr_max": 118.0, "bis_min": 32.0},
        signals={
            "ecg": WindowSignalStats(source_column="SNUADC/ECG_II", samples=4, expected_samples=4, coverage_ratio=1.0),
            "art": WindowSignalStats(source_column="SNUADC/ART", samples=4, expected_samples=4, coverage_ratio=1.0),
            "co2": WindowSignalStats(source_column="Primus/CO2", samples=2, expected_samples=2, coverage_ratio=1.0),
            "awp": WindowSignalStats(source_column="Primus/AWP", samples=2, expected_samples=2, coverage_ratio=1.0),
            "eeg": WindowSignalStats(source_column="BIS/EEG1_WAV", samples=4, expected_samples=4, coverage_ratio=1.0),
        },
        source_files={"numeric": "case_00001.parquet"},
        case_context={"age": 64},
    )

    feature_record = extract_feature_record(segment, manifest, cache=cache)

    assert feature_record.numeric_features["pam_mean"] == 60.0
    assert feature_record.numeric_features["pam_delta"] == -4.0
    assert feature_record.signal_features["ecg"].samples == 4
    assert feature_record.signal_features["ecg"].amplitude is not None
    assert feature_record.signal_features["awp"].max == 22.0


def test_problem_engine_ranks_hemodynamic_instability_first(tmp_path):
    metadata_path, cases_dir, _ = _write_test_case_dataset(tmp_path)
    manifest = _build_manifest(metadata_path, cases_dir, tmp_path)
    cache = CaseFrameCache(manifest)

    segment = SegmentRecord(
        segment_id="case00001_00001_0000001000",
        case_id=1,
        start_s=1.0,
        end_s=3.0,
        weak_labels=["hypotension_critical", "desaturation_critical", "deep_hypnosis"],
        vitals_snapshot={"pam_min": 52.0, "spo2_min": 87.0, "hr_max": 118.0, "bis_min": 32.0},
        signals={
            "ecg": WindowSignalStats(source_column="SNUADC/ECG_II", samples=4, expected_samples=4, coverage_ratio=1.0),
            "art": WindowSignalStats(source_column="SNUADC/ART", samples=4, expected_samples=4, coverage_ratio=1.0),
            "co2": WindowSignalStats(source_column="Primus/CO2", samples=2, expected_samples=2, coverage_ratio=1.0),
            "awp": WindowSignalStats(source_column="Primus/AWP", samples=2, expected_samples=2, coverage_ratio=1.0),
            "eeg": WindowSignalStats(source_column="BIS/EEG1_WAV", samples=4, expected_samples=4, coverage_ratio=1.0),
        },
        source_files={"numeric": "case_00001.parquet"},
        case_context={"age": 64},
    )

    feature_record = extract_feature_record(segment, manifest, cache=cache)
    problem_record = infer_problem_record(feature_record)

    assert problem_record.primary_problem_id == "hemodynamic_instability"
    problem_ids = [item.problem_id for item in problem_record.problem_hypotheses]
    assert "respiratory_instability" in problem_ids
    assert "depth_excess" in problem_ids


def test_build_problem_dataset_writes_feature_and_problem_indexes(tmp_path):
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

    build_segment_index(manifest_path=manifest_path, limit_cases=1, max_segments_per_case=2)
    summary = build_problem_dataset(manifest_path=manifest_path, limit_segments=2)

    feature_index = output_dir / "feature_index.jsonl"
    problem_index = output_dir / "problem_index.jsonl"
    problem_summary = output_dir / "problem_summary.json"

    assert summary["segments_processed"] == 2
    assert feature_index.exists()
    assert problem_index.exists()
    assert problem_summary.exists()

    feature_rows = [json.loads(line) for line in feature_index.read_text(encoding="utf-8").splitlines()]
    problem_rows = [json.loads(line) for line in problem_index.read_text(encoding="utf-8").splitlines()]

    assert len(feature_rows) == 2
    assert len(problem_rows) == 2
    assert "numeric_features" in feature_rows[0]
    assert "problem_hypotheses" in problem_rows[0]
    assert problem_rows[0]["primary_problem_id"] is not None
