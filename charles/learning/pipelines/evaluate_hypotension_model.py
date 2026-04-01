from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path

import pandas as pd

from learning.problems.hypotension_model import (
    HypotensionDetector,
    HypotensionDetectorConfig,
    build_case_baselines,
    build_snapshot_from_row,
    build_waveform_feature_frame,
    find_reference_hypotension_onset,
    load_case_numeric_frame,
)


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT_DIR = ROOT / "learning" / "evaluation" / "hypotension_model"


def _has_waveforms(case_id: int, waveforms_dir: Path) -> bool:
    return any((waveforms_dir / f"wave_{case_id:05d}_{suffix}.parquet").exists() for suffix in ("500hz", "25hz", "128hz"))


def _infer_phase(time_s: float, metadata_row: pd.Series) -> str:
    anestart = float(metadata_row.get("anestart", 0) or 0)
    opstart = float(metadata_row.get("opstart", 0) or 0)
    opend = float(metadata_row.get("opend", 0) or 0)
    aneend = float(metadata_row.get("aneend", 0) or 0)
    if anestart <= time_s < opstart:
        return "induction"
    if opstart <= time_s < opstart + 300:
        return "postintubation"
    if opend and max(opend - 300, 0) <= time_s < aneend:
        return "emergence"
    return "maintenance"


def _augment_baselines_with_waveforms(baselines, waveform_frame: pd.DataFrame) -> None:
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
        baselines.patient_t0[target] = float(series.median())
        baselines.stable[target] = float(series.median())


def _merge_numeric_and_waveforms(case_frame: pd.DataFrame, waveform_frame: pd.DataFrame | None) -> pd.DataFrame:
    if waveform_frame is None or waveform_frame.empty:
        return case_frame.copy()
    numeric = case_frame.copy()
    numeric["time_sec"] = pd.to_numeric(numeric["time_sec"], errors="coerce").astype("float64")
    waves = waveform_frame.copy()
    waves["time_s"] = pd.to_numeric(waves["time_s"], errors="coerce").astype("float64")
    merged = pd.merge_asof(
        numeric.sort_values("time_sec"),
        waves.sort_values("time_s"),
        left_on="time_sec",
        right_on="time_s",
        direction="nearest",
        tolerance=10.0,
    )
    return merged


