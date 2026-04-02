from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

import math

import numpy as np
import pandas as pd


HypotensionState = Literal[
    "stable",
    "vulnerable",
    "early_transition",
    "probable_hypotension",
    "confirmed_hypotension",
    "critical_hypotension",
    "refractory_hypotension",
    "recovering",
]

CauseName = Literal[
    "vasoplegic",
    "hypovolemic",
    "cardiodepressive",
    "brady_dependent",
    "obstructive",
    "mixed",
    "artifact",
    "indeterminate",
]

TIME_COLUMN = "time_sec"
ART_MBP_COLUMNS = ("Solar8000/ART_MBP",)
ART_SBP_COLUMNS = ("Solar8000/ART_SBP",)
NIBP_MBP_COLUMNS = ("Solar8000/NIBP_MBP",)
NIBP_SBP_COLUMNS = ("Solar8000/NIBP_SBP",)
HR_COLUMNS = ("Solar8000/HR",)
SPO2_COLUMNS = ("Solar8000/PLETH_SPO2",)
ETCO2_COLUMNS = ("Solar8000/ETCO2",)
BIS_COLUMNS = ("BIS/BIS",)
PPF_COLUMNS = ("Orchestra/PPF20_CE",)
RFTN_COLUMNS = ("Orchestra/RFTN20_CE",)
ART_WAVE_COLUMN = "SNUADC/ART"
PLETH_WAVE_COLUMN = "SNUADC/PLETH"
CO2_WAVE_COLUMN = "Primus/CO2"


@dataclass(slots=True)
class HypotensionDetectorConfig:
    map_target: float = 65.0
    map_critical: float = 55.0
    sap_target: float = 90.0
    sap_critical: float = 75.0
    relative_drop_mild: float = 0.10
    relative_drop_severe: float = 0.25
    early_relative_drop_mild: float = 0.05
    early_relative_drop_severe: float = 0.18
    etco2_drop_mild: float = 0.08
    etco2_drop_severe: float = 0.20
    pleth_drop_mild: float = 0.10
    pleth_drop_severe: float = 0.30
    short_window_s: float = 180.0
    fast_slope_window_s: float = 30.0
    incipient_burden_window_s: float = 90.0
    incipient_burden_fraction_mild: float = 0.10
    incipient_burden_fraction_severe: float = 0.35
    episode_close_stable_s: float = 180.0
    refractory_after_s: float = 180.0
    sustained_confirm_s: float = 60.0
    risk_smoothing_alpha: float = 0.70
    severity_smoothing_alpha: float = 0.75
    stable_baseline_alpha: float = 0.08
    waveform_bin_seconds: float = 10.0
    baseline_min_points: int = 10


@dataclass(slots=True)
class HypotensionSnapshot:
    time_s: float
    map_value: float | None
    sap_value: float | None
    hr: float | None
    etco2: float | None
    spo2: float | None
    bis: float | None
    ppf_ce: float | None = None
    rftn_ce: float | None = None
    art_wave_amplitude: float | None = None
    art_wave_slope: float | None = None
    pleth_wave_amplitude: float | None = None
    pleth_wave_slope: float | None = None
    capno_wave_amplitude: float | None = None
    capno_wave_slope: float | None = None
    operative_phase: str = "maintenance"
    chronic_hypertension: bool = False
    coronary_disease: bool = False
    heart_failure: bool = False
    frailty: bool = False
    obstetric_context: bool = False


@dataclass(slots=True)
class HypotensionBaselines:
    patient_t0: dict[str, float] = field(default_factory=dict)
    stable: dict[str, float] = field(default_factory=dict)
    reliability: float = 0.0


@dataclass(slots=True)
class HypotensionOutput:
    time_s: float
    state: HypotensionState
    risk_5min: float
    severity: float
    refractory_flag: bool
    cause_profile: dict[str, float]
    confidence: float
    explanation: list[str]
    episode_id: int | None
    episode_start_s: float | None
    contradiction_score: float
    novelty_score: float
    burden_seconds: float
    burden_area: float
    map_value: float | None
    sap_value: float | None


@dataclass(slots=True)
class _EpisodeMemory:
    state: HypotensionState = "stable"
    episode_id: int | None = None
    episode_start_s: float | None = None
    peak_risk: float = 0.0
    peak_severity: float = 0.0
    time_under_threshold_s: float = 0.0
    area_under_target: float = 0.0
    relapse_count: int = 0
    confirmed_duration_s: float = 0.0
    stable_duration_s: float = 0.0
    risk_short: float = 0.0
    severity_short: float = 0.0
    last_time_s: float | None = None
    last_state: HypotensionState = "stable"


def _safe_float(value: object) -> float | None:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return None
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(numeric) or math.isinf(numeric):
        return None
    return numeric


def _clip01(value: float) -> float:
    return min(max(float(value), 0.0), 1.0)


def _linear_band(value: float | None, *, mild: float, severe: float, inverse: bool = False) -> float:
    numeric = _safe_float(value)
    if numeric is None:
        return 0.0
    if inverse:
        if numeric >= mild:
            return 0.0
        if numeric <= severe:
            return 1.0
        return _clip01((mild - numeric) / max(mild - severe, 1e-6))
    if numeric <= mild:
        return 0.0
    if numeric >= severe:
        return 1.0
    return _clip01((numeric - mild) / max(severe - mild, 1e-6))


