from __future__ import annotations

import json
import statistics as stats
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import pandas as pd

from learning.pipelines.evaluate_hypotension_model import _has_waveforms, _infer_phase
from learning.problems.hypotension_model import (
    HypotensionBaselines,
    HypotensionDetector,
    HypotensionDetectorConfig,
    build_case_baselines,
    build_waveform_feature_frame,
    find_reference_hypotension_onset,
)


ROOT = Path(__file__).resolve().parents[2]
CASES_DIR = ROOT / "vitaldb" / "cases"
WAVEFORMS_DIR = ROOT / "vitaldb" / "waveforms"
OUTPUT_DIR = ROOT / "learning" / "evaluation" / "hypotension_model_asa1_v2"

NUMERIC_COLUMNS = [
    "time_sec",
    "Solar8000/ART_MBP",
    "Solar8000/NIBP_MBP",
    "Solar8000/ART_SBP",
    "Solar8000/NIBP_SBP",
    "Solar8000/HR",
    "Solar8000/PLETH_SPO2",
    "Solar8000/ETCO2",
    "BIS/BIS",
]


def load_minimal_case_frame(case_path: Path) -> pd.DataFrame:
    frame = pd.read_parquet(case_path, columns=NUMERIC_COLUMNS).copy()
    frame = frame.sort_values("time_sec").reset_index(drop=True)

    art_map = pd.to_numeric(frame.get("Solar8000/ART_MBP"), errors="coerce")
    art_map = art_map.where((art_map >= 20) & (art_map <= 180))
    nibp_map = pd.to_numeric(frame.get("Solar8000/NIBP_MBP"), errors="coerce")
    nibp_map = nibp_map.where((nibp_map >= 20) & (nibp_map <= 180))
    art_sap = pd.to_numeric(frame.get("Solar8000/ART_SBP"), errors="coerce")
    art_sap = art_sap.where((art_sap >= 30) & (art_sap <= 260))
    nibp_sap = pd.to_numeric(frame.get("Solar8000/NIBP_SBP"), errors="coerce")
    nibp_sap = nibp_sap.where((nibp_sap >= 30) & (nibp_sap <= 260))

    frame["clean_map"] = art_map.combine_first(nibp_map)
    frame["clean_sap"] = art_sap.combine_first(nibp_sap)
    frame["clean_hr"] = pd.to_numeric(frame.get("Solar8000/HR"), errors="coerce")
    frame.loc[(frame["clean_hr"] < 20) | (frame["clean_hr"] > 220), "clean_hr"] = pd.NA
    frame["clean_spo2"] = pd.to_numeric(frame.get("Solar8000/PLETH_SPO2"), errors="coerce")
    frame.loc[(frame["clean_spo2"] < 40) | (frame["clean_spo2"] > 100), "clean_spo2"] = pd.NA
    frame["clean_etco2"] = pd.to_numeric(frame.get("Solar8000/ETCO2"), errors="coerce")
    frame.loc[(frame["clean_etco2"] < 0) | (frame["clean_etco2"] > 80), "clean_etco2"] = pd.NA
    frame["clean_bis"] = pd.to_numeric(frame.get("BIS/BIS"), errors="coerce")
    frame.loc[(frame["clean_bis"] < 0) | (frame["clean_bis"] > 100), "clean_bis"] = pd.NA
    return frame


def augment_baselines_with_waveforms(baselines: HypotensionBaselines, waveform_frame: pd.DataFrame) -> None:
    if waveform_frame.empty:
        return
    early = waveform_frame[waveform_frame["time_s"] <= 300.0].copy()
    if early.empty:
        early = waveform_frame.head(20)
    for source, target in {
        "art_amp": "art_wave_amplitude",
        "pleth_amp": "pleth_wave_amplitude",
        "co2_amp": "capno_wave_amplitude",
    }.items():
        if source not in early.columns:
            continue
        series = pd.to_numeric(early[source], errors="coerce").dropna()
        if series.empty:
            continue
        median = float(series.median())
        baselines.patient_t0[target] = median
        baselines.stable[target] = median


def merge_numeric_and_waveforms(case_frame: pd.DataFrame, waveform_frame: pd.DataFrame) -> pd.DataFrame:
    if waveform_frame.empty:
        return case_frame.copy()
    numeric = case_frame.copy()
    numeric["time_sec"] = pd.to_numeric(numeric["time_sec"], errors="coerce").astype("float64")
    waves = waveform_frame.copy()
    waves["time_s"] = pd.to_numeric(waves["time_s"], errors="coerce").astype("float64")
    return pd.merge_asof(
        numeric.sort_values("time_sec"),
        waves.sort_values("time_s"),
        left_on="time_sec",
        right_on="time_s",
        direction="nearest",
        tolerance=10.0,
    )


