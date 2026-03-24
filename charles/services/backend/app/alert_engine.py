"""
CHARLES — Moteur d'alertes intelligent.

Évalue les vitaux en temps réel contre des règles cliniques.
3 niveaux : info (jaune), warning (orange), critical (rouge).
Support hysteresis, tendances, corrélations multi-paramètres.
"""

from __future__ import annotations

import copy
import logging
from collections import defaultdict, deque
from datetime import datetime, timezone
from typing import Any

from app.models import Alert, MonitoringMessage

logger = logging.getLogger("charles.alerts")


# ── Seuils cliniques adulte ────────────────────────────────────
# Basés ASA Standards, SFAR recommandations
THRESHOLDS = {
    "hr": {
        "info_low": 50, "warning_low": 45, "critical_low": 40,
        "info_high": 100, "warning_high": 120, "critical_high": 150,
        "unit": "bpm", "label": "Fréquence cardiaque",
    },
    "spo2": {
        "info_low": 95, "warning_low": 92, "critical_low": 90,
        "unit": "%", "label": "SpO2",
    },
    "pas": {
        "info_low": 100, "warning_low": 90, "critical_low": 80,
        "info_high": 160, "warning_high": 180, "critical_high": 200,
        "unit": "mmHg", "label": "PAS",
    },
    "pad": {
        "info_low": 55, "warning_low": 50, "critical_low": 40,
        "info_high": 100, "warning_high": 110, "critical_high": 120,
        "unit": "mmHg", "label": "PAD",
    },
    "pam": {
        "info_low": 70, "warning_low": 65, "critical_low": 60,
        "info_high": 110, "warning_high": 120, "critical_high": 130,
        "unit": "mmHg", "label": "PAM",
    },
    "etco2": {
        "info_low": 30, "warning_low": 25, "critical_low": 20,
        "info_high": 45, "warning_high": 50, "critical_high": 60,
        "unit": "mmHg", "label": "EtCO2",
    },
    "fr": {
        "info_low": 10, "warning_low": 8, "critical_low": 6,
        "info_high": 22, "warning_high": 28, "critical_high": 35,
        "unit": "/min", "label": "FR",
    },
    "temp": {
        "info_low": 36.0, "warning_low": 35.5, "critical_low": 35.0,
        "info_high": 38.0, "warning_high": 38.5, "critical_high": 39.5,
        "unit": "°C", "label": "Température",
    },
}

BIS_THRESHOLDS = {
    "bis": {
        "critical_low": 20, "warning_low": 30, "target_low": 40,
        "target_high": 60, "warning_high": 70, "critical_high": 80,
        "label": "BIS",
    },
    "sr": {
        "warning_high": 1, "critical_high": 10,
        "label": "Suppression Ratio",
    },
}


