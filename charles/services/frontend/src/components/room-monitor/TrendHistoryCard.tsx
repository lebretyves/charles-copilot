import { useEffect, useMemo, useRef, useState } from "react";

import type { TrendHistoryPoint, VitalsFrame } from "../../types";

type RangeKey = "15m" | "30m" | "1h" | "2h" | "all";
type AxisKind = "left" | "right";

interface TrendHistoryCardProps {
  history: TrendHistoryPoint[];
  currentVitals: VitalsFrame;
  elapsedFmt?: string;
  phaseLabel?: string;
}

interface ResolvedPoint {
  index: number;
  elapsedS: number;
  vitals: VitalsFrame;
}

interface MetricConfig {
  key: keyof VitalsFrame;
  label: string;
  color: string;
  axis: AxisKind;
  decimals?: number;
}

const RANGE_OPTIONS: Array<{ key: RangeKey; label: string; seconds: number }> = [
  { key: "15m", label: "15 min", seconds: 15 * 60 },
  { key: "30m", label: "30 min", seconds: 30 * 60 },
  { key: "1h", label: "1 heure", seconds: 60 * 60 },
  { key: "2h", label: "2 heures", seconds: 2 * 60 * 60 },
  { key: "all", label: "Tout", seconds: 0 },
];

const METRICS: MetricConfig[] = [
  { key: "hr", label: "FC", color: "#15803d", axis: "left" },
  { key: "spo2", label: "SpO2", color: "#2563eb", axis: "left" },
  { key: "fr", label: "FR", color: "#eab308", axis: "left" },
  { key: "pam", label: "PAM", color: "#dc2626", axis: "left" },
  { key: "etco2", label: "EtCO2", color: "#ea580c", axis: "left", decimals: 1 },
  { key: "temp", label: "T°C", color: "#7c3aed", axis: "right", decimals: 1 },
];

const GRAPH_WIDTH = 800;
const GRAPH_HEIGHT = 200;
const GRAPH_TOP = 20;
const GRAPH_BOTTOM = GRAPH_HEIGHT - 30;
const LEFT_AXIS_MIN = 0;
const LEFT_AXIS_MAX = 160;
const RIGHT_AXIS_MIN = 34;
const RIGHT_AXIS_MAX = 41;