def evaluate_case(case_id: int, metadata_row: pd.Series, config: HypotensionDetectorConfig) -> dict | None:
    case_frame = load_minimal_case_frame(CASES_DIR / f"case_{case_id:05d}.parquet")
    onset = find_reference_hypotension_onset(
        case_frame,
        map_target=config.map_target,
        sap_target=config.sap_target,
        min_duration_s=config.sustained_confirm_s,
    )
    if onset is None:
        return None

    waveform_frame = pd.DataFrame()
    waveform_mode = "numeric_only"
    if _has_waveforms(case_id, WAVEFORMS_DIR):
        waveform_frame = build_waveform_feature_frame(case_id, WAVEFORMS_DIR, bin_seconds=config.waveform_bin_seconds)
        waveform_mode = "waveforms_enabled"

    baselines = build_case_baselines(case_frame, config=config)
    augment_baselines_with_waveforms(baselines, waveform_frame)
    merged = merge_numeric_and_waveforms(case_frame, waveform_frame)
    detector = HypotensionDetector(baselines, config=config)

    first_early = None
    first_probable = None
    first_confirmed = None
    peak_risk = 0.0
    peak_confidence = 0.0

    for row in merged.itertuples(index=False):
        snapshot = detector.update(
            snapshot=detector_snapshot_from_row(row, metadata_row)
        )
        peak_risk = max(peak_risk, snapshot.risk_5min)
        peak_confidence = max(peak_confidence, snapshot.confidence)
        if first_early is None and snapshot.state in {
            "early_transition",
            "probable_hypotension",
            "confirmed_hypotension",
            "critical_hypotension",
            "refractory_hypotension",
        }:
            first_early = snapshot.time_s
        if first_probable is None and snapshot.state in {
            "probable_hypotension",
            "confirmed_hypotension",
            "critical_hypotension",
            "refractory_hypotension",
        }:
            first_probable = snapshot.time_s
        if first_confirmed is None and snapshot.state in {
            "confirmed_hypotension",
            "critical_hypotension",
            "refractory_hypotension",
        }:
            first_confirmed = snapshot.time_s

    return {
        "case_id": case_id,
        "waveform_mode": waveform_mode,
        "reference_onset_s": float(onset),
        "anticipation_early_s": None if first_early is None else float(onset - first_early),
        "anticipation_probable_s": None if first_probable is None else float(onset - first_probable),
        "anticipation_confirmed_s": None if first_confirmed is None else float(onset - first_confirmed),
        "peak_risk": peak_risk,
        "peak_confidence": peak_confidence,
    }


def detector_snapshot_from_row(row, metadata_row: pd.Series):
    row_dict = row._asdict()
    from learning.problems.hypotension_model import HypotensionSnapshot

    return HypotensionSnapshot(
        time_s=float(row_dict["time_sec"]),
        map_value=_safe_float(row_dict.get("clean_map")),
        sap_value=_safe_float(row_dict.get("clean_sap")),
        hr=_safe_float(row_dict.get("clean_hr")),
        etco2=_safe_float(row_dict.get("clean_etco2")),
        spo2=_safe_float(row_dict.get("clean_spo2")),
        bis=_safe_float(row_dict.get("clean_bis")),
        art_wave_amplitude=_safe_float(row_dict.get("art_amp")),
        art_wave_slope=_safe_float(row_dict.get("art_slope")),
        pleth_wave_amplitude=_safe_float(row_dict.get("pleth_amp")),
        pleth_wave_slope=_safe_float(row_dict.get("pleth_slope")),
        capno_wave_amplitude=_safe_float(row_dict.get("co2_amp")),
        capno_wave_slope=_safe_float(row_dict.get("co2_slope")),
        operative_phase=_infer_phase(float(row_dict["time_sec"]), metadata_row),
        chronic_hypertension=bool(metadata_row.get("preop_htn", 0) == 1),
        coronary_disease=False,
        heart_failure=False,
        frailty=bool(float(metadata_row.get("age", 0) or 0) >= 75.0),
        obstetric_context=str(metadata_row.get("department", "")).lower().startswith("obst"),
    )


def _safe_float(value):
    try:
        if pd.isna(value):
            return None
        return float(value)
    except Exception:
        return None