def _relative_drop(current: float | None, baseline: float | None) -> float | None:
    current_value = _safe_float(current)
    baseline_value = _safe_float(baseline)
    if current_value is None or baseline_value is None or baseline_value <= 0:
        return None
    return (baseline_value - current_value) / baseline_value


def _score_relative_drop(current: float | None, baseline: float | None, *, mild: float, severe: float) -> float:
    return _linear_band(_relative_drop(current, baseline), mild=mild, severe=severe)


def _plausible_pressure(value: float | None, *, lower: float, upper: float) -> float | None:
    numeric = _safe_float(value)
    if numeric is None:
        return None
    if numeric < lower or numeric > upper:
        return None
    return numeric


def _first_plausible(row: pd.Series, columns: tuple[str, ...], *, lower: float, upper: float) -> float | None:
    for column in columns:
        if column not in row.index:
            continue
        numeric = _plausible_pressure(row[column], lower=lower, upper=upper)
        if numeric is not None:
            return numeric
    return None


def _median_of_plausible(frame: pd.DataFrame, columns: tuple[str, ...], *, lower: float, upper: float) -> float | None:
    values: list[float] = []
    for column in columns:
        if column not in frame.columns:
            continue
        series = pd.to_numeric(frame[column], errors="coerce").dropna()
        if series.empty:
            continue
        plausible = series[(series >= lower) & (series <= upper)]
        if not plausible.empty:
            values.extend(float(x) for x in plausible.to_list())
            break
    if not values:
        return None
    return float(np.median(values))


def _mean_of_plausible(frame: pd.DataFrame, columns: tuple[str, ...], *, lower: float, upper: float) -> float | None:
    values: list[float] = []
    for column in columns:
        if column not in frame.columns:
            continue
        series = pd.to_numeric(frame[column], errors="coerce").dropna()
        plausible = series[(series >= lower) & (series <= upper)]
        if not plausible.empty:
            values.extend(float(x) for x in plausible.to_list())
            break
    if not values:
        return None
    return float(np.mean(values))


def _normalize_distribution(raw_scores: dict[str, float]) -> dict[str, float]:
    clipped = {key: max(float(value), 0.0) for key, value in raw_scores.items()}
    total = sum(clipped.values())
    if total <= 0:
        return {key: 0.0 for key in raw_scores}
    return {key: round(value / total, 6) for key, value in clipped.items()}


