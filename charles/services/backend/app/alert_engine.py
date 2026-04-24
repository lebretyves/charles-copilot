"""Configurable alert engine for CHARLES."""

from __future__ import annotations

import json
import logging
from collections import defaultdict, deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.models import Alert, MonitoringMessage

logger = logging.getLogger("charles.alerts")


DEFAULT_THRESHOLDS = {
    "hr": {
        "info_low": 50,
        "warning_low": 45,
        "critical_low": 40,
        "info_high": 100,
        "warning_high": 120,
        "critical_high": 150,
        "unit": "bpm",
        "label": "Frequence cardiaque",
    },
    "spo2": {
        "info_low": 95,
        "warning_low": 92,
        "critical_low": 90,
        "unit": "%",
        "label": "SpO2",
    },
    "pas": {
        "info_low": 100,
        "warning_low": 90,
        "critical_low": 80,
        "info_high": 160,
        "warning_high": 180,
        "critical_high": 200,
        "unit": "mmHg",
        "label": "PAS",
    },
    "pad": {
        "info_low": 55,
        "warning_low": 50,
        "critical_low": 40,
        "info_high": 100,
        "warning_high": 110,
        "critical_high": 120,
        "unit": "mmHg",
        "label": "PAD",
    },
    "pam": {
        "info_low": 70,
        "warning_low": 65,
        "critical_low": 60,
        "info_high": 110,
        "warning_high": 120,
        "critical_high": 130,
        "unit": "mmHg",
        "label": "PAM",
    },
    "etco2": {
        "info_low": 30,
        "warning_low": 25,
        "critical_low": 20,
        "info_high": 45,
        "warning_high": 50,
        "critical_high": 60,
        "unit": "mmHg",
        "label": "EtCO2",
    },
    "fr": {
        "info_low": 10,
        "warning_low": 8,
        "critical_low": 6,
        "info_high": 22,
        "warning_high": 28,
        "critical_high": 35,
        "unit": "/min",
        "label": "FR",
    },
    "temp": {
        "info_low": 36.0,
        "warning_low": 35.5,
        "critical_low": 35.0,
        "info_high": 38.0,
        "warning_high": 38.5,
        "critical_high": 39.5,
        "unit": "C",
        "label": "Temperature",
    },
}

DEFAULT_BIS_RULES = {
    "bis": {
        "enabled": True,
        "target_low": 40,
        "target_high": 60,
        "warning_low": 30,
        "critical_low": 20,
        "warning_high": 70,
        "critical_high": 80,
        "unit": "index",
        "label": "BIS",
        "complication_id_warning_high": "reveil_perop",
        "complication_id_warning_low": "burst_suppression",
        "complication_id_critical_low": "burst_suppression",
    },
    "sr": {
        "enabled": True,
        "warning_high": 1,
        "critical_high": 10,
        "unit": "%",
        "label": "Suppression Ratio",
        "complication_id_warning_high": "burst_suppression",
        "complication_id_critical_high": "burst_suppression",
    },
}

DEFAULT_PPEAK_RULES = {
    "enabled": True,
    "warning_high": 30,
    "critical_high": 40,
    "unit": "cmH2O",
    "label": "Ppeak",
}

