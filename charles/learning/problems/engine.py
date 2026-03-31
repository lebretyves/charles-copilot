from __future__ import annotations

from learning.problems.schemas import ProblemAnalysisRecord, ProblemHypothesis
from learning.waveforms.schemas import FeatureRecord


PROBLEM_IDS = {
    "hemodynamic_instability",
    "respiratory_instability",
    "airway_mechanics_issue",
    "depth_excess",
    "light_anesthesia_possible",
    "hemorrhage_context",
    "vasopressor_dependence_context",
    "adverse_outcome_context",
    "difficult_airway_context",
    "metabolic_derangement_context",
    "signal_quality_issue",
    "stable_segment",
}


def _severity_from_score(score: float, critical: bool = False) -> str:
    if critical or score >= 0.85:
        return "critical"
    if score >= 0.55:
        return "warning"
    return "info"


def _append_if_relevant(
    hypotheses: list[ProblemHypothesis],
    *,
    problem_id: str,
    score: float,
    reasons: list[str],
    evidence: dict,
    critical: bool = False,
) -> None:
    if score < 0.35:
        return
    hypotheses.append(
        ProblemHypothesis(
            problem_id=problem_id,
            severity=_severity_from_score(score, critical=critical),
            score=min(round(score, 4), 1.0),
            reasons=reasons,
            evidence=evidence,
        )
    )


def _get_numeric(record: FeatureRecord, key: str):
    if key in record.numeric_features:
        return record.numeric_features[key]
    return record.vitals_snapshot.get(key)