class HypotensionDetector:
    def __init__(self, baselines: HypotensionBaselines, config: HypotensionDetectorConfig | None = None):
        self.baselines = baselines
        self.config = config or HypotensionDetectorConfig()
        self.memory = _EpisodeMemory()
        self._next_episode_id = 1
        self._recent: deque[HypotensionSnapshot] = deque()

    def update(self, snapshot: HypotensionSnapshot) -> HypotensionOutput:
        dt = self._step_delta(snapshot.time_s)
        self._push_recent(snapshot)
        pressure_scores = self._compute_pressure_scores(snapshot)
        perfusion_scores = self._compute_perfusion_scores(snapshot)
        context_scores = self._compute_context_scores(snapshot)
        waveform_scores = self._compute_waveform_scores(snapshot)
        contradiction_score = self._compute_contradiction_score(snapshot, pressure_scores, perfusion_scores, waveform_scores)
        cause_profile = self._compute_cause_profile(snapshot, pressure_scores, perfusion_scores, context_scores, waveform_scores, contradiction_score)
        confidence = self._compute_confidence(snapshot, contradiction_score, waveform_scores)
        has_nonpressure_support = perfusion_scores["support"] >= 0.12 or waveform_scores["multicurve"] >= 0.12
        deviation_score = (
            0.35 * pressure_scores["relative_early"]
            + 0.20 * pressure_scores["slope"]
            + 0.10 * pressure_scores["incipient_burden"]
            + 0.20 * perfusion_scores["support"]
            + 0.15 * waveform_scores["novelty"]
        )
        changepoint_score = max(pressure_scores["slope"], waveform_scores["novelty"], perfusion_scores["trend"])
        transition_coherence = self._compute_transition_coherence(snapshot, pressure_scores, perfusion_scores, context_scores, waveform_scores)
        confirmation_score = (
            0.50 * pressure_scores["absolute"]
            + 0.20 * pressure_scores["relative"]
            + 0.15 * perfusion_scores["support"]
            + 0.15 * pressure_scores["burden"]
        )
        risk_precoce = _clip01(
            0.28 * deviation_score
            + 0.18 * changepoint_score
            + 0.16 * perfusion_scores["support"]
            + 0.14 * waveform_scores["multicurve"]
            + 0.14 * pressure_scores["relative_early"]
            + 0.04 * pressure_scores["incipient_burden"]
            + 0.12 * transition_coherence
            - 0.25 * contradiction_score
        )
        risk_constitue = _clip01(
            0.55 * confirmation_score
            + 0.15 * perfusion_scores["support"]
            + 0.10 * waveform_scores["multicurve"]
            + 0.10 * context_scores["tolerance"]
            + 0.10 * max(cause_profile.values())
            - 0.20 * contradiction_score
        )
        severity = _clip01(
            0.45 * pressure_scores["absolute"]
            + 0.25 * pressure_scores["burden"]
            + 0.15 * perfusion_scores["support"]
            + 0.15 * context_scores["response_failure"]
        )

        self.memory.risk_short = (
            self.config.risk_smoothing_alpha * self.memory.risk_short
            + (1.0 - self.config.risk_smoothing_alpha) * max(risk_precoce, risk_constitue)
        )
        self.memory.severity_short = (
            self.config.severity_smoothing_alpha * self.memory.severity_short
            + (1.0 - self.config.severity_smoothing_alpha) * severity
        )
        self._update_episode_burden(snapshot, dt)
        state = self._update_state(snapshot, risk_precoce, risk_constitue, severity, contradiction_score, transition_coherence, pressure_scores, has_nonpressure_support)
        self._update_stable_baseline(snapshot, confidence, state)

        explanation = self._build_explanation(snapshot, pressure_scores, perfusion_scores, waveform_scores, context_scores, contradiction_score, cause_profile, confidence, transition_coherence)
        self.memory.peak_risk = max(self.memory.peak_risk, max(risk_precoce, risk_constitue))
        self.memory.peak_severity = max(self.memory.peak_severity, severity)
        reported_risk = _clip01(max(risk_precoce, risk_constitue, self.memory.risk_short, severity if state != "stable" else 0.0))

        return HypotensionOutput(
            time_s=round(snapshot.time_s, 3),
            state=state,
            risk_5min=round(reported_risk, 6),
            severity=round(_clip01(max(severity, self.memory.severity_short)), 6),
            refractory_flag=state == "refractory_hypotension",
            cause_profile=cause_profile,
            confidence=round(confidence, 6),
            explanation=explanation,
            episode_id=self.memory.episode_id,
            episode_start_s=self.memory.episode_start_s,
            contradiction_score=round(contradiction_score, 6),
            novelty_score=round(waveform_scores["novelty"], 6),
            burden_seconds=round(self.memory.time_under_threshold_s, 3),
            burden_area=round(self.memory.area_under_target, 3),
            map_value=snapshot.map_value,
            sap_value=snapshot.sap_value,
        )

    def _step_delta(self, time_s: float) -> float:
        last_time = self.memory.last_time_s
        self.memory.last_time_s = time_s
        if last_time is None:
            return 0.0
        return max(time_s - last_time, 0.0)

    def _push_recent(self, snapshot: HypotensionSnapshot) -> None:
        self._recent.append(snapshot)
        cutoff = snapshot.time_s - self.config.short_window_s
        while self._recent and self._recent[0].time_s < cutoff:
            self._recent.popleft()

    def _recent_window(self, end_time_s: float, window_s: float) -> list[HypotensionSnapshot]:
        cutoff = end_time_s - window_s
        return [item for item in self._recent if item.time_s >= cutoff]

    def _compute_pressure_scores(self, snapshot: HypotensionSnapshot) -> dict[str, float]:
        baseline_map = self.baselines.stable.get("map") or self.baselines.patient_t0.get("map")
        baseline_sap = self.baselines.stable.get("sap") or self.baselines.patient_t0.get("sap")
        absolute_map = _linear_band(snapshot.map_value, mild=self.config.map_target, severe=self.config.map_critical, inverse=True)
        absolute_sap = _linear_band(snapshot.sap_value, mild=self.config.sap_target, severe=self.config.sap_critical, inverse=True)
        relative_map = _score_relative_drop(
            snapshot.map_value,
            baseline_map,
            mild=self.config.relative_drop_mild,
            severe=self.config.relative_drop_severe,
        )
        relative_sap = _score_relative_drop(
            snapshot.sap_value,
            baseline_sap,
            mild=self.config.relative_drop_mild,
            severe=self.config.relative_drop_severe,
        )
        relative_map_early = _score_relative_drop(
            snapshot.map_value,
            baseline_map,
            mild=self.config.early_relative_drop_mild,
            severe=self.config.early_relative_drop_severe,
        )
        relative_sap_early = _score_relative_drop(
            snapshot.sap_value,
            baseline_sap,
            mild=self.config.early_relative_drop_mild,
            severe=self.config.early_relative_drop_severe,
        )
        slope = 0.0
        if len(self._recent) >= 2:
            first = self._recent[0]
            last = self._recent[-1]
            if first.map_value is not None and last.map_value is not None and last.time_s > first.time_s:
                map_slope = (last.map_value - first.map_value) / max(last.time_s - first.time_s, 1e-6)
                slope = _linear_band(-map_slope, mild=0.01, severe=0.08)
        slope_fast = 0.0
        fast_window = self._recent_window(snapshot.time_s, self.config.fast_slope_window_s)
        if len(fast_window) >= 2:
            first_fast = fast_window[0]
            last_fast = fast_window[-1]
            if first_fast.map_value is not None and last_fast.map_value is not None and last_fast.time_s > first_fast.time_s:
                map_slope_fast = (last_fast.map_value - first_fast.map_value) / max(last_fast.time_s - first_fast.time_s, 1e-6)
                slope_fast = _linear_band(-map_slope_fast, mild=0.03, severe=0.20)
        burden = 0.0
        if self.memory.time_under_threshold_s > 0:
            burden = _clip01(
                0.60 * _linear_band(self.memory.time_under_threshold_s, mild=30.0, severe=180.0)
                + 0.40 * _linear_band(self.memory.area_under_target, mild=30.0, severe=300.0)
            )
        incipient_burden = 0.0
        incipient_window = self._recent_window(snapshot.time_s, self.config.incipient_burden_window_s)
        valid_map = [item.map_value for item in incipient_window if item.map_value is not None]
        if valid_map:
            low_fraction = sum(1 for value in valid_map if value < self.config.map_target) / len(valid_map)
            incipient_burden = _linear_band(
                low_fraction,
                mild=self.config.incipient_burden_fraction_mild,
                severe=self.config.incipient_burden_fraction_severe,
            )
        return {
            "absolute": _clip01(0.70 * absolute_map + 0.30 * absolute_sap),
            "relative": _clip01(0.65 * relative_map + 0.35 * relative_sap),
            "relative_early": _clip01(0.65 * relative_map_early + 0.35 * relative_sap_early),
            "slope": max(slope, slope_fast),
            "slope_fast": slope_fast,
            "burden": burden,
            "incipient_burden": incipient_burden,
        }

    def _compute_perfusion_scores(self, snapshot: HypotensionSnapshot) -> dict[str, float]:
        baseline_etco2 = self.baselines.stable.get("etco2") or self.baselines.patient_t0.get("etco2")
        baseline_spo2 = self.baselines.stable.get("spo2") or self.baselines.patient_t0.get("spo2")
        baseline_pleth_amp = self.baselines.stable.get("pleth_wave_amplitude") or self.baselines.patient_t0.get("pleth_wave_amplitude")
        etco2_drop = _score_relative_drop(snapshot.etco2, baseline_etco2, mild=self.config.etco2_drop_mild, severe=self.config.etco2_drop_severe)
        spo2_drop = _score_relative_drop(snapshot.spo2, baseline_spo2, mild=0.01, severe=0.05)
        pleth_drop = _score_relative_drop(
            snapshot.pleth_wave_amplitude,
            baseline_pleth_amp,
            mild=self.config.pleth_drop_mild,
            severe=self.config.pleth_drop_severe,
        )
        trend = max(etco2_drop, pleth_drop, spo2_drop)
        support = _clip01(0.45 * etco2_drop + 0.35 * pleth_drop + 0.20 * spo2_drop)
        return {"support": support, "trend": trend, "etco2_drop": etco2_drop, "pleth_drop": pleth_drop}

    def _compute_context_scores(self, snapshot: HypotensionSnapshot) -> dict[str, float]:
        low_bis = _linear_band(snapshot.bis, mild=45.0, severe=30.0, inverse=True)
        induction_context = 1.0 if snapshot.operative_phase in {"induction", "postintubation"} else 0.0
        tolerance = 0.0
        tolerance += 0.10 if snapshot.chronic_hypertension else 0.0
        tolerance += 0.10 if snapshot.coronary_disease else 0.0
        tolerance += 0.08 if snapshot.heart_failure else 0.0
        tolerance += 0.05 if snapshot.frailty else 0.0
        response_failure = 0.0
        if self.memory.state in {"confirmed_hypotension", "critical_hypotension"} and self.memory.time_under_threshold_s >= 60.0:
            response_failure += 0.4
        if self.memory.relapse_count >= 1:
            response_failure += 0.2
        return {
            "low_bis": low_bis,
            "induction_context": induction_context,
            "tolerance": _clip01(tolerance),
            "response_failure": _clip01(response_failure),
        }

    def _compute_waveform_scores(self, snapshot: HypotensionSnapshot) -> dict[str, float]:
        art_amp_drop = _score_relative_drop(
            snapshot.art_wave_amplitude,
            self.baselines.stable.get("art_wave_amplitude") or self.baselines.patient_t0.get("art_wave_amplitude"),
            mild=0.08,
            severe=0.25,
        )
        pleth_amp_drop = _score_relative_drop(
            snapshot.pleth_wave_amplitude,
            self.baselines.stable.get("pleth_wave_amplitude") or self.baselines.patient_t0.get("pleth_wave_amplitude"),
            mild=0.10,
            severe=0.35,
        )
        capno_amp_drop = _score_relative_drop(
            snapshot.capno_wave_amplitude,
            self.baselines.stable.get("capno_wave_amplitude") or self.baselines.patient_t0.get("capno_wave_amplitude"),
            mild=0.08,
            severe=0.30,
        )
        novelty = _clip01(0.40 * art_amp_drop + 0.35 * pleth_amp_drop + 0.25 * capno_amp_drop)
        multicurve = _clip01(
            0.50 * min(1.0, art_amp_drop + pleth_amp_drop)
            + 0.25 * capno_amp_drop
            + 0.25 * max(snapshot.art_wave_slope or 0.0, snapshot.pleth_wave_slope or 0.0) / 1000.0
        )
        return {"novelty": novelty, "multicurve": multicurve}

    def _compute_contradiction_score(
        self,
        snapshot: HypotensionSnapshot,
        pressure_scores: dict[str, float],
        perfusion_scores: dict[str, float],
        waveform_scores: dict[str, float],
    ) -> float:
        if pressure_scores["absolute"] < 0.30:
            return 0.0
        contradiction = 0.0
        if perfusion_scores["support"] < 0.10:
            contradiction += 0.35
        if waveform_scores["multicurve"] < 0.10 and snapshot.art_wave_amplitude is not None:
            contradiction += 0.25
        if snapshot.hr is not None and 55 <= snapshot.hr <= 95:
            contradiction += 0.10
        if snapshot.spo2 is not None and snapshot.spo2 >= 95:
            contradiction += 0.05
        return _clip01(contradiction)

    def _compute_transition_coherence(
        self,
        snapshot: HypotensionSnapshot,
        pressure_scores: dict[str, float],
        perfusion_scores: dict[str, float],
        context_scores: dict[str, float],
        waveform_scores: dict[str, float],
    ) -> float:
        components = 0.0
        if pressure_scores["relative_early"] >= 0.20:
            components += 1.0
        if max(pressure_scores["slope_fast"], pressure_scores["slope"]) >= 0.20:
            components += 1.0
        if perfusion_scores["support"] >= 0.18:
            components += 1.0
        if waveform_scores["multicurve"] >= 0.18:
            components += 1.0
        near_threshold = False
        if snapshot.map_value is not None and snapshot.map_value <= self.config.map_target + 3.0:
            near_threshold = True
        if snapshot.sap_value is not None and snapshot.sap_value <= self.config.sap_target + 8.0:
            near_threshold = True
        if near_threshold:
            components += 0.5
        return _linear_band(components, mild=1.0, severe=3.0)

    def _compute_cause_profile(
        self,
        snapshot: HypotensionSnapshot,
        pressure_scores: dict[str, float],
        perfusion_scores: dict[str, float],
        context_scores: dict[str, float],
        waveform_scores: dict[str, float],
        contradiction_score: float,
    ) -> dict[str, float]:
        hypotension_weight = max(pressure_scores["absolute"], pressure_scores["relative"], self.memory.risk_short)
        hr_high = _linear_band(snapshot.hr, mild=95.0, severe=120.0)
        hr_low = _linear_band(snapshot.hr, mild=55.0, severe=40.0, inverse=True)
        preserved_perfusion = 1.0 - perfusion_scores["support"]
        vasoplegic = hypotension_weight * (0.45 * context_scores["induction_context"] + 0.30 * context_scores["low_bis"] + 0.25 * preserved_perfusion)
        hypovolemic = hypotension_weight * (0.45 * perfusion_scores["support"] + 0.25 * waveform_scores["multicurve"] + 0.20 * hr_high + 0.10 * pressure_scores["burden"])
        cardiodepressive = hypotension_weight * (0.40 * perfusion_scores["support"] + 0.25 * (1.0 - hr_high) + 0.20 * context_scores["low_bis"] + 0.15 * pressure_scores["absolute"])
        brady_dependent = hypotension_weight * (0.70 * hr_low + 0.30 * pressure_scores["absolute"])
        obstructive = hypotension_weight * (0.40 * perfusion_scores["etco2_drop"] + 0.30 * hr_high + 0.30 * waveform_scores["novelty"])
        artifact = max(0.05, contradiction_score)
        raw = {
            "vasoplegic": vasoplegic,
            "hypovolemic": hypovolemic,
            "cardiodepressive": cardiodepressive,
            "brady_dependent": brady_dependent,
            "obstructive": obstructive,
            "artifact": artifact,
            "indeterminate": 0.10,
        }
        profile = _normalize_distribution(raw)
        sorted_items = sorted(profile.items(), key=lambda item: item[1], reverse=True)
        if len(sorted_items) >= 2 and abs(sorted_items[0][1] - sorted_items[1][1]) <= 0.10:
            profile["mixed"] = round(sorted_items[0][1] + sorted_items[1][1], 6)
        else:
            profile["mixed"] = 0.0
        total = sum(profile.values())
        if total > 0:
            profile = {key: round(value / total, 6) for key, value in profile.items()}
        return profile

    def _compute_confidence(self, snapshot: HypotensionSnapshot, contradiction_score: float, waveform_scores: dict[str, float]) -> float:
        density = 0.0
        if snapshot.map_value is not None:
            density += 0.30
        if snapshot.sap_value is not None:
            density += 0.10
        if snapshot.etco2 is not None:
            density += 0.15
        if snapshot.hr is not None:
            density += 0.10
        if snapshot.bis is not None:
            density += 0.05
        if snapshot.art_wave_amplitude is not None or snapshot.pleth_wave_amplitude is not None or snapshot.capno_wave_amplitude is not None:
            density += 0.20
        density += 0.10 * self.baselines.reliability
        confidence = density - 0.35 * contradiction_score + 0.10 * waveform_scores["multicurve"]
        return _clip01(confidence)

    def _update_episode_burden(self, snapshot: HypotensionSnapshot, dt: float) -> None:
        if dt <= 0 or snapshot.map_value is None:
            return
        if snapshot.map_value < self.config.map_target:
            self.memory.time_under_threshold_s += dt
            self.memory.area_under_target += (self.config.map_target - snapshot.map_value) * dt
            if self.memory.state in {"confirmed_hypotension", "critical_hypotension", "refractory_hypotension"}:
                self.memory.confirmed_duration_s += dt
            self.memory.stable_duration_s = 0.0
        else:
            self.memory.stable_duration_s += dt

    def _update_state(
        self,
        snapshot: HypotensionSnapshot,
        risk_precoce: float,
        risk_constitue: float,
        severity: float,
        contradiction_score: float,
        transition_coherence: float,
        pressure_scores: dict[str, float],
        has_nonpressure_support: bool,
    ) -> HypotensionState:
        previous_state = self.memory.state
        risk = max(risk_precoce, risk_constitue, self.memory.risk_short)
        confirmed_like = risk_constitue >= 0.72 or (snapshot.map_value is not None and snapshot.map_value < self.config.map_target and self.memory.time_under_threshold_s >= self.config.sustained_confirm_s)
        near_threshold_pressure = pressure_scores["absolute"] >= 0.15 or (snapshot.map_value is not None and snapshot.map_value <= self.config.map_target)
        permissive_early_support = has_nonpressure_support or near_threshold_pressure

        if snapshot.map_value is not None and snapshot.map_value <= self.config.map_critical:
            state: HypotensionState = "critical_hypotension"
        elif confirmed_like:
            state = "confirmed_hypotension"
        elif risk >= 0.60:
            state = "probable_hypotension"
        elif (risk >= 0.42 and permissive_early_support) or (
            risk_precoce >= 0.34 and transition_coherence >= 0.55 and contradiction_score <= 0.25 and permissive_early_support
        ):
            state = "early_transition"
        elif risk_precoce >= 0.30 and pressure_scores["relative_early"] >= 0.25 and contradiction_score <= 0.30:
            state = "vulnerable"
        elif self.memory.episode_id is not None and self.memory.stable_duration_s < self.config.episode_close_stable_s:
            state = "recovering"
        else:
            state = "stable"

        if contradiction_score >= 0.60 and severity < 0.50:
            state = "stable"

        if state in {"early_transition", "probable_hypotension", "confirmed_hypotension", "critical_hypotension"} and self.memory.episode_id is None:
            self.memory.episode_id = self._next_episode_id
            self._next_episode_id += 1
            self.memory.episode_start_s = snapshot.time_s

        if previous_state in {"confirmed_hypotension", "critical_hypotension"} and state in {"early_transition", "probable_hypotension"}:
            state = "recovering"

        if self.memory.confirmed_duration_s >= self.config.refractory_after_s and state in {"confirmed_hypotension", "critical_hypotension"}:
            state = "refractory_hypotension"

        if previous_state == "recovering" and state in {"early_transition", "probable_hypotension", "confirmed_hypotension", "critical_hypotension"}:
            self.memory.relapse_count += 1

        if state == "stable" and self.memory.episode_id is not None and self.memory.stable_duration_s >= self.config.episode_close_stable_s:
            self.memory = _EpisodeMemory(last_time_s=self.memory.last_time_s)
            return "stable"

        self.memory.last_state = previous_state
        self.memory.state = state
        return state

    def _update_stable_baseline(self, snapshot: HypotensionSnapshot, confidence: float, state: HypotensionState) -> None:
        if confidence < 0.50 or state not in {"stable", "recovering"}:
            return
        alpha = self.config.stable_baseline_alpha
        for key, value in {
            "map": snapshot.map_value,
            "sap": snapshot.sap_value,
            "hr": snapshot.hr,
            "etco2": snapshot.etco2,
            "spo2": snapshot.spo2,
            "bis": snapshot.bis,
            "art_wave_amplitude": snapshot.art_wave_amplitude,
            "pleth_wave_amplitude": snapshot.pleth_wave_amplitude,
            "capno_wave_amplitude": snapshot.capno_wave_amplitude,
        }.items():
            numeric = _safe_float(value)
            if numeric is None:
                continue
            previous = self.baselines.stable.get(key)
            if previous is None:
                self.baselines.stable[key] = numeric
            else:
                self.baselines.stable[key] = (1.0 - alpha) * previous + alpha * numeric

    def _build_explanation(
        self,
        snapshot: HypotensionSnapshot,
        pressure_scores: dict[str, float],
        perfusion_scores: dict[str, float],
        waveform_scores: dict[str, float],
        context_scores: dict[str, float],
        contradiction_score: float,
        cause_profile: dict[str, float],
        confidence: float,
        transition_coherence: float,
    ) -> list[str]:
        reasons: list[str] = []
        baseline_map = self.baselines.stable.get("map") or self.baselines.patient_t0.get("map")
        if snapshot.map_value is not None and baseline_map is not None:
            delta = _relative_drop(snapshot.map_value, baseline_map)
            if delta is not None:
                reasons.append(f"MAP delta_vs_baseline={delta:.1%}")
        if snapshot.map_value is not None:
            reasons.append(f"MAP={snapshot.map_value:.1f}")
        if snapshot.sap_value is not None:
            reasons.append(f"SAP={snapshot.sap_value:.1f}")
        if perfusion_scores["etco2_drop"] > 0:
            reasons.append(f"EtCO2_drop_score={perfusion_scores['etco2_drop']:.2f}")
        if perfusion_scores["pleth_drop"] > 0:
            reasons.append(f"pleth_drop_score={perfusion_scores['pleth_drop']:.2f}")
        if waveform_scores["multicurve"] > 0:
            reasons.append(f"multicurve_score={waveform_scores['multicurve']:.2f}")
        if pressure_scores["incipient_burden"] > 0:
            reasons.append(f"incipient_burden_score={pressure_scores['incipient_burden']:.2f}")
        if transition_coherence > 0:
            reasons.append(f"transition_coherence={transition_coherence:.2f}")
        if context_scores["low_bis"] > 0:
            reasons.append("low_BIS_context")
        if context_scores["induction_context"] > 0:
            reasons.append("induction_related_phase")
        if contradiction_score > 0:
            reasons.append(f"contradiction_score={contradiction_score:.2f}")
        dominant = max(cause_profile.items(), key=lambda item: item[1])
        reasons.append(f"dominant_cause={dominant[0]}:{dominant[1]:.2f}")
        reasons.append(f"confidence={confidence:.2f}")
        return reasons


