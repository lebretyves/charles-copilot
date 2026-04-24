from __future__ import annotations

import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import pandas as pd

from learning.pipelines.evaluate_hypotension_asa1_v2_summary import (
    CASES_DIR,
    ROOT,
    evaluate_case,
    load_minimal_case_frame,
    summarize,
)
from learning.problems.hypotension_model import (
    HypotensionDetectorConfig,
    find_reference_hypotension_onset,
)


OUTPUT_DIR = ROOT / "learning" / "evaluation" / "hypotension_model_asa1_strict_v2"
SOURCE_SUMMARY_PATH = ROOT / "learning" / "evaluation" / "hypotension_model_asa1_v2" / "summary.json"


def load_metadata_with_cohorts() -> pd.DataFrame:
    metadata = pd.read_csv(ROOT / "vitaldb" / "clinical_metadata.csv").set_index("caseid", drop=False)
    metadata["asa_num"] = pd.to_numeric(metadata["asa"], errors="coerce")
    metadata["preop_htn_num"] = pd.to_numeric(metadata.get("preop_htn"), errors="coerce").fillna(0)
    metadata["preop_dm_num"] = pd.to_numeric(metadata.get("preop_dm"), errors="coerce").fillna(0)
    metadata["asa1_source"] = metadata["asa_num"] == 1.0
    metadata["asa_label_conflict"] = metadata["asa1_source"] & (
        (metadata["preop_htn_num"] == 1.0) | (metadata["preop_dm_num"] == 1.0)
    )
    metadata["asa1_strict_eligible"] = metadata["asa1_source"] & ~metadata["asa_label_conflict"]

    metadata["asa_effective_for_analysis"] = metadata["asa_num"]
    metadata.loc[metadata["asa_label_conflict"], "asa_effective_for_analysis"] = 2.0
    return metadata


def build_hypotension_case_ids(metadata: pd.DataFrame, config: HypotensionDetectorConfig) -> list[int]:
    target_case_ids: list[int] = []
    for case_path in sorted(CASES_DIR.glob("case_*.parquet")):
        case_id = int(case_path.stem.split("_")[1])
        if case_id not in metadata.index:
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
    return target_case_ids


def run_subset(case_ids: list[int], metadata: pd.DataFrame, config: HypotensionDetectorConfig) -> tuple[list[dict], float]:
    started_at = time.perf_counter()
    results: list[dict] = []
    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = {
            executor.submit(evaluate_case, case_id, metadata.loc[case_id], config): case_id
            for case_id in case_ids
        }
        for future in as_completed(futures):
            result = future.result()
            if result is not None:
                results.append(result)
    elapsed = time.perf_counter() - started_at
    return results, elapsed


def summarize_modes(results: list[dict]) -> dict:
    wave = [item for item in results if item["waveform_mode"] == "waveforms_enabled"]
    nowave = [item for item in results if item["waveform_mode"] == "numeric_only"]
    return {
        "overall": summarize(results),
        "waveforms_enabled": summarize(wave),
        "numeric_only": summarize(nowave),
        "with_waveforms": len(wave),
        "without_waveforms": len(nowave),
    }


def percent(numerator: int, denominator: int) -> float | None:
    if denominator == 0:
        return None
    return round((numerator / denominator) * 100.0, 3)


def metric_delta(source_metric: dict, strict_metric: dict) -> dict:
    source_count = source_metric["available"]
    strict_count = strict_metric["available"]
    source_before = source_metric["detected_before_onset"]
    strict_before = strict_metric["detected_before_onset"]
    source_rate = percent(source_before, source_count)
    strict_rate = percent(strict_before, strict_count)
    absolute_rate_delta = None
    if source_rate is not None and strict_rate is not None:
        absolute_rate_delta = round(strict_rate - source_rate, 3)
    mean_delta = None
    if source_metric["mean_s"] is not None and strict_metric["mean_s"] is not None:
        mean_delta = round(strict_metric["mean_s"] - source_metric["mean_s"], 3)
    median_delta = None
    if source_metric["median_s"] is not None and strict_metric["median_s"] is not None:
        median_delta = round(strict_metric["median_s"] - source_metric["median_s"], 3)
    return {
        "source_rate_pct": source_rate,
        "strict_rate_pct": strict_rate,
        "rate_delta_pct_points": absolute_rate_delta,
        "mean_s_delta": mean_delta,
        "median_s_delta": median_delta,
    }


