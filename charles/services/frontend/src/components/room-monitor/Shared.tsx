import type { Alert, RoomState } from "../../types";

export function AlertStrips({ alerts, onAck }: { alerts: Alert[]; onAck?: (id: number) => void }) {
  if (alerts.length === 0) {
    return null;
  }

  return (
    <div className="rm-alerts" data-testid="room-alerts">
      {alerts.slice(0, 3).map((alert, index) => (
        <div key={index} className={`rm-alert-row rm-alert--${alert.level}`} data-testid={`room-alert-${alert.level}`}>
          <span className="rm-alert-icon">{alert.level === "critical" ? "!" : "i"}</span>
          <span className="rm-alert-title">{alert.title}</span>
          <span className="rm-alert-detail">{alert.detail}</span>
          {alert.id != null && onAck && (
            <button className="rm-alert-ack" data-testid="room-alert-ack" onClick={() => onAck(alert.id!)}>x</button>
          )}
        </div>
      ))}
    </div>
  );
}

export function PatientBar({ data }: { data: RoomState }) {
  const patient = data.patient_info;

  return (
    <div className="rm-patient-bar">
      {patient ? (
        <>
          <span className="pt-name">{patient.opname ?? "Patient"}</span>
          {patient.asa != null && <span className={`ptag ptag-asa ptag-asa--${patient.asa}`}>ASA {patient.asa}</span>}
          {patient.ane_type && <span className="ptag ptag-ane">{patient.ane_type}</span>}
          {(patient.preop_htn || patient.preop_dm) && (
            <span className="ptag ptag-co">
              {[patient.preop_htn && "HTA", patient.preop_dm && "DT2"].filter(Boolean).join(" · ")}
            </span>
          )}
          {patient.weight != null && (
            <span className="pt-demo">
              {patient.weight}kg{patient.height ? ` · ${patient.height}cm` : ""}{patient.age ? ` · ${patient.age}ans` : ""}
            </span>
          )}
        </>
      ) : (
        <span className="pt-name" style={{ color: "#2a2a3a" }}>Aucun patient enregistre</span>
      )}
      {data.phase_label && (
        <span className="rm-phase-tag">
          {data.macro_phase ?? "PER"}-OP · {data.elapsed_fmt ?? "-"} · {data.phase_label}
        </span>
      )}
    </div>
  );
}