def load_case_numeric_frame(case_path: str | Path) -> pd.DataFrame:
    frame = pd.read_parquet(case_path).copy()
    if TIME_COLUMN not in frame.columns:
        raise ValueError(f"Missing {TIME_COLUMN} in {case_path}")
    frame = frame.sort_values(TIME_COLUMN).reset_index(drop=True)
    frame["clean_map"] = frame.apply(
        lambda row: _first_plausible(row, ART_MBP_COLUMNS, lower=20.0, upper=180.0)
        or _first_plausible(row, NIBP_MBP_COLUMNS, lower=20.0, upper=180.0),
        axis=1,
    )
    frame["clean_sap"] = frame.apply(
        lambda row: _first_plausible(row, ART_SBP_COLUMNS, lower=30.0, upper=260.0)
        or _first_plausible(row, NIBP_SBP_COLUMNS, lower=30.0, upper=260.0),
        axis=1,
    )
    frame["clean_hr"] = pd.to_numeric(frame.get(HR_COLUMNS[0]), errors="coerce")
    frame.loc[(frame["clean_hr"] < 20) | (frame["clean_hr"] > 220), "clean_hr"] = np.nan
    frame["clean_spo2"] = pd.to_numeric(frame.get(SPO2_COLUMNS[0]), errors="coerce")
    frame.loc[(frame["clean_spo2"] < 40) | (frame["clean_spo2"] > 100), "clean_spo2"] = np.nan
    frame["clean_etco2"] = pd.to_numeric(frame.get(ETCO2_COLUMNS[0]), errors="coerce")
    frame.loc[(frame["clean_etco2"] < 0) | (frame["clean_etco2"] > 80), "clean_etco2"] = np.nan
    frame["clean_bis"] = pd.to_numeric(frame.get(BIS_COLUMNS[0]), errors="coerce")
    frame.loc[(frame["clean_bis"] < 0) | (frame["clean_bis"] > 100), "clean_bis"] = np.nan
    frame["clean_ppf_ce"] = pd.to_numeric(frame.get(PPF_COLUMNS[0]), errors="coerce")
    frame["clean_rftn_ce"] = pd.to_numeric(frame.get(RFTN_COLUMNS[0]), errors="coerce")
    return frame


