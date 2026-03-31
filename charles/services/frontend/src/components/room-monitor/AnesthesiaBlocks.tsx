import type { BISFrame, LLMAnalysis } from "../../types";
import { fmt } from "./format";

export function BISMedtronic({ bis }: { bis?: BISFrame }) {
  const bisValue = bis?.bis ?? null;
  const bisColor = bisValue == null ? "#334466" : bisValue < 30 ? "#ef5350" : bisValue > 65 ? "#ffee58" : "#05cbee";

  return (
    <div className="bm-block">
      <div className="bm-topbar">
        <span className="bm-tbrand">BIS Bilateral</span>
        <span className="bm-tdate">
          {new Date().toLocaleDateString("fr-FR", { day: "2-digit", month: "2-digit" })} / {new Date().toLocaleTimeString("fr-FR", { hour: "2-digit", minute: "2-digit" })}
        </span>
      </div>

      <div className="bm-main">
        <div className="bm-sidebar">
          <div className="bm-sb-zone bm-sb-deep">80</div>
          <div className="bm-sb-zone bm-sb-good">60</div>
          <div className="bm-sb-zone bm-sb-target">40</div>
          <div className="bm-sb-zone bm-sb-low">20</div>
        </div>

        <div className="bm-center">
          <div className="bm-eeg-strip">
            <span className="bm-eeg-lbl">EEG</span>
            <div className="bm-eeg-line"></div>
          </div>

          <div className="bm-bigrow">
            <div className="bm-bisstack">
              <span className="bm-bislbl">BIS</span>
              <span className="bm-sqilbl">SQI {bis ? fmt(bis.sqi) : "-"}</span>
            </div>
            <span className="bm-num" style={{ color: bisColor }}>{bisValue != null ? fmt(bisValue) : "-"}</span>
          </div>

          <div className="bm-metrics">
            <div className="bm-m"><div className="bm-mlbl">SR</div><div className="bm-mval">{bis ? `${fmt(bis.sr, 0)}%` : "-"}</div></div>
            <div className="bm-m"><div className="bm-mlbl">EMG</div><div className="bm-mval">{bis ? `${fmt(bis.emg)}dB` : "-"}</div></div>
            <div className="bm-m"><div className="bm-mlbl">SQI</div><div className="bm-mval">{bis ? `${fmt(bis.sqi)}%` : "-"}</div></div>
          </div>
        </div>

        <div className="bm-rbar">
          <div className="bm-rbar-cell"><span>SR</span><span style={{ color: bisColor }}>{bis ? `${fmt(bis.sr, 1)}%` : "-"}</span></div>
          <div className="bm-rbar-cell"><span>EMG</span><span style={{ color: bisColor }}>{bis ? fmt(bis.emg) : "-"}</span></div>
          <div className="bm-rbar-cell"><span>SEF</span><span style={{ color: "#4070a0" }}>-</span></div>
        </div>
      </div>

      <div className="bm-foot"><span className="bm-fbrand">Medtronic</span></div>
    </div>
  );
}

export function BISEntropy({ bis }: { bis?: BISFrame }) {
  const re = bis ? fmt(bis.bis) : "-";
  const se = bis ? fmt(Math.max(0, bis.bis - 4)) : "-";
  const color = bis == null ? "#445566" : bis.bis < 30 ? "#ef5350" : bis.bis > 65 ? "#ffee58" : "#0ab0b0";

  return (
    <div className="bge-block">
      <div className="bge-hdr">
        <span className="bge-brand">GE</span>
        <span className="bge-model">E-Entropy Module</span>
      </div>
      <div className="bge-body">
        <div className="bge-vals">
          <div className="bge-v">
            <div className="bge-vlbl">RE</div>
            <div className="bge-vnum" style={{ color }}>{re}</div>
          </div>
          <span className="bge-sep">/</span>
          <div className="bge-v">
            <div className="bge-vlbl">SE</div>
            <div className="bge-vnum" style={{ color }}>{se}</div>
          </div>
        </div>
        <div className="bge-eeg">
          <span className="bge-eeg-lbl">- EEG -</span>
        </div>
        <div className="bge-params">
          <div className="bge-p"><div className="bge-plbl">BSR</div><div className="bge-pval" style={{ color }}>{bis ? "0%" : "-"}</div></div>
          <div className="bge-p"><div className="bge-plbl">RQI</div><div className="bge-pval" style={{ color }}>{bis ? `${fmt(bis.sqi)}%` : "-"}</div></div>
          <div className="bge-p"><div className="bge-plbl">EMG</div><div className="bge-pval" style={{ color }}>{bis ? `${fmt(bis.emg)}dB` : "-"}</div></div>
          <div className="bge-p"><div className="bge-plbl">SR</div><div className="bge-pval" style={{ color }}>{bis ? `${fmt(bis.sr, 1)}%` : "-"}</div></div>
        </div>
      </div>
    </div>
  );
}

