import type { Alert, VentilatorFrame, VitalsFrame } from "../../types";
import type { WaveRef } from "../../hooks/useCharlesWS";
import { WaveformCanvas } from "../WaveformCanvas";
import { alertClass, fmt } from "./format";

interface ScopeBaseProps {
  v: VitalsFrame;
  waveRef: WaveRef;
  roomId: string;
  hasWaveData: boolean;
  timestamp: string;
  alerts: Alert[];
  ventBrand?: "drager" | "ge";
  vent?: VentilatorFrame;
  bis?: number;
}

export function ScopeDrager({ v, waveRef, roomId, hasWaveData, timestamp, alerts, ventBrand, vent, bis }: ScopeBaseProps) {
  const hasCritical = alerts.some((alert) => alert.level === "critical");
  const alarmAlert = alerts.find((alert) => alert.level === "critical") ?? alerts.find((alert) => alert.level === "warning");

  return (
    <div className="scd-block">
      <div className="scd-hdr">
        <span className="scd-brand">Drager</span>
        <span className="scd-model">Infinity C500</span>
        {alarmAlert && (
          <span className={`scd-alarm ${hasCritical ? "scd-alarm--crit" : "scd-alarm--warn"}`}>
            ! {alarmAlert.title}
          </span>
        )}
        <span className="scd-time">{new Date(timestamp).toLocaleTimeString("fr-FR")}</span>
      </div>

      <div className="scd-body">
        <div className="scd-row">
          <div className="scd-row-label" style={{ borderLeftColor: "#00e676" }}>
            <span className="scd-row-tag" style={{ color: "#00e676" }}>II</span>
          </div>
          <div className="scd-row-wave"></div>
          <div className="scd-row-num">
            <span className="scd-row-param" style={{ color: "#006830" }}>ECG</span>
            <span className={`scd-row-val ${alertClass(v.hr, 50, 110, 40, 150)}`} style={{ color: "#00e676" }}>{fmt(v.hr)}</span>
            <span className="scd-row-unit" style={{ color: "#006830" }}>bpm</span>
          </div>
        </div>
        <div className="scd-row">
          <div className="scd-row-label" style={{ borderLeftColor: "#29b6f6" }}>
            <span className="scd-row-tag" style={{ color: "#29b6f6" }}>Pleth</span>
          </div>
          <div className="scd-row-wave"></div>
          <div className="scd-row-num">
            <span className="scd-row-param" style={{ color: "#0d47a1" }}>SpO2</span>
            <span className={`scd-row-val ${alertClass(v.spo2, 94, 101, 90, 101)}`} style={{ color: "#29b6f6" }}>{fmt(v.spo2)}</span>
            <span className="scd-row-unit" style={{ color: "#0d47a1" }}>%</span>
          </div>
        </div>
        <div className="scd-row">
          <div className="scd-row-label" style={{ borderLeftColor: "#ef5350" }}>
            <span className="scd-row-tag" style={{ color: "#ef5350" }}>ART</span>
          </div>
          <div className="scd-row-wave"></div>
          <div className="scd-row-num">
            <span className="scd-row-param" style={{ color: "#b71c1c" }}>ART</span>
            <span className={`scd-row-val scd-row-val--sm ${alertClass(v.pam, 60, 105, 50, 130)}`} style={{ color: "#ef5350" }}>
              {fmt(v.pas)}/{fmt(v.pad)}
            </span>
            <span className="scd-row-unit" style={{ color: "#b71c1c" }}>({fmt(v.pam)})</span>
          </div>
        </div>
        <div className="scd-row">
          <div className="scd-row-label" style={{ borderLeftColor: "#fdd835" }}>
            <span className="scd-row-tag" style={{ color: "#fdd835" }}>CO2</span>
          </div>
          <div className="scd-row-wave"></div>
          <div className="scd-row-num">
            <span className="scd-row-param" style={{ color: "#f9a825" }}>EtCO2</span>
            <span className={`scd-row-val ${alertClass(v.etco2, 30, 45, 20, 60)}`} style={{ color: "#fdd835" }}>{fmt(v.etco2, 1)}</span>
            <span className="scd-row-unit" style={{ color: "#f9a825" }}>mmHg</span>
          </div>
        </div>

        <div className="scd-canvas-layer">
          <WaveformCanvas
            waveRef={waveRef}
            roomId={roomId}
            hasWaveData={hasWaveData}
            compact={true}
            scopeBrand="drager"
            ventBrand={ventBrand}
            vitals={v}
            ventCurrent={vent ?? undefined}
            bis={bis}
          />
        </div>

        <div className="scd-side">
          <div className="scd-side-cell">
            <span className="scd-side-lbl" style={{ color: "#7ab5c8" }}>PANI</span>
            <span className="scd-side-val" style={{ color: "#ef5350" }}>{fmt(v.pas)}/{fmt(v.pad)}</span>
            <span className="scd-side-sub" style={{ color: "#7ab5c8" }}>PAM {fmt(v.pam)}</span>
          </div>
          <div className="scd-side-cell">
            <span className="scd-side-lbl" style={{ color: "#7ab5c8" }}>FR</span>
            <span className="scd-side-val" style={{ color: "#fdd835" }}>{fmt(v.fr)}</span>
            <span className="scd-side-sub" style={{ color: "#7ab5c8" }}>/min</span>
          </div>
          <div className="scd-side-cell">
            <span className="scd-side-lbl" style={{ color: "#7ab5c8" }}>Temp</span>
            <span className="scd-side-val" style={{ color: "#e0e0e0" }}>{fmt(v.temp, 1)}</span>
            <span className="scd-side-sub" style={{ color: "#7ab5c8" }}>C</span>
          </div>
          <div className="scd-side-cell">
            <span className="scd-side-lbl" style={{ color: "#7ab5c8" }}>ST</span>
            <span className="scd-side-val" style={{ color: "#00e676" }}>+0.0</span>
            <span className="scd-side-sub" style={{ color: "#7ab5c8" }}>mV</span>
          </div>
        </div>
      </div>

      <div className="scd-keys">
        <div className="scd-key">Alarmes</div>
        <div className="scd-key">Tendances</div>
        <div className="scd-key">Menu</div>
        <div className="scd-key">Setup</div>
        <div className="scd-key">Son 3</div>
      </div>
    </div>
  );
}