def build_case_baselines(case_frame: pd.DataFrame, config: HypotensionDetectorConfig | None = None) -> HypotensionBaselines:
    config = config or HypotensionDetectorConfig()
    early = case_frame[case_frame[TIME_COLUMN] <= min(300.0, float(case_frame[TIME_COLUMN].max()))].copy()
    baselines = HypotensionBaselines()
    if len(early) < config.baseline_min_points:
        early = case_frame.head(config.baseline_min_points)
    baselines.patient_t0 = {
        "map": _median_of_plausible(early, ("clean_map",), lower=20.0, upper=180.0),
        "sap": _median_of_plausible(early, ("clean_sap",), lower=30.0, upper=260.0),
        "hr": _mean_of_plausible(early, ("clean_hr",), lower=20.0, upper=220.0),
        "etco2": _mean_of_plausible(early, ("clean_etco2",), lower=5.0, upper=80.0),
        "spo2": _mean_of_plausible(early, ("clean_spo2",), lower=40.0, upper=100.0),
        "bis": _mean_of_plausible(early, ("clean_bis",), lower=0.0, upper=100.0),
    }
    baselines.stable = dict(baselines.patient_t0)
    valid_count = sum(value is not None for value in baselines.patient_t0.values())
    baselines.reliability = valid_count / max(len(baselines.patient_t0), 1)
    return baselines