export function IABlock({
  analysis,
  status,
  error,
  onRequest,
}: {
  analysis?: LLMAnalysis;
  status?: "queued" | "running" | "completed" | "error";
  error?: string;
  onRequest?: () => void;
}) {
  const busy = status === "queued" || status === "running";
  const effectiveStatus = error
    ? "error"
    : status ?? (analysis ? "completed" : "idle");
  const statusLabel =
    effectiveStatus === "queued"
      ? "En file"
      : effectiveStatus === "running"
        ? "Analyse live"
        : effectiveStatus === "completed"
          ? "Resultat pret"
          : effectiveStatus === "error"
            ? "Erreur IA"
            : "Veille";
  const buttonLabel = busy ? "Analyse en cours" : analysis ? "Relancer l'analyse" : "Analyser maintenant";
  const helperText = "Auto sur alerte critique. Manuel possible a tout moment.";
  const metaText = analysis
    ? [analysis.model, analysis.latency_ms ? `${Math.round(analysis.latency_ms)} ms` : null].filter(Boolean).join(" / ")
    : "LLM local temps reel";

  return (
    <div className="ia-block">
      <div className="ia-head">
        <div className="ia-head-main">
          <span className="ia-badge">CHARLES LIVE</span>
          <span className={`ia-status ia-status--${effectiveStatus}`}>{statusLabel}</span>
          {analysis && (
            <span className="ia-conf" style={{ color: (analysis.confidence ?? 0) > 0.7 ? "#6ce18d" : "#ffb34f" }}>
              Confiance {Math.round((analysis.confidence ?? 0) * 100)}%
            </span>
          )}
        </div>
        {onRequest && (
          <button className="ia-btn" data-testid="ia-request-analysis" onClick={onRequest} disabled={busy}>
            {buttonLabel}
          </button>
        )}
      </div>

      <div className="ia-helper">{helperText}</div>
      <div className="ia-meta">{metaText}</div>

      {busy ? (
        <div className="ia-sit" style={{ color: "#f0b36a" }}>
          {status === "queued"
            ? "Analyse placee en file apres alerte critique ou demande manuelle."
            : "CHARLES traite la salle en temps reel et prepare son interpretation."}
        </div>
      ) : error ? (
        <div className="ia-sit" style={{ color: "#ff8c7b" }}>{error}</div>
      ) : analysis ? (
        <>
          <div className="ia-sit">{analysis.situation}</div>
          {analysis.risks.length > 0 && (
            <div className="ia-risks">
              {analysis.risks.slice(0, 3).map((risk, index) => (
                <span key={index} className="ia-rtag">! {risk}</span>
              ))}
            </div>
          )}
          <div className="ia-recos">
            {analysis.recommendations.slice(0, 3).map((recommendation, index) => (
              <span key={index} className="ia-reco">{recommendation}</span>
            ))}
          </div>
          {analysis.call_mar && <div className="ia-call-mar">Appeler MAR - {analysis.call_mar_reason}</div>}
        </>
      ) : (
        <div className="ia-sit" style={{ color: "#8d96af" }}>
          CHARLES surveille les alertes critiques en continu. Lance une analyse manuelle pour forcer un commentaire immediat.
        </div>
      )}
    </div>
  );
}

export function TOFBlock() {
  return (
    <div className="tof-block">
      <div className="tof-hdr">
        <span className="tof-brand">Drager</span>
        <span className="tof-model">TOF-Watch SX</span>
        <span className="tof-mode">TOF / 15mA</span>
      </div>
      <div className="tof-body">
        <div className="tof-ratio-box">
          <div className="tof-rlbl">TOF Ratio</div>
          <div className="tof-rval">-</div>
          <div className="tof-pct">Non connecte</div>
        </div>
        <div className="tof-dots">
          {["T1", "T2", "T3", "T4"].map((label) => (
            <div key={label} className="tof-dot tof-dot--off">{label}</div>
          ))}
        </div>
        <div className="tof-stim">
          <div className="tof-stim-lbl">Stim</div>
          <div className="tof-stim-bar">
            <div className="tof-stim-fill" style={{ width: "0%" }}></div>
          </div>
        </div>
      </div>
    </div>
  );
}