export function TrendHistoryCard({ history, currentVitals, elapsedFmt, phaseLabel }: TrendHistoryCardProps) {
  const [rangeKey, setRangeKey] = useState<RangeKey>("15m");
  const [windowEndIndex, setWindowEndIndex] = useState(0);
  const previousLength = useRef(0);
  const previousRange = useRef<RangeKey>("15m");

  const points = useMemo<ResolvedPoint[]>(() => {
    let lastElapsed = 0;
    return history.map((point, index) => {
      const elapsed = typeof point.elapsed_s === "number"
        ? point.elapsed_s
        : index === 0
          ? 0
          : lastElapsed + 5;
      lastElapsed = elapsed;
      return { index, elapsedS: elapsed, vitals: point.vitals };
    });
  }, [history]);

  useEffect(() => {
    if (points.length === 0) {
      setWindowEndIndex(0);
      previousLength.current = 0;
      previousRange.current = rangeKey;
      return;
    }
    const maxIndex = points.length - 1;
    const previousMaxIndex = Math.max(0, previousLength.current - 1);
    const rangeChanged = previousRange.current !== rangeKey;
    const wasNearLatest = windowEndIndex >= Math.max(0, previousMaxIndex - 1);

    setWindowEndIndex((current) => {
      if (rangeChanged || previousLength.current === 0 || wasNearLatest) {
        return maxIndex;
      }
      return Math.max(0, Math.min(current, maxIndex));
    });

    previousLength.current = points.length;
    previousRange.current = rangeKey;
  }, [points.length, rangeKey, windowEndIndex]);

  if (points.length < 2) {
    return (
      <div className="trend-card trend-card--empty">
        <div className="trend-card-title">Tendances vitales</div>
        <div className="trend-card-empty">Historique insuffisant pour afficher une tendance.</div>
      </div>
    );
  }

  const rangeSeconds = RANGE_OPTIONS.find((option) => option.key === rangeKey)?.seconds ?? 15 * 60;
  const maxIndex = points.length - 1;
  const safeEndIndex = Math.max(0, Math.min(windowEndIndex, maxIndex));
  const startIndex = resolveWindowStartIndex(points, safeEndIndex, rangeSeconds);
  const visiblePoints = rangeSeconds <= 0 ? points : points.slice(startIndex, safeEndIndex + 1);
  const visibleStart = visiblePoints[0]?.elapsedS ?? 0;
  const visibleEnd = visiblePoints[visiblePoints.length - 1]?.elapsedS ?? visibleStart;
  const sliderMinEndIndex = resolveMinimumEndIndex(points, rangeSeconds);
  const showSlider = rangeSeconds > 0 && sliderMinEndIndex < maxIndex;
  const xTicks = buildXTicks(visibleStart, visibleEnd);

  return (
    <section className="trend-card">
      <div className="trend-card-header">
        <div>
          <h3 className="trend-card-title">Tendances vitales</h3>
          <div className="trend-card-subtitle">
            Historique relatif à T0
            {elapsedFmt ? ` · ${elapsedFmt}` : ""}
            {phaseLabel ? ` · ${phaseLabel}` : ""}
          </div>
        </div>
        <div className="trend-card-range">
          {RANGE_OPTIONS.map((option) => (
            <button
              key={option.key}
              type="button"
              className={`trend-card-range-btn ${rangeKey === option.key ? "trend-card-range-btn--active" : ""}`}
              onClick={() => setRangeKey(option.key)}
            >
              {option.label}
            </button>
          ))}
        </div>
      </div>

      <div className="trend-card-legend">
        {METRICS.map((metric) => (
          <div key={metric.key} className="trend-card-legend-item">
            <span className="trend-card-legend-dot" style={{ background: metric.color }} />
            <span className="trend-card-legend-label">{metric.label}</span>
            <span className="trend-card-legend-value" style={{ color: metric.color }}>
              {formatMetricValue(currentVitals[metric.key], metric.decimals)}
            </span>
          </div>
        ))}
      </div>

      <div className="trend-card-chart-shell">
        <div className="trend-card-chart-container">
          <div className="trend-card-axis trend-card-axis--left">
            <span>160</span>
            <span>120</span>
            <span>80</span>
            <span>40</span>
            <span>0</span>
          </div>

          <div className="trend-card-chart-scroll">
            <svg viewBox={`0 0 ${GRAPH_WIDTH} ${GRAPH_HEIGHT}`} preserveAspectRatio="xMidYMid meet" className="trend-card-chart">
          <rect x="0" y="0" width={GRAPH_WIDTH} height="54" fill="#ffffff" />
          {[GRAPH_TOP, 16.5, 27, 37.5, GRAPH_BOTTOM].map((y) => (
            <line key={y} x1="0" y1={y} x2={GRAPH_WIDTH} y2={y} className="trend-card-grid" />
          ))}
          {xTicks.map((tick) => (
            <line key={tick.x} x1={tick.x} y1={GRAPH_TOP} x2={tick.x} y2={GRAPH_BOTTOM} className="trend-card-grid trend-card-grid--vertical" />
          ))}

          {METRICS.map((metric) => {
            const path = buildMetricPath(visiblePoints, metric);
            if (!path) {
              return null;
            }
            return (
              <path
                key={metric.key}
                d={path}
                fill="none"
                stroke={metric.color}
                strokeWidth={metric.key === "pam" ? 2.2 : 1.8}
                strokeLinecap="round"
                strokeLinejoin="round"
              />
            );
          })}

          {xTicks.map((tick) => (
            <text key={`${tick.x}-label`} x={tick.x} y="53" textAnchor="middle" className="trend-card-tick-label">
              {tick.label}
            </text>
          ))}
        </svg>
        </div>

        <div className="trend-card-axis trend-card-axis--right">
          <span>41</span>
          <span>39</span>
          <span>37</span>
          <span>35</span>
          <span>34</span>
        </div>
      </div>
    </div>

      {showSlider ? (
        <div className="trend-card-slider">
          <div className="trend-card-slider-labels">
            <span>{formatElapsed(visibleStart)}</span>
            <span>{formatElapsed(visibleEnd)}</span>
          </div>
          <input
            className="trend-card-slider-input"
            type="range"
            min={sliderMinEndIndex}
            max={maxIndex}
            step={1}
            value={safeEndIndex}
            onChange={(event) => setWindowEndIndex(Number(event.target.value))}
          />
        </div>
      ) : null}
    </section>
  );
}

