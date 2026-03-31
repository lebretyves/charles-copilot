// ═══════════════════════════════════════════════════════════════
// CHARLES — Vue MAR (Médecin Anesthésiste-Réanimateur)
// Supervision multi-salles + historique cas + analyses LLM
// ═══════════════════════════════════════════════════════════════

import { useState, useEffect, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../hooks/useAuth";
import { getStoredToken } from "../hooks/useAuth";
import { useCharlesWS } from "../hooks/useCharlesWS";

const API_URL = "/api";
const WS_URL = `${location.protocol.replace("http", "ws")}//${location.host}/ws`;

interface Case {
  case_id: string;
  patient_age: number | null;
  patient_sex: string | null;
  asa_score: number | null;
  surgery_type: string | null;
  anesthesia_type: string | null;
  room_id: string;
  started_at: string;
  ended_at: string | null;
  status: string;
}

interface AlertRecord {
  id: number;
  room_id: string;
  level: string;
  rule_id: string;
  title: string;
  detail: string;
  timestamp: string;
  acknowledged: boolean;
}

interface LLMRecord {
  id: number;
  timestamp: string;
  model: string;
  latency_ms: number;
  analysis: { situation: string; risks: string[]; recommendations: string[]; confidence: number };
}

function levelColor(level: string) {
  if (level === "critical") return "#ef5350";
  if (level === "warning") return "#ffee58";
  return "#29b6f6";
}

export function MARPage() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const { rooms, connected } = useCharlesWS(WS_URL);

  const [cases, setCases] = useState<Case[]>([]);
  const [selectedCase, setSelectedCase] = useState<string | null>(null);
  const [caseAlerts, setCaseAlerts] = useState<AlertRecord[]>([]);
  const [caseLLM, setCaseLLM] = useState<LLMRecord[]>([]);
  const [activeTab, setActiveTab] = useState<"supervision" | "cases" | "alerts">("supervision");

  function authHeaders(extra?: Record<string, string>) {
    const token = getStoredToken();
    return {
      ...(extra ?? {}),
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    };
  }

  // Charger les cas actifs
  const loadCases = useCallback(async () => {
    try {
      const r = await fetch(`${API_URL}/cases?limit=20`, {
        headers: authHeaders(),
      });
      const data = await r.json();
      setCases(Array.isArray(data) ? data : []);
    } catch { /* ignore */ }
  }, []);

  useEffect(() => { void loadCases(); }, [loadCases]);

  // Charger alertes + LLM d'un cas
  useEffect(() => {
    if (!selectedCase) return;
    Promise.all([
      fetch(`${API_URL}/cases/${selectedCase}/llm`, { headers: authHeaders() }).then((r) => r.json()),
      fetch(`${API_URL}/alerts?case_id=${selectedCase}&limit=50`, { headers: authHeaders() }).then((r) => r.json()),
    ]).then(([llm, alerts]) => {
      setCaseLLM(Array.isArray(llm) ? llm : []);
      setCaseAlerts(Array.isArray(alerts) ? alerts : []);
    }).catch(() => { /* ignore */ });
  }, [selectedCase]);

  // Clôturer un cas
  async function endCase(caseId: string) {
    await fetch(`${API_URL}/cases/${caseId}/end`, {
      method: "PUT",
      headers: authHeaders(),
    });
    void loadCases();
    if (selectedCase === caseId) setSelectedCase(null);
  }

  const roomIds = Object.keys(rooms);

  return (
    <div className="charles-app">
      {/* Header */}
      <div className="status-bar">
        <div className="status-left">
          <span className="charles-logo">CHARLES</span>
          <span className="charles-subtitle mar-badge">MAR — Supervision médicale</span>
        </div>
        <div className="status-right">
          <span className="status-rooms">{roomIds.length} salle{roomIds.length > 1 ? "s" : ""}</span>
          <span className={`status-dot ${connected ? "status-dot--ok" : "status-dot--err"}`} />
          <span className="user-badge">👨‍⚕️ {user?.name}</span>
          <button className="nav-btn" onClick={() => navigate("/")}>↗ IADE</button>
          <button className="nav-btn nav-btn--logout" onClick={() => { logout(); navigate("/login"); }}>Déconnexion</button>
        </div>
      </div>

      {/* Onglets navigation */}
      <div className="page-tabs">
        <button className={`page-tab ${activeTab === "supervision" ? "page-tab--active" : ""}`}
          onClick={() => setActiveTab("supervision")}>📡 Supervision temps réel</button>
        <button className={`page-tab ${activeTab === "cases" ? "page-tab--active" : ""}`}
          onClick={() => { setActiveTab("cases"); void loadCases(); }}>📋 Cas opératoires</button>
        <button className={`page-tab ${activeTab === "alerts" ? "page-tab--active" : ""}`}
          onClick={() => setActiveTab("alerts")}>🚨 Alertes & Analyses LLM</button>
      </div>

      <div className="mar-content">

        {/* ── Supervision temps réel ── */}
        {activeTab === "supervision" && (
          <div className="mar-supervision">
            <h2 className="section-title">État des salles — temps réel</h2>
            {roomIds.length === 0 ? (
              <div className="empty-state">
                <div className="empty-icon">⏳</div>
                <p>Aucune salle active. Le simulateur doit être lancé.</p>
              </div>
            ) : (
              <div className="supervision-grid">
                {roomIds.map((rid) => {
                  const room = rooms[rid]!;
                  const v = room.vitals;
                  const criticals = room.alerts.filter((a) => a.level === "critical");
                  const warnings = room.alerts.filter((a) => a.level === "warning");
                  const hasAlerts = room.alerts.length > 0;

                  return (
                    <div key={rid} className={`supervision-card ${criticals.length > 0 ? "supervision-card--critical" : warnings.length > 0 ? "supervision-card--warning" : ""}`}>
                      {/* ── Entête salle façon scope ── */}
                      <div className="sup-card-hdr">
                        <span className="sup-card-room">{rid.replace(/_/g, " ").toUpperCase()}</span>
                        {room.patient_info?.asa != null && (
                          <span className={`sup-asa asa-${room.patient_info.asa}`}>ASA {room.patient_info.asa}</span>
                        )}
                        {(criticals.length > 0 || warnings.length > 0) && (
                          <span className={`sup-alarm-dot ${criticals.length > 0 ? "sup-alarm-dot--crit" : "sup-alarm-dot--warn"}`}>⚠</span>
                        )}
                        <span className="sup-card-time">{new Date(room.timestamp).toLocaleTimeString("fr-FR")}</span>
                      </div>

                      {/* ── Info patient compacte ── */}
                      <div className="sup-patient-line">
                        {room.patient_info ? (
                          <>
                            <span className="sup-pt-name">{room.patient_info.opname ?? "Chirurgie"}</span>
                            <span className="sup-pt-demo">{room.patient_info.age}a {room.patient_info.sex}</span>
                            {room.patient_info.ane_type && <span className="sup-pt-ane">{room.patient_info.ane_type}</span>}
                          </>
                        ) : (
                          <span className="sup-pt-name" style={{ color: "#444" }}>Aucun patient</span>
                        )}
                      </div>

                      {/* ── Grille vitaux style moniteur ── */}
                      <div className="sup-vitals-grid">
                        <div className="sup-vital">
                          <span className="sup-vtag" style={{ color: "#007a30" }}>ECG</span>
                          <span className="sup-vval" style={{ color: "#00e676" }}>{v.hr ?? "—"}</span>
                          <span className="sup-vunit" style={{ color: "#005020" }}>bpm</span>
                        </div>
                        <div className="sup-vital">
                          <span className="sup-vtag" style={{ color: "#0070b0" }}>SpO₂</span>
                          <span className="sup-vval" style={{ color: "#29b6f6" }}>{v.spo2 ?? "—"}</span>
                          <span className="sup-vunit" style={{ color: "#004880" }}>%</span>
                        </div>
                        <div className="sup-vital">
                          <span className="sup-vtag" style={{ color: "#800000" }}>PAM</span>
                          <span className="sup-vval" style={{ color: "#ef5350" }}>{v.pam ?? "—"}</span>
                          <span className="sup-vunit" style={{ color: "#550000" }}>mmHg</span>
                        </div>
                        <div className="sup-vital">
                          <span className="sup-vtag" style={{ color: "#807000" }}>CO₂</span>
                          <span className="sup-vval" style={{ color: "#ffee58" }}>{v.etco2 ?? "—"}</span>
                          <span className="sup-vunit" style={{ color: "#504800" }}>mmHg</span>
                        </div>
                        {room.bis && (
                          <div className="sup-vital">
                            <span className="sup-vtag" style={{ color: "#6020a0" }}>BIS</span>
                            <span className="sup-vval" style={{ color: "#ce93d8" }}>{room.bis.bis ?? "—"}</span>
                            <span className="sup-vunit" style={{ color: "#401060" }}></span>
                          </div>
                        )}
                        {v.fr != null && (
                          <div className="sup-vital">
                            <span className="sup-vtag" style={{ color: "#806000" }}>FR</span>
                            <span className="sup-vval" style={{ color: "#ffa726" }}>{v.fr}</span>
                            <span className="sup-vunit" style={{ color: "#503800" }}>/min</span>
                          </div>
                        )}
                      </div>

                      {/* ── Phase + durée ── */}
                      {room.phase_label && (
                        <div className="sup-phase-row">
                          <span className="sup-phase-dot">◆</span>
                          <span className="sup-phase-lbl">{room.phase_label}</span>
                          {room.elapsed_fmt && <span className="sup-phase-time">{room.elapsed_fmt}</span>}
                        </div>
                      )}

                      {/* ── Alertes ou stable ── */}
                      {hasAlerts ? (
                        <div className="sup-alerts-block">
                          {room.alerts.slice(0, 3).map((a, i) => (
                            <div key={i} className={`sup-alert-row sup-alert--${a.level}`}>
                              <span className="sup-alert-lv">{a.level === "critical" ? "CRITIQUE" : a.level === "warning" ? "AVERT." : "INFO"}</span>
                              <span className="sup-alert-txt">{a.title}</span>
                            </div>
                          ))}
                        </div>
                      ) : (
                        <div className="sup-stable-row">
                          <span className="sup-stable-dot">●</span>
                          <span>Patient stable</span>
                        </div>
                      )}

                      {/* LLM */}
                      {room.llm_analysis && (
                        <div className="supervision-llm">
                          <span className="llm-icon">🤖</span>
                          <span className="supervision-llm-sit">{room.llm_analysis.situation}</span>
                          {room.llm_analysis.call_mar && (
                            <span className="call-mar-badge">⚠️ APPEL MAR REQUIS</span>
                          )}
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        )}

        {/* ── Cas opératoires ── */}
        {activeTab === "cases" && (
          <div className="mar-cases">
            <div className="mar-cases-list">
              <div className="section-header">
                <h2 className="section-title">Cas opératoires</h2>
                <button className="refresh-btn" onClick={() => void loadCases()}>↻ Rafraîchir</button>
              </div>
              {cases.length === 0 ? (
                <p className="text-muted">Aucun cas trouvé.</p>
              ) : (
                <table className="data-table">
                  <thead>
                    <tr>
                      <th>ID</th><th>Salle</th><th>Patient</th><th>Chirurgie</th><th>Anesthésie</th><th>Statut</th><th>Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {cases.map((c) => (
                      <tr
                        key={c.case_id}
                        className={`data-row ${selectedCase === c.case_id ? "data-row--selected" : ""}`}
                        onClick={() => { setSelectedCase(c.case_id); setActiveTab("alerts"); }}
                      >
                        <td className="mono">{c.case_id}</td>
                        <td>{c.room_id}</td>
                        <td>{c.patient_age ?? "?"}ans {c.patient_sex ?? ""} {c.asa_score ? `ASA ${c.asa_score}` : ""}</td>
                        <td>{c.surgery_type ?? "—"}</td>
                        <td>{c.anesthesia_type ?? "—"}</td>
                        <td>
                          <span className={`status-badge status-badge--${c.status}`}>{c.status}</span>
                        </td>
                        <td>
                          {c.status === "active" && (
                            <button className="action-btn action-btn--danger"
                              onClick={(e) => { e.stopPropagation(); void endCase(c.case_id); }}>
                              Clôturer
                            </button>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          </div>
        )}

        {/* ── Alertes & Analyses LLM d'un cas ── */}
        {activeTab === "alerts" && (
          <div className="mar-detail">
            {!selectedCase ? (
              <div className="empty-state">
                <p>Sélectionnez un cas dans l'onglet "Cas opératoires"</p>
                <button className="nav-btn" onClick={() => setActiveTab("cases")}>← Voir les cas</button>
              </div>
            ) : (
              <>
                <div className="section-header">
                  <h2 className="section-title">Cas {selectedCase}</h2>
                  <button className="nav-btn" onClick={() => setSelectedCase(null)}>✕ Fermer</button>
                </div>

                {/* Alertes */}
                <div className="detail-section">
                  <h3 className="subsection-title">🚨 Alertes ({caseAlerts.length})</h3>
                  {caseAlerts.length === 0 ? <p className="text-muted">Aucune alerte enregistrée.</p> : (
                    <div className="alert-timeline">
                      {caseAlerts.map((a) => (
                        <div key={a.id} className={`timeline-item timeline-item--${a.level}`}>
                          <span className="timeline-time">{new Date(a.timestamp).toLocaleTimeString("fr-FR")}</span>
                          <span className="timeline-badge" style={{ color: levelColor(a.level) }}>
                            {a.level === "critical" ? "🔴" : a.level === "warning" ? "🟡" : "🔵"}
                          </span>
                          <div className="timeline-content">
                            <strong>{a.title}</strong>
                            <span className="text-muted"> — {a.detail}</span>
                          </div>
                          {a.acknowledged && <span className="ack-badge">✓ ACQ</span>}
                        </div>
                      ))}
                    </div>
                  )}
                </div>

                {/* Analyses LLM */}
                <div className="detail-section">
                  <h3 className="subsection-title">🤖 Analyses LLM ({caseLLM.length})</h3>
                  {caseLLM.length === 0 ? <p className="text-muted">Aucune analyse LLM pour ce cas.</p> : (
                    <div className="llm-timeline">
                      {caseLLM.map((l) => (
                        <div key={l.id} className="llm-record">
                          <div className="llm-record-header">
                            <span className="timeline-time">{new Date(l.timestamp).toLocaleTimeString("fr-FR")}</span>
                            <span className="llm-model-tag">{l.model}</span>
                            <span className="llm-latency-tag">{l.latency_ms}ms</span>
                            <span className="llm-confidence-tag">{Math.round((l.analysis?.confidence ?? 0) * 100)}%</span>
                          </div>
                          <p className="llm-situation">{l.analysis?.situation}</p>
                          {l.analysis?.recommendations?.length > 0 && (
                            <ul className="llm-reco-list">
                              {l.analysis.recommendations.map((r, i) => <li key={i}>{r}</li>)}
                            </ul>
                          )}
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
