// ═══════════════════════════════════════════════════════════════
// CHARLES — Application principale avec routing multi-rôles
// Routes : /login  /  (IADE)  /mar  /admin
// ═══════════════════════════════════════════════════════════════

import { useState } from "react";
import { Routes, Route, Navigate, useNavigate } from "react-router-dom";
import { useAuth } from "./hooks/useAuth";
import { useCharlesWS } from "./hooks/useCharlesWS";
import { RoomMonitor } from "./components/RoomMonitor";
import { LoginPage } from "./pages/LoginPage";
import { MARPage } from "./pages/MARPage";
import { AdminPage } from "./pages/AdminPage";
import { PreviewPage } from "./pages/PreviewPage";
import { UXConfigProvider } from "./context/UXConfigContext";
import "./scope.css";

const WS_URL = `${location.protocol.replace("http", "ws")}//${location.host}/ws`;

// ── Garde de route par rôle ───────────────────────────────────
function RequireAuth({
  children,
  allowedRoles,
}: {
  children: JSX.Element;
  allowedRoles?: string[];
}) {
  const { user } = useAuth();
  if (!user) return <Navigate to="/login" replace />;
  if (allowedRoles && !allowedRoles.includes(user.role)) return <Navigate to="/" replace />;
  return children;
}

// ── Dashboard IADE (page principale) ─────────────────────────
function IADEDashboard() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const { rooms, connected, waveRef, acknowledgeAlert, requestAnalysis, transportMetrics } = useCharlesWS(WS_URL);
  const roomIds = Object.keys(rooms);
  const [selectedRoom, setSelectedRoom] = useState<string | null>(null);

  const activeRoom = selectedRoom ?? roomIds[0] ?? null;

  return (
    <div className="charles-app">
      <div className="status-bar">
        <div className="status-left">
          <span className="charles-logo">CHARLES</span>
          <span className="charles-subtitle iade-badge">IADE — Vigilance peropératoire</span>
        </div>
        <div className="status-right">
          <span className="status-rooms" data-testid="status-rooms">{roomIds.length} salle{roomIds.length > 1 ? "s" : ""}</span>
          <span className={`status-dot ${connected ? "status-dot--ok" : "status-dot--err"}`} />
          <span className="status-text">{connected ? "Connecté" : "Déconnecté"}</span>
          <span className="status-text" data-testid="transport-metrics">
            ws {transportMetrics.messagesReceived} · waves {transportMetrics.waveChunksReceived} · lag {transportMetrics.approxLagMs ?? 0}ms
          </span>
          {user?.role === "mar" || user?.role === "admin" ? (
            <button className="nav-btn" onClick={() => navigate("/mar")}>↗ MAR</button>
          ) : null}
          {user?.role === "admin" ? (
            <button className="nav-btn" onClick={() => navigate("/admin")}>↗ Admin</button>
          ) : null}
          <span className="user-badge">👤 {user?.name ?? "IADE"}</span>
          <button className="nav-btn nav-btn--logout" onClick={() => { logout(); navigate("/login"); }}>
            Déconnexion
          </button>
        </div>
      </div>

      {roomIds.length === 0 ? (
        <div className="empty-state">
          <div className="empty-icon">⏳</div>
          <h2>En attente de données...</h2>
          <p>Lancez le simulateur ou le replay VitalDB pour voir les signaux vitaux en temps réel.</p>
          <code>docker compose up simulator</code>
        </div>
      ) : (
        <>
          {roomIds.length > 1 && (
            <div className="room-tabs">
              {roomIds.map((rid) => {
                const room = rooms[rid]!;
                const hasCritical = room.alerts.some((a) => a.level === "critical");
                const hasWarning = room.alerts.some((a) => a.level === "warning");
                return (
                  <button
                    key={rid}
                    data-testid={`room-tab-${rid}`}
                    className={`room-tab ${rid === activeRoom ? "room-tab--active" : ""} ${
                      hasCritical ? "room-tab--critical" : hasWarning ? "room-tab--warning" : ""
                    }`}
                    onClick={() => setSelectedRoom(rid)}
                  >
                    {rid.replace("_", " ").toUpperCase()}
                    {hasCritical && <span className="tab-alert">🔴</span>}
                    {!hasCritical && hasWarning && <span className="tab-alert">🟡</span>}
                  </button>
                );
              })}
            </div>
          )}
          {activeRoom && rooms[activeRoom] && (
            <RoomMonitor
              roomId={activeRoom}
              data={rooms[activeRoom]}
              waveRef={waveRef}
              onAcknowledgeAlert={acknowledgeAlert}
              onRequestAnalysis={() => requestAnalysis(activeRoom)}
            />
          )}
        </>
      )}
    </div>
  );
}

// ── Router principal ──────────────────────────────────────────
export default function App() {
  return (
    <UXConfigProvider>
      <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/preview" element={<PreviewPage />} />

      <Route path="/" element={
        <RequireAuth>
          <IADEDashboard />
        </RequireAuth>
      } />

      <Route path="/mar" element={
        <RequireAuth allowedRoles={["mar", "admin"]}>
          <MARPage />
        </RequireAuth>
      } />

      <Route path="/admin" element={
        <RequireAuth allowedRoles={["admin"]}>
          <AdminPage />
        </RequireAuth>
      } />

      {/* Fallback */}
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
    </UXConfigProvider>
  );
}