def summarize(items: list[dict]) -> dict:
    def values(key: str) -> list[float]:
        return [item[key] for item in items if item.get(key) is not None]

    def summary_for(series: list[float]) -> dict[str, float | int | None]:
        if not series:
            return {
                "available": 0,
                "detected_before_onset": 0,
                "mean_s": None,
                "median_s": None,
            }
        return {
            "available": len(series),
            "detected_before_onset": sum(1 for value in series if value > 0),
            "mean_s": round(stats.mean(series), 3),
            "median_s": round(stats.median(series), 3),
        }

    early = values("anticipation_early_s")
    probable = values("anticipation_probable_s")
    confirmed = values("anticipation_confirmed_s")

    return {
        "count": len(items),
        "early": summary_for(early),
        "probable": summary_for(probable),
        "confirmed": summary_for(confirmed),
        "mean_peak_risk": round(stats.mean([item["peak_risk"] for item in items]), 4) if items else None,
        "mean_peak_confidence": round(stats.mean([item["peak_confidence"] for item in items]), 4) if items else None,
    }


def main() -> int:
    metadata = pd.read_csv(ROOT / "vitaldb" / "clinical_metadata.csv").set_index("caseid", drop=False)
    config = HypotensionDetectorConfig()

    target_case_ids: list[int] = []
    for case_path in sorted(CASES_DIR.glob("case_*.parquet")):
        case_id = int(case_path.stem.split("_")[1])
        if case_id not in metadata.index:
            continue
        asa = metadata.loc[case_id, "asa"]
        try:
            asa_value = float(asa)
        except (TypeError, ValueError):
            continue
        if asa_value != 1.0:
            continue
        case_frame = load_minimal_case_frame(case_path)
        onset = find_reference_hypotension_onset(
            case_frame,
            map_target=config.map_target,
            sap_target=config.sap_target,
            min_duration_s=config.sustained_confirm_s,
        )
        if onset is not None:
            target_case_ids.append(case_id)

    started_at = time.perf_counter()
    results: list[dict] = []
    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = {
            executor.submit(evaluate_case, case_id, metadata.loc[case_id], config): case_id
            for case_id in target_case_ids
        }
        for future in as_completed(futures):
            result = future.result()
            if result is not None:
                results.append(result)
    elapsed = time.perf_counter() - started_at

    wave = [item for item in results if item["waveform_mode"] == "waveforms_enabled"]
    nowave = [item for item in results if item["waveform_mode"] == "numeric_only"]

    payload = {
        "subset": "ASA1_hypotension_v2_only",
        "total_cases_in_subset": len(results),
        "with_waveforms": len(wave),
        "without_waveforms": len(nowave),
        "elapsed_seconds": round(elapsed, 3),
        "overall": summarize(results),
        "waveforms_enabled": summarize(wave),
        "numeric_only": summarize(nowave),
    }

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUTPUT_DIR / "summary.json").write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

    lines = [
        "# Hypotension V2 - ASA 1 Summary",
        "",
        f"- Cases processed: `{payload['total_cases_in_subset']}`",
        f"- With waveforms: `{payload['with_waveforms']}`",
        f"- Without waveforms: `{payload['without_waveforms']}`",
        f"- Runtime: `{payload['elapsed_seconds']} s`",
        "",
        "## Overall",
        f"- early: `{payload['overall']['early']}`",
        f"- probable: `{payload['overall']['probable']}`",
        f"- confirmed: `{payload['overall']['confirmed']}`",
        f"- mean_peak_risk: `{payload['overall']['mean_peak_risk']}`",
        f"- mean_peak_confidence: `{payload['overall']['mean_peak_confidence']}`",
        "",
        "## Waveforms Enabled",
        f"- early: `{payload['waveforms_enabled']['early']}`",
        f"- probable: `{payload['waveforms_enabled']['probable']}`",
        f"- confirmed: `{payload['waveforms_enabled']['confirmed']}`",
        f"- mean_peak_risk: `{payload['waveforms_enabled']['mean_peak_risk']}`",
        f"- mean_peak_confidence: `{payload['waveforms_enabled']['mean_peak_confidence']}`",
        "",
        "## Numeric Only",
        f"- early: `{payload['numeric_only']['early']}`",
        f"- probable: `{payload['numeric_only']['probable']}`",
        f"- confirmed: `{payload['numeric_only']['confirmed']}`",
        f"- mean_peak_risk: `{payload['numeric_only']['mean_peak_risk']}`",
        f"- mean_peak_confidence: `{payload['numeric_only']['mean_peak_confidence']}`",
    ]
    (OUTPUT_DIR / "summary.md").write_text("\n".join(lines), encoding="utf-8")

    print(json.dumps(payload, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