DEFAULT_COMPLICATION_RULES = [
    {
        "id": "hypotension_post_induction",
        "title": "Hypotension post-induction",
        "family": "hemodynamiques",
        "level": "critical",
        "enabled": True,
        "logic": "any",
        "detail": "PAS < 90 ou PAM < 65 en phase precoce.",
        "conditions": [
            {"field": "pas", "op": "lt", "value": 90},
            {"field": "pam", "op": "lt", "value": 65},
        ],
    },
    {
        "id": "hemorragie_chirurgicale",
        "title": "Hemorragie chirurgicale",
        "family": "hemodynamiques",
        "level": "critical",
        "enabled": True,
        "logic": "all",
        "detail": "Hypotension associee a tachycardie et shock index eleve.",
        "conditions": [
            {"field": "pas", "op": "lt", "value": 90},
            {"field": "hr", "op": "gt", "value": 100},
            {"field": "shock_index", "op": "gt", "value": 0.9},
        ],
    },
    {
        "id": "crise_hypertensive",
        "title": "Crise hypertensive peroperatoire",
        "family": "hemodynamiques",
        "level": "critical",
        "enabled": True,
        "logic": "any",
        "detail": "PAS > 180 ou PAM > 120.",
        "conditions": [
            {"field": "pas", "op": "gt", "value": 180},
            {"field": "pam", "op": "gt", "value": 120},
        ],
    },
    {
        "id": "bradycardie_severe",
        "title": "Bradycardie severe",
        "family": "hemodynamiques",
        "level": "critical",
        "enabled": True,
        "logic": "all",
        "detail": "FC < 45/min.",
        "conditions": [{"field": "hr", "op": "lt", "value": 45}],
    },
    {
        "id": "tachycardie",
        "title": "Tachycardie peroperatoire",
        "family": "hemodynamiques",
        "level": "warning",
        "enabled": True,
        "logic": "all",
        "detail": "FC > 120/min.",
        "conditions": [{"field": "hr", "op": "gt", "value": 120}],
    },
    {
        "id": "arret_cardiaque_perop",
        "title": "Arret cardiaque peroperatoire",
        "family": "hemodynamiques",
        "level": "critical",
        "enabled": True,
        "logic": "all",
        "detail": "FC < 20 et PAS < 40.",
        "conditions": [
            {"field": "hr", "op": "lt", "value": 20},
            {"field": "pas", "op": "lt", "value": 40},
        ],
    },
    {
        "id": "desaturation",
        "title": "Desaturation / Hypoxemie",
        "family": "respiratoires",
        "level": "critical",
        "enabled": True,
        "logic": "all",
        "detail": "SpO2 < 92.",
        "conditions": [{"field": "spo2", "op": "lt", "value": 92}],
    },
    {
        "id": "bronchospasme",
        "title": "Bronchospasme peroperatoire",
        "family": "respiratoires",
        "level": "critical",
        "enabled": True,
        "logic": "all",
        "detail": "Ppeak > 30, EtCO2 > 48 et SpO2 < 92.",
        "conditions": [
            {"field": "ppeak", "op": "gt", "value": 30},
            {"field": "etco2", "op": "gt", "value": 48},
            {"field": "spo2", "op": "lt", "value": 92},
        ],
    },
    {
        "id": "intubation_difficile",
        "title": "Intubation difficile / impossible",
        "family": "respiratoires",
        "level": "critical",
        "enabled": True,
        "logic": "all",
        "detail": "SpO2 basse avec EtCO2 bas en phase d'induction.",
        "conditions": [
            {"field": "spo2", "op": "lt", "value": 94},
            {"field": "etco2", "op": "lt", "value": 20},
        ],
    },
    {
        "id": "pneumothorax",
        "title": "Pneumothorax peroperatoire",
        "family": "respiratoires",
        "level": "critical",
        "enabled": True,
        "logic": "all",
        "detail": "Ppeak elevee, SpO2 basse et hypotension.",
        "conditions": [
            {"field": "ppeak", "op": "gt", "value": 35},
            {"field": "spo2", "op": "lt", "value": 90},
            {"field": "pam", "op": "lt", "value": 60},
        ],
    },
    {
        "id": "embolie_gazeuse",
        "title": "Embolie gazeuse",
        "family": "respiratoires",
        "level": "critical",
        "enabled": True,
        "logic": "all",
        "detail": "EtCO2 basse, hypotension et tachycardie.",
        "conditions": [
            {"field": "etco2", "op": "lt", "value": 20},
            {"field": "pas", "op": "lt", "value": 90},
            {"field": "hr", "op": "gt", "value": 110},
        ],
    },
    {
        "id": "anaphylaxie_perop",
        "title": "Reaction anaphylactique peroperatoire",
        "family": "anaphylaxie",
        "level": "critical",
        "enabled": True,
        "logic": "all",
        "detail": "Hypotension, desaturation, tachycardie et pressions elevees.",
        "conditions": [
            {"field": "pam", "op": "lt", "value": 60},
            {"field": "spo2", "op": "lt", "value": 92},
            {"field": "hr", "op": "gt", "value": 110},
            {"field": "ppeak", "op": "gt", "value": 28},
        ],
    },
    {
        "id": "hypothermie",
        "title": "Hypothermie peroperatoire",
        "family": "temperature",
        "level": "warning",
        "enabled": True,
        "logic": "all",
        "detail": "Temperature basse.",
        "conditions": [{"field": "temp", "op": "lt", "value": 35.5}],
    },
    {
        "id": "hyperthermie_maligne",
        "title": "Hyperthermie maligne",
        "family": "temperature",
        "level": "critical",
        "enabled": True,
        "logic": "all",
        "detail": "Temperature, EtCO2 et FC eleves.",
        "conditions": [
            {"field": "temp", "op": "gt", "value": 38.5},
            {"field": "etco2", "op": "gt", "value": 50},
            {"field": "hr", "op": "gt", "value": 110},
        ],
    },
    {
        "id": "reveil_perop",
        "title": "Reveil peroperatoire",
        "family": "neuro_anesthesie",
        "level": "warning",
        "enabled": True,
        "logic": "all",
        "detail": "BIS eleve avec reponse sympathique.",
        "conditions": [
            {"field": "bis", "op": "gt", "value": 70},
            {"field": "hr", "op": "gt", "value": 100},
        ],
    },
    {
        "id": "burst_suppression",
        "title": "Burst suppression / surdosage",
        "family": "neuro_anesthesie",
        "level": "critical",
        "enabled": True,
        "logic": "all",
        "detail": "BIS tres bas avec SR eleve.",
        "conditions": [
            {"field": "bis", "op": "lt", "value": 30},
            {"field": "sr", "op": "gt", "value": 5},
        ],
    },
    {
        "id": "HYPO_TRIAD",
        "title": "Triade hypotension",
        "family": "legacy",
        "level": "critical",
        "enabled": True,
        "logic": "all",
        "detail": "PAM < 65 + FC > 100 + SpO2 < 95.",
        "conditions": [
            {"field": "pam", "op": "lt", "value": 65},
            {"field": "hr", "op": "gt", "value": 100},
            {"field": "spo2", "op": "lt", "value": 95},
        ],
    },
]

