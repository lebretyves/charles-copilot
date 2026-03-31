// ═══════════════════════════════════════════════════════════════
// CHARLES — Vue Admin
// Statut système, stats globales, contrôle simulateur
// ═══════════════════════════════════════════════════════════════

import { useState, useEffect, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../hooks/useAuth";
import { getStoredToken } from "../hooks/useAuth";
import { ScenarioPanel } from "../components/ScenarioPanel";
import { useUXConfig, UX_CATALOG } from "../context/UXConfigContext";

const API_URL = "/api";

interface Health {
  status: string;
  service: string;
  rooms_active: number;
  ws_clients: number;
  db_persistence_failures?: number;
  data_scope?: string;
  uptime_s?: number;
  last_monitoring_update_at?: string;
  last_wave_chunk_at?: string;
}

interface KBStatus {
  loaded: boolean;
  files: string[];
  llm_available: boolean;
  llm_provider: string;
  llm_model?: string;
}

interface BackendMetrics {
  monitoring_updates_total: number;
  wave_chunks_total: number;
  alerts_total: number;
  critical_alerts_total: number;
  llm_requests_total: number;
  llm_completed_total: number;
  llm_failures_total: number;
  llm_timeouts_total: number;
  ws_connections_total: number;
  ws_disconnects_total: number;
  ws_commands_total: number;
  simulator_commands_total: number;
  manual_alert_ack_total: number;
  llm_avg_latency_ms?: number | null;
}

interface AlertStats {
  total: number;
  critical: number;
  warning: number;
  info: number;
  acknowledged: number;
}

interface GlobalAlerts {
  id: number;
  room_id: string;
  level: string;
  rule_id: string;
  title: string;
  timestamp: string;
  acknowledged: boolean;
}

const ROOMS = ["salle_1", "salle_2", "salle_3"];

export function AdminPage() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  const [health, setHealth] = useState<Health | null>(null);
  const [kbStatus, setKBStatus] = useState<KBStatus | null>(null);
  const [metrics, setMetrics] = useState<BackendMetrics | null>(null);
  const [alerts, setAlerts] = useState<GlobalAlerts[]>([]);
  const [alertStats, setAlertStats] = useState<AlertStats | null>(null);
  const [activeTab, setActiveTab] = useState<"system" | "alerts" | "simulator" | "waveforms" | "ux">("system");
  const { config: uxConfig, set: setUX } = useUXConfig();
  const [simRoom, setSimRoom] = useState("salle_1");
  const [simFeedback, setSimFeedback] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  function authHeaders(extra?: Record<string, string>) {
    const token = getStoredToken();
    return {
      ...(extra ?? {}),
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    };
  }

  const loadSystem = useCallback(async () => {
    try {
      const [h, kb, m] = await Promise.all([
        fetch(`${API_URL}/health`, { headers: authHeaders() }).then((r) => r.json()),
        fetch(`${API_URL}/kb/status`, { headers: authHeaders() }).then((r) => r.json()),
        fetch(`${API_URL}/metrics`, { headers: authHeaders() }).then((r) => r.json()),
      ]);
      setHealth(h as Health);
      setKBStatus(kb as KBStatus);
      setMetrics(m as BackendMetrics);
    } catch { /* ignore */ }
  }, []);

  const loadAlerts = useCallback(async () => {
    try {
      const data: GlobalAlerts[] = await fetch(`${API_URL}/alerts?limit=100`, {
        headers: authHeaders(),
      }).then((r) => r.json());
      setAlerts(Array.isArray(data) ? data : []);

      const stats: AlertStats = {
        total: data.length,
        critical: data.filter((a) => a.level === "critical").length,
        warning: data.filter((a) => a.level === "warning").length,
        info: data.filter((a) => a.level === "info").length,
        acknowledged: data.filter((a) => a.acknowledged).length,
      };
      setAlertStats(stats);
    } catch { /* ignore */ }
  }, []);

  useEffect(() => { void loadSystem(); }, [loadSystem]);
  useEffect(() => {
    if (activeTab === "alerts") void loadAlerts();
  }, [activeTab, loadAlerts]);

  async function stopRoom() {
    setLoading(true);
    try {
      await fetch(`${API_URL}/simulator/control`, {
        method: "POST",
        headers: authHeaders({ "Content-Type": "application/json" }),
        body: JSON.stringify({ action: "stop", room_id: simRoom }),
      });
      setSimFeedback(`⏹ ${simRoom} arrêtée`);
    } catch { /* ignore */ }
    setLoading(false);
  }

  return (
    <div className="charles-app">
      {/* Header */}
      <div className="status-bar">
        <div className="status-left">
          <span className="charles-logo">CHARLES</span>
          <span className="charles-subtitle admin-badge">ADMIN — Système</span>
        </div>
        <div className="status-right">
          <span className="user-badge">⚙️ {user?.name}</span>
          <button className="nav-btn" onClick={() => navigate("/")}>↗ IADE</button>
          <button className="nav-btn" onClick={() => navigate("/mar")}>↗ MAR</button>
          <button className="nav-btn nav-btn--logout" onClick={() => { logout(); navigate("/login"); }}>Déconnexion</button>
        </div>
      </div>

      {/* Onglets */}
      <div className="page-tabs">
        <button data-testid="admin-tab-system" className={`page-tab ${activeTab === "system" ? "page-tab--active" : ""}`}
          onClick={() => { setActiveTab("system"); void loadSystem(); }}>🖥️ Système / KB / LLM</button>
        <button data-testid="admin-tab-alerts" className={`page-tab ${activeTab === "alerts" ? "page-tab--active" : ""}`}
          onClick={() => setActiveTab("alerts")}>📊 Stats & Alertes</button>
        <button data-testid="admin-tab-simulator" className={`page-tab ${activeTab === "simulator" ? "page-tab--active" : ""}`}
          onClick={() => setActiveTab("simulator")}>🎭 Simulateur</button>
        <button data-testid="admin-tab-waveforms" className={`page-tab ${activeTab === "waveforms" ? "page-tab--active" : ""}`}
          onClick={() => setActiveTab("waveforms")}>📈 Waveforms réels</button>
        <button className={`page-tab ${activeTab === "ux" ? "page-tab--active" : ""}`}
          onClick={() => setActiveTab("ux")}>🖥️ Configuration UX</button>
      </div>

      <div className="mar-content">

        {/* ── Statut système ── */}
        {activeTab === "system" && (
          <div className="admin-system">
            <div className="section-header">
              <h2 className="section-title">Statut système</h2>
              <button className="refresh-btn" onClick={() => void loadSystem()}>↻ Rafraîchir</button>
            </div>

            <div className="admin-cards">
              {/* Backend */}
              <div className="admin-card">
                <div className="admin-card-title">⚡ Backend FastAPI</div>
                {health ? (
                  <div className="admin-card-body">
                    <div className="stat-row"><span>Statut</span><span className="stat-val stat-ok">● {health.status}</span></div>
                    <div className="stat-row"><span>Salles actives</span><span className="stat-val">{health.rooms_active}</span></div>
                    <div className="stat-row"><span>Clients WebSocket</span><span className="stat-val">{health.ws_clients}</span></div>
                    <div className="stat-row"><span>Echecs DB</span><span className="stat-val">{health.db_persistence_failures ?? 0}</span></div>
                    <div className="stat-row"><span>Scope donnees</span><span className="stat-val">{health.data_scope ?? "public_anonymized_waveforms"}</span></div>
                    <div className="stat-row"><span>Uptime</span><span className="stat-val">{Math.round(health.uptime_s ?? 0)}s</span></div>
                  </div>
                ) : <p className="text-muted">Chargement...</p>}
              </div>

              <div className="admin-card" data-testid="admin-metrics-card">
                <div className="admin-card-title">ðŸ“Š Metrics live</div>
                {metrics ? (
                  <div className="admin-card-body">
                    <div className="stat-row"><span>Updates monitor</span><span className="stat-val">{metrics.monitoring_updates_total}</span></div>
                    <div className="stat-row"><span>Wave chunks</span><span className="stat-val">{metrics.wave_chunks_total}</span></div>
                    <div className="stat-row"><span>Alertes critiques</span><span className="stat-val">{metrics.critical_alerts_total}</span></div>
                    <div className="stat-row"><span>Demandes LLM</span><span className="stat-val">{metrics.llm_requests_total}</span></div>
                    <div className="stat-row"><span>LLM OK / KO</span><span className="stat-val">{metrics.llm_completed_total} / {metrics.llm_failures_total}</span></div>
                    <div className="stat-row"><span>Latence LLM moy.</span><span className="stat-val">{metrics.llm_avg_latency_ms ?? "—"} ms</span></div>
                    <div className="stat-row"><span>Cmd simulateur</span><span className="stat-val">{metrics.simulator_commands_total}</span></div>
                    <div className="stat-row"><span>WS connexions / cmds</span><span className="stat-val">{metrics.ws_connections_total} / {metrics.ws_commands_total}</span></div>
                  </div>
                ) : <p className="text-muted">Chargement...</p>}
              </div>

              {/* KB */}
              <div className="admin-card">
                <div className="admin-card-title">📚 Knowledge Base</div>
                {kbStatus ? (
                  <div className="admin-card-body">
                    <div className="stat-row">
                      <span>Chargée</span>
                      <span className={`stat-val ${kbStatus.loaded ? "stat-ok" : "stat-err"}`}>
                        {kbStatus.loaded ? "● Oui" : "✗ Non"}
                      </span>
                    </div>
                    <div className="stat-row"><span>Fichiers YAML</span><span className="stat-val">{kbStatus.files.length}</span></div>
                    <div className="kb-files">
                      {kbStatus.files.map((f) => (
                        <span key={f} className="kb-file-tag">{f}</span>
                      ))}
                    </div>
                  </div>
                ) : <p className="text-muted">Chargement...</p>}
              </div>

              {/* LLM */}
              <div className="admin-card">
                <div className="admin-card-title">🤖 LLM / RAG</div>
                {kbStatus ? (
                  <div className="admin-card-body">
                    <div className="stat-row">
                      <span>LLM disponible</span>
                      <span className={`stat-val ${kbStatus.llm_available ? "stat-ok" : "stat-warn"}`}>
                        {kbStatus.llm_available ? "● Actif" : "⚠ Inactif"}
                      </span>
                    </div>
                    <div className="stat-row"><span>Fournisseur</span><span className="stat-val">{kbStatus.llm_provider}</span></div>
                    {!kbStatus.llm_available && (
                      <p className="admin-hint">Lancez Ollama : <code>ollama pull {kbStatus.llm_model ?? "meditron:7b"}</code></p>
                    )}
                  </div>
                ) : <p className="text-muted">Chargement...</p>}
              </div>

              {/* Services Docker */}
              <div className="admin-card">
                <div className="admin-card-title">🐳 Services Docker</div>
                <div className="admin-card-body">
                  {[
                    { name: "Backend FastAPI", port: "8000", ok: !!health },
                    { name: "Frontend React", port: "3000", ok: true },
                    { name: "PostgreSQL", port: "5432 (interne)", ok: true },
                    { name: "Redis", port: "6379 (interne)", ok: true },
                    { name: "Mosquitto MQTT", port: "1883 (interne)", ok: true },
                    { name: "Simulateur", port: "—", ok: true },
                  ].map((s) => (
                    <div key={s.name} className="stat-row">
                      <span>{s.name}</span>
                      <span className="stat-val">
                        <span className={`stat-dot-inline ${s.ok ? "stat-ok" : "stat-err"}`}>●</span> :{s.port}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </div>
        )}

        {/* ── Stats & Alertes ── */}
        {activeTab === "alerts" && (
          <div className="admin-alerts">
            <div className="section-header">
              <h2 className="section-title">Statistiques des alertes</h2>
              <button className="refresh-btn" onClick={() => void loadAlerts()}>↻ Rafraîchir</button>
            </div>

            {alertStats && (
              <div className="stats-row">
                <div className="stat-card"><div className="stat-num">{alertStats.total}</div><div className="stat-label">Total</div></div>
                <div className="stat-card stat-card--critical"><div className="stat-num">{alertStats.critical}</div><div className="stat-label">Critiques</div></div>
                <div className="stat-card stat-card--warning"><div className="stat-num">{alertStats.warning}</div><div className="stat-label">Warnings</div></div>
                <div className="stat-card stat-card--info"><div className="stat-num">{alertStats.info}</div><div className="stat-label">Info</div></div>
                <div className="stat-card stat-card--ack"><div className="stat-num">{alertStats.acknowledged}</div><div className="stat-label">Acquittées</div></div>
              </div>
            )}

            <table className="data-table">
              <thead>
                <tr><th>Heure</th><th>Salle</th><th>Niveau</th><th>Règle</th><th>Titre</th><th>ACQ</th></tr>
              </thead>
              <tbody>
                {alerts.map((a) => (
                  <tr key={a.id}>
                    <td className="mono">{new Date(a.timestamp).toLocaleTimeString("fr-FR")}</td>
                    <td>{a.room_id}</td>
                    <td><span className={`level-badge level-badge--${a.level}`}>{a.level}</span></td>
                    <td className="mono small">{a.rule_id}</td>
                    <td>{a.title}</td>
                    <td>{a.acknowledged ? <span className="ack-badge">✓</span> : "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {/* ── Contrôle simulateur ── */}
        {activeTab === "simulator" && (
          <div className="admin-simulator">
            {/* Arrêt rapide d'une salle */}
            <div className="sim-panel sim-panel--stop">
              <h3 className="sim-stop-title">⏹ Arrêter une salle</h3>
              <div className="sim-row">
                <label className="sim-label">Salle cible</label>
                <select className="sim-select" value={simRoom} onChange={(e) => setSimRoom(e.target.value)}>
                  {ROOMS.map((r) => <option key={r} value={r}>{r.replace("_", " ").toUpperCase()}</option>)}
                </select>
                <button className="action-btn action-btn--danger" onClick={() => void stopRoom()} disabled={loading}>
                  ⏹ Arrêter la salle
                </button>
              </div>
              {simFeedback && <div className="sim-feedback">{simFeedback}</div>}
            </div>

            {/* Catalogue complet VitalDB + scénarios synthétiques */}
            <ScenarioPanel hideClose onClose={() => {}} mode="all" />
          </div>
        )}

        {/* ── Configuration UX matériel ── */}
        {activeTab === "ux" && (
          <div className="admin-system">
            <div className="section-header">
              <h2 className="section-title">Configuration UX — Matériel disponible</h2>
              <span className="text-muted small">Ce choix s'applique à toutes les salles. Persisté dans le navigateur.</span>
            </div>

            <div className="ux-cfg-grid">
              {/* ── Moniteur scope ── */}
              <div className="ux-cfg-section">
                <div className="ux-cfg-label">📟 Moniteur patient (scope)</div>
                <div className="ux-cfg-options">
                  {UX_CATALOG.scope.map(opt => (
                    <button
                      key={opt.value}
                      className={`ux-cfg-btn ${uxConfig.scope === opt.value ? "ux-cfg-btn--active" : ""}`}
                      onClick={() => setUX({ scope: opt.value })}
                    >
                      <span className="ux-cfg-brand">{opt.tag}</span>
                      <span className="ux-cfg-desc">{opt.label}</span>
                    </button>
                  ))}
                </div>
              </div>

              {/* ── Ventilateur ── */}
              <div className="ux-cfg-section">
                <div className="ux-cfg-label">💨 Ventilateur</div>
                <div className="ux-cfg-options">
                  {UX_CATALOG.vent.map(opt => (
                    <button
                      key={opt.value}
                      className={`ux-cfg-btn ${uxConfig.vent === opt.value ? "ux-cfg-btn--active" : ""}`}
                      onClick={() => setUX({ vent: opt.value })}
                    >
                      <span className="ux-cfg-brand">{opt.tag}</span>
                      <span className="ux-cfg-desc">{opt.label}</span>
                    </button>
                  ))}
                </div>
              </div>

              {/* ── Profondeur anesthésie ── */}
              <div className="ux-cfg-section">
                <div className="ux-cfg-label">🧠 Profondeur d'anesthésie</div>
                <div className="ux-cfg-options">
                  {UX_CATALOG.bis.map(opt => (
                    <button
                      key={opt.value}
                      className={`ux-cfg-btn ${uxConfig.bis === opt.value ? "ux-cfg-btn--active" : ""}`}
                      onClick={() => setUX({ bis: opt.value })}
                    >
                      <span className="ux-cfg-brand">{opt.tag}</span>
                      <span className="ux-cfg-desc">{opt.label}</span>
                    </button>
                  ))}
                </div>
              </div>

              {/* ── Pompe TCI ── */}
              <div className="ux-cfg-section">
                <div className="ux-cfg-label">💉 Pompe seringue TCI</div>
                <div className="ux-cfg-options">
                  {UX_CATALOG.pump.map(opt => (
                    <button
                      key={opt.value}
                      className={`ux-cfg-btn ${uxConfig.pump === opt.value ? "ux-cfg-btn--active" : ""}`}
                      onClick={() => setUX({ pump: opt.value })}
                    >
                      <span className="ux-cfg-brand">{opt.tag}</span>
                      <span className="ux-cfg-desc">{opt.label}</span>
                    </button>
                  ))}
                </div>
              </div>
            </div>

            <div className="ux-cfg-current">
              <span className="text-muted small">Configuration active :</span>
              <code className="ux-cfg-summary">
                Scope : {UX_CATALOG.scope.find(o => o.value === uxConfig.scope)?.label} ·
                Vent : {UX_CATALOG.vent.find(o => o.value === uxConfig.vent)?.label} ·
                BIS : {UX_CATALOG.bis.find(o => o.value === uxConfig.bis)?.label} ·
                Pompe : {UX_CATALOG.pump.find(o => o.value === uxConfig.pump)?.label}
              </code>
            </div>
          </div>
        )}

        {/* ── Waveforms réels ── */}
        {activeTab === "waveforms" && (
          <div className="admin-simulator">
            <div className="wave-intro-banner">
              <div className="wave-intro-icon">📈</div>
              <div>
                <div className="wave-intro-title">Scénarios VitalDB avec Waveforms Haute Fréquence</div>
                <div className="wave-intro-desc">
                  Replay de waveforms réels : ECG (500Hz), SpO₂ pléthysmogramme (500Hz), PA invasive (500Hz),
                  Capnogramme CO₂ (25Hz), Pression voie aérienne (25Hz), EEG (128Hz).
                  Les courbes en temps réel s'affichent sur les moniteurs de la salle sélectionnée.
                </div>
              </div>
            </div>
            <ScenarioPanel hideClose onClose={() => {}} mode="waveforms" />
          </div>
        )}
      </div>
    </div>
  );
}