def run_case_evaluation(
    *,
    case_id: int,
    metadata_row: pd.Series,
    cases_dir: Path,
    waveforms_dir: Path,
    config: HypotensionDetectorConfig,
    with_waveforms: bool,
) -> dict | None:
    case_path = cases_dir / f"case_{case_id:05d}.parquet"
    case_frame = load_case_numeric_frame(case_path)
    onset = find_reference_hypotension_onset(case_frame, map_target=config.map_target, sap_target=config.sap_target, min_duration_s=config.sustained_confirm_s)
    if onset is None or onset < 300.0:
        return None

    waveform_frame = pd.DataFrame()
    waveform_mode = "numeric_only"
    if with_waveforms and _has_waveforms(case_id, waveforms_dir):
        waveform_frame = build_waveform_feature_frame(case_id, waveforms_dir, bin_seconds=config.waveform_bin_seconds)
        waveform_mode = "waveforms_enabled"
    merged = _merge_numeric_and_waveforms(case_frame, waveform_frame)
    baselines = build_case_baselines(case_frame, config=config)
    _augment_baselines_with_waveforms(baselines, waveform_frame)
    detector = HypotensionDetector(baselines, config=config)

    outputs: list[dict] = []
    for row in merged.itertuples(index=False):
        series = pd.Series(row._asdict())
        snapshot = build_snapshot_from_row(
            series,
            waveform_row=series,
            metadata_row=metadata_row,
            phase=_infer_phase(float(series["time_sec"]), metadata_row),
        )
        output = detector.update(snapshot)
        outputs.append(asdict(output))

    outputs_df = pd.DataFrame(outputs)
    if outputs_df.empty:
        return None

    def first_time(states: set[str]) -> float | None:
        matches = outputs_df[outputs_df["state"].isin(states)]
        if matches.empty:
            return None
        return float(matches.iloc[0]["time_s"])

    first_early = first_time({"early_transition", "probable_hypotension", "confirmed_hypotension", "critical_hypotension", "refractory_hypotension"})
    first_probable = first_time({"probable_hypotension", "confirmed_hypotension", "critical_hypotension", "refractory_hypotension"})
    first_confirmed = first_time({"confirmed_hypotension", "critical_hypotension", "refractory_hypotension"})
    first_critical = first_time({"critical_hypotension", "refractory_hypotension"})

    pre_onset_outputs = outputs_df[outputs_df["time_s"] < onset]
    first_pre_onset_alert = None
    if not pre_onset_outputs.empty:
        alerts = pre_onset_outputs[pre_onset_outputs["state"] != "stable"]
        if not alerts.empty:
            first_pre_onset_alert = float(alerts.iloc[0]["time_s"])

    peak_row = outputs_df.sort_values(["severity", "risk_5min"], ascending=False).iloc[0]
    return {
        "case_id": case_id,
        "waveform_mode": waveform_mode,
        "reference_onset_s": round(float(onset), 3),
        "first_early_transition_s": None if first_early is None else round(first_early, 3),
        "first_probable_s": None if first_probable is None else round(first_probable, 3),
        "first_confirmed_s": None if first_confirmed is None else round(first_confirmed, 3),
        "first_critical_s": None if first_critical is None else round(first_critical, 3),
        "first_pre_onset_alert_s": None if first_pre_onset_alert is None else round(first_pre_onset_alert, 3),
        "anticipation_early_s": None if first_early is None else round(float(onset - first_early), 3),
        "anticipation_confirmed_s": None if first_confirmed is None else round(float(onset - first_confirmed), 3),
        "peak_state": str(peak_row["state"]),
        "peak_risk": round(float(peak_row["risk_5min"]), 6),
        "peak_severity": round(float(peak_row["severity"]), 6),
        "peak_confidence": round(float(peak_row["confidence"]), 6),
        "peak_time_s": round(float(peak_row["time_s"]), 3),
        "peak_cause_profile": peak_row["cause_profile"],
        "peak_explanation": peak_row["explanation"],
        "baseline_map": round(float(baselines.patient_t0["map"]), 3) if baselines.patient_t0.get("map") is not None else None,
        "baseline_sap": round(float(baselines.patient_t0["sap"]), 3) if baselines.patient_t0.get("sap") is not None else None,
        "baseline_etco2": round(float(baselines.patient_t0["etco2"]), 3) if baselines.patient_t0.get("etco2") is not None else None,
        "baseline_reliability": round(float(baselines.reliability), 6),
        "outputs": outputs,
    }


def select_cases(metadata: pd.DataFrame, cases_dir: Path, waveforms_dir: Path, config: HypotensionDetectorConfig, *, limit_scan: int) -> dict[str, list[int]]:
    with_waveforms: list[int] = []
    without_waveforms: list[int] = []
    scanned = 0
    for row in metadata.itertuples(index=False):
        case_id = int(row.caseid)
        case_path = cases_dir / f"case_{case_id:05d}.parquet"
        if not case_path.exists():
            continue
        scanned += 1
        case_frame = load_case_numeric_frame(case_path)
        onset = find_reference_hypotension_onset(case_frame, map_target=config.map_target, sap_target=config.sap_target, min_duration_s=config.sustained_confirm_s)
        if onset is None or onset < 300.0:
            if scanned >= limit_scan and len(with_waveforms) >= 2 and len(without_waveforms) >= 2:
                break
            continue
        has_wave = _has_waveforms(case_id, waveforms_dir)
        if has_wave and len(with_waveforms) < 2:
            with_waveforms.append(case_id)
        if not has_wave and len(without_waveforms) < 2:
            without_waveforms.append(case_id)
        if scanned >= limit_scan and len(with_waveforms) >= 2 and len(without_waveforms) >= 2:
            break
        if len(with_waveforms) >= 2 and len(without_waveforms) >= 2:
            break

    if len(without_waveforms) < 2:
        for case_id in with_waveforms:
            if case_id not in without_waveforms:
                without_waveforms.append(case_id)
            if len(without_waveforms) >= 2:
                break
    return {"with_waveforms": with_waveforms[:2], "without_waveforms": without_waveforms[:2]}