DEFAULT_TREND_RULES = [
    {
        "id": "trend_pas_drop",
        "title": "Chute rapide de PAS",
        "level": "critical",
        "enabled": True,
        "field": "pas",
        "delta_op": "lt",
        "delta": -30,
        "window_points": 12,
        "detail": "PAS en chute rapide.",
        "complication_id": "hypotension_post_induction",
    },
    {
        "id": "trend_spo2_drop",
        "title": "Desaturation rapide",
        "level": "critical",
        "enabled": True,
        "field": "spo2",
        "delta_op": "lt",
        "delta": -3,
        "window_points": 12,
        "detail": "SpO2 en chute rapide.",
        "complication_id": "desaturation",
    },
    {
        "id": "trend_hr_spike",
        "title": "Tachycardie croissante",
        "level": "warning",
        "enabled": True,
        "field": "hr",
        "delta_op": "gt",
        "delta": 30,
        "window_points": 12,
        "detail": "FC en hausse rapide.",
        "complication_id": "tachycardie",
    },
    {
        "id": "trend_etco2_rise",
        "title": "EtCO2 en hausse rapide",
        "level": "critical",
        "enabled": True,
        "field": "etco2",
        "delta_op": "gt",
        "delta": 10,
        "window_points": 12,
        "detail": "EtCO2 en hausse rapide.",
        "complication_id": "hyperthermie_maligne",
    },
    {
        "id": "trend_etco2_drop",
        "title": "EtCO2 en chute rapide",
        "level": "critical",
        "enabled": True,
        "field": "etco2",
        "delta_op": "lt",
        "delta": -8,
        "window_points": 12,
        "detail": "EtCO2 en chute rapide.",
        "complication_id": "embolie_gazeuse",
    },
    {
        "id": "trend_temp_rise",
        "title": "Temperature en hausse rapide",
        "level": "warning",
        "enabled": True,
        "field": "temp",
        "delta_op": "gt",
        "delta": 0.5,
        "window_points": 12,
        "detail": "Temperature en hausse rapide.",
        "complication_id": "hyperthermie_maligne",
    },
]

PROFILE_PATHS = {
    "pam_seuil_bas": "thresholds.pam.warning_low",
    "pam_seuil_haut": "thresholds.pam.warning_high",
    "spo2_seuil_bas": "thresholds.spo2.warning_low",
    "temperature_seuil_bas": "thresholds.temp.warning_low",
    "bis_seuil_bas": "bis_rules.bis.target_low",
    "etco2_seuil_haut": "thresholds.etco2.warning_high",
    "pip_seuil_haut": "ppeak_rules.warning_high",
    "hr_seuil_haut": "thresholds.hr.warning_high",
}


def _coerce_float(value: Any, fallback: float | int | None = None) -> float | None:
    try:
        if value is None or value == "":
            return None if fallback is None else float(fallback)
        return float(value)
    except (TypeError, ValueError):
        return None if fallback is None else float(fallback)


