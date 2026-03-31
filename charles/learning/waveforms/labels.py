from __future__ import annotations

LABEL_TAXONOMY = {
    "stable_window": "No critical numeric drift detected in the window.",
    "hypotension": "Mean arterial pressure trend below 65 mmHg.",
    "hypotension_critical": "Mean arterial pressure trend below 55 mmHg.",
    "desaturation": "SpO2 trend below 92%.",
    "desaturation_critical": "SpO2 trend below 88%.",
    "tachycardia": "Heart rate trend above 110 bpm.",
    "bradycardia": "Heart rate trend below 45 bpm.",
    "hypercapnia": "EtCO2 trend above 50 mmHg.",
    "hypocapnia": "EtCO2 trend below 30 mmHg.",
    "tachypnea": "Respiratory rate trend above 24/min.",
    "bradypnea": "Respiratory rate trend below 8/min.",
    "deep_hypnosis": "BIS trend below 40.",
}


def infer_weak_labels(vitals_summary: dict[str, float | int | None]) -> list[str]:
    labels: list[str] = []

    pam_min = vitals_summary.get("pam_min")
    spo2_min = vitals_summary.get("spo2_min")
    hr_max = vitals_summary.get("hr_max")
    hr_min = vitals_summary.get("hr_min")
    etco2_max = vitals_summary.get("etco2_max")
    etco2_min = vitals_summary.get("etco2_min")
    fr_max = vitals_summary.get("fr_max")
    fr_min = vitals_summary.get("fr_min")
    bis_min = vitals_summary.get("bis_min")

    if pam_min is not None and pam_min < 55:
        labels.append("hypotension_critical")
    elif pam_min is not None and pam_min < 65:
        labels.append("hypotension")

    if spo2_min is not None and spo2_min < 88:
        labels.append("desaturation_critical")
    elif spo2_min is not None and spo2_min < 92:
        labels.append("desaturation")

    if hr_max is not None and hr_max > 110:
        labels.append("tachycardia")
    if hr_min is not None and hr_min < 45:
        labels.append("bradycardia")

    if etco2_max is not None and etco2_max > 50:
        labels.append("hypercapnia")
    if etco2_min is not None and etco2_min < 30:
        labels.append("hypocapnia")

    if fr_max is not None and fr_max > 24:
        labels.append("tachypnea")
    if fr_min is not None and fr_min < 8:
        labels.append("bradypnea")

    if bis_min is not None and bis_min < 40:
        labels.append("deep_hypnosis")

    if not labels:
        labels.append("stable_window")

    return labels