def build_snapshot_from_row(
    row: pd.Series,
    *,
    waveform_row: pd.Series | None = None,
    metadata_row: pd.Series | None = None,
    phase: str = "maintenance",
) -> HypotensionSnapshot:
    waveform_row = waveform_row if waveform_row is not None else pd.Series(dtype="float64")
    metadata_row = metadata_row if metadata_row is not None else pd.Series(dtype="object")
    return HypotensionSnapshot(
        time_s=float(row[TIME_COLUMN]),
        map_value=_safe_float(row.get("clean_map")),
        sap_value=_safe_float(row.get("clean_sap")),
        hr=_safe_float(row.get("clean_hr")),
        etco2=_safe_float(row.get("clean_etco2")),
        spo2=_safe_float(row.get("clean_spo2")),
        bis=_safe_float(row.get("clean_bis")),
        ppf_ce=_safe_float(row.get("clean_ppf_ce")),
        rftn_ce=_safe_float(row.get("clean_rftn_ce")),
        art_wave_amplitude=_safe_float(waveform_row.get("art_amp")),
        art_wave_slope=_safe_float(waveform_row.get("art_slope")),
        pleth_wave_amplitude=_safe_float(waveform_row.get("pleth_amp")),
        pleth_wave_slope=_safe_float(waveform_row.get("pleth_slope")),
        capno_wave_amplitude=_safe_float(waveform_row.get("co2_amp")),
        capno_wave_slope=_safe_float(waveform_row.get("co2_slope")),
        operative_phase=phase,
        chronic_hypertension=bool(metadata_row.get("preop_htn", 0) == 1),
        coronary_disease=False,
        heart_failure=False,
        frailty=bool((_safe_float(metadata_row.get("age")) or 0.0) >= 75.0),
        obstetric_context=str(metadata_row.get("department", "")).lower().startswith("obst"),
    )