def _coerce_int(value: Any, fallback: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return fallback


def _coerce_bool(value: Any, fallback: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"true", "1", "yes", "oui", "on"}:
            return True
        if lowered in {"false", "0", "no", "non", "off"}:
            return False
    if value is None:
        return fallback
    return bool(value)


def _deep_copy_jsonable(value: Any) -> Any:
    return json.loads(json.dumps(value))


def _apply_path(target: dict[str, Any], dotted_path: str, value: Any) -> None:
    cursor: dict[str, Any] = target
    parts = dotted_path.split(".")
    for part in parts[:-1]:
        next_value = cursor.get(part)
        if not isinstance(next_value, dict):
            next_value = {}
            cursor[part] = next_value
        cursor = next_value
    cursor[parts[-1]] = value


class AlertEngine:
    """Evaluates live monitoring and exposes configurable alerting."""

    def __init__(self, kb: Any | None = None, runtime_path: str | Path | None = None):
        self.kb = kb
        self.runtime_path = Path(runtime_path) if runtime_path else None
        self.history: dict[str, deque[dict[str, Any]]] = defaultdict(lambda: deque(maxlen=60))
        self.active_alerts: dict[str, dict[str, datetime]] = defaultdict(dict)
        self.room_profiles: dict[str, dict[str, Any]] = {}
        self._base_config = self._build_default_config()
        self._runtime_config = _deep_copy_jsonable(self._base_config)
        self._last_loaded_from_disk: str | None = None
        self._load_runtime_config()

    def reset_room(self, room_id: str) -> None:
        self.history.pop(room_id, None)
        self.active_alerts.pop(room_id, None)
        self.room_profiles.pop(room_id, None)

    def _build_default_config(self) -> dict[str, Any]:
        config = {
            "updated_at": None,
            "hysteresis_seconds": 30,
            "thresholds": _deep_copy_jsonable(DEFAULT_THRESHOLDS),
            "bis_rules": _deep_copy_jsonable(DEFAULT_BIS_RULES),
            "ppeak_rules": _deep_copy_jsonable(DEFAULT_PPEAK_RULES),
            "complication_rules": _deep_copy_jsonable(DEFAULT_COMPLICATION_RULES),
            "trend_rules": _deep_copy_jsonable(DEFAULT_TREND_RULES),
            "population_overrides": {},
            "terrain_overrides": {},
        }
        self._inject_kb_overrides(config)
        return config

    def _inject_kb_overrides(self, config: dict[str, Any]) -> None:
        if not self.kb or not getattr(self.kb, "loaded", False):
            return

        try:
            population_thresholds = self.kb.get_thresholds_for_population("adulte_standard")
            for param, values in population_thresholds.items():
                if param not in config["thresholds"]:
                    config["thresholds"][param] = {}
                config["thresholds"][param].update(values)
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("Failed to merge KB base thresholds: %s", exc)

        pops = (self.kb.populations or {}).get("populations", {})
        for population_id, payload in pops.items():
            overrides = {}
            raw = payload.get("alertes_adaptees") or {}
            for raw_key, raw_value in raw.items():
                mapped_path = PROFILE_PATHS.get(raw_key)
                if mapped_path:
                    overrides[mapped_path] = raw_value
            config["population_overrides"][population_id] = {
                "label": payload.get("label_fr", population_id),
                "enabled": True,
                "overrides": overrides,
                "source_keys": sorted(raw.keys()),
            }

        terrains_root = (self.kb.terrains or {}).get("systemes", {})
        for system_id, system_payload in terrains_root.items():
            for terrain_id, terrain_payload in (system_payload.get("terrains") or {}).items():
                raw = terrain_payload.get("alertes_charles") or {}
                overrides = {}
                for raw_key, raw_value in raw.items():
                    mapped_path = PROFILE_PATHS.get(raw_key)
                    if mapped_path:
                        overrides[mapped_path] = raw_value
                config["terrain_overrides"][terrain_id] = {
                    "label": terrain_payload.get("label_fr", terrain_id),
                    "system": system_id,
                    "enabled": True,
                    "overrides": overrides,
                    "source_keys": sorted(raw.keys()),
                }

    def _normalize_thresholds(self, raw: Any, base: dict[str, Any]) -> dict[str, Any]:
        normalized = _deep_copy_jsonable(base)
        if not isinstance(raw, dict):
            return normalized
        for param, thresholds in raw.items():
            if param not in normalized or not isinstance(thresholds, dict):
                continue
            for key, value in thresholds.items():
                if key in {"label", "unit"}:
                    normalized[param][key] = str(value)
                elif key.startswith("complication_id_"):
                    normalized[param][key] = str(value)
                elif key == "enabled":
                    normalized[param][key] = _coerce_bool(value, normalized[param].get(key, True))
                else:
                    coerced = _coerce_float(value, normalized[param].get(key))
                    if coerced is not None:
                        normalized[param][key] = coerced
        return normalized

    def _normalize_overrides(self, raw: Any, base: dict[str, Any]) -> dict[str, Any]:
        normalized = _deep_copy_jsonable(base)
        if not isinstance(raw, dict):
            return normalized
        for profile_id, payload in raw.items():
            if profile_id not in normalized or not isinstance(payload, dict):
                continue
            normalized[profile_id]["enabled"] = _coerce_bool(payload.get("enabled"), normalized[profile_id]["enabled"])
            if "label" in payload:
                normalized[profile_id]["label"] = str(payload.get("label"))
            if "overrides" in payload and isinstance(payload["overrides"], dict):
                clean: dict[str, float] = {}
                for dotted_path, value in payload["overrides"].items():
                    coerced = _coerce_float(value)
                    if coerced is not None:
                        clean[str(dotted_path)] = coerced
                normalized[profile_id]["overrides"] = clean
        return normalized

    def _normalize_rule_list(self, raw: Any, base: list[dict[str, Any]], *, trend: bool = False) -> list[dict[str, Any]]:
        if not isinstance(raw, list):
            return _deep_copy_jsonable(base)

        base_map = {rule["id"]: _deep_copy_jsonable(rule) for rule in base}
        normalized: list[dict[str, Any]] = []
        for payload in raw:
            if not isinstance(payload, dict):
                continue
            rule_id = str(payload.get("id", "")).strip()
            if not rule_id or rule_id not in base_map:
                continue
            rule = base_map[rule_id]
            rule["title"] = str(payload.get("title", rule.get("title", rule_id)))
            rule["detail"] = str(payload.get("detail", rule.get("detail", "")))
            rule["level"] = str(payload.get("level", rule.get("level", "warning")))
            rule["enabled"] = _coerce_bool(payload.get("enabled"), rule.get("enabled", True))
            if trend:
                rule["field"] = str(payload.get("field", rule.get("field")))
                rule["delta_op"] = str(payload.get("delta_op", rule.get("delta_op")))
                rule["delta"] = _coerce_float(payload.get("delta"), rule.get("delta"))
                rule["window_points"] = _coerce_int(payload.get("window_points"), rule.get("window_points", 12))
            else:
                rule["logic"] = str(payload.get("logic", rule.get("logic", "all")))
                conditions: list[dict[str, Any]] = []
                for condition in payload.get("conditions", []):
                    if not isinstance(condition, dict):
                        continue
                    if "field" not in condition or "op" not in condition:
                        continue
                    conditions.append(
                        {
                            "field": str(condition["field"]),
                            "op": str(condition["op"]),
                            "value": condition.get("value"),
                        }
                    )
                if conditions:
                    rule["conditions"] = conditions
            normalized.append(rule)
        normalized_ids = {rule["id"] for rule in normalized}
        for base_rule in base:
            if base_rule["id"] not in normalized_ids:
                normalized.append(_deep_copy_jsonable(base_rule))
        return normalized

    def _normalize_config(self, raw: Any, *, base: dict[str, Any] | None = None) -> dict[str, Any]:
        reference = _deep_copy_jsonable(base or self._base_config)
        if not isinstance(raw, dict):
            return reference

        reference["hysteresis_seconds"] = _coerce_int(raw.get("hysteresis_seconds"), reference["hysteresis_seconds"])
        reference["thresholds"] = self._normalize_thresholds(raw.get("thresholds"), reference["thresholds"])
        reference["bis_rules"] = self._normalize_thresholds(raw.get("bis_rules"), reference["bis_rules"])
        reference["ppeak_rules"] = self._normalize_thresholds({"ppeak": raw.get("ppeak_rules", {})}, {"ppeak": reference["ppeak_rules"]})["ppeak"]
        reference["complication_rules"] = self._normalize_rule_list(raw.get("complication_rules"), reference["complication_rules"])
        reference["trend_rules"] = self._normalize_rule_list(raw.get("trend_rules"), reference["trend_rules"], trend=True)
        reference["population_overrides"] = self._normalize_overrides(raw.get("population_overrides"), reference["population_overrides"])
        reference["terrain_overrides"] = self._normalize_overrides(raw.get("terrain_overrides"), reference["terrain_overrides"])
        reference["updated_at"] = raw.get("updated_at") if raw.get("updated_at") else reference.get("updated_at")
        return reference

    def _load_runtime_config(self) -> None:
        if not self.runtime_path or not self.runtime_path.exists():
            return
        try:
            payload = json.loads(self.runtime_path.read_text(encoding="utf-8"))
            self._runtime_config = self._normalize_config(payload)
            self._last_loaded_from_disk = str(self.runtime_path)
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("Failed to load runtime alert config from %s: %s", self.runtime_path, exc)

    def save_runtime_config(self, payload: dict[str, Any]) -> dict[str, Any]:
        normalized = self._normalize_config(payload)
        normalized["updated_at"] = datetime.now(timezone.utc).isoformat()
        self._runtime_config = normalized
        if self.runtime_path:
            self.runtime_path.parent.mkdir(parents=True, exist_ok=True)
            self.runtime_path.write_text(json.dumps(normalized, indent=2, ensure_ascii=False), encoding="utf-8")
            self._last_loaded_from_disk = str(self.runtime_path)
        return self.export_config()

    def reset_runtime_config(self) -> dict[str, Any]:
        self._runtime_config = _deep_copy_jsonable(self._base_config)
        self._runtime_config["updated_at"] = datetime.now(timezone.utc).isoformat()
        if self.runtime_path:
            self.runtime_path.parent.mkdir(parents=True, exist_ok=True)
            self.runtime_path.write_text(json.dumps(self._runtime_config, indent=2, ensure_ascii=False), encoding="utf-8")
            self._last_loaded_from_disk = str(self.runtime_path)
        return self.export_config()

    def _detect_population_profiles(self, patient_info: dict[str, Any] | None) -> list[str]:
        if not isinstance(patient_info, dict):
            return []
        profiles: list[str] = []
        age = patient_info.get("age")
        bmi = patient_info.get("imc", patient_info.get("bmi"))
        if bmi is None and patient_info.get("weight") and patient_info.get("height"):
            try:
                weight = float(patient_info["weight"])
                height_m = float(patient_info["height"]) / 100.0
                if height_m > 0:
                    bmi = weight / (height_m * height_m)
            except (TypeError, ValueError, ZeroDivisionError):
                bmi = None
        ane_type = str(patient_info.get("ane_type", "")).lower()
        opname = str(patient_info.get("opname", "")).lower()
        try:
            if age is not None and int(age) >= 65:
                profiles.append("geriatrique")
            elif age is not None and int(age) < 18:
                profiles.append("pediatrique")
        except (TypeError, ValueError):
            pass
        try:
            if bmi is not None and float(bmi) >= 30:
                profiles.append("obese")
        except (TypeError, ValueError):
            pass
        if "cesar" in opname or "grossesse" in opname or "partur" in ane_type:
            profiles.append("obstetrique")
        return sorted(set(profiles))

    def _detect_terrain_profiles(self, patient_info: dict[str, Any] | None) -> list[str]:
        if not isinstance(patient_info, dict):
            return []
        haystack = " ".join(
            str(patient_info.get(key, "")).lower()
            for key in ("antecedents", "opname", "department", "optype", "diagnosis")
        )
        keyword_map = {
            "hta": ["hta", "hypertension"],
            "coronaropathie": ["coronar", "stent", "pontage", "ischem"],
            "insuffisance_cardiaque": ["insuffisance card", "oap", "cardiomyopath"],
            "arythmie": ["arythm", "fibrillation", "pace"],
            "bpco": ["bpco", "emphy", "copd"],
            "asthme": ["asthme", "wheeze", "atop"],
            "saos": ["saos", "apnee sommeil", "stop-bang"],
            "diabete": ["diabet", "glyc"],
            "insuffisant_renal": ["renal", "dialys", "creat"],
        }
        matches = []
        for terrain_id, keywords in keyword_map.items():
            if any(keyword in haystack for keyword in keywords):
                matches.append(terrain_id)
        return sorted(set(matches))

    def _build_effective_config(self, room_id: str, patient_info: dict[str, Any] | None) -> dict[str, Any]:
        effective = _deep_copy_jsonable(self._runtime_config)
        population_ids = self._detect_population_profiles(patient_info)
        terrain_ids = self._detect_terrain_profiles(patient_info)

        for profile_id in population_ids:
            payload = effective["population_overrides"].get(profile_id)
            if not payload or not payload.get("enabled"):
                continue
            for dotted_path, value in payload.get("overrides", {}).items():
                _apply_path(effective, dotted_path, value)

        for terrain_id in terrain_ids:
            payload = effective["terrain_overrides"].get(terrain_id)
            if not payload or not payload.get("enabled"):
                continue
            for dotted_path, value in payload.get("overrides", {}).items():
                _apply_path(effective, dotted_path, value)

        self.room_profiles[room_id] = {
            "populations": population_ids,
            "terrains": terrain_ids,
            "patient_info": patient_info or {},
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        return effective

    def _build_context(self, msg: MonitoringMessage, effective: dict[str, Any]) -> dict[str, Any]:
        vitals = msg.vitals
        context = {
            "hr": vitals.hr,
            "spo2": vitals.spo2,
            "pas": vitals.pas,
            "pad": vitals.pad,
            "pam": vitals.pam,
            "etco2": vitals.etco2,
            "fr": vitals.fr,
            "temp": vitals.temp,
            "phase": msg.phase,
            "macro_phase": msg.macro_phase,
            "elapsed_s": msg.elapsed_s,
        }
        context["shock_index"] = (vitals.hr / vitals.pas) if vitals.pas else None
        if msg.bis:
            context["bis"] = msg.bis.bis
            context["sr"] = msg.bis.sr
        if msg.ventilator:
            context["ppeak"] = msg.ventilator.ppeak
            context["peep"] = msg.ventilator.peep
        history_entry = {key: context.get(key) for key in ("hr", "spo2", "pas", "pad", "pam", "etco2", "fr", "temp", "bis", "sr", "ppeak")}
        self.history[msg.room_id].append({"ts": msg.timestamp, **history_entry})
        return context

    def _check_simple_threshold(self, room_id: str, now: datetime, param: str, value: float, thresholds: dict[str, Any]) -> Alert | None:
        label = thresholds.get("label", param.upper())
        unit = thresholds.get("unit", "")
        for level_name, key in (("critical", "critical_low"), ("warning", "warning_low"), ("info", "info_low")):
            if key in thresholds and value < thresholds[key]:
                rule_id = f"{param.upper()}_LOW_{level_name.upper()}"
                if self._in_hysteresis(room_id, rule_id, now):
                    return None
                self.active_alerts[room_id][rule_id] = now
                return Alert(rule_id=rule_id, level=level_name, title=f"{label} basse", detail=f"{label} = {value:.1f} {unit} (< {thresholds[key]})", parameters={param: value, "threshold": thresholds[key]}, timestamp=now)
        for level_name, key in (("critical", "critical_high"), ("warning", "warning_high"), ("info", "info_high")):
            if key in thresholds and value > thresholds[key]:
                rule_id = f"{param.upper()}_HIGH_{level_name.upper()}"
                if self._in_hysteresis(room_id, rule_id, now):
                    return None
                self.active_alerts[room_id][rule_id] = now
                return Alert(rule_id=rule_id, level=level_name, title=f"{label} elevee", detail=f"{label} = {value:.1f} {unit} (> {thresholds[key]})", parameters={param: value, "threshold": thresholds[key]}, timestamp=now)
        return None

    def _evaluate_condition(self, context: dict[str, Any], condition: dict[str, Any]) -> bool:
        field = condition.get("field")
        op = condition.get("op")
        value = condition.get("value")
        current = context.get(field)
        if op == "in":
            return current in (value or [])
        if current is None:
            return False
        if op == "lt":
            return current < value
        if op == "lte":
            return current <= value
        if op == "gt":
            return current > value
        if op == "gte":
            return current >= value
        if op == "eq":
            return current == value
        if op == "contains":
            return str(value).lower() in str(current).lower()
        return False

    def _in_hysteresis(self, room_id: str, rule_id: str, now: datetime) -> bool:
        last = self.active_alerts.get(room_id, {}).get(rule_id)
        if last is None:
            return False
        return (now - last).total_seconds() < self._runtime_config.get("hysteresis_seconds", 30)

    def evaluate(self, msg: MonitoringMessage) -> list[Alert]:
        effective = self._build_effective_config(msg.room_id, msg.patient_info)
        now = msg.timestamp
        room_id = msg.room_id
        context = self._build_context(msg, effective)
        alerts: list[Alert] = []

        for param, thresholds in effective["thresholds"].items():
            value = context.get(param)
            if value is None:
                continue
            alert = self._check_simple_threshold(room_id, now, param, value, thresholds)
            if alert:
                alerts.append(alert)

        bis_rules = effective["bis_rules"]
        if context.get("bis") is not None and bis_rules.get("bis", {}).get("enabled", True):
            alert = self._check_simple_threshold(room_id, now, "bis", context["bis"], bis_rules["bis"])
            if alert:
                alerts.append(alert)
        if context.get("sr") is not None and bis_rules.get("sr", {}).get("enabled", True):
            alert = self._check_simple_threshold(room_id, now, "sr", context["sr"], bis_rules["sr"])
            if alert:
                alerts.append(alert)
        if context.get("ppeak") is not None and effective["ppeak_rules"].get("enabled", True):
            alert = self._check_simple_threshold(room_id, now, "ppeak", context["ppeak"], effective["ppeak_rules"])
            if alert:
                alerts.append(alert)

        for rule in effective["complication_rules"]:
            conditions = rule.get("conditions", [])
            if not rule.get("enabled", True) or not conditions:
                continue
            results = [self._evaluate_condition(context, condition) for condition in conditions]
            triggered = any(results) if rule.get("logic", "all") == "any" else all(results)
            if not triggered or self._in_hysteresis(room_id, rule["id"], now):
                continue
            self.active_alerts[room_id][rule["id"]] = now
            alerts.append(
                Alert(
                    rule_id=rule["id"].upper(),
                    level=rule.get("level", "warning"),
                    title=rule.get("title", rule["id"]),
                    detail=rule.get("detail", ""),
                    parameters={"context": context, "conditions": conditions, "complication_id": rule["id"]},
                    timestamp=now,
                )
            )

        alerts.extend(self._evaluate_trends(room_id, now, context, effective["trend_rules"]))
        return alerts

    def _evaluate_trends(self, room_id: str, now: datetime, context: dict[str, Any], trend_rules: list[dict[str, Any]]) -> list[Alert]:
        history = self.history[room_id]
        alerts: list[Alert] = []
        if len(history) < 2:
            return alerts
        for rule in trend_rules:
            if not rule.get("enabled", True):
                continue
            window_points = max(_coerce_int(rule.get("window_points"), 12), 2)
            if len(history) < window_points:
                continue
            previous = history[-window_points]
            current_value = context.get(rule.get("field"))
            previous_value = previous.get(rule.get("field"))
            if current_value is None or previous_value is None:
                continue
            delta = current_value - previous_value
            matched = delta < rule.get("delta") if rule.get("delta_op") == "lt" else delta > rule.get("delta")
            if not matched or self._in_hysteresis(room_id, rule["id"], now):
                continue
            self.active_alerts[room_id][rule["id"]] = now
            alerts.append(
                Alert(
                    rule_id=rule["id"].upper(),
                    level=rule.get("level", "warning"),
                    title=rule.get("title", rule["id"]),
                    detail=f"{rule.get('detail', '')} Delta {rule.get('field')}: {delta:+.2f}",
                    parameters={"field": rule.get("field"), "delta": delta, "window_points": window_points, "complication_id": rule.get("complication_id")},
                    timestamp=now,
                )
            )
        return alerts

    def _build_complication_catalog(self) -> list[dict[str, Any]]:
        complication_map = {rule["id"]: rule for rule in self._runtime_config.get("complication_rules", [])}
        trend_ids = {rule.get("complication_id"): rule["id"] for rule in self._runtime_config.get("trend_rules", []) if rule.get("complication_id")}
        catalog: list[dict[str, Any]] = []
        complications_root = ((self.kb.complications if self.kb else {}) or {}).get("complications", {})
        for family_id, entries in complications_root.items():
            for complication_id, payload in entries.items():
                linked_rule = complication_map.get(complication_id)
                detector_status = "supported" if linked_rule else ("trend-only" if complication_id in trend_ids else "needs_inputs")
                catalog.append(
                    {
                        "id": complication_id,
                        "family": family_id,
                        "label": payload.get("label_fr", complication_id),
                        "pattern_detection": payload.get("pattern_detection", {}),
                        "risk_factors": payload.get("facteurs_risque", []),
                        "tracks_vitaldb": payload.get("tracks_vitaldb", []),
                        "detector_status": detector_status,
                        "linked_rule_id": linked_rule["id"] if linked_rule else trend_ids.get(complication_id),
                    }
                )
        return catalog

    def _build_terrain_catalog(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        terrains_root = ((self.kb.terrains if self.kb else {}) or {}).get("systemes", {})
        for system_id, system_payload in terrains_root.items():
            for terrain_id, terrain_payload in (system_payload.get("terrains") or {}).items():
                rows.append(
                    {
                        "id": terrain_id,
                        "system": system_id,
                        "label": terrain_payload.get("label_fr", terrain_id),
                        "alertes_charles": terrain_payload.get("alertes_charles", {}),
                    }
                )
        return rows

    def export_config(self) -> dict[str, Any]:
        payload = _deep_copy_jsonable(self._runtime_config)
        complication_catalog = self._build_complication_catalog()
        payload.update(
            {
                "runtime_path": str(self.runtime_path) if self.runtime_path else None,
                "loaded_from_disk": self._last_loaded_from_disk,
                "room_profiles": _deep_copy_jsonable(self.room_profiles),
                "complication_catalog": complication_catalog,
                "terrain_catalog": self._build_terrain_catalog(),
                "summary": {
                    "threshold_count": len(payload["thresholds"]),
                    "complication_rule_count": len(payload["complication_rules"]),
                    "trend_rule_count": len(payload["trend_rules"]),
                    "population_override_count": len(payload["population_overrides"]),
                    "terrain_override_count": len(payload["terrain_overrides"]),
                    "kb_complication_count": len(complication_catalog),
                    "supported_complication_count": sum(1 for row in complication_catalog if row["detector_status"] != "needs_inputs"),
                },
            }
        )
        return payload
