import json
import sys
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))


from learning.llm.schemas import ExplanationTarget, LLMConversationMessage, LLMTrainingSample
from learning.pipelines.build_llm_dataset import build_llm_dataset
from learning.pipelines.build_problem_dataset import build_problem_dataset
from learning.pipelines.build_review_pack import build_review_pack
from learning.review import choose_review_tasks
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


def _make_review_sample(
    sample_id: str,
    *,
    primary_problem_id: str,
    split: str = "train",
    source_problem_ids: list[str] | None = None,
    case_complications: list[str] | None = None,
) -> LLMTrainingSample:
    return LLMTrainingSample(
        sample_id=sample_id,
        case_id=1,
        segment_id=sample_id.split(":")[0],
        split=split,
        prompt_id="charles-perop-waveform-v2-local-train",
        prompt_version="2026-03-30",
        primary_problem_id=primary_problem_id,
        primary_severity="critical",
        target_origin="heuristic_bootstrap",
        source_problem_ids=source_problem_ids or [primary_problem_id],
        case_complications=case_complications or [],
        system_prompt="system prompt",
        user_prompt="user prompt",
        messages=[
            LLMConversationMessage(role="system", content="system prompt"),
            LLMConversationMessage(role="user", content="user prompt"),
        ],
        expected_output=ExplanationTarget(
            situation="Situation test.",
            risks=["Risque test"],
            recommendations=["Reco test"],
            call_mar=True,
            call_mar_reason="Critique",
            confidence=0.9,
        ),
    )


def test_build_review_pack_writes_pending_review_tasks(tmp_path):
    metadata_path, cases_dir, output_dir = _write_test_case_dataset(tmp_path)
    manifest_path = _write_manifest(tmp_path, metadata_path, cases_dir, output_dir)

    build_segment_index(manifest_path=manifest_path, limit_cases=1, max_segments_per_case=2)
    build_problem_dataset(manifest_path=manifest_path, limit_segments=2)
    build_llm_dataset(manifest_path=manifest_path, limit_samples=2, eval_ratio=0.5)
    summary = build_review_pack(manifest_path=manifest_path, per_problem_limit=5, limit_total=2)

    review_path = output_dir / "review_candidates.jsonl"
    summary_path = output_dir / "review_summary.json"
    instructions_path = output_dir / "review_instructions.md"

    assert summary["review_candidates_written"] == 2
    assert review_path.exists()
    assert summary_path.exists()
    assert instructions_path.exists()

    rows = [json.loads(line) for line in review_path.read_text(encoding="utf-8").splitlines()]
    assert len(rows) == 2
    assert rows[0]["review_status"] == "pending"
    assert rows[0]["review_priority"] in {"normal", "high"}
    assert "sample" in rows[0]


def test_choose_review_tasks_prioritizes_focus_families_even_when_primary_problem_is_dominated():
    samples = [
        _make_review_sample("generic-hemo-1:train", primary_problem_id="hemodynamic_instability"),
        _make_review_sample("generic-hemo-2:eval", primary_problem_id="hemodynamic_instability", split="eval"),
        _make_review_sample(
            "focus-respiratory:train",
            primary_problem_id="depth_excess",
            source_problem_ids=["depth_excess", "respiratory_instability"],
        ),
        _make_review_sample(
            "focus-airway:train",
            primary_problem_id="hemodynamic_instability",
            source_problem_ids=["hemodynamic_instability"],
            case_complications=["difficult_airway_proxy"],
        ),
        _make_review_sample(
            "focus-metabolic:eval",
            primary_problem_id="hemodynamic_instability",
            split="eval",
            source_problem_ids=["hemodynamic_instability", "metabolic_derangement_context"],
            case_complications=["intraop_acidemia_lab"],
        ),
    ]

    tasks = choose_review_tasks(samples, per_problem_limit=1, per_focus_limit=1, limit_total=4)
    tags_by_id = {task.sample.sample_id: set(task.review_tags) for task in tasks}

    assert "focus-respiratory:train" in tags_by_id
    assert "focus_respiratory" in tags_by_id["focus-respiratory:train"]
    assert "focus-airway:train" in tags_by_id
    assert "focus_airway" in tags_by_id["focus-airway:train"]
    assert "focus-metabolic:eval" in tags_by_id
    assert "focus_metabolic" in tags_by_id["focus-metabolic:eval"]


def test_build_review_pack_reports_focus_counts(tmp_path):
    output_dir = tmp_path / "exports"
    output_dir.mkdir()
    reference_path = output_dir / "llm_reference.jsonl"
    samples = [
        _make_review_sample(
            "sample-respiratory:train",
            primary_problem_id="depth_excess",
            source_problem_ids=["depth_excess", "respiratory_instability"],
        ),
        _make_review_sample(
            "sample-airway:train",
            primary_problem_id="hemodynamic_instability",
            case_complications=["difficult_airway_proxy"],
        ),
        _make_review_sample(
            "sample-metabolic:eval",
            primary_problem_id="hemodynamic_instability",
            split="eval",
            source_problem_ids=["hemodynamic_instability", "metabolic_derangement_context"],
            case_complications=["intraop_hyperkalemia_lab"],
        ),
    ]
    reference_path.write_text(
        "\n".join(json.dumps(sample.model_dump(mode="json"), ensure_ascii=False) for sample in samples) + "\n",
        encoding="utf-8",
    )

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
                f"  metadata_csv: {(tmp_path / 'clinical_metadata.csv').as_posix()}",
                f"  cases_dir: {(tmp_path / 'cases').as_posix()}",
                f"  waveforms_dir: {(tmp_path / 'waveforms').as_posix()}",
                f"  output_dir: {output_dir.as_posix()}",
                "signal_specs:",
                "  - name: ecg",
                "    file_key: 500hz",
                "    column: SNUADC/ECG_II",
                "    sample_rate_hz: 2",
                "segment_spec:",
                "  window_seconds: 2.0",
                "  stride_seconds: 1.0",
                "  min_signal_coverage: 0.5",
                "  min_required_signals: 1",
            ]
        ),
        encoding="utf-8",
    )
    (tmp_path / "clinical_metadata.csv").write_text("caseid\n1\n", encoding="utf-8")
    (tmp_path / "cases").mkdir(exist_ok=True)
    (tmp_path / "waveforms").mkdir(exist_ok=True)

    summary = build_review_pack(
        manifest_path=manifest_path,
        reference_path=reference_path,
        per_problem_limit=1,
        per_focus_limit=1,
        limit_total=3,
    )

    assert summary["review_candidates_written"] == 3
    assert summary["focus_counts"] == {
        "airway": 1,
        "metabolic": 1,
        "respiratory": 1,
    }
