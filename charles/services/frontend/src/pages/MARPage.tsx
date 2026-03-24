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
                      <div className="supervision-room-header">
                        <strong>{rid.replace("_", " ").toUpperCase()}</strong>
                        <span className="supervision-time">{new Date(room.timestamp).toLocaleTimeString("fr-FR")}</span>
                      </div>

                      {/* Info patient */}
                      {room.patient_info && (
                        <div className="supervision-patient">
                          {room.patient_info.age}ans {room.patient_info.sex} — {room.patient_info.opname ?? "Chirurgie"}
                          {room.patient_info.asa && <span className={`cs-tag cs-asa asa-${room.patient_info.asa}`}> ASA {room.patient_info.asa}</span>}
                        </div>
                      )}

                      {/* Vitaux synthétiques */}
                      <div className="supervision-vitals">
                        <span style={{ color: "#00e676" }}>FC {v.hr}</span>
                        <span style={{ color: "#29b6f6" }}>SpO2 {v.spo2}%</span>
                        <span style={{ color: "#ef5350" }}>PAM {v.pam}</span>
                        <span style={{ color: "#ffee58" }}>EtCO2 {v.etco2}</span>
                        {room.bis && <span style={{ color: "#ce93d8" }}>BIS {room.bis.bis}</span>}
                      </div>

                      {/* Phase */}
                      {room.phase_label && (
                        <div className="supervision-phase">{room.phase_label} {room.elapsed_fmt && `· ${room.elapsed_fmt}`}</div>
                      )}

                      {/* Alertes */}
                      {hasAlerts ? (
                        <div className="supervision-alerts">
                          {criticals.length > 0 && <span className="sup-badge sup-badge--critical">🔴 {criticals.length} critique{criticals.length > 1 ? "s" : ""}</span>}
                          {warnings.length > 0 && <span className="sup-badge sup-badge--warning">🟡 {warnings.length} warning{warnings.length > 1 ? "s" : ""}</span>}
                          <div className="sup-alert-list">
                            {room.alerts.slice(0, 2).map((a, i) => (
                              <div key={i} className="sup-alert-item" style={{ color: levelColor(a.level) }}>
                                {a.title}
                              </div>
                            ))}
                          </div>
                        </div>
                      ) : (
                        <div className="supervision-ok">● Patient stable</div>
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