def main() -> int:
    metadata = load_metadata_with_cohorts()
    config = HypotensionDetectorConfig()
    hypotension_case_ids = build_hypotension_case_ids(metadata, config)

    hypotension_metadata = metadata.loc[hypotension_case_ids].copy()
    asa1_source = hypotension_metadata[hypotension_metadata["asa1_source"]].copy()
    asa1_strict = hypotension_metadata[hypotension_metadata["asa1_strict_eligible"]].copy()
    removed = asa1_source[asa1_source["asa_label_conflict"]].copy()

    cohort_labels = (
        asa1_source[
            [
                "caseid",
                "asa",
                "asa_num",
                "asa_effective_for_analysis",
                "preop_htn",
                "preop_dm",
                "asa1_source",
                "asa_label_conflict",
                "asa1_strict_eligible",
            ]
        ]
        .copy()
        .reset_index(drop=True)
        .sort_values("caseid")
    )

    strict_results, strict_elapsed = run_subset(asa1_strict["caseid"].tolist(), metadata, config)
    removed_results, removed_elapsed = run_subset(removed["caseid"].tolist(), metadata, config)

    strict_summary = summarize_modes(strict_results)
    removed_summary = summarize_modes(removed_results)

    source_summary = json.loads(SOURCE_SUMMARY_PATH.read_text(encoding="utf-8"))
    source_overall = source_summary["overall"]
    strict_overall = strict_summary["overall"]

    comparison = {
        "source_cases": len(asa1_source),
        "strict_cases": len(asa1_strict),
        "removed_conflict_cases": len(removed),
        "removed_fraction_pct": percent(len(removed), len(asa1_source)),
        "strict_fraction_pct": percent(len(asa1_strict), len(asa1_source)),
        "early": metric_delta(source_overall["early"], strict_overall["early"]),
        "probable": metric_delta(source_overall["probable"], strict_overall["probable"]),
        "confirmed": metric_delta(source_overall["confirmed"], strict_overall["confirmed"]),
        "peak_risk_delta": round(strict_overall["mean_peak_risk"] - source_overall["mean_peak_risk"], 4),
        "peak_confidence_delta": round(strict_overall["mean_peak_confidence"] - source_overall["mean_peak_confidence"], 4),
    }

    payload = {
        "subset": "ASA1_strict_hypotension_v2_only",
        "cohort_definition": {
            "asa1_source": "asa == 1.0",
            "asa1_conflict": "asa == 1.0 and (preop_htn == 1 or preop_dm == 1)",
            "asa1_strict": "asa == 1.0 and preop_htn == 0 and preop_dm == 0",
            "asa_effective_for_analysis": "2.0 when asa1_conflict else asa_num",
        },
        "hypotension_total": len(hypotension_metadata),
        "asa1_source_total": len(asa1_source),
        "asa1_strict_total": len(asa1_strict),
        "asa1_conflict_total": len(removed),
        "strict_elapsed_seconds": round(strict_elapsed, 3),
        "removed_elapsed_seconds": round(removed_elapsed, 3),
        "source_summary_reference": source_summary,
        "strict_summary": strict_summary,
        "removed_conflict_summary": removed_summary,
        "comparison_vs_asa1_source": comparison,
    }

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    cohort_labels.to_csv(OUTPUT_DIR / "asa1_cohort_labels.csv", index=False)
    (OUTPUT_DIR / "strict_summary.json").write_text(
        json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    lines = [
        "# Hypotension V2 - ASA 1 Strict Summary",
        "",
        "## Cohortes",
        f"- Hypotension total: `{payload['hypotension_total']}`",
        f"- ASA 1 source: `{payload['asa1_source_total']}`",
        f"- ASA 1 strict: `{payload['asa1_strict_total']}`",
        f"- ASA 1 conflict: `{payload['asa1_conflict_total']}`",
        f"- Fraction retirée: `{comparison['removed_fraction_pct']}%`",
        "",
        "## ASA 1 Strict",
        f"- Runtime: `{payload['strict_elapsed_seconds']} s`",
        f"- early: `{strict_summary['overall']['early']}`",
        f"- probable: `{strict_summary['overall']['probable']}`",
        f"- confirmed: `{strict_summary['overall']['confirmed']}`",
        f"- mean_peak_risk: `{strict_summary['overall']['mean_peak_risk']}`",
        f"- mean_peak_confidence: `{strict_summary['overall']['mean_peak_confidence']}`",
        "",
        "## Cas retirés (conflict ASA 1)",
        f"- Runtime: `{payload['removed_elapsed_seconds']} s`",
        f"- early: `{removed_summary['overall']['early']}`",
        f"- probable: `{removed_summary['overall']['probable']}`",
        f"- confirmed: `{removed_summary['overall']['confirmed']}`",
        f"- mean_peak_risk: `{removed_summary['overall']['mean_peak_risk']}`",
        f"- mean_peak_confidence: `{removed_summary['overall']['mean_peak_confidence']}`",
        "",
        "## Incidence vs ASA 1 Source",
        f"- early: `{comparison['early']}`",
        f"- probable: `{comparison['probable']}`",
        f"- confirmed: `{comparison['confirmed']}`",
        f"- peak_risk_delta: `{comparison['peak_risk_delta']}`",
        f"- peak_confidence_delta: `{comparison['peak_confidence_delta']}`",
    ]
    (OUTPUT_DIR / "strict_summary.md").write_text("\n".join(lines), encoding="utf-8")

    print(json.dumps(payload, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
