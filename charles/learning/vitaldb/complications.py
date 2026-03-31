from __future__ import annotations

from collections import Counter, defaultdict, deque
from pathlib import Path
from typing import Any

import pandas as pd


COMPLICATION_TAXONOMY = {
    "emergency_case": "Emergency surgery flag from VitalDB metadata.",
    "postop_icu_admission": "ICU stay after surgery (icu_days > 0).",
    "in_hospital_mortality": "In-hospital mortality outcome.",
    "major_blood_loss": "Estimated blood loss >= 500 mL.",
    "massive_blood_loss": "Estimated blood loss >= 1000 mL.",
    "rbc_transfusion": "Red blood cell transfusion recorded intraoperatively.",
    "plasma_transfusion": "Fresh frozen plasma transfusion recorded intraoperatively.",
    "vasopressor_support": "At least one vasopressor support signal in metadata.",
    "ephedrine_support": "Intraoperative ephedrine recorded.",
    "phenylephrine_support": "Intraoperative phenylephrine recorded.",
    "epinephrine_support": "Intraoperative epinephrine recorded.",
    "difficult_airway_proxy": "Cormack III/IV or non-standard airway metadata.",
    "intraop_anemia_lab": "Intraoperative Hb/Hct crossed anemia threshold.",
    "intraop_acidemia_lab": "Intraoperative pH < 7.30.",
    "severe_intraop_acidemia_lab": "Intraoperative pH < 7.20.",
    "intraop_hypercapnia_lab": "Intraoperative pCO2 > 50.",
    "intraop_hyperglycemia_lab": "Intraoperative glucose > 180.",
    "intraop_hyperkalemia_lab": "Intraoperative potassium > 5.5.",
    "intraop_hypokalemia_lab": "Intraoperative potassium < 3.0.",
    "renal_dysfunction_lab": "Intraoperative creatinine or BUN elevated.",
}

RELEVANT_LABS = {"hb", "hct", "ph", "pco2", "gluc", "k", "cr", "bun"}


def _clean_value(value: Any) -> Any:
    if pd.isna(value):
        return None
    if hasattr(value, "item"):
        try:
            return value.item()
        except Exception:
            return value
    return value


def _as_float(value: Any) -> float | None:
    cleaned = _clean_value(value)
    if cleaned is None:
        return None
    try:
        return float(cleaned)
    except (TypeError, ValueError):
        return None


def load_lab_summary(labs_csv: str | Path | None) -> dict[int, dict[str, float | None]]:
    if not labs_csv:
        return {}
    source = Path(labs_csv)
    if not source.exists():
        return {}

    frame = pd.read_csv(source, usecols=["caseid", "name", "result"])
    frame = frame[frame["name"].isin(RELEVANT_LABS)].copy()
    if frame.empty:
        return {}

    frame["result"] = pd.to_numeric(frame["result"], errors="coerce")
    frame = frame.dropna(subset=["result"])
    if frame.empty:
        return {}

    grouped = frame.groupby(["caseid", "name"])["result"].agg(["min", "max"]).reset_index()
    summary: dict[int, dict[str, float | None]] = defaultdict(dict)
    for row in grouped.itertuples(index=False):
        case_id = int(row.caseid)
        summary[case_id][f"{row.name}_min"] = round(float(row.min), 4)
        summary[case_id][f"{row.name}_max"] = round(float(row.max), 4)
    return dict(summary)