def infer_problem_hypotheses(record: FeatureRecord) -> list[ProblemHypothesis]:
    weak_labels = set(record.weak_labels)
    case_complications = set(record.case_complications)
    hypotheses: list[ProblemHypothesis] = []

    pam_min = _get_numeric(record, "pam_min")
    pas_min = _get_numeric(record, "pas_min")
    pas_max = _get_numeric(record, "pas_max")
    spo2_min = _get_numeric(record, "spo2_min")
    hr_max = _get_numeric(record, "hr_max")
    etco2_min = _get_numeric(record, "etco2_min")
    etco2_max = _get_numeric(record, "etco2_max")
    fr_max = _get_numeric(record, "fr_max")
    fr_min = _get_numeric(record, "fr_min")
    bis_min = _get_numeric(record, "bis_min")
    bis_max = _get_numeric(record, "bis_max")
    pam_delta = record.numeric_features.get("pam_delta")
    awp_features = record.signal_features.get("awp")

    hemo_score = 0.0
    hemo_reasons: list[str] = []
    hemo_evidence = {}
    critical_hemo = False
    if "hypotension_critical" in weak_labels:
        hemo_score += 0.55
        hemo_reasons.append("weak label hypotension_critical")
        critical_hemo = True
    elif "hypotension" in weak_labels:
        hemo_score += 0.35
        hemo_reasons.append("weak label hypotension")
    if pam_min is not None and pam_min < 65:
        hemo_score += 0.2
        hemo_reasons.append("pam_min below 65")
        hemo_evidence["pam_min"] = pam_min
        if pam_min < 55:
            critical_hemo = True
    if pas_min is not None and pas_min < 90:
        hemo_score += 0.15
        hemo_reasons.append("pas_min below 90")
        hemo_evidence["pas_min"] = pas_min
    if hr_max is not None and hr_max > 100:
        hemo_score += 0.1
        hemo_reasons.append("hr_max above 100")
        hemo_evidence["hr_max"] = hr_max
    if pam_delta is not None and pam_delta < -10:
        hemo_score += 0.1
        hemo_reasons.append("pam trending down")
        hemo_evidence["pam_delta"] = pam_delta
    _append_if_relevant(
        hypotheses,
        problem_id="hemodynamic_instability",
        score=hemo_score,
        reasons=hemo_reasons,
        evidence=hemo_evidence,
        critical=critical_hemo,
    )

    resp_score = 0.0
    resp_reasons: list[str] = []
    resp_evidence = {}
    critical_resp = False
    if "desaturation_critical" in weak_labels:
        resp_score += 0.45
        resp_reasons.append("weak label desaturation_critical")
        critical_resp = True
    elif "desaturation" in weak_labels:
        resp_score += 0.3
        resp_reasons.append("weak label desaturation")
    if "hypercapnia" in weak_labels or "hypocapnia" in weak_labels:
        resp_score += 0.2
        resp_reasons.append("EtCO2 weak label present")
    if spo2_min is not None and spo2_min < 92:
        resp_score += 0.15
        resp_reasons.append("spo2_min below 92")
        resp_evidence["spo2_min"] = spo2_min
        if spo2_min < 88:
            critical_resp = True
    if etco2_max is not None and etco2_max > 50:
        resp_score += 0.1
        resp_reasons.append("etco2_max above 50")
        resp_evidence["etco2_max"] = etco2_max
    if etco2_min is not None and etco2_min < 30:
        resp_score += 0.1
        resp_reasons.append("etco2_min below 30")
        resp_evidence["etco2_min"] = etco2_min
    if (fr_max is not None and fr_max > 24) or (fr_min is not None and fr_min < 8):
        resp_score += 0.1
        resp_reasons.append("respiratory rate out of range")
        resp_evidence["fr_max"] = fr_max
        resp_evidence["fr_min"] = fr_min
    _append_if_relevant(
        hypotheses,
        problem_id="respiratory_instability",
        score=resp_score,
        reasons=resp_reasons,
        evidence=resp_evidence,
        critical=critical_resp,
    )

    airway_score = 0.0
    airway_reasons: list[str] = []
    airway_evidence = {}
    if awp_features:
        if awp_features.max is not None and awp_features.max > 18:
            airway_score += 0.25
            airway_reasons.append("awp max above 18")
            airway_evidence["awp_max"] = awp_features.max
        if awp_features.amplitude is not None and awp_features.amplitude > 8:
            airway_score += 0.15
            airway_reasons.append("awp amplitude above 8")
            airway_evidence["awp_amplitude"] = awp_features.amplitude
        if resp_score >= 0.55:
            airway_score += 0.1
            airway_reasons.append("paired with respiratory instability")
    _append_if_relevant(
        hypotheses,
        problem_id="airway_mechanics_issue",
        score=airway_score,
        reasons=airway_reasons,
        evidence=airway_evidence,
    )

    depth_score = 0.0
    depth_reasons: list[str] = []
    depth_evidence = {}
    if "deep_hypnosis" in weak_labels:
        depth_score += 0.45
        depth_reasons.append("weak label deep_hypnosis")
    if bis_min is not None and bis_min < 40:
        depth_score += 0.25
        depth_reasons.append("bis_min below 40")
        depth_evidence["bis_min"] = bis_min
    _append_if_relevant(
        hypotheses,
        problem_id="depth_excess",
        score=depth_score,
        reasons=depth_reasons,
        evidence=depth_evidence,
        critical=bis_min is not None and bis_min < 30,
    )

    light_score = 0.0
    light_reasons: list[str] = []
    light_evidence = {}
    if bis_max is not None and bis_max > 65:
        light_score += 0.3
        light_reasons.append("bis_max above 65")
        light_evidence["bis_max"] = bis_max
    if hr_max is not None and hr_max > 110:
        light_score += 0.15
        light_reasons.append("hr_max above 110")
        light_evidence["hr_max"] = hr_max
    if pas_max is not None and pas_max > 160:
        light_score += 0.2
        light_reasons.append("pas_max above 160")
        light_evidence["pas_max"] = pas_max
    if "deep_hypnosis" not in weak_labels and light_score >= 0.3:
        light_score += 0.05
        light_reasons.append("no deep_hypnosis weak label")
    _append_if_relevant(
        hypotheses,
        problem_id="light_anesthesia_possible",
        score=light_score,
        reasons=light_reasons,
        evidence=light_evidence,
    )

    hemorrhage_score = 0.0
    hemorrhage_reasons: list[str] = []
    hemorrhage_evidence = {}
    if "major_blood_loss" in case_complications:
        hemorrhage_score += 0.35
        hemorrhage_reasons.append("major blood loss metadata")
    if "massive_blood_loss" in case_complications:
        hemorrhage_score += 0.3
        hemorrhage_reasons.append("massive blood loss metadata")
    if "rbc_transfusion" in case_complications:
        hemorrhage_score += 0.2
        hemorrhage_reasons.append("rbc transfusion metadata")
    if "plasma_transfusion" in case_complications:
        hemorrhage_score += 0.15
        hemorrhage_reasons.append("plasma transfusion metadata")
    if hemorrhage_reasons:
        hemorrhage_evidence["case_complications"] = sorted(case_complications & {"major_blood_loss", "massive_blood_loss", "rbc_transfusion", "plasma_transfusion"})
    _append_if_relevant(
        hypotheses,
        problem_id="hemorrhage_context",
        score=hemorrhage_score,
        reasons=hemorrhage_reasons,
        evidence=hemorrhage_evidence,
        critical="massive_blood_loss" in case_complications,
    )

    vaso_score = 0.0
    vaso_reasons: list[str] = []
    vaso_evidence = {}
    if "vasopressor_support" in case_complications:
        vaso_score += 0.35
        vaso_reasons.append("vasopressor support metadata")
    if "epinephrine_support" in case_complications:
        vaso_score += 0.25
        vaso_reasons.append("epinephrine support metadata")
    if "phenylephrine_support" in case_complications:
        vaso_score += 0.1
        vaso_reasons.append("phenylephrine support metadata")
    if "ephedrine_support" in case_complications:
        vaso_score += 0.1
        vaso_reasons.append("ephedrine support metadata")
    if hemo_score >= 0.55:
        vaso_score += 0.1
        vaso_reasons.append("paired with hemodynamic instability")
    if vaso_reasons:
        vaso_evidence["case_complications"] = sorted(case_complications & {"vasopressor_support", "epinephrine_support", "phenylephrine_support", "ephedrine_support"})
    _append_if_relevant(
        hypotheses,
        problem_id="vasopressor_dependence_context",
        score=vaso_score,
        reasons=vaso_reasons,
        evidence=vaso_evidence,
    )

    outcome_score = 0.0
    outcome_reasons: list[str] = []
    outcome_evidence = {}
    if "postop_icu_admission" in case_complications:
        outcome_score += 0.3
        outcome_reasons.append("postop icu admission metadata")
    if "in_hospital_mortality" in case_complications:
        outcome_score += 0.45
        outcome_reasons.append("in-hospital mortality metadata")
    if "emergency_case" in case_complications:
        outcome_score += 0.15
        outcome_reasons.append("emergency case metadata")
    if outcome_reasons:
        outcome_evidence["case_complications"] = sorted(case_complications & {"postop_icu_admission", "in_hospital_mortality", "emergency_case"})
    _append_if_relevant(
        hypotheses,
        problem_id="adverse_outcome_context",
        score=outcome_score,
        reasons=outcome_reasons,
        evidence=outcome_evidence,
        critical="in_hospital_mortality" in case_complications,
    )

    airway_ctx_score = 0.0
    airway_ctx_reasons: list[str] = []
    airway_ctx_evidence = {}
    if "difficult_airway_proxy" in case_complications:
        airway_ctx_score += 0.4
        airway_ctx_reasons.append("difficult airway metadata")
    if airway_score >= 0.35:
        airway_ctx_score += 0.15
        airway_ctx_reasons.append("paired with airway mechanics issue")
    if airway_ctx_reasons:
        airway_ctx_evidence["case_complications"] = sorted(case_complications & {"difficult_airway_proxy"})
    _append_if_relevant(
        hypotheses,
        problem_id="difficult_airway_context",
        score=airway_ctx_score,
        reasons=airway_ctx_reasons,
        evidence=airway_ctx_evidence,
    )

    metabolic_score = 0.0
    metabolic_reasons: list[str] = []
    metabolic_evidence = {}
    metabolic_tags = case_complications & {
        "intraop_anemia_lab",
        "intraop_acidemia_lab",
        "severe_intraop_acidemia_lab",
        "intraop_hypercapnia_lab",
        "intraop_hyperglycemia_lab",
        "intraop_hyperkalemia_lab",
        "intraop_hypokalemia_lab",
        "renal_dysfunction_lab",
    }
    if "intraop_anemia_lab" in metabolic_tags:
        metabolic_score += 0.15
        metabolic_reasons.append("intraoperative anemia lab proxy")
    if "intraop_acidemia_lab" in metabolic_tags:
        metabolic_score += 0.2
        metabolic_reasons.append("intraoperative acidemia lab proxy")
    if "severe_intraop_acidemia_lab" in metabolic_tags:
        metabolic_score += 0.2
        metabolic_reasons.append("severe intraoperative acidemia lab proxy")
    if "intraop_hypercapnia_lab" in metabolic_tags:
        metabolic_score += 0.15
        metabolic_reasons.append("intraoperative hypercapnia lab proxy")
    if "intraop_hyperglycemia_lab" in metabolic_tags:
        metabolic_score += 0.1
        metabolic_reasons.append("intraoperative hyperglycemia lab proxy")
    if "intraop_hyperkalemia_lab" in metabolic_tags or "intraop_hypokalemia_lab" in metabolic_tags:
        metabolic_score += 0.15
        metabolic_reasons.append("potassium derangement lab proxy")
    if "renal_dysfunction_lab" in metabolic_tags:
        metabolic_score += 0.1
        metabolic_reasons.append("renal dysfunction lab proxy")
    if metabolic_reasons:
        metabolic_evidence["case_complications"] = sorted(metabolic_tags)
    _append_if_relevant(
        hypotheses,
        problem_id="metabolic_derangement_context",
        score=metabolic_score,
        reasons=metabolic_reasons,
        evidence=metabolic_evidence,
        critical="severe_intraop_acidemia_lab" in metabolic_tags,
    )

    quality_score = 0.0
    quality_reasons: list[str] = []
    quality_evidence = {}
    low_coverage = [name for name, stats in record.signal_features.items() if stats.coverage_ratio < 0.85]
    flat_signals = [name for name, stats in record.signal_features.items() if stats.std is not None and stats.std < 1e-6 and stats.samples > 1]
    if low_coverage:
        quality_score += min(0.2 * len(low_coverage), 0.5)
        quality_reasons.append(f"low coverage signals: {', '.join(low_coverage)}")
        quality_evidence["low_coverage_signals"] = low_coverage
    if flat_signals:
        quality_score += min(0.2 * len(flat_signals), 0.4)
        quality_reasons.append(f"flat signals: {', '.join(flat_signals)}")
        quality_evidence["flat_signals"] = flat_signals
    _append_if_relevant(
        hypotheses,
        problem_id="signal_quality_issue",
        score=quality_score,
        reasons=quality_reasons,
        evidence=quality_evidence,
    )

    hypotheses.sort(key=lambda item: item.score, reverse=True)
    if not hypotheses:
        hypotheses.append(
            ProblemHypothesis(
                problem_id="stable_segment",
                severity="info",
                score=0.8,
                reasons=["no baseline problem heuristic crossed the threshold"],
                evidence={},
            )
        )
    return hypotheses


def infer_problem_record(feature_record: FeatureRecord) -> ProblemAnalysisRecord:
    hypotheses = infer_problem_hypotheses(feature_record)
    return ProblemAnalysisRecord(
        segment_id=feature_record.segment_id,
        case_id=feature_record.case_id,
        start_s=feature_record.start_s,
        end_s=feature_record.end_s,
        weak_labels=list(feature_record.weak_labels),
        vitals_snapshot=dict(feature_record.vitals_snapshot),
        numeric_features=dict(feature_record.numeric_features),
        signal_features=dict(feature_record.signal_features),
        source_files=dict(feature_record.source_files),
        case_context=dict(feature_record.case_context),
        case_complications=list(feature_record.case_complications),
        feature_version=feature_record.feature_version,
        primary_problem_id=hypotheses[0].problem_id if hypotheses else None,
        problem_hypotheses=hypotheses,
    )