def _format_case_block(result: dict) -> str:
    return "\n".join(
        [
            f"### Case {result['case_id']} ({result['waveform_mode']})",
            f"- Reference onset: `{result['reference_onset_s']} s`",
            f"- First early transition: `{result['first_early_transition_s']} s`",
            f"- First probable: `{result['first_probable_s']} s`",
            f"- First confirmed: `{result['first_confirmed_s']} s`",
            f"- First critical: `{result['first_critical_s']} s`",
            f"- Early anticipation vs onset: `{result['anticipation_early_s']} s`",
            f"- Confirmed anticipation vs onset: `{result['anticipation_confirmed_s']} s`",
            f"- Peak state: `{result['peak_state']}` at `{result['peak_time_s']} s`",
            f"- Peak risk / severity / confidence: `{result['peak_risk']}` / `{result['peak_severity']}` / `{result['peak_confidence']}`",
            f"- Baseline MAP / SAP / EtCO2: `{result['baseline_map']}` / `{result['baseline_sap']}` / `{result['baseline_etco2']}`",
            f"- Peak cause profile: `{json.dumps(result['peak_cause_profile'], ensure_ascii=False)}`",
            f"- Peak explanation: `{'; '.join(result['peak_explanation'])}`",
        ]
    )


def write_report(output_dir: Path, payload: dict) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "hypotension_evaluation_results.json"
    md_path = output_dir / "hypotension_evaluation_report.md"
    json_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

    lines = [
        "# Hypotension Model Evaluation",
        "",
        f"- Generated at: `{payload['generated_at']}`",
        f"- Cases with waveforms: `{payload['selected_cases']['with_waveforms']}`",
        f"- Cases without waveforms: `{payload['selected_cases']['without_waveforms']}`",
        "",
        "## Summary",
    ]
    for result in payload["results"]:
        lines.append(
            f"- Case `{result['case_id']}` / `{result['waveform_mode']}`: onset `{result['reference_onset_s']} s`, early `{result['first_early_transition_s']} s`, confirmed `{result['first_confirmed_s']} s`, peak `{result['peak_state']}`"
        )
    lines.extend(["", "## Detailed Results", ""])
    for result in payload["results"]:
        lines.append(_format_case_block(result))
        lines.append("")
    md_path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate the robust hypotension detector on VitalDB cases.")
    parser.add_argument("--limit-scan", type=int, default=250, help="Maximum number of case files to scan while selecting examples.")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--with-waveforms", type=int, nargs="*", default=None, help="Explicit case ids to evaluate with waveforms enabled.")
    parser.add_argument("--without-waveforms", type=int, nargs="*", default=None, help="Explicit case ids to evaluate in numeric-only mode.")
    args = parser.parse_args()

    config = HypotensionDetectorConfig()
    cases_dir = ROOT / "vitaldb" / "cases"
    waveforms_dir = ROOT / "vitaldb" / "waveforms"
    metadata = pd.read_csv(ROOT / "vitaldb" / "clinical_metadata.csv")
    if args.with_waveforms is not None or args.without_waveforms is not None:
        selected = {
            "with_waveforms": list(args.with_waveforms or [])[:2],
            "without_waveforms": list(args.without_waveforms or [])[:2],
        }
    else:
        selected = select_cases(metadata, cases_dir, waveforms_dir, config, limit_scan=args.limit_scan)

    metadata_indexed = metadata.set_index("caseid", drop=False)
    results: list[dict] = []
    for case_id in selected["with_waveforms"]:
        result = run_case_evaluation(
            case_id=case_id,
            metadata_row=metadata_indexed.loc[case_id],
            cases_dir=cases_dir,
            waveforms_dir=waveforms_dir,
            config=config,
            with_waveforms=True,
        )
        if result is not None:
            results.append(result)
    for case_id in selected["without_waveforms"]:
        result = run_case_evaluation(
            case_id=case_id,
            metadata_row=metadata_indexed.loc[case_id],
            cases_dir=cases_dir,
            waveforms_dir=waveforms_dir,
            config=config,
            with_waveforms=False,
        )
        if result is not None:
            results.append(result)

    payload = {
        "generated_at": pd.Timestamp.now("UTC").isoformat(),
        "selected_cases": selected,
        "config": asdict(config),
        "results": results,
    }
    write_report(args.output_dir, payload)
    print(json.dumps({"selected_cases": selected, "output_dir": str(args.output_dir), "result_count": len(results)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