function resolveWindowStartIndex(points: ResolvedPoint[], endIndex: number, rangeSeconds: number): number {
  if (points.length === 0 || rangeSeconds <= 0) {
    return 0;
  }
  const threshold = (points[endIndex]?.elapsedS ?? 0) - rangeSeconds;
  const found = points.findIndex((point) => point.elapsedS >= threshold);
  return found === -1 ? 0 : found;
}

function resolveMinimumEndIndex(points: ResolvedPoint[], rangeSeconds: number): number {
  if (points.length === 0 || rangeSeconds <= 0) {
    return 0;
  }
  const threshold = (points[0]?.elapsedS ?? 0) + rangeSeconds;
  const found = points.findIndex((point) => point.elapsedS >= threshold);
  return found === -1 ? points.length - 1 : found;
}

function buildXTicks(startS: number, endS: number): Array<{ x: number; label: string }> {
  const tickCount = 5;
  if (endS <= startS) {
    return [{ x: GRAPH_WIDTH / 2, label: formatElapsed(startS) }];
  }
  return Array.from({ length: tickCount }, (_, index) => {
    const ratio = index / (tickCount - 1);
    const elapsed = startS + (endS - startS) * ratio;
    return {
      x: GRAPH_WIDTH * ratio,
      label: formatElapsedShort(elapsed),
    };
  });
}

function buildMetricPath(points: ResolvedPoint[], metric: MetricConfig): string {
  if (points.length < 2) {
    return "";
  }
  const total = points.length - 1;
  return points
    .map((point, index) => {
      const x = total === 0 ? 0 : (index / total) * GRAPH_WIDTH;
      const y = normalizeMetricValue(point.vitals[metric.key], metric.axis);
      return `${index === 0 ? "M" : "L"} ${x.toFixed(2)} ${y.toFixed(2)}`;
    })
    .join(" ");
}

function normalizeMetricValue(value: number, axis: AxisKind): number {
  const min = axis === "left" ? LEFT_AXIS_MIN : RIGHT_AXIS_MIN;
  const max = axis === "left" ? LEFT_AXIS_MAX : RIGHT_AXIS_MAX;
  const clamped = Math.min(Math.max(value, min), max);
  const ratio = (clamped - min) / (max - min || 1);
  return GRAPH_BOTTOM - ratio * (GRAPH_BOTTOM - GRAPH_TOP);
}

function formatMetricValue(value: number, decimals = 0): string {
  if (!Number.isFinite(value)) {
    return "—";
  }
  return decimals > 0 ? value.toFixed(decimals) : `${Math.round(value)}`;
}

function formatElapsed(totalSeconds: number): string {
  const safe = Math.max(0, Math.round(totalSeconds));
  const hours = Math.floor(safe / 3600);
  const minutes = Math.floor((safe % 3600) / 60);
  const seconds = safe % 60;
  if (hours > 0) {
    return `T0+${hours.toString().padStart(2, "0")}:${minutes.toString().padStart(2, "0")}:${seconds.toString().padStart(2, "0")}`;
  }
  return `T0+${minutes.toString().padStart(2, "0")}:${seconds.toString().padStart(2, "0")}`;
}

function formatElapsedShort(totalSeconds: number): string {
  const safe = Math.max(0, Math.round(totalSeconds));
  const hours = Math.floor(safe / 3600);
  const minutes = Math.floor((safe % 3600) / 60);
  if (hours > 0) {
    return `${hours.toString().padStart(2, "0")}:${minutes.toString().padStart(2, "0")}`;
  }
  const seconds = safe % 60;
  return `${minutes.toString().padStart(2, "0")}:${seconds.toString().padStart(2, "0")}`;
}
