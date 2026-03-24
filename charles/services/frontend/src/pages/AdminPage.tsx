// ═══════════════════════════════════════════════════════════════
// CHARLES — Vue Admin
// Statut système, stats globales, contrôle simulateur
// ═══════════════════════════════════════════════════════════════

import { useState, useEffect, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../hooks/useAuth";
import { getStoredToken } from "../hooks/useAuth";

const API_URL = "/api";

interface Health {
  status: string;
  service: string;
  rooms_active: number;
  ws_clients: number;
}

interface KBStatus {
  loaded: boolean;
  files: string[];
  llm_available: boolean;
  llm_provider: string;
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

const SYNTHETIC_SCENARIOS = ["normal", "hypotension", "desaturation", "anaphylaxie", "hemorragie"];
const ROOMS = ["salle_1", "salle_2", "salle_3"];

export function AdminPage() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  const [health, setHealth] = useState<Health | null>(null);
  const [kbStatus, setKBStatus] = useState<KBStatus | null>(null);
  const [alerts, setAlerts] = useState<GlobalAlerts[]>([]);
  const [alertStats, setAlertStats] = useState<AlertStats | null>(null);
  const [activeTab, setActiveTab] = useState<"system" | "alerts" | "simulator">("system");
  const [simRoom, setSimRoom] = useState("salle_1");
  const [simScenario, setSimScenario] = useState("normal");
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
      const [h, kb] = await Promise.all([
        fetch(`${API_URL}/health`, { headers: authHeaders() }).then((r) => r.json()),
        fetch(`${API_URL}/kb/status`, { headers: authHeaders() }).then((r) => r.json()),
      ]);
      setHealth(h as Health);
      setKBStatus(kb as KBStatus);
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

  async function startScenario() {
    setLoading(true);
    setSimFeedback(null);
    try {
      const resp = await fetch(`${API_URL}/simulator/control`, {
        method: "POST",
        headers: authHeaders({ "Content-Type": "application/json" }),
        body: JSON.stringify({ action: "start_synthetic", room_id: simRoom, scenario: simScenario, speed: 1.0 }),
      });
      if (resp.ok) setSimFeedback(`✅ Scénario "${simScenario}" lancé sur ${simRoom}`);
      else setSimFeedback("❌ Erreur lors du lancement");
    } catch {
      setSimFeedback("❌ Impossible de contacter le backend");
    }
    setLoading(false);
  }

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
        <button className={`page-tab ${activeTab === "system" ? "page-tab--active" : ""}`}
          onClick={() => { setActiveTab("system"); void loadSystem(); }}>🖥️ Système / KB / LLM</button>
        <button className={`page-tab ${activeTab === "alerts" ? "page-tab--active" : ""}`}
          onClick={() => setActiveTab("alerts")}>📊 Stats & Alertes</button>
        <button className={`page-tab ${activeTab === "simulator" ? "page-tab--active" : ""}`}
          onClick={() => setActiveTab("simulator")}>🎭 Simulateur</button>
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
                      <p className="admin-hint">Lancez Ollama : <code>ollama pull meditron:7b</code></p>
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
            <h2 className="section-title">Contrôle du simulateur</h2>

            <div className="sim-panel">
              <div className="sim-row">
                <label className="sim-label">Salle cible</label>
                <select className="sim-select" value={simRoom} onChange={(e) => setSimRoom(e.target.value)}>
                  {ROOMS.map((r) => <option key={r} value={r}>{r}</option>)}
                </select>
              </div>

              <div className="sim-row">
                <label className="sim-label">Scénario synthétique</label>
                <select className="sim-select" value={simScenario} onChange={(e) => setSimScenario(e.target.value)}>
                  {SYNTHETIC_SCENARIOS.map((s) => <option key={s} value={s}>{s}</option>)}
                </select>
              </div>

              <div className="sim-actions">
                <button className="action-btn action-btn--primary" onClick={() => void startScenario()} disabled={loading}>
                  ▶ Lancer scénario
                </button>
                <button className="action-btn action-btn--danger" onClick={() => void stopRoom()} disabled={loading}>
                  ⏹ Arrêter la salle
                </button>
              </div>

              {simFeedback && <div className="sim-feedback">{simFeedback}</div>}

              <div className="sim-hint">
                <strong>Scénarios disponibles :</strong>
                <ul>
                  <li><strong>normal</strong> — cholécystectomie coelioscopique ASA 1, vitaux stables</li>
                  <li><strong>hypotension</strong> — chute progressive PAS/PAM après induction</li>
                  <li><strong>desaturation</strong> — SpO2 qui chute (intubation difficile)</li>
                  <li><strong>anaphylaxie</strong> — réaction allergique brutale (tachycardie + hypotension + désaturation)</li>
                  <li><strong>hemorragie</strong> — pertes sanguines progressives (tachycardie + hypotension)</li>
                </ul>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
