import { useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";

import { AlertingDashboard, type AlertingDashboardData } from "../components/admin/AlertingDashboard";
import { LearningDashboard, type LearningDashboardData } from "../components/admin/LearningDashboard";
import { UserManagement, type AdminUserCreatePayload, type AdminUserRecord } from "../components/admin/UserManagement";
import { ScenarioPanel } from "../components/ScenarioPanel";
import { useUXConfig, UX_CATALOG } from "../context/UXConfigContext";
import { getStoredToken, useAuth } from "../hooks/useAuth";

const API_URL = "/api";
const ROOMS = ["salle_1", "salle_2", "salle_3"];

type AdminTab = "system" | "alerts" | "complications" | "simulator" | "waveforms" | "learning" | "users" | "ux";

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

export function AdminPage() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const { config: uxConfig, set: setUX } = useUXConfig();

  const [health, setHealth] = useState<Health | null>(null);
  const [kbStatus, setKBStatus] = useState<KBStatus | null>(null);
  const [metrics, setMetrics] = useState<BackendMetrics | null>(null);
  const [alerts, setAlerts] = useState<GlobalAlerts[]>([]);
  const [alertStats, setAlertStats] = useState<AlertStats | null>(null);
  const [alertingDashboard, setAlertingDashboard] = useState<AlertingDashboardData | null>(null);
  const [alertingError, setAlertingError] = useState<string | null>(null);
  const [learningDashboard, setLearningDashboard] = useState<LearningDashboardData | null>(null);
  const [learningError, setLearningError] = useState<string | null>(null);
  const [users, setUsers] = useState<AdminUserRecord[]>([]);
  const [usersError, setUsersError] = useState<string | null>(null);
  const [usersFeedback, setUsersFeedback] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<AdminTab>("system");
  const [simRoom, setSimRoom] = useState("salle_1");
  const [simFeedback, setSimFeedback] = useState<string | null>(null);
  const [loadingSimulator, setLoadingSimulator] = useState(false);
  const [loadingAlerting, setLoadingAlerting] = useState(false);
  const [savingAlerting, setSavingAlerting] = useState(false);
  const [loadingLearning, setLoadingLearning] = useState(false);
  const [loadingUsers, setLoadingUsers] = useState(false);
  const [creatingUser, setCreatingUser] = useState(false);

  function authHeaders(extra?: Record<string, string>) {
    const token = getStoredToken();
    return {
      ...(extra ?? {}),
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    };
  }

  const loadSystem = useCallback(async () => {
    try {
      const [healthResponse, kbResponse, metricsResponse] = await Promise.all([
        fetch(`${API_URL}/health`, { headers: authHeaders() }).then((response) => response.json()),
        fetch(`${API_URL}/kb/status`, { headers: authHeaders() }).then((response) => response.json()),
        fetch(`${API_URL}/metrics`, { headers: authHeaders() }).then((response) => response.json()),
      ]);
      setHealth(healthResponse as Health);
      setKBStatus(kbResponse as KBStatus);
      setMetrics(metricsResponse as BackendMetrics);
    } catch {
      // keep last visible values
    }
  }, []);

  const loadAlerts = useCallback(async () => {
    try {
      const data: GlobalAlerts[] = await fetch(`${API_URL}/alerts?limit=100`, {
        headers: authHeaders(),
      }).then((response) => response.json());
      const safeAlerts = Array.isArray(data) ? data : [];
      setAlerts(safeAlerts);
      setAlertStats({
        total: safeAlerts.length,
        critical: safeAlerts.filter((alert) => alert.level === "critical").length,
        warning: safeAlerts.filter((alert) => alert.level === "warning").length,
        info: safeAlerts.filter((alert) => alert.level === "info").length,
        acknowledged: safeAlerts.filter((alert) => alert.acknowledged).length,
      });
    } catch {
      // keep last visible values
    }
  }, []);

  const loadLearning = useCallback(async () => {
    setLoadingLearning(true);
    setLearningError(null);
    try {
      const response = await fetch(`${API_URL}/admin/learning/status`, {
        headers: authHeaders(),
      });
      if (!response.ok) {
        throw new Error(`Dashboard learning indisponible (${response.status})`);
      }
      const data = await response.json();
      setLearningDashboard(data as LearningDashboardData);
    } catch (error) {
      setLearningError(error instanceof Error ? error.message : "Chargement learning impossible");
    } finally {
      setLoadingLearning(false);
    }
  }, []);

  const loadAlerting = useCallback(async () => {
    setLoadingAlerting(true);
    setAlertingError(null);
    try {
      const response = await fetch(`${API_URL}/admin/alerting/config`, {
        headers: authHeaders(),
      });
      if (!response.ok) {
        throw new Error(`Dashboard alerting indisponible (${response.status})`);
      }
      const data = await response.json();
      setAlertingDashboard(data as AlertingDashboardData);
    } catch (error) {
      setAlertingError(error instanceof Error ? error.message : "Chargement alerting impossible");
    } finally {
      setLoadingAlerting(false);
    }
  }, []);

  const loadUsers = useCallback(async () => {
    setLoadingUsers(true);
    setUsersError(null);
    try {
      const response = await fetch(`${API_URL}/admin/users`, {
        headers: authHeaders(),
      });
      if (!response.ok) {
        throw new Error(`Chargement utilisateurs impossible (${response.status})`);
      }
      const data = await response.json();
      setUsers(Array.isArray(data) ? (data as AdminUserRecord[]) : []);
    } catch (error) {
      setUsersError(error instanceof Error ? error.message : "Chargement utilisateurs impossible");
    } finally {
      setLoadingUsers(false);
    }
  }, []);

  const createUser = useCallback(async (payload: AdminUserCreatePayload): Promise<boolean> => {
    setCreatingUser(true);
    setUsersError(null);
    setUsersFeedback(null);
    try {
      const response = await fetch(`${API_URL}/admin/users`, {
        method: "POST",
        headers: authHeaders({ "Content-Type": "application/json" }),
        body: JSON.stringify(payload),
      });
      if (!response.ok) {
        const maybeJson = await response.json().catch(() => null);
        throw new Error((maybeJson as { detail?: string } | null)?.detail ?? `Creation utilisateur impossible (${response.status})`);
      }
      const created = (await response.json()) as AdminUserRecord;
      setUsersFeedback(`Compte ${created.username} cree avec succes`);
      await loadUsers();
      return true;
    } catch (error) {
      setUsersError(error instanceof Error ? error.message : "Creation utilisateur impossible");
      return false;
    } finally {
      setCreatingUser(false);
    }
  }, [loadUsers]);

  useEffect(() => {
    void loadSystem();
  }, [loadSystem]);

  useEffect(() => {
    if (activeTab === "alerts") {
      void loadAlerts();
    }
    if (activeTab === "complications") {
      void loadAlerting();
    }
    if (activeTab === "learning") {
      void loadLearning();
    }
    if (activeTab === "users") {
      void loadUsers();
    }
  }, [activeTab, loadAlerts, loadAlerting, loadLearning, loadUsers]);

  async function stopRoom() {
    setLoadingSimulator(true);
    try {
      await fetch(`${API_URL}/simulator/control`, {
        method: "POST",
        headers: authHeaders({ "Content-Type": "application/json" }),
        body: JSON.stringify({ action: "stop", room_id: simRoom }),
      });
      setSimFeedback(`${simRoom} arretee`);
    } catch {
      setSimFeedback("Commande simulateur en echec");
    } finally {
      setLoadingSimulator(false);
    }
  }

  async function saveAlertingConfig(payload: AlertingDashboardData) {
    setSavingAlerting(true);
    setAlertingError(null);
    try {
      const response = await fetch(`${API_URL}/admin/alerting/config`, {
        method: "PUT",
        headers: authHeaders({ "Content-Type": "application/json" }),
        body: JSON.stringify(payload),
      });
      if (!response.ok) {
        const detail = await response.text();
        throw new Error(detail || `Sauvegarde impossible (${response.status})`);
      }
      const data = await response.json();
      setAlertingDashboard(data as AlertingDashboardData);
    } catch (error) {
      setAlertingError(error instanceof Error ? error.message : "Sauvegarde alerting impossible");
    } finally {
      setSavingAlerting(false);
    }
  }

  async function resetAlertingConfig() {
    setSavingAlerting(true);
    setAlertingError(null);
    try {
      const response = await fetch(`${API_URL}/admin/alerting/config/reset`, {
        method: "POST",
        headers: authHeaders(),
      });
      if (!response.ok) {
        throw new Error(`Reset impossible (${response.status})`);
      }
      const data = await response.json();
      setAlertingDashboard(data as AlertingDashboardData);
    } catch (error) {
      setAlertingError(error instanceof Error ? error.message : "Reset alerting impossible");
    } finally {
      setSavingAlerting(false);
    }
  }

  return (
    <div className="charles-app">
      <div className="status-bar">
        <div className="status-left">
          <span className="charles-logo">CHARLES</span>
          <span className="charles-subtitle admin-badge">ADMIN - Systeme</span>
        </div>
        <div className="status-right">
          <span className="user-badge">Admin {user?.name}</span>
          <button className="nav-btn" onClick={() => navigate("/")}>IADE</button>
          <button className="nav-btn" onClick={() => navigate("/mar")}>MAR</button>
          <button
            className="nav-btn nav-btn--logout"
            onClick={() => {
              logout();
              navigate("/login");
            }}
          >
            Deconnexion
          </button>
        </div>
      </div>

      <div className="page-tabs">
        <button
          data-testid="admin-tab-system"
          className={`page-tab ${activeTab === "system" ? "page-tab--active" : ""}`}
          onClick={() => {
            setActiveTab("system");
            void loadSystem();
          }}
        >
          Systeme / KB / LLM
        </button>
        <button
          data-testid="admin-tab-alerts"
          className={`page-tab ${activeTab === "alerts" ? "page-tab--active" : ""}`}
          onClick={() => setActiveTab("alerts")}
        >
          Stats & alertes
        </button>
        <button
          data-testid="admin-tab-complications"
          className={`page-tab ${activeTab === "complications" ? "page-tab--active" : ""}`}
          onClick={() => setActiveTab("complications")}
        >
          Complications / seuils
        </button>
        <button
          data-testid="admin-tab-simulator"
          className={`page-tab ${activeTab === "simulator" ? "page-tab--active" : ""}`}
          onClick={() => setActiveTab("simulator")}
        >
          Simulateur
        </button>
        <button
          data-testid="admin-tab-waveforms"
          className={`page-tab ${activeTab === "waveforms" ? "page-tab--active" : ""}`}
          onClick={() => setActiveTab("waveforms")}
        >
          Waveforms reels
        </button>
        <button
          data-testid="admin-tab-learning"
          className={`page-tab ${activeTab === "learning" ? "page-tab--active" : ""}`}
          onClick={() => setActiveTab("learning")}
        >
          Learning / MLOps
        </button>
        <button
          data-testid="admin-tab-users"
          className={`page-tab ${activeTab === "users" ? "page-tab--active" : ""}`}
          onClick={() => setActiveTab("users")}
        >
          Utilisateurs
        </button>
        <button
          className={`page-tab ${activeTab === "ux" ? "page-tab--active" : ""}`}
          onClick={() => setActiveTab("ux")}
        >
          Configuration UX
        </button>
      </div>

      <div className="mar-content">
        {activeTab === "system" && (
          <div className="admin-system">
            <div className="section-header">
              <h2 className="section-title">Statut systeme</h2>
              <button className="refresh-btn" onClick={() => void loadSystem()}>Rafraichir</button>
            </div>

            <div className="admin-cards">
              <div className="admin-card">
                <div className="admin-card-title">Backend FastAPI</div>
                {health ? (
                  <div className="admin-card-body">
                    <div className="stat-row"><span>Statut</span><span className="stat-val stat-ok">{health.status}</span></div>
                    <div className="stat-row"><span>Salles actives</span><span className="stat-val">{health.rooms_active}</span></div>
                    <div className="stat-row"><span>Clients WebSocket</span><span className="stat-val">{health.ws_clients}</span></div>
                    <div className="stat-row"><span>Echecs DB</span><span className="stat-val">{health.db_persistence_failures ?? 0}</span></div>
                    <div className="stat-row"><span>Scope donnees</span><span className="stat-val">{health.data_scope ?? "public_anonymized_waveforms"}</span></div>
                    <div className="stat-row"><span>Uptime</span><span className="stat-val">{Math.round(health.uptime_s ?? 0)} s</span></div>
                  </div>
                ) : <p className="text-muted">Chargement...</p>}
              </div>

              <div className="admin-card" data-testid="admin-metrics-card">
                <div className="admin-card-title">Metrics live</div>
                {metrics ? (
                  <div className="admin-card-body">
                    <div className="stat-row"><span>Updates monitor</span><span className="stat-val">{metrics.monitoring_updates_total}</span></div>
                    <div className="stat-row"><span>Wave chunks</span><span className="stat-val">{metrics.wave_chunks_total}</span></div>
                    <div className="stat-row"><span>Alertes critiques</span><span className="stat-val">{metrics.critical_alerts_total}</span></div>
                    <div className="stat-row"><span>Demandes LLM</span><span className="stat-val">{metrics.llm_requests_total}</span></div>
                    <div className="stat-row"><span>LLM OK / KO</span><span className="stat-val">{metrics.llm_completed_total} / {metrics.llm_failures_total}</span></div>
                    <div className="stat-row"><span>Latence LLM moy.</span><span className="stat-val">{metrics.llm_avg_latency_ms ?? "--"} ms</span></div>
                    <div className="stat-row"><span>Cmd simulateur</span><span className="stat-val">{metrics.simulator_commands_total}</span></div>
                    <div className="stat-row"><span>WS connexions / cmds</span><span className="stat-val">{metrics.ws_connections_total} / {metrics.ws_commands_total}</span></div>
                  </div>
                ) : <p className="text-muted">Chargement...</p>}
              </div>

              <div className="admin-card">
                <div className="admin-card-title">Knowledge Base</div>
                {kbStatus ? (
                  <div className="admin-card-body">
                    <div className="stat-row">
                      <span>Chargee</span>
                      <span className={`stat-val ${kbStatus.loaded ? "stat-ok" : "stat-err"}`}>
                        {kbStatus.loaded ? "oui" : "non"}
                      </span>
                    </div>
                    <div className="stat-row"><span>Fichiers YAML</span><span className="stat-val">{kbStatus.files.length}</span></div>
                    <div className="kb-files">
                      {kbStatus.files.map((file) => (
                        <span key={file} className="kb-file-tag">{file}</span>
                      ))}
                    </div>
                  </div>
                ) : <p className="text-muted">Chargement...</p>}
              </div>

              <div className="admin-card">
                <div className="admin-card-title">LLM / RAG</div>
                {kbStatus ? (
                  <div className="admin-card-body">
                    <div className="stat-row">
                      <span>LLM disponible</span>
                      <span className={`stat-val ${kbStatus.llm_available ? "stat-ok" : "stat-warn"}`}>
                        {kbStatus.llm_available ? "actif" : "inactif"}
                      </span>
                    </div>
                    <div className="stat-row"><span>Fournisseur</span><span className="stat-val">{kbStatus.llm_provider}</span></div>
                    <div className="stat-row"><span>Modele</span><span className="stat-val">{kbStatus.llm_model ?? "meditron:7b"}</span></div>
                    {!kbStatus.llm_available && (
                      <p className="admin-hint">Lancer Ollama ou verifier la config du worker.</p>
                    )}
                  </div>
                ) : <p className="text-muted">Chargement...</p>}
              </div>

              <div className="admin-card">
                <div className="admin-card-title">Services Docker</div>
                <div className="admin-card-body">
                  {[
                    { name: "Backend FastAPI", port: "8000", ok: !!health },
                    { name: "Frontend React", port: "443 / 3000", ok: true },
                    { name: "PostgreSQL", port: "5432 (interne)", ok: true },
                    { name: "Redis", port: "6379 (interne)", ok: true },
                    { name: "Mosquitto MQTT", port: "1883 (interne)", ok: true },
                    { name: "Simulateur", port: "--", ok: true },
                  ].map((service) => (
                    <div key={service.name} className="stat-row">
                      <span>{service.name}</span>
                      <span className="stat-val">
                        <span className={`stat-dot-inline ${service.ok ? "stat-ok" : "stat-err"}`}>●</span> {service.port}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </div>
        )}

        {activeTab === "alerts" && (
          <div className="admin-alerts">
            <div className="section-header">
              <h2 className="section-title">Statistiques des alertes</h2>
              <button className="refresh-btn" onClick={() => void loadAlerts()}>Rafraichir</button>
            </div>

            {alertStats && (
              <div className="stats-row">
                <div className="stat-card"><div className="stat-num">{alertStats.total}</div><div className="stat-label">Total</div></div>
                <div className="stat-card stat-card--critical"><div className="stat-num">{alertStats.critical}</div><div className="stat-label">Critiques</div></div>
                <div className="stat-card stat-card--warning"><div className="stat-num">{alertStats.warning}</div><div className="stat-label">Warnings</div></div>
                <div className="stat-card stat-card--info"><div className="stat-num">{alertStats.info}</div><div className="stat-label">Info</div></div>
                <div className="stat-card stat-card--ack"><div className="stat-num">{alertStats.acknowledged}</div><div className="stat-label">Acquittees</div></div>
              </div>
            )}

            <table className="data-table">
              <thead>
                <tr>
                  <th>Heure</th>
                  <th>Salle</th>
                  <th>Niveau</th>
                  <th>Regle</th>
                  <th>Titre</th>
                  <th>ACQ</th>
                </tr>
              </thead>
              <tbody>
                {alerts.map((alert) => (
                  <tr key={alert.id}>
                    <td className="mono">{new Date(alert.timestamp).toLocaleTimeString("fr-FR")}</td>
                    <td>{alert.room_id}</td>
                    <td><span className={`level-badge level-badge--${alert.level}`}>{alert.level}</span></td>
                    <td className="mono small">{alert.rule_id}</td>
                    <td>{alert.title}</td>
                    <td>{alert.acknowledged ? <span className="ack-badge">ok</span> : "--"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {activeTab === "simulator" && (
          <div className="admin-simulator">
            <div className="sim-panel sim-panel--stop">
              <h3 className="sim-stop-title">Arreter une salle</h3>
              <div className="sim-row">
                <label className="sim-label">Salle cible</label>
                <select className="sim-select" value={simRoom} onChange={(event) => setSimRoom(event.target.value)}>
                  {ROOMS.map((room) => (
                    <option key={room} value={room}>{room.replace("_", " ").toUpperCase()}</option>
                  ))}
                </select>
                <button className="action-btn action-btn--danger" onClick={() => void stopRoom()} disabled={loadingSimulator}>
                  Arreter la salle
                </button>
              </div>
              {simFeedback && <div className="sim-feedback">{simFeedback}</div>}
            </div>

            <ScenarioPanel hideClose onClose={() => {}} mode="all" />
          </div>
        )}

        {activeTab === "complications" && (
          <AlertingDashboard
            data={alertingDashboard}
            loading={loadingAlerting}
            saving={savingAlerting}
            error={alertingError}
            onRefresh={() => { void loadAlerting(); }}
            onSave={(payload) => { void saveAlertingConfig(payload); }}
            onReset={() => { void resetAlertingConfig(); }}
          />
        )}

        {activeTab === "ux" && (
          <div className="admin-system">
            <div className="section-header">
              <h2 className="section-title">Configuration UX - Materiel disponible</h2>
              <span className="text-muted small">Configuration globale persistante dans le navigateur.</span>
            </div>

            <div className="ux-cfg-grid">
              <div className="ux-cfg-section">
                <div className="ux-cfg-label">Moniteur patient</div>
                <div className="ux-cfg-options">
                  {UX_CATALOG.scope.map((option) => (
                    <button
                      key={option.value}
                      className={`ux-cfg-btn ${uxConfig.scope === option.value ? "ux-cfg-btn--active" : ""}`}
                      onClick={() => setUX({ scope: option.value })}
                    >
                      <span className="ux-cfg-brand">{option.tag}</span>
                      <span className="ux-cfg-desc">{option.label}</span>
                    </button>
                  ))}
                </div>
              </div>

              <div className="ux-cfg-section">
                <div className="ux-cfg-label">Ventilateur</div>
                <div className="ux-cfg-options">
                  {UX_CATALOG.vent.map((option) => (
                    <button
                      key={option.value}
                      className={`ux-cfg-btn ${uxConfig.vent === option.value ? "ux-cfg-btn--active" : ""}`}
                      onClick={() => setUX({ vent: option.value })}
                    >
                      <span className="ux-cfg-brand">{option.tag}</span>
                      <span className="ux-cfg-desc">{option.label}</span>
                    </button>
                  ))}
                </div>
              </div>

              <div className="ux-cfg-section">
                <div className="ux-cfg-label">Profondeur anesthesie</div>
                <div className="ux-cfg-options">
                  {UX_CATALOG.bis.map((option) => (
                    <button
                      key={option.value}
                      className={`ux-cfg-btn ${uxConfig.bis === option.value ? "ux-cfg-btn--active" : ""}`}
                      onClick={() => setUX({ bis: option.value })}
                    >
                      <span className="ux-cfg-brand">{option.tag}</span>
                      <span className="ux-cfg-desc">{option.label}</span>
                    </button>
                  ))}
                </div>
              </div>

              <div className="ux-cfg-section">
                <div className="ux-cfg-label">Pompe TCI</div>
                <div className="ux-cfg-options">
                  {UX_CATALOG.pump.map((option) => (
                    <button
                      key={option.value}
                      className={`ux-cfg-btn ${uxConfig.pump === option.value ? "ux-cfg-btn--active" : ""}`}
                      onClick={() => setUX({ pump: option.value })}
                    >
                      <span className="ux-cfg-brand">{option.tag}</span>
                      <span className="ux-cfg-desc">{option.label}</span>
                    </button>
                  ))}
                </div>
              </div>
            </div>

            <div className="ux-cfg-current">
              <span className="text-muted small">Configuration active :</span>
              <code className="ux-cfg-summary">
                Scope: {UX_CATALOG.scope.find((option) => option.value === uxConfig.scope)?.label}
                {" · "}Vent: {UX_CATALOG.vent.find((option) => option.value === uxConfig.vent)?.label}
                {" · "}BIS: {UX_CATALOG.bis.find((option) => option.value === uxConfig.bis)?.label}
                {" · "}Pompe: {UX_CATALOG.pump.find((option) => option.value === uxConfig.pump)?.label}
              </code>
            </div>
          </div>
        )}

        {activeTab === "waveforms" && (
          <div className="admin-simulator">
            <div className="wave-intro-banner">
              <div className="wave-intro-icon">WF</div>
              <div>
                <div className="wave-intro-title">Scenarios VitalDB avec waveforms haute frequence</div>
                <div className="wave-intro-desc">
                  Replay de waveforms reels: ECG, pleth SpO2, pression arterielle invasive,
                  capnogramme CO2, pression voie aerienne et EEG. Les courbes live partent
                  vers le scope de la salle selectionnee.
                </div>
              </div>
            </div>
            <ScenarioPanel hideClose onClose={() => {}} mode="waveforms" />
          </div>
        )}

        {activeTab === "users" && (
          <UserManagement
            users={users}
            loading={loadingUsers}
            creating={creatingUser}
            error={usersError}
            feedback={usersFeedback}
            onRefresh={() => { void loadUsers(); }}
            onCreate={createUser}
          />
        )}

        {activeTab === "learning" && (
          <LearningDashboard
            data={learningDashboard}
            loading={loadingLearning}
            error={learningError}
            onRefresh={() => { void loadLearning(); }}
          />
        )}
      </div>
    </div>
  );
}
