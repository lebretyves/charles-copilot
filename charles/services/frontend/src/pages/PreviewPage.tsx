// ═══════════════════════════════════════════════════════════════
// CHARLES — Page de prévisualisation (dev only)
// Rend tous les composants de monitoring avec des données mockées
// Accessible sans authentification sur /preview
// ═══════════════════════════════════════════════════════════════

import { RoomMonitor } from "../components/RoomMonitor";
import { UXConfigProvider } from "../context/UXConfigContext";
import type { RoomState } from "../types";
import "../scope.css";

const MOCK_ROOM: RoomState = {
  history: [],
  timestamp: new Date().toISOString(),
  hasWaveData: false,
  patient_info: {
    opname: "Chirurgie laparoscopique cholécystectomie",
    age: 58,
    weight: 82,
    height: 172,
    sex: "M",
    asa: 2,
    ane_type: "AG – AIVOC",
    preop_htn: true,
    preop_dm: false,
  },
  phase_label: "Entretien",
  macro_phase: "PER",
  elapsed_fmt: "01:24",
  vitals: {
    hr: 72,
    spo2: 98,
    pas: 128,
    pad: 74,
    pam: 92,
    etco2: 36.5,
    fr: 12,
    temp: 36.4,
  },
  ventilator: {
    mode: "VCV",
    vt: 520,
    vt_kg: 6.3,
    mv: 7.1,
    ppeak: 22,
    pplat: 18,
    peep: 5,
    fio2: 50,
    ratio_ie: "1:2",
  },
  bis: {
    bis: 44,
    sqi: 95,
    emg: 28,
    sr: 0,
  },
  aivoc_hypnotic: {
    drug: "Propofol",
    model: "Schnider",
    target_type: "effect",
    target: 3.5,
    predicted_plasma: 3.8,
    predicted_effect: 3.4,
    infusion_rate: 18.4,
  },
  aivoc_opioid: {
    drug: "Remifentanil",
    model: "Minto",
    target_type: "effect",
    target: 4.0,
    predicted_plasma: 4.1,
    predicted_effect: 3.9,
    infusion_rate: 6.2,
  },
  alerts: [],
  llm_analysis: {
    situation: "Anesthésie stable. Patient en entretien VCV, BIS à 44 (cible 40-60). AIVOC Propofol Ce 3.4 µg/mL, Rémifentanil Ce 3.9 ng/mL.",
    risks: [],
    recommendations: ["Maintien des paramètres actuels", "Surveillance EtCO₂ stable"],
    call_mar: false,
    call_mar_reason: "",
    confidence: 0.91,
    model: "preview",
    latency_ms: 0,
  },
};

const MOCK_ROOM_ALERT: RoomState = {
  ...MOCK_ROOM,
  vitals: { ...MOCK_ROOM.vitals, hr: 118, spo2: 91, pam: 55 },
  bis: { bis: 72, sqi: 88, emg: 35, sr: 0 },
  alerts: [
    { rule_id: "hr_high", level: "critical", title: "FC ÉLEVÉE", detail: "FC : 118 bpm > 110", id: 1, parameters: {}, timestamp: new Date().toISOString() },
    { rule_id: "spo2_low", level: "warning", title: "SpO₂ BASSE", detail: "SpO₂ : 91% < 94%", id: 2, parameters: {}, timestamp: new Date().toISOString() },
  ],
};

const MOCK_WAVE_REF = { current: {} } as any;

export function PreviewPage() {
  return (
    <div style={{ background: "#070710", height: "100vh", padding: "0", overflow: "hidden", display: "flex", flexDirection: "column" }}>
      {/* Header */}
      <div style={{
        background: "#06080f",
        borderBottom: "1px solid rgba(0,150,200,0.2)",
        padding: "6px 16px",
        display: "flex",
        alignItems: "center",
        gap: "16px",
      }}>
        <span style={{ fontFamily: "monospace", fontSize: 16, fontWeight: 700, color: "#00d458", letterSpacing: 3 }}>
          CHARLES
        </span>
        <span style={{ color: "#4a4a6a", fontSize: 12 }}>
          ⚙ Mode prévisualisation — données simulées
        </span>
      </div>

      {/* Salle 1 — stables */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", height: "calc(100vh - 52px)", gap: 2, padding: "2px" }}>
        <UXConfigProvider>
          {/* rm-root est rendu par RoomMonitor lui-même – pas de wrapper supplémentaire */}
          <div style={{ display: "flex", flexDirection: "column", overflow: "hidden", height: "100%" }}>
            <RoomMonitor
              roomId="salle_1"
              data={MOCK_ROOM}
              waveRef={MOCK_WAVE_REF}
            />
          </div>
          <div style={{ display: "flex", flexDirection: "column", overflow: "hidden", height: "100%" }}>
            <RoomMonitor
              roomId="salle_2"
              data={MOCK_ROOM_ALERT}
              waveRef={MOCK_WAVE_REF}
            />
          </div>
        </UXConfigProvider>
      </div>
    </div>
  );
}
