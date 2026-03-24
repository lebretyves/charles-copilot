// ═══════════════════════════════════════════════════════════════
// CHARLES — AlertPanel : bandeau d'alertes cliniques
// ═══════════════════════════════════════════════════════════════

import type { Alert } from "../types";

interface AlertPanelProps {
  alerts: Alert[];
  onAcknowledge?: (alertId: number) => void;
}

export function AlertPanel({ alerts, onAcknowledge }: AlertPanelProps) {
  if (alerts.length === 0) {
    return (
      <div className="alert-panel alert-panel--ok">
        <span className="alert-icon">●</span>
        <span>Aucune alerte — patient stable</span>
      </div>
    );
  }

  const sorted = [...alerts].sort((a, b) => {
    const priority = { critical: 0, warning: 1, info: 2 };
    return (priority[a.level] ?? 3) - (priority[b.level] ?? 3);
  });

  const maxLevel = sorted[0]?.level ?? "info";

  return (
    <div className={`alert-panel alert-panel--${maxLevel}`}>
      {sorted.map((alert, i) => (
        <div key={`${alert.rule_id}-${i}`} className={`alert-item alert-item--${alert.level}`}>
          <span className="alert-level-badge">
            {alert.level === "critical" ? "🔴" : alert.level === "warning" ? "🟡" : "🔵"}
          </span>
          <div className="alert-content">
            <strong>{alert.title}</strong>
            <span className="alert-detail">{alert.detail}</span>
          </div>
          {onAcknowledge && alert.id != null && !alert.acknowledged && (
            <button
              className="alert-ack-btn"
              onClick={() => onAcknowledge(alert.id!)}
              title="Acquitter l'alerte"
            >
              ACQ
            </button>
          )}
          {alert.acknowledged && <span className="alert-ack-badge">✓</span>}
        </div>
      ))}
    </div>
  );
}