interface ScopeGenericProps extends ScopeBaseProps {
  theme: "ge" | "philips";
}

export function ScopeGeneric({ v, waveRef, roomId, hasWaveData, timestamp, alerts, theme, ventBrand, vent, bis }: ScopeGenericProps) {
  const hasCritical = alerts.some((alert) => alert.level === "critical");
  const alarmAlert = alerts.find((alert) => alert.level === "critical") ?? alerts.find((alert) => alert.level === "warning");
  const isGE = theme === "ge";

  return (
    <div className={`scd-block ${isGE ? "scg-root" : "scp-root"}`}>
      <div className="scd-hdr" style={isGE ? { background: "#1a2028" } : { background: "#00266a" }}>
        <span
          className="scd-brand"
          style={isGE ? { color: "#1268b0", fontWeight: 900, fontStyle: "italic" } : { color: "#e8e8f0", fontWeight: 700, fontStyle: "italic" }}
        >
          {isGE ? "GE" : "Philips"}
        </span>
        <span className="scd-model">{isGE ? "B40 Patient Monitor" : "IntelliVue MX800"}</span>
        {alarmAlert && (
          <span className={`scd-alarm ${hasCritical ? "scd-alarm--crit" : "scd-alarm--warn"}`}>
            ! {alarmAlert.title}
          </span>
        )}
        <span className="scd-time">{new Date(timestamp).toLocaleTimeString("fr-FR")}</span>
      </div>

      <div className="scd-body" style={isGE ? { background: "#1e2228" } : { background: "#0a1028" }}>
        <div className="scd-row">
          <div className="scd-row-label" style={{ borderLeftColor: "#00e676" }}>
            <span className="scd-row-tag" style={{ color: "#00e676" }}>II</span>
          </div>
          <div className="scd-row-wave"></div>
          <div className="scd-row-num">
            <span className="scd-row-param" style={{ color: "#006830" }}>ECG</span>
            <span className={`scd-row-val ${alertClass(v.hr, 50, 110, 40, 150)}`} style={{ color: "#00e676" }}>{fmt(v.hr)}</span>
            <span className="scd-row-unit" style={{ color: "#006830" }}>bpm</span>
          </div>
        </div>
        <div className="scd-row">
          <div className="scd-row-label" style={{ borderLeftColor: "#29b6f6" }}>
            <span className="scd-row-tag" style={{ color: "#29b6f6" }}>Pleth</span>
          </div>
          <div className="scd-row-wave"></div>
          <div className="scd-row-num">
            <span className="scd-row-param" style={{ color: "#0d47a1" }}>SpO2</span>
            <span className={`scd-row-val ${alertClass(v.spo2, 94, 101, 90, 101)}`} style={{ color: "#29b6f6" }}>{fmt(v.spo2)}</span>
            <span className="scd-row-unit" style={{ color: "#0d47a1" }}>%</span>
          </div>
        </div>
        <div className="scd-row">
          <div className="scd-row-label" style={{ borderLeftColor: "#ef5350" }}>
            <span className="scd-row-tag" style={{ color: "#ef5350" }}>ART</span>
          </div>
          <div className="scd-row-wave"></div>
          <div className="scd-row-num">
            <span className="scd-row-param" style={{ color: "#b71c1c" }}>ART</span>
            <span className={`scd-row-val scd-row-val--sm ${alertClass(v.pam, 60, 105, 50, 130)}`} style={{ color: "#ef5350" }}>
              {fmt(v.pas)}/{fmt(v.pad)}
            </span>
            <span className="scd-row-unit" style={{ color: "#b71c1c" }}>({fmt(v.pam)})</span>
          </div>
        </div>
        <div className="scd-row">
          <div className="scd-row-label" style={{ borderLeftColor: "#fdd835" }}>
            <span className="scd-row-tag" style={{ color: "#fdd835" }}>CO2</span>
          </div>
          <div className="scd-row-wave"></div>
          <div className="scd-row-num">
            <span className="scd-row-param" style={{ color: "#f9a825" }}>EtCO2</span>
            <span className={`scd-row-val ${alertClass(v.etco2, 30, 45, 20, 60)}`} style={{ color: "#fdd835" }}>{fmt(v.etco2, 1)}</span>
            <span className="scd-row-unit" style={{ color: "#f9a825" }}>mmHg</span>
          </div>
        </div>

        <div className="scd-canvas-layer">
          <WaveformCanvas
            waveRef={waveRef}
            roomId={roomId}
            hasWaveData={hasWaveData}
            compact={true}
            scopeBrand={theme}
            ventBrand={ventBrand}
            vitals={v}
            ventCurrent={vent ?? undefined}
            bis={bis}
          />
        </div>

        <div className="scd-side" style={isGE ? { background: "#161a20" } : { background: "#081838" }}>
          <div className="scd-side-cell">
            <span className="scd-side-lbl">PANI</span>
            <span className="scd-side-val" style={{ color: "#ef5350" }}>{fmt(v.pas)}/{fmt(v.pad)}</span>
            <span className="scd-side-sub">PAM {fmt(v.pam)}</span>
          </div>
          <div className="scd-side-cell">
            <span className="scd-side-lbl">FR</span>
            <span className="scd-side-val" style={{ color: "#fdd835" }}>{fmt(v.fr)}</span>
            <span className="scd-side-sub">/min</span>
          </div>
          <div className="scd-side-cell">
            <span className="scd-side-lbl">Temp</span>
            <span className="scd-side-val" style={{ color: "#b0b0b0" }}>{fmt(v.temp, 1)}</span>
            <span className="scd-side-sub">C</span>
          </div>
          <div className="scd-side-cell">
            <span className="scd-side-lbl">{isGE ? "SpO2" : "SaO2"}</span>
            <span className="scd-side-val" style={{ color: "#29b6f6" }}>{fmt(v.spo2)}</span>
            <span className="scd-side-sub">%</span>
          </div>
        </div>
      </div>

      <div className="scd-keys">
        {["Alarmes", "Tendances", "Menu", "Debit", "Son 3"].map((label) => (
          <div key={label} className="scd-key">{label}</div>
        ))}
      </div>
    </div>
  );
}
