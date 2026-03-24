"""CHARLES Backend — Pydantic models (data contracts)."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


# ── Vital Signs Frame ──────────────────────────────────────────
class VitalValue(BaseModel):
    value: float
    unit: str


class VitalsFrame(BaseModel):
    """Trame vitaux standard — publiée toutes les 5s par le scope."""
    hr: float = Field(..., description="Fréquence cardiaque (bpm)")
    spo2: float = Field(..., description="Saturation O2 (%)")
    pas: float = Field(..., description="Pression artérielle systolique (mmHg)")
    pad: float = Field(..., description="Pression artérielle diastolique (mmHg)")
    pam: float = Field(..., description="Pression artérielle moyenne (mmHg)")
    etco2: float = Field(..., description="CO2 expiré (mmHg)")
    fr: float = Field(..., description="Fréquence respiratoire (cycles/min)")
    temp: float = Field(..., description="Température (°C)")


class VentilatorFrame(BaseModel):
    """Trame ventilateur."""
    mode: str = Field(..., description="VACI, VPC, VS-AI, etc.")
    vt: float = Field(..., description="Volume courant (mL)")
    vt_kg: Optional[float] = Field(None, description="Vt/kg PIT (mL/kg)")
    mv: float = Field(..., description="Volume minute (L/min)")
    ppeak: float = Field(..., description="Pression crête (cmH2O)")
    pplat: Optional[float] = Field(None, description="Pression plateau (cmH2O)")
    peep: float = Field(..., description="PEP (cmH2O)")
    fio2: float = Field(..., description="FiO2 (%)")
    ratio_ie: Optional[str] = Field(None, description="Ratio I:E")


class BISFrame(BaseModel):
    """Trame profondeur d'anesthésie."""
    bis: float = Field(..., description="Index BIS (0-100)")
    sqi: float = Field(..., description="Signal Quality Index (%)")
    emg: float = Field(..., description="EMG (dB)")
    sr: float = Field(..., description="Suppression Ratio (%)")


class AIVOCFrame(BaseModel):
    """Trame AIVOC (objectif de concentration)."""
    drug: str = Field(..., description="propofol ou remifentanil")
    model: str = Field(..., description="Modèle PK: Schnider, Marsh, Minto, Eleveld")
    target_type: str = Field(..., description="plasma ou effect_site")
    target: float = Field(..., description="Concentration cible (µg/mL ou ng/mL)")
    predicted_plasma: float = Field(..., description="Concentration plasma prédite")
    predicted_effect: float = Field(..., description="Concentration site effet prédite")
    infusion_rate: float = Field(..., description="Débit perfusion (mL/h)")


# ── Message MQTT complet ──────────────────────────────────────
class MonitoringMessage(BaseModel):
    """Message complet publié sur MQTT par le simulateur/gateway."""
    room_id: str
    case_id: Optional[str] = None
    timestamp: datetime
    vitals: VitalsFrame
    ventilator: Optional[VentilatorFrame] = None
    bis: Optional[BISFrame] = None
    aivoc_hypnotic: Optional[AIVOCFrame] = None
    aivoc_opioid: Optional[AIVOCFrame] = None
    # ── Phase anesthésique ──
    phase: Optional[str] = None
    phase_label: Optional[str] = None
    macro_phase: Optional[str] = None
    elapsed_s: Optional[int] = None
    elapsed_fmt: Optional[str] = None
    patient_info: Optional[dict] = None
    scenario: Optional[str] = None


# ── Alertes ────────────────────────────────────────────────────
class Alert(BaseModel):
    id: Optional[int] = None
    rule_id: str
    level: str  # info, warning, critical
    title: str
    detail: str
    parameters: dict
    timestamp: datetime
    acknowledged: bool = False


# ── WebSocket push ─────────────────────────────────────────────
class WSUpdate(BaseModel):
    type: str = "update"
    room_id: str
    vitals: VitalsFrame
    ventilator: Optional[VentilatorFrame] = None
    bis: Optional[BISFrame] = None
    aivoc_hypnotic: Optional[AIVOCFrame] = None
    aivoc_opioid: Optional[AIVOCFrame] = None
    alerts: list[Alert] = []
    llm_analysis: Optional[LLMAnalysis] = None
    timestamp: datetime
    # ── Phase anesthésique ──
    phase: Optional[str] = None
    phase_label: Optional[str] = None
    macro_phase: Optional[str] = None
    elapsed_s: Optional[int] = None
    elapsed_fmt: Optional[str] = None
    patient_info: Optional[dict] = None


class FluidBalance(BaseModel):
    type: str  # input | output
    category: str
    volume_ml: int
    product_name: Optional[str] = None


# ── Case / Patient ─────────────────────────────────────────────
class CaseCreate(BaseModel):
    patient_age: int
    patient_sex: str
    patient_weight: float
    patient_height: float
    asa_score: int = Field(..., ge=1, le=5)
    surgery_type: str
    surgery_approach: Optional[str] = None
    anesthesia_type: str
    room_id: str


class CaseResponse(CaseCreate):
    case_id: str
    started_at: datetime
    status: str


# ── Drug Administration ────────────────────────────────────────
class DrugAdmin(BaseModel):
    drug_name: str
    dose: float
    dose_unit: str
    route: str
    bolus_or_continuous: str = "bolus"
    rate: Optional[float] = None
    rate_unit: Optional[str] = None


# ── Clinical Event ─────────────────────────────────────────────
class CaseEvent(BaseModel):
    event_type: str  # induction, intubation, incision, clampage, declampage, extubation, transfert_sspi
    detail: Optional[str] = None


# ── LLM Analysis ──────────────────────────────────────────────
class LLMAnalysis(BaseModel):
    situation: str
    risks: list[str]
    recommendations: list[str]
    confidence: float
    call_mar: bool = False
    call_mar_reason: Optional[str] = None
    model: str
    latency_ms: int
    prompt_tokens: int = 0
    completion_tokens: int = 0
