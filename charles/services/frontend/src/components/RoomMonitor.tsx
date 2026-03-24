// ═══════════════════════════════════════════════════════════════
// CHARLES — RoomMonitor : dashboard scope-like pour une salle
// Disposition inspirée des moniteurs GE B40 / Philips MX800
// ═══════════════════════════════════════════════════════════════

import type { RoomState } from "../types";
import { VitalCard } from "./VitalCard";
import { AlertPanel } from "./AlertPanel";
import { LLMPanel } from "./LLMPanel";

interface RoomMonitorProps {
  roomId: string;
  data: RoomState;
  onAcknowledgeAlert?: (alertId: number) => void;
  onRequestAnalysis?: () => void;
}

function getAlertLevel(
  value: number,
  warningLow: number,
  warningHigh: number,
  criticalLow: number,
  criticalHigh: number,
): "normal" | "warning" | "critical" {
  if (value <= criticalLow || value >= criticalHigh) return "critical";
  if (value <= warningLow || value >= warningHigh) return "warning";
  return "normal";
}

export function RoomMonitor({ roomId, data, onAcknowledgeAlert, onRequestAnalysis }: RoomMonitorProps) {
  const { vitals: v, ventilator: vent, bis, aivoc_hypnotic: aH, aivoc_opioid: aO, alerts, llm_analysis, history, phase_label, macro_phase, elapsed_fmt, patient_info } = data;

  const p = patient_info;

  const hrHistory = history.map((h) => h.hr);
  const spo2History = history.map((h) => h.spo2);
  const pasHistory = history.map((h) => h.pas);
  const pamHistory = history.map((h) => h.pam);
  const etco2History = history.map((h) => h.etco2);
  const frHistory = history.map((h) => h.fr);

  return (
    <div className="room-monitor">
      {/* ── Header ── */}
      <div className="room-header">
        <h2 className="room-title">{roomId.replace("_", " ").toUpperCase()}</h2>
        <span className="room-time">
          {new Date(data.timestamp).toLocaleTimeString("fr-FR")}
        </span>
      </div>

      {/* ── Bandeau Patient (mini CS anesthésie) ── */}
      {p && (
        <div className="patient-summary">
          {/* Ligne 1: Identité + ASA + Urgence */}
          <div className="cs-row cs-identity">
            <span className="cs-tag cs-age">
              {p.age != null && `${p.age}ans`}{p.sex && ` ${p.sex}`}
              {p.weight != null && ` ${p.weight}kg`}{p.height != null && `/${p.height}cm`}
              {p.imc != null && ` IMC ${p.imc}`}
            </span>
            <span className={`cs-tag cs-asa asa-${p.asa ?? 1}`}>ASA {p.asa ?? "?"}</span>
            <span className="cs-tag cs-ane">{p.ane_type ?? "AG"}</span>
            {p.emop && <span className="cs-tag cs-urgence">URGENCE</span>}
            {p.mallampati != null && <span className="cs-tag">Mall. {p.mallampati}</span>}
            {p.cormack && <span className="cs-tag">Cormack {p.cormack}</span>}
          </div>

          {/* Ligne 2: Chirurgie */}
          <div className="cs-row cs-surgery">
            <span className="cs-opname">{p.opname ?? "Chirurgie"}</span>
            {p.dx && <span className="cs-dx">Dx: {p.dx}</span>}
          </div>
          <div className="cs-row cs-surgery-detail">
            {p.optype && <span className="cs-tag">{p.optype}</span>}
            {p.approach && <span className="cs-tag">{p.approach}</span>}
            {p.position && <span className="cs-tag">{p.position}</span>}
            {p.department && <span className="cs-tag cs-dept">{p.department}</span>}
          </div>

          {/* Ligne 3: Terrain / ATCD */}
          {(p.antecedents || p.preop_htn || p.preop_dm) && (
            <div className="cs-row cs-terrain">
              <span className="cs-section-label">ATCD</span>
              {p.preop_htn && <span className="cs-tag cs-patho">HTA</span>}
              {p.preop_dm && <span className="cs-tag cs-patho">Diabète</span>}
              {p.antecedents && p.antecedents !== "Aucun noté" && p.antecedents !== "Aucun" && (
                <span className="cs-detail">{p.antecedents}</span>
              )}
            </div>
          )}

          {/* Allergies + TTT */}
          {p.allergies && p.allergies !== "Aucune" && (
            <div className="cs-row cs-allergy">
              <span className="cs-section-label">ALLERGIES</span>
              <span className="cs-detail cs-allergy-text">{p.allergies}</span>
            </div>
          )}
          {p.traitement && p.traitement !== "Aucun" && (
            <div className="cs-row">
              <span className="cs-section-label">TTT</span>
              <span className="cs-detail">{p.traitement}</span>
            </div>
          )}

          {/* ECG + EFR */}
          {(p.preop_ecg || p.preop_pft) && (
            <div className="cs-row">
              {p.preop_ecg && <span className="cs-tag">ECG: {p.preop_ecg}</span>}
              {p.preop_pft && <span className="cs-tag">EFR: {p.preop_pft}</span>}
            </div>
          )}

          {/* Voies d'abord */}
          {(p.airway || p.iv1 || p.aline1 || p.cline1) && (
            <div className="cs-row cs-access">
              <span className="cs-section-label">VOIES</span>
              {p.airway && <span className="cs-tag">{p.airway}{p.tubesize ? ` ${p.tubesize}` : ""}</span>}
              {p.iv1 && <span className="cs-tag">VVP: {p.iv1}</span>}
              {p.iv2 && <span className="cs-tag">VVP2: {p.iv2}</span>}
              {p.aline1 && <span className="cs-tag cs-aline">KTA: {p.aline1}</span>}
              {p.cline1 && <span className="cs-tag cs-cline">VVC: {p.cline1}</span>}
            </div>
          )}

          {/* Bilan préop */}
          {p.bilan_preop && Object.keys(p.bilan_preop).length > 0 && (
            <div className="cs-row cs-bilan">
              <span className="cs-section-label">BILAN</span>
              {Object.entries(p.bilan_preop).map(([k, val]) => (
                <span key={k} className="cs-tag cs-bio">{k} {val}</span>
              ))}
            </div>
          )}

          {/* GDS préop */}
          {p.gds_preop && Object.keys(p.gds_preop).length > 0 && (
            <div className="cs-row cs-bilan">
              <span className="cs-section-label">GDS</span>
              {Object.entries(p.gds_preop).map(([k, val]) => (
                <span key={k} className="cs-tag cs-bio">{k} {val}</span>
              ))}
            </div>
          )}

          {/* Drogues peropératoires */}
          {p.drogues && Object.keys(p.drogues).length > 0 && (
            <div className="cs-row cs-drugs">
              <span className="cs-section-label">DROGUES</span>
              {Object.entries(p.drogues).map(([k, val]) => (
                <span key={k} className="cs-tag cs-drug">{k}: {val}</span>
              ))}
            </div>
          )}

          {/* Peropératoire (remplissage, saignement) */}
          {p.perop && Object.keys(p.perop).length > 0 && (
            <div className="cs-row cs-perop">
              <span className="cs-section-label">PEROP</span>
              {Object.entries(p.perop).map(([k, val]) => (
                <span key={k} className="cs-tag cs-perop-val">{k}: {val}</span>
              ))}
            </div>
          )}

          {/* Devenir */}
          {(p.icu_days != null && p.icu_days > 0 || p.death_inhosp) && (
            <div className="cs-row cs-outcome">
              {p.icu_days != null && p.icu_days > 0 && <span className="cs-tag cs-icu">REA {p.icu_days}j</span>}
              {p.death_inhosp && <span className="cs-tag cs-death">DÉCÈS HOSP.</span>}
            </div>
          )}
        </div>
      )}

      {/* ── Bandeau Phase PRE/PER/POST ── */}
      {phase_label && (
        <div className="phase-strip">
          <div className={`macro-phase macro--${(macro_phase ?? "PER").toLowerCase()}`}>
            {macro_phase === "PRE" && "PRÉ-OP"}
            {macro_phase === "PER" && "PER-OP"}
            {macro_phase === "POST" && "POST-OP"}
            {!macro_phase && "PER-OP"}
          </div>
          <div className="phase-detail">
            <span className="phase-label">{phase_label}</span>
            {elapsed_fmt && <span className="phase-elapsed">{elapsed_fmt}</span>}
          </div>
        </div>
      )}

      {/* ── Alertes ── */}
      <AlertPanel alerts={alerts} onAcknowledge={onAcknowledgeAlert} />

      {/* ── Grille vitaux : layout scope ── */}
      <div className="vitals-grid">
        {/* Ligne 1 : Hémodynamique */}
        <VitalCard
          label="FC"
          value={v.hr}
          unit="bpm"
          color="#00e676"
          min={45}
          max={120}
          history={hrHistory}
          alertLevel={getAlertLevel(v.hr, 50, 110, 40, 150)}
        />
        <VitalCard
          label="SpO₂"
          value={v.spo2}
          unit="%"
          color="#29b6f6"
          min={92}
          max={100}
          history={spo2History}
          alertLevel={getAlertLevel(v.spo2, 94, 101, 90, 101)}
        />
        <VitalCard
          label="PA"
          value={`${Math.round(v.pas)}/${Math.round(v.pad)}`}
          unit="mmHg"
          color="#ef5350"
          history={pasHistory}
          secondary={{ label: "PAM", value: Math.round(v.pam) }}
          alertLevel={getAlertLevel(v.pam, 60, 105, 50, 130)}
        />
        <VitalCard
          label="PAM"
          value={v.pam}
          unit="mmHg"
          color="#ef5350"
          min={55}
          max={120}
          history={pamHistory}
          alertLevel={getAlertLevel(v.pam, 60, 105, 50, 130)}
        />

        {/* Ligne 2 : Respiratoire */}
        <VitalCard
          label="EtCO₂"
          value={v.etco2}
          unit="mmHg"
          color="#ffee58"
          decimals={1}
          min={30}
          max={45}
          history={etco2History}
          alertLevel={getAlertLevel(v.etco2, 32, 42, 25, 55)}
        />
        <VitalCard
          label="FR"
          value={v.fr}
          unit="/min"
          color="#ffee58"
          min={8}
          max={25}
          history={frHistory}
          alertLevel={getAlertLevel(v.fr, 8, 25, 5, 35)}
        />
        <VitalCard
          label="T°"
          value={v.temp}
          unit="°C"
          color="#ffffff"
          decimals={1}
          alertLevel={getAlertLevel(v.temp, 35.5, 37.5, 35, 38.5)}
        />

        {/* Ventilateur */}
        {vent && (
          <>
            <VitalCard
              label="Vt"
              value={vent.vt}
              unit="mL"
              color="#80cbc4"
              secondary={vent.vt_kg ? { label: "mL/kg", value: vent.vt_kg.toFixed(1) } : undefined}
            />
            <VitalCard
              label="Ppeak"
              value={vent.ppeak}
              unit="cmH₂O"
              color="#80cbc4"
              decimals={1}
              secondary={vent.pplat ? { label: "Pplat", value: vent.pplat.toFixed(1) } : undefined}
              tertiary={{ label: "PEP", value: vent.peep.toFixed(1) }}
              alertLevel={getAlertLevel(vent.ppeak, 0, 28, 0, 35)}
            />
            <VitalCard
              label="FiO₂"
              value={vent.fio2}
              unit="%"
              color="#80cbc4"
            />
          </>
        )}

        {/* BIS */}
        {bis && (
          <VitalCard
            label="BIS"
            value={bis.bis}
            unit=""
            color="#ce93d8"
            min={40}
            max={60}
            secondary={{ label: "SQI", value: `${bis.sqi}%` }}
            tertiary={{ label: "SR", value: `${bis.sr.toFixed(1)}%` }}
            alertLevel={
              bis.bis < 30 ? "critical" :
              bis.bis < 40 ? "warning" :
              bis.bis > 65 ? "warning" :
              "normal"
            }
          />
        )}
      </div>

      {/* ── AIVOC ── */}
      {(aH || aO) && (
        <div className="aivoc-section">
          {aH && (
            <div className="aivoc-card aivoc-card--hypnotic">
              <div className="aivoc-drug">{aH.drug.toUpperCase()}</div>
              <div className="aivoc-model">{aH.model} — {aH.target_type}</div>
              <div className="aivoc-values">
                <span className="aivoc-target">Cible: {aH.target} µg/mL</span>
                <span className="aivoc-ce">Ce: {aH.predicted_effect.toFixed(2)}</span>
                <span className="aivoc-cp">Cp: {aH.predicted_plasma.toFixed(2)}</span>
              </div>
              <div className="aivoc-rate">{aH.infusion_rate} mL/h</div>
            </div>
          )}
          {aO && (
            <div className="aivoc-card aivoc-card--opioid">
              <div className="aivoc-drug">{aO.drug.toUpperCase()}</div>
              <div className="aivoc-model">{aO.model} — {aO.target_type}</div>
              <div className="aivoc-values">
                <span className="aivoc-target">Cible: {aO.target} ng/mL</span>
                <span className="aivoc-ce">Ce: {aO.predicted_effect.toFixed(2)}</span>
                <span className="aivoc-cp">Cp: {aO.predicted_plasma.toFixed(2)}</span>
              </div>
              <div className="aivoc-rate">{aO.infusion_rate} mL/h</div>
            </div>
          )}
        </div>
      )}

      {/* ── CHARLES IA ── */}
      <LLMPanel
        analysis={llm_analysis}
        onRequestAnalysis={onRequestAnalysis ?? (() => {})}
      />
    </div>
  );
}