def build_waveform_feature_frame(case_id: int, waveforms_dir: str | Path, *, bin_seconds: float = 10.0) -> pd.DataFrame:
    waveforms_dir = Path(waveforms_dir)
    sources = {
        "500hz": (waveforms_dir / f"wave_{case_id:05d}_500hz.parquet", {ART_WAVE_COLUMN: ("art_amp", "art_slope"), PLETH_WAVE_COLUMN: ("pleth_amp", "pleth_slope")}),
        "25hz": (waveforms_dir / f"wave_{case_id:05d}_25hz.parquet", {CO2_WAVE_COLUMN: ("co2_amp", "co2_slope")}),
    }
    pieces: list[pd.DataFrame] = []
    for path, columns in sources.values():
        if not path.exists():
            continue
        frame = pd.read_parquet(path)
        if TIME_COLUMN not in frame.columns:
            continue
        available_columns = {column: names for column, names in columns.items() if column in frame.columns}
        if not available_columns:
            continue
        frame = frame[[TIME_COLUMN, *available_columns.keys()]].copy()
        frame["time_bin"] = (pd.to_numeric(frame[TIME_COLUMN], errors="coerce") / bin_seconds).round().astype("Int64")
        group = frame.groupby("time_bin", dropna=True)
        rows: list[dict[str, float]] = []
        for time_bin, grouped in group:
            item: dict[str, float] = {"time_s": float(time_bin) * bin_seconds}
            for column, (amp_name, slope_name) in available_columns.items():
                series = pd.to_numeric(grouped[column], errors="coerce").dropna()
                if series.empty:
                    continue
                q05, q95 = series.quantile([0.05, 0.95]).to_list()
                item[amp_name] = float(q95 - q05)
                diffs = np.diff(series.to_numpy(dtype="float64"))
                item[slope_name] = float(np.mean(np.abs(diffs))) if diffs.size else 0.0
            rows.append(item)
        if rows:
            pieces.append(pd.DataFrame(rows))
    if not pieces:
        return pd.DataFrame(columns=["time_s", "art_amp", "art_slope", "pleth_amp", "pleth_slope", "co2_amp", "co2_slope"])
    merged = pieces[0]
    for piece in pieces[1:]:
        merged = merged.merge(piece, on="time_s", how="outer")
    return merged.sort_values("time_s").reset_index(drop=True)


def find_reference_hypotension_onset(
    case_frame: pd.DataFrame,
    *,
    map_target: float = 65.0,
    sap_target: float = 90.0,
    min_duration_s: float = 60.0,
) -> float | None:
    frame = case_frame[[TIME_COLUMN, "clean_map", "clean_sap"]].copy()
    frame["is_low"] = ((frame["clean_map"] < map_target) | ((frame["clean_map"].isna()) & (frame["clean_sap"] < sap_target))).fillna(False)
    start_time: float | None = None
    accumulated = 0.0
    previous_time: float | None = None
    for row in frame.itertuples(index=False):
        current_time = float(row.time_sec)
        is_low = bool(row.is_low)
        if previous_time is None:
            previous_time = current_time
        dt = max(current_time - previous_time, 0.0)
        previous_time = current_time
        if is_low:
            if start_time is None:
                start_time = current_time
                accumulated = 0.0
            accumulated += dt
            if accumulated >= min_duration_s:
                return start_time
        else:
            start_time = None
            accumulated = 0.0
    return None
