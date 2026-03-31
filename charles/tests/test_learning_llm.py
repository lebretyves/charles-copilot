import json
import sys
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "services" / "backend"))


from app.models import LLMAnalysis
from learning.llm import PROMPT_ID, PROMPT_VERSION, build_prompt_variants, build_reference_target, build_user_prompt
from learning.pipelines.build_llm_dataset import build_llm_dataset
from learning.pipelines.build_problem_dataset import build_problem_dataset
from learning.pipelines.build_vitaldb_dataset import build_segment_index
from learning.problems.schemas import ProblemAnalysisRecord, ProblemHypothesis


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
    return manifest_path


def test_reference_target_matches_backend_llm_schema():
    record = ProblemAnalysisRecord(
        segment_id="case00001_00001_0000001000",
        case_id=1,
        start_s=1.0,
        end_s=3.0,
        weak_labels=["hypotension_critical", "desaturation_critical", "deep_hypnosis"],
        vitals_snapshot={"pam_min": 52.0, "spo2_min": 87.0, "hr_max": 118.0, "bis_min": 32.0},
        numeric_features={"pam_delta": -12.0},
        signal_features={},
        source_files={"numeric": "case_00001.parquet"},
        case_context={"age": 64},
        primary_problem_id="hemodynamic_instability",
        problem_hypotheses=[
            ProblemHypothesis(
                problem_id="hemodynamic_instability",
                severity="critical",
                score=0.9,
                reasons=["test"],
                evidence={"pam_min": 52.0},
            )
        ],
    )

    target = build_reference_target(record)
    prompt = build_user_prompt(record)

    parsed = LLMAnalysis(
        situation=target.situation,
        risks=target.risks,
        recommendations=target.recommendations,
        confidence=target.confidence,
        call_mar=target.call_mar,
        call_mar_reason=target.call_mar_reason,
        model="meditron:7b",
        latency_ms=0,
        prompt_id=PROMPT_ID,
        prompt_version=PROMPT_VERSION,
    )

    assert parsed.call_mar is True
    assert "hemodynamique" in target.situation.lower()
    assert "Produis un JSON" in prompt


def test_build_user_prompt_variants_hide_or_mask_waveforms():
    record = ProblemAnalysisRecord(
        segment_id="case00001_00001_0000001000",
        case_id=1,
        start_s=1.0,
        end_s=3.0,
        weak_labels=["hypotension_critical"],
        vitals_snapshot={"pam_min": 52.0},
        numeric_features={"pam_delta": -12.0},
        signal_features={
            "art": {"source_column": "art", "samples": 10, "coverage_ratio": 1.0, "amplitude": 20.0},
            "co2": {"source_column": "co2", "samples": 10, "coverage_ratio": 1.0, "amplitude": 5.0},
        },
        source_files={"numeric": "case_00001.parquet"},
        case_context={"age": 64},
        primary_problem_id="hemodynamic_instability",
        problem_hypotheses=[
            ProblemHypothesis(
                problem_id="hemodynamic_instability",
                severity="critical",
                score=0.9,
                reasons=["test"],
                evidence={"pam_min": 52.0},
            )
        ],
    )

    no_wave = build_user_prompt(record, input_variant="no_wave")
    partial = build_user_prompt(record, input_variant="partial_wave", masked_signals=["co2"])
    variants = build_prompt_variants(record)

    assert "- unavailable: true" in no_wave
    assert "reason only from vitals" in no_wave
    assert "masked_signals: co2" in partial
    assert "- art:" in partial
    assert "- co2:" not in partial
    assert {variant for variant, _, _ in variants} == {"full_wave", "no_wave", "partial_wave"}


def test_build_llm_dataset_writes_train_eval_and_reference_files(tmp_path):
    metadata_path, cases_dir, output_dir = _write_test_case_dataset(tmp_path)
    manifest_path = _write_manifest(tmp_path, metadata_path, cases_dir, output_dir)

    build_segment_index(manifest_path=manifest_path, limit_cases=1, max_segments_per_case=3)
    build_problem_dataset(manifest_path=manifest_path, limit_segments=3)
    summary = build_llm_dataset(manifest_path=manifest_path, limit_samples=3, eval_ratio=0.34)

    train_path = output_dir / "llm_train.jsonl"
    eval_path = output_dir / "llm_eval.jsonl"
    reference_path = output_dir / "llm_reference.jsonl"
    summary_path = output_dir / "llm_summary.json"
    variant_reference = output_dir / "llm_reference_no_wave.jsonl"

    assert summary["samples_written"] == 6
    assert train_path.exists()
    assert eval_path.exists()
    assert reference_path.exists()
    assert summary_path.exists()
    assert variant_reference.exists()

    reference_rows = [json.loads(line) for line in reference_path.read_text(encoding="utf-8").splitlines()]
    assert len(reference_rows) == 6
    assert reference_rows[0]["prompt_id"] == PROMPT_ID
    assert reference_rows[0]["messages"][0]["role"] == "system"
    assert "expected_output" in reference_rows[0]
    assert reference_rows[0]["split"] in {"train", "eval"}
    assert reference_rows[0]["input_variant"] in {"full_wave", "no_wave", "partial_wave"}