# ── Règles multi-paramètres ───────────────────────────────────
MULTI_RULES = [
    {
        "id": "HYPO_TRIAD",
        "title": "Triade hypotension",
        "detail": "PAM < 65 + FC > 100 + SpO2 < 95 → choc possible",
        "level": "critical",
        "conditions": lambda v: v.pam < 65 and v.hr > 100 and v.spo2 < 95,
    },
    {
        "id": "BRADY_HYPO",
        "title": "Bradycardie + Hypotension",
        "detail": "FC < 50 + PAS < 90 → réflexe vagal / surdosage morphinique",
        "level": "critical",
        "conditions": lambda v: v.hr < 50 and v.pas < 90,
    },
    {
        "id": "DESATURATION_PROGRESSIVE",
        "title": "Désaturation + Tachycardie",
        "detail": "SpO2 < 92 + FC > 110 → détresse respiratoire",
        "level": "warning",
        "conditions": lambda v: v.spo2 < 92 and v.hr > 110,
    },
    {
        "id": "HYPOTHERMIA_COMBO",
        "title": "Hypothermie + Bradycardie",
        "detail": "T° < 35.5 + FC < 55 → hypothermie peropératoire critique",
        "level": "warning",
        "conditions": lambda v: v.temp < 35.5 and v.hr < 55,
    },
    {
        "id": "HYPERTENSIVE_CRISIS",
        "title": "Crise hypertensive",
        "detail": "PAS > 180 + FC > 100 → analgésie insuffisante ou allègement",
        "level": "critical",
        "conditions": lambda v: v.pas > 180 and v.hr > 100,
    },
    {
        "id": "BRONCHOSPASME",
        "title": "Bronchospasme péropératoire",
        "detail": "SpO2 < 92 + EtCO2 > 48 + FR > 20 → air trapping, bronchospasme",
        "level": "critical",
        "conditions": lambda v: v.spo2 < 92 and v.etco2 > 48 and v.fr > 20,
    },
    {
        "id": "BRADYCARDIE_EXTREME",
        "title": "Bradycardie extrême",
        "detail": "FC < 30 bpm → risque d’asystolie immédiat",
        "level": "critical",
        "conditions": lambda v: v.hr < 30,
    },
    {
        "id": "HYPERTHERMIE_MALIGNE",
        "title": "Hyperthermie maligne suspecte",
        "detail": "T° > 38.5 + EtCO2 > 48 + FC > 110 → arrêt halogénés, dantrolène",
        "level": "critical",
        "conditions": lambda v: v.temp > 38.5 and v.etco2 > 48 and v.hr > 110,
    },
    {
        "id": "EMBOLIE_GAZEUSE",
        "title": "Embolie gazeuse suspecte",
        "detail": "EtCO2 < 20 + FC > 110 + PAS < 90 → position, aspiration",
        "level": "critical",
        "conditions": lambda v: v.etco2 < 20 and v.hr > 110 and v.pas < 90,
    },
    {
        "id": "PNEUMOTHORAX_TENSION",
        "title": "Pneumothorax sous tension suspect",
        "detail": "SpO2 < 90 + PAM < 60 + FC > 110 → exsufflation urgente",
        "level": "critical",
        "conditions": lambda v: v.spo2 < 90 and v.pam < 60 and v.hr > 110,
    },
    {
        "id": "AWARENESS_COMBO",
        "title": "Awareness peropératoire suspect",
        "detail": "PAS > 160 + FC > 110 → vérifier BIS, profondeur anesthésie",
        "level": "warning",
        "conditions": lambda v: v.pas > 160 and v.hr > 110,
    },
    {
        "id": "ACR_IMMINENT",
        "title": "Arrêt cardiaque imminent",
        "detail": "FC < 20 + PAS < 40 → MCE, adrénaline, appel à l’aide",
        "level": "critical",
        "conditions": lambda v: v.hr < 20 and v.pas < 40,
    },    {
        "id": "HYPOTHERMIE_SEVERE",
        "title": "Hypothermie sévère peropératoire",
        "detail": "T° < 34 °C + FC < 50 → couverture chauffante, solutés chauds, réduire agents",
        "level": "critical",
        "conditions": lambda v: v.temp < 34 and v.hr < 50,
    },
    {
        "id": "TACHYCARDIE_NOCICEPTIVE",
        "title": "Tachycardie — analgésie insuffisante ?",
        "detail": "FC > 120 + BIS > 60 → bolus rémifentanil, vérifier profondeur",
        "level": "warning",
        "conditions": lambda v: v.hr > 120 and v.bis > 60,
    },]


