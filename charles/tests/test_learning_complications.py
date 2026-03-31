import json
import sys
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))


from learning.pipelines.build_vitaldb_dataset import build_segment_index
from learning.vitaldb import choose_diverse_case_files, derive_case_complications, load_case_contexts_with_complications


def test_derive_case_complications_from_metadata_and_labs():
    tags = derive_case_complications(
        {
            "emop": 1,
            "icu_days": 2,
            "death_inhosp": 0,
            "intraop_ebl": 1200,
            "intraop_rbc": 2,
            "intraop_ffp": 1,
            "intraop_eph": 0,
            "intraop_phe": 50,
            "intraop_epi": 0,
            "cormack": "IIIa",
            "airway": "Oral",
        },
        {
            "hb_min": 7.4,
            "ph_min": 7.18,
            "pco2_max": 52.0,
            "gluc_max": 210.0,
            "k_min": 2.8,
            "k_max": 5.9,
            "cr_max": 1.8,
        },
    )

    assert "emergency_case" in tags
    assert "postop_icu_admission" in tags
    assert "massive_blood_loss" in tags
    assert "rbc_transfusion" in tags
    assert "plasma_transfusion" in tags
    assert "phenylephrine_support" in tags
    assert "difficult_airway_proxy" in tags
    assert "intraop_anemia_lab" in tags
    assert "severe_intraop_acidemia_lab" in tags
    assert "intraop_hypercapnia_lab" in tags
    assert "intraop_hyperglycemia_lab" in tags
    assert "intraop_hyperkalemia_lab" in tags
    assert "intraop_hypokalemia_lab" in tags
    assert "renal_dysfunction_lab" in tags


def test_choose_diverse_case_files_prefers_tag_coverage(tmp_path):
    case_files = []
    for case_id in [1, 2, 3]:
        case_path = tmp_path / f"case_{case_id:05d}.parquet"
        pd.DataFrame({"time_sec": [0.0], "Solar8000/HR": [70.0]}).to_parquet(case_path, index=False)
        case_files.append(case_path)

    contexts = {
        1: {"case_complications": ["massive_blood_loss"]},
        2: {"case_complications": ["difficult_airway_proxy"]},
        3: {"case_complications": []},
    }
    selected = choose_diverse_case_files(case_files, contexts, limit_cases=2, per_complication_cap=1)

    selected_ids = [int(path.stem.replace("case_", "")) for path in selected]
    assert 1 in selected_ids
    assert 2 in selected_ids


def test_build_segment_index_with_diverse_complications_attaches_case_tags(tmp_path):
    cases_dir = tmp_path / "cases"
    waves_dir = tmp_path / "waveforms"
    output_dir = tmp_path / "exports"
    cases_dir.mkdir()
    waves_dir.mkdir()
    output_dir.mkdir()

    for case_id in [1, 2]:
        pd.DataFrame(
            {
                "time_sec": [0.0, 1.0, 2.0],
                "Solar8000/HR": [70.0, 75.0, 80.0],
                "Solar8000/PLETH_SPO2": [98.0, 98.0, 97.0],
                "Solar8000/ART_MBP": [80.0, 78.0, 76.0],
            }
        ).to_parquet(cases_dir / f"case_{case_id:05d}.parquet", index=False)
        pd.DataFrame(
            {
                "time_sec": [0.0, 0.5, 1.0, 1.5],
                "SNUADC/ECG_II": [0.1, 0.2, 0.1, 0.2],
                "SNUADC/PLETH": [0.5, 0.6, 0.5, 0.6],
            }
        ).to_parquet(waves_dir / f"wave_{case_id:05d}_500hz.parquet", index=False)

    metadata = pd.DataFrame(
        {
            "caseid": [1, 2],
            "age": [64, 55],
            "sex": ["M", "F"],
            "asa": [3, 2],
            "department": ["General surgery", "Thoracic surgery"],
            "ane_type": ["General", "General"],
            "emop": [1, 0],
            "icu_days": [1, 0],
            "death_inhosp": [0, 0],
            "cormack": ["I", "IIIa"],
            "airway": ["Oral", "Oral"],
            "intraop_ebl": [1200, 50],
            "intraop_rbc": [2, 0],
            "intraop_ffp": [1, 0],
            "intraop_eph": [0, 0],
            "intraop_phe": [20, 0],
            "intraop_epi": [0, 0],
        }
    )
    metadata_path = tmp_path / "clinical_metadata.csv"
    metadata.to_csv(metadata_path, index=False)

    labs = pd.DataFrame(
        {
            "caseid": [1, 1, 2],
            "dt": ["t1", "t2", "t3"],
            "name": ["ph", "hb", "ph"],
            "result": [7.18, 7.4, 7.36],
        }
    )
    labs_path = tmp_path / "intraop_labs.csv"
    labs.to_csv(labs_path, index=False)

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
                f"  labs_csv: {labs_path.as_posix()}",
                f"  cases_dir: {cases_dir.as_posix()}",
                f"  waveforms_dir: {waves_dir.as_posix()}",
                f"  output_dir: {output_dir.as_posix()}",
                "context_columns:",
                "  - age",
                "  - sex",
                "  - asa",
                "  - department",
                "  - ane_type",
                "  - emop",
                "  - icu_days",
                "  - death_inhosp",
                "  - cormack",
                "  - airway",
                "  - intraop_ebl",
                "  - intraop_rbc",
                "  - intraop_ffp",
                "  - intraop_eph",
                "  - intraop_phe",
                "  - intraop_epi",
                "signal_specs:",
                "  - name: ecg",
                "    file_key: 500hz",
                "    column: SNUADC/ECG_II",
                "    sample_rate_hz: 2",
                "  - name: pleth",
                "    file_key: 500hz",
                "    column: SNUADC/PLETH",
                "    sample_rate_hz: 2",
                "segment_spec:",
                "  window_seconds: 2.0",
                "  stride_seconds: 1.0",
                "  min_signal_coverage: 0.5",
                "  min_required_signals: 2",
            ]
        ),
        encoding="utf-8",
    )

    summary = build_segment_index(
        manifest_path=manifest_path,
        limit_cases=2,
        max_segments_per_case=1,
        case_selection="diverse_complications",
        per_complication_cap=1,
    )

    rows = [
        json.loads(line)
        for line in (output_dir / "segment_index.jsonl").read_text(encoding="utf-8").splitlines()
    ]

    assert summary["case_selection"] == "diverse_complications"
    assert "massive_blood_loss" in summary["case_complication_counts"]
    assert any("difficult_airway_proxy" in row["case_complications"] for row in rows)
    assert any("massive_blood_loss" in row["case_complications"] for row in rows)
