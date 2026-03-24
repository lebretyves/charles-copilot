// ═══════════════════════════════════════════════════════════════
// CHARLES — LLMPanel : recommandations IA pour l'IADE
// ═══════════════════════════════════════════════════════════════

import type { LLMAnalysis } from "../types";

interface LLMPanelProps {
  analysis: LLMAnalysis | undefined;
  onRequestAnalysis: () => void;
}

export function LLMPanel({ analysis, onRequestAnalysis }: LLMPanelProps) {
  if (!analysis) {
    return (
      <div className="llm-panel llm-panel--empty">
        <div className="llm-header">
          <span className="llm-icon">🤖</span>
          <span className="llm-title">CHARLES IA</span>
        </div>
        <p className="llm-hint">Aucune analyse — déclenche une analyse sur alerte critique</p>
        <button className="llm-trigger-btn" onClick={onRequestAnalysis}>
          Analyser la situation
        </button>
      </div>
    );
  }

  const confidencePct = Math.round(analysis.confidence * 100);
  const confidenceClass =
    analysis.confidence >= 0.8 ? "high" : analysis.confidence >= 0.5 ? "medium" : "low";

  return (
    <div className="llm-panel llm-panel--active">
      <div className="llm-header">
        <span className="llm-icon">🤖</span>
        <span className="llm-title">CHARLES IA</span>
        <span className={`llm-confidence llm-confidence--${confidenceClass}`}>
          {confidencePct}%
        </span>
        <span className="llm-model">{analysis.model}</span>
        <span className="llm-latency">{analysis.latency_ms}ms</span>
      </div>

      <div className="llm-situation">{analysis.situation}</div>

      {analysis.risks.length > 0 && (
        <div className="llm-section">
          <strong>⚠️ Risques identifiés</strong>
          <ul>
            {analysis.risks.map((r, i) => (
              <li key={i}>{r}</li>
            ))}
          </ul>
        </div>
      )}

      {analysis.recommendations.length > 0 && (
        <div className="llm-section">
          <strong>💡 Recommandations</strong>
          <ol>
            {analysis.recommendations.map((r, i) => (
              <li key={i}>{r}</li>
            ))}
          </ol>
        </div>
      )}

      <button className="llm-trigger-btn" onClick={onRequestAnalysis}>
        Nouvelle analyse
      </button>
    </div>
  );
}