class AlertEngine:
    """Évalue les paramètres vitaux contre les seuils et règles."""

    def __init__(self, kb=None):
        # Historique par salle pour calcul de tendances
        self.history: dict[str, deque] = defaultdict(lambda: deque(maxlen=60))
        # Hysteresis : ne pas re-alerter en boucle
        self.active_alerts: dict[str, dict[str, datetime]] = defaultdict(dict)
        self.hysteresis_seconds = 30
        self.kb = kb
        # Charger les seuils depuis KB si disponible, sinon fallback hard-codé
        self._thresholds = copy.deepcopy(THRESHOLDS)
        if kb and kb.loaded:
            try:
                kb_thresholds = kb.get_thresholds_for_population("adulte_standard")
                if kb_thresholds:
                    # Fusionner KB thresholds avec les defaults
                    for param, values in kb_thresholds.items():
                        if param in self._thresholds:
                            self._thresholds[param].update(values)
                        else:
                            self._thresholds[param] = values
                    logger.info("Alert thresholds loaded from KB")
            except Exception as e:
                logger.warning("Failed to load KB thresholds, using defaults: %s", e)

    def evaluate(self, msg: MonitoringMessage) -> list[Alert]:
        """Évalue un message complet et retourne les alertes."""
        alerts: list[Alert] = []
        now = msg.timestamp
        room = msg.room_id
        v = msg.vitals

        # Stocker dans l'historique
        self.history[room].append({
            "ts": now,
            "hr": v.hr, "spo2": v.spo2, "pas": v.pas, "pad": v.pad,
            "pam": v.pam, "etco2": v.etco2, "fr": v.fr, "temp": v.temp,
        })

        # 1. Seuils simples
        vitals_dict = {"hr": v.hr, "spo2": v.spo2, "pas": v.pas, "pad": v.pad,
                        "pam": v.pam, "etco2": v.etco2, "fr": v.fr, "temp": v.temp}

        for param, value in vitals_dict.items():
            if param not in self._thresholds:
                continue
            th = self._thresholds[param]
            alert = self._check_threshold(param, value, th, now, room)
            if alert:
                alerts.append(alert)

        # 2. BIS si disponible
        if msg.bis:
            bis_val = msg.bis.bis
            sr_val = msg.bis.sr
            if bis_val > 70:
                alerts.append(Alert(
                    rule_id="BIS_HIGH",
                    level="warning",
                    title="BIS élevé — risque mémorisation",
                    detail=f"BIS = {bis_val} (cible 40–60). Vérifier profondeur.",
                    parameters={"bis": bis_val},
                    timestamp=now,
                ))
            elif bis_val < 30 and sr_val > 5:
                alerts.append(Alert(
                    rule_id="BIS_BURST",
                    level="critical",
                    title="Burst suppression",
                    detail=f"BIS = {bis_val}, SR = {sr_val}%. Surdosage probable.",
                    parameters={"bis": bis_val, "sr": sr_val},
                    timestamp=now,
                ))

        # 2b. Pression voies aériennes (ventilateur) si disponible
        if msg.ventilator:
            ppeak = msg.ventilator.ppeak
            if ppeak > 40:
                rule_id = "PPEAK_CRITICAL"
                if not self._in_hysteresis(room, rule_id, now):
                    self.active_alerts[room][rule_id] = now
                    alerts.append(Alert(
                        rule_id=rule_id,
                        level="critical",
                        title="Pression de crête élevée",
                        detail=f"Ppeak = {ppeak} cmH₂O (> 40) → bronchospasme, pneumothorax, intubation sélective ?",
                        parameters={"ppeak": ppeak},
                        timestamp=now,
                    ))
            elif ppeak > 30:
                rule_id = "PPEAK_WARNING"
                if not self._in_hysteresis(room, rule_id, now):
                    self.active_alerts[room][rule_id] = now
                    alerts.append(Alert(
                        rule_id=rule_id,
                        level="warning",
                        title="Pression de crête augmentée",
                        detail=f"Ppeak = {ppeak} cmH₂O (> 30) → surveiller résistances.",
                        parameters={"ppeak": ppeak},
                        timestamp=now,
                    ))

        # 3. Règles multi-paramètres
        for rule in MULTI_RULES:
            try:
                if rule["conditions"](v):
                    if not self._in_hysteresis(room, rule["id"], now):
                        alerts.append(Alert(
                            rule_id=rule["id"],
                            level=rule["level"],
                            title=rule["title"],
                            detail=rule["detail"],
                            parameters=vitals_dict,
                            timestamp=now,
                        ))
                        self.active_alerts[room][rule["id"]] = now
            except Exception as e:
                logger.debug("Multi-rule evaluation error: %s", e)

        # 4. Tendances (delta sur 2 minutes = 24 points à 5s)
        alerts.extend(self._evaluate_trends(room, v, now))

        return alerts

    def _check_threshold(self, param: str, value: float, th: dict, now: datetime, room: str) -> Alert | None:
        """Vérifie un paramètre contre ses seuils."""
        label = th["label"]
        unit = th.get("unit", "")

        # Bas
        for level_name, key in [("critical", "critical_low"), ("warning", "warning_low"), ("info", "info_low")]:
            if key in th and value < th[key]:
                rule_id = f"{param.upper()}_LOW_{level_name.upper()}"
                if not self._in_hysteresis(room, rule_id, now):
                    self.active_alerts[room][rule_id] = now
                    return Alert(
                        rule_id=rule_id,
                        level=level_name,
                        title=f"{label} basse",
                        detail=f"{label} = {value} {unit} (seuil {level_name}: < {th[key]})",
                        parameters={param: value, "threshold": th[key]},
                        timestamp=now,
                    )
                return None

        # Haut
        for level_name, key in [("critical", "critical_high"), ("warning", "warning_high"), ("info", "info_high")]:
            if key in th and value > th[key]:
                rule_id = f"{param.upper()}_HIGH_{level_name.upper()}"
                if not self._in_hysteresis(room, rule_id, now):
                    self.active_alerts[room][rule_id] = now
                    return Alert(
                        rule_id=rule_id,
                        level=level_name,
                        title=f"{label} élevée",
                        detail=f"{label} = {value} {unit} (seuil {level_name}: > {th[key]})",
                        parameters={param: value, "threshold": th[key]},
                        timestamp=now,
                    )
                return None

        return None

    def _in_hysteresis(self, room: str, rule_id: str, now: datetime) -> bool:
        """Vérifie si une alerte est en période d'hysteresis."""
        last = self.active_alerts.get(room, {}).get(rule_id)
        if last is None:
            return False
        delta = (now - last).total_seconds()
        return delta < self.hysteresis_seconds

    def _evaluate_trends(self, room: str, v: Any, now: datetime) -> list[Alert]:
        """Détecte les tendances dangereuses (baisse/hausse progressive)."""
        alerts = []
        history = self.history[room]

        if len(history) < 12:  # minimum 1 minute de données
            return alerts

        # Comparer valeur actuelle vs il y a 2 minutes
        old = history[0]

        # Chute de PAS > 30 mmHg en 2 min
        pas_delta = v.pas - old["pas"]
        if pas_delta < -30:
            alerts.append(Alert(
                rule_id="TREND_PAS_DROP",
                level="critical",
                title="Chute rapide de PAS",
                detail=f"PAS: {old['pas']} → {v.pas} mmHg ({pas_delta:+.0f} en ~{len(history)*5}s)",
                parameters={"pas_current": v.pas, "pas_previous": old["pas"], "delta": pas_delta},
                timestamp=now,
            ))
        elif pas_delta < -20:
            alerts.append(Alert(
                rule_id="TREND_PAS_DECLINE",
                level="warning",
                title="Baisse progressive de PAS",
                detail=f"PAS: {old['pas']} → {v.pas} mmHg ({pas_delta:+.0f} en ~{len(history)*5}s)",
                parameters={"pas_current": v.pas, "pas_previous": old["pas"], "delta": pas_delta},
                timestamp=now,
            ))

        # Chute SpO2 > 3% en 1 min
        spo2_delta = v.spo2 - old["spo2"]
        if spo2_delta < -3:
            alerts.append(Alert(
                rule_id="TREND_SPO2_DROP",
                level="critical",
                title="Désaturation rapide",
                detail=f"SpO2: {old['spo2']} → {v.spo2}% ({spo2_delta:+.1f}%)",
                parameters={"spo2_current": v.spo2, "spo2_previous": old["spo2"], "delta": spo2_delta},
                timestamp=now,
            ))

        # Hausse FC > 30 bpm en 2 min
        hr_delta = v.hr - old["hr"]
        if hr_delta > 30:
            alerts.append(Alert(
                rule_id="TREND_HR_SPIKE",
                level="warning",
                title="Tachycardie croissante",
                detail=f"FC: {old['hr']} → {v.hr} bpm ({hr_delta:+.0f})",
                parameters={"hr_current": v.hr, "hr_previous": old["hr"], "delta": hr_delta},
                timestamp=now,
            ))

        # Hausse EtCO2 > 10 mmHg en 2 min (bronchospasme / HM)
        etco2_delta = v.etco2 - old["etco2"]
        if etco2_delta > 10:
            alerts.append(Alert(
                rule_id="TREND_ETCO2_RISE",
                level="critical",
                title="EtCO2 en hausse rapide",
                detail=f"EtCO2: {old['etco2']} → {v.etco2} mmHg ({etco2_delta:+.1f}) → bronchospasme / HM ?",
                parameters={"etco2_current": v.etco2, "etco2_previous": old["etco2"], "delta": etco2_delta},
                timestamp=now,
            ))
        # Chute EtCO2 > 8 mmHg en 2 min (embolie gazeuse / ACR)
        elif etco2_delta < -8:
            alerts.append(Alert(
                rule_id="TREND_ETCO2_DROP",
                level="critical",
                title="EtCO2 en chute rapide",
                detail=f"EtCO2: {old['etco2']} → {v.etco2} mmHg ({etco2_delta:+.1f}) → embolie / ACR ?",
                parameters={"etco2_current": v.etco2, "etco2_previous": old["etco2"], "delta": etco2_delta},
                timestamp=now,
            ))

        # Hausse température > 0.5°C en 2 min (hyperthermie maligne précoce)
        temp_delta = v.temp - old["temp"]
        if temp_delta > 0.5:
            alerts.append(Alert(
                rule_id="TREND_TEMP_RISE",
                level="warning",
                title="Température en hausse rapide",
                detail=f"T°: {old['temp']} → {v.temp}°C ({temp_delta:+.2f}) → hyperthermie maligne ?",
                parameters={"temp_current": v.temp, "temp_previous": old["temp"], "delta": temp_delta},
                timestamp=now,
            ))

        return alerts
