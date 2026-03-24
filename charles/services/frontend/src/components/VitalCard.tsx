// ═══════════════════════════════════════════════════════════════
// CHARLES — VitalCard : affichage d'un paramètre vital
// Style scope anesthésie (GE / Philips / Dräger)
// ═══════════════════════════════════════════════════════════════

import { useEffect, useRef } from "react";

interface VitalCardProps {
  label: string;
  value: number | string;
  unit: string;
  color: string;
  min?: number;
  max?: number;
  history?: number[];
  decimals?: number;
  alertLevel?: "normal" | "warning" | "critical";
  secondary?: { label: string; value: number | string };
  tertiary?: { label: string; value: number | string };
}

export function VitalCard({
  label,
  value,
  unit,
  color,
  min,
  max,
  history,
  decimals = 0,
  alertLevel = "normal",
  secondary,
  tertiary,
}: VitalCardProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  // Mini-trend canvas
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas || !history || history.length < 2) return;

    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const w = canvas.width;
    const h = canvas.height;
    ctx.clearRect(0, 0, w, h);

    const data = history;
    const dataMin = min ?? Math.min(...data) - 5;
    const dataMax = max ?? Math.max(...data) + 5;
    const range = dataMax - dataMin || 1;

    ctx.strokeStyle = color;
    ctx.lineWidth = 1.5;
    ctx.beginPath();

    for (let i = 0; i < data.length; i++) {
      const x = (i / (data.length - 1)) * w;
      const y = h - ((data[i]! - dataMin) / range) * h;
      if (i === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    }
    ctx.stroke();

    // Bornes alert
    if (min !== undefined) {
      ctx.strokeStyle = "rgba(255,0,0,0.3)";
      ctx.lineWidth = 1;
      ctx.setLineDash([4, 4]);
      const yMin = h - ((min - dataMin) / range) * h;
      ctx.beginPath();
      ctx.moveTo(0, yMin);
      ctx.lineTo(w, yMin);
      ctx.stroke();
      ctx.setLineDash([]);
    }
    if (max !== undefined) {
      ctx.strokeStyle = "rgba(255,0,0,0.3)";
      ctx.lineWidth = 1;
      ctx.setLineDash([4, 4]);
      const yMax = h - ((max - dataMin) / range) * h;
      ctx.beginPath();
      ctx.moveTo(0, yMax);
      ctx.lineTo(w, yMax);
      ctx.stroke();
      ctx.setLineDash([]);
    }
  }, [history, color, min, max]);

  const borderColor =
    alertLevel === "critical"
      ? "#ff1744"
      : alertLevel === "warning"
        ? "#ffc107"
        : "rgba(255,255,255,0.08)";

  const formatted =
    typeof value === "number"
      ? value.toFixed(decimals)
      : value;

  return (
    <div
      className="vital-card"
      style={{
        borderColor,
        boxShadow:
          alertLevel === "critical"
            ? "0 0 16px rgba(255,23,68,0.4)"
            : alertLevel === "warning"
              ? "0 0 8px rgba(255,193,7,0.3)"
              : "none",
      }}
    >
      <div className="vital-header">
        <span className="vital-label" style={{ color }}>{label}</span>
        <span className="vital-unit" style={{ color }}>{unit}</span>
      </div>

      <div className="vital-value" style={{ color }}>
        {formatted}
      </div>

      {(secondary || tertiary) && (
        <div className="vital-secondary">
          {secondary && (
            <span style={{ color }}>
              {secondary.label} {secondary.value}
            </span>
          )}
          {tertiary && (
            <span style={{ color }}>
              {tertiary.label} {tertiary.value}
            </span>
          )}
        </div>
      )}

      {history && history.length > 1 && (
        <canvas
          ref={canvasRef}
          width={160}
          height={40}
          className="vital-trend"
        />
      )}
    </div>
  );
}