def derive_case_complications(
    metadata_row: dict[str, Any],
    lab_summary: dict[str, float | None] | None = None,
) -> list[str]:
    tags: list[str] = []
    lab_summary = lab_summary or {}

    emop = _as_float(metadata_row.get("emop"))
    icu_days = _as_float(metadata_row.get("icu_days"))
    death_inhosp = _as_float(metadata_row.get("death_inhosp"))
    ebl = _as_float(metadata_row.get("intraop_ebl"))
    rbc = _as_float(metadata_row.get("intraop_rbc"))
    ffp = _as_float(metadata_row.get("intraop_ffp"))
    eph = _as_float(metadata_row.get("intraop_eph"))
    phe = _as_float(metadata_row.get("intraop_phe"))
    epi = _as_float(metadata_row.get("intraop_epi"))

    if emop and emop > 0:
        tags.append("emergency_case")
    if icu_days and icu_days > 0:
        tags.append("postop_icu_admission")
    if death_inhosp and death_inhosp > 0:
        tags.append("in_hospital_mortality")

    if ebl is not None and ebl >= 500:
        tags.append("major_blood_loss")
    if ebl is not None and ebl >= 1000:
        tags.append("massive_blood_loss")
    if rbc and rbc > 0:
        tags.append("rbc_transfusion")
    if ffp and ffp > 0:
        tags.append("plasma_transfusion")

    if any(value is not None and value > 0 for value in (eph, phe, epi)):
        tags.append("vasopressor_support")
    if eph and eph > 0:
        tags.append("ephedrine_support")
    if phe and phe > 0:
        tags.append("phenylephrine_support")
    if epi and epi > 0:
        tags.append("epinephrine_support")

    cormack = str(metadata_row.get("cormack") or "").strip().upper()
    airway = str(metadata_row.get("airway") or "").strip().lower()
    if cormack.startswith("III") or cormack == "IV" or airway in {"tracheostomy", "nasal"}:
        tags.append("difficult_airway_proxy")

    hb_min = _as_float(lab_summary.get("hb_min"))
    hct_min = _as_float(lab_summary.get("hct_min"))
    ph_min = _as_float(lab_summary.get("ph_min"))
    pco2_max = _as_float(lab_summary.get("pco2_max"))
    gluc_max = _as_float(lab_summary.get("gluc_max"))
    k_min = _as_float(lab_summary.get("k_min"))
    k_max = _as_float(lab_summary.get("k_max"))
    cr_max = _as_float(lab_summary.get("cr_max"))
    bun_max = _as_float(lab_summary.get("bun_max"))

    if (hb_min is not None and hb_min < 8.0) or (hct_min is not None and hct_min < 24.0):
        tags.append("intraop_anemia_lab")
    if ph_min is not None and ph_min < 7.30:
        tags.append("intraop_acidemia_lab")
    if ph_min is not None and ph_min < 7.20:
        tags.append("severe_intraop_acidemia_lab")
    if pco2_max is not None and pco2_max > 50:
        tags.append("intraop_hypercapnia_lab")
    if gluc_max is not None and gluc_max > 180:
        tags.append("intraop_hyperglycemia_lab")
    if k_max is not None and k_max > 5.5:
        tags.append("intraop_hyperkalemia_lab")
    if k_min is not None and k_min < 3.0:
        tags.append("intraop_hypokalemia_lab")
    if (cr_max is not None and cr_max > 1.5) or (bun_max is not None and bun_max > 30):
        tags.append("renal_dysfunction_lab")

    return sorted(set(tags))


def load_case_contexts_with_complications(
    metadata_csv: str | Path,
    context_columns: list[str],
    labs_csv: str | Path | None = None,
) -> dict[int, dict[str, Any]]:
    metadata_path = Path(metadata_csv)
    if not metadata_path.exists():
        return {}

    wanted_columns = ["caseid", *context_columns]
    frame = pd.read_csv(metadata_path, usecols=lambda column: column in wanted_columns or column == "caseid")
    lab_summary = load_lab_summary(labs_csv)
    contexts: dict[int, dict[str, Any]] = {}
    for _, row in frame.iterrows():
        case_id = int(row["caseid"])
        context = {column: _clean_value(row[column]) for column in context_columns if column in row.index}
        context["case_complications"] = derive_case_complications(context, lab_summary.get(case_id))
        contexts[case_id] = context
    return contexts


def choose_diverse_case_files(
    case_files: list[Path],
    contexts: dict[int, dict[str, Any]],
    *,
    limit_cases: int | None = None,
    per_complication_cap: int = 20,
) -> list[Path]:
    if limit_cases is None:
        return case_files

    case_lookup = {int(path.stem.replace("case_", "")): path for path in case_files}
    tag_buckets: dict[str, deque[int]] = defaultdict(deque)
    baseline_bucket: deque[int] = deque()

    for case_id in sorted(case_lookup):
        tags = contexts.get(case_id, {}).get("case_complications", [])
        if not tags:
            baseline_bucket.append(case_id)
            continue
        for tag in tags:
            tag_buckets[tag].append(case_id)

    tag_order = sorted(tag_buckets, key=lambda tag: (len(tag_buckets[tag]), tag))
    per_tag_count: Counter[str] = Counter()
    selected_ids: list[int] = []
    selected_set: set[int] = set()

    progress = True
    while progress and len(selected_ids) < limit_cases:
        progress = False
        for tag in tag_order:
            if per_tag_count[tag] >= per_complication_cap:
                continue
            bucket = tag_buckets[tag]
            while bucket and bucket[0] in selected_set:
                bucket.popleft()
            if not bucket:
                continue
            case_id = bucket.popleft()
            if case_id in selected_set:
                continue
            selected_ids.append(case_id)
            selected_set.add(case_id)
            per_tag_count[tag] += 1
            progress = True
            if len(selected_ids) >= limit_cases:
                break

    while baseline_bucket and len(selected_ids) < limit_cases:
        case_id = baseline_bucket.popleft()
        if case_id not in selected_set:
            selected_ids.append(case_id)
            selected_set.add(case_id)

    for case_id in sorted(case_lookup):
        if len(selected_ids) >= limit_cases:
            break
        if case_id not in selected_set:
            selected_ids.append(case_id)
            selected_set.add(case_id)

    return [case_lookup[case_id] for case_id in selected_ids]
