// â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
// CHARLES â€” WaveformCanvas : scope mÃ©dical haute frÃ©quence
// Signaux : ECG, SpOâ‚‚, ART, COâ‚‚, AWP, EEG
//
// Architecture :
//   - Lecture depuis waveRef (MutableRefObject) â€” AUCUN re-render React
//     sur les mises Ã  jour wave_chunk â†’ ventilateur/pompe stables
//   - boucle rAF persistante par voie (30 fps)
//   - Sweep Lâ†’R avec curseur d'Ã©criture + bande d'effacement (comportement
//     scope rÃ©el : DrÃ¤ger C500 / GE B40 / Philips MX800)
//   - Gain par voie : boutons +/- (stockÃ©s dans gainRef, pas de re-render)
//   - FenÃªtre temporelle : 4s / 8s (sÃ©lecteur global)
//   - Valeurs numÃ©riques overlayÃ©es sur le canvas (ECGâ†’HR, ARTâ†’SYS/DIA...)
// â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•

// ═══════════════════════════════════════════════════════════════

import { useEffect, useRef, useLayoutEffect, useState } from "react";
import type { WaveBuffers } from "../types";
import type { WaveRef } from "../hooks/useCharlesWS";

// ─── Fréquences d'échantillonnage par signal ─────────────────
const SAMPLE_RATES: Record<string, number> = {
  ecg: 500, pleth: 500, art: 500,
  co2: 25,  awp: 25,
  eeg: 128,
};

// ─── Échelles cliniques fixes par marque ─────────────────────
// Sources : doc opérateurs Dräger C500 / GE B40 / Philips MX800
export interface LaneScale {
  yMin: number; yMax: number;
  zeroLine?: boolean;
  refLines?: number[];
  autoGain?: boolean;
}
type ScaleMap = Partial<Record<string, LaneScale>>;

// Dräger Infinity C500 + Perseus A500
// ECG : yMin -0.5 / yMax 2.0 → 2.5 mV total → QRS 1 mV ≈ 40% hauteur lane
const SCALE_DRAGER: ScaleMap = {
  ecg:   { yMin: -0.5, yMax: 2.0, zeroLine: true },
  pleth: { yMin: 0,    yMax: 1,   autoGain: true },
  art:   { yMin: 0,    yMax: 200, refLines: [60, 80, 120, 160] },
  co2:   { yMin: 0,    yMax: 60,  refLines: [35, 45] },
  awp:   { yMin: -5,   yMax: 60,  refLines: [0, 20, 40] },
  eeg:   { yMin: -100, yMax: 100, zeroLine: true },
};
// GE B40 + Aisys CS²  — ART -20→220, AWP 0→80
const SCALE_GE: ScaleMap = {
  ecg:   { yMin: -0.5, yMax: 2.0, zeroLine: true },
  pleth: { yMin: 0,    yMax: 1,   autoGain: true },
  art:   { yMin: -20,  yMax: 220, refLines: [0, 60, 80, 120, 200] },
  co2:   { yMin: 0,    yMax: 60,  refLines: [35, 45] },
  awp:   { yMin: 0,    yMax: 80,  refLines: [20, 40, 60] },
  eeg:   { yMin: -100, yMax: 100, zeroLine: true },
};
// Philips IntelliVue MX800 — ART 0→200, AWP -10→80
const SCALE_PHILIPS: ScaleMap = {
  ecg:   { yMin: -0.5, yMax: 2.0, zeroLine: true },
  pleth: { yMin: 0,    yMax: 1,   autoGain: true },
  art:   { yMin: 0,    yMax: 200, refLines: [50, 100, 150] },
  co2:   { yMin: 0,    yMax: 60,  refLines: [35, 45] },
  awp:   { yMin: -10,  yMax: 80,  refLines: [0, 20, 40] },
  eeg:   { yMin: -100, yMax: 100, zeroLine: true },
};
const FALLBACK_SCALE: LaneScale = { yMin: -1, yMax: 1, autoGain: true };

export function getScaleMap(scopeBrand?: string, ventBrand?: string): ScaleMap {
  const base = scopeBrand === "ge" ? SCALE_GE
    : scopeBrand === "philips" ? SCALE_PHILIPS
    : SCALE_DRAGER;
  if (ventBrand && ventBrand !== scopeBrand) {
    return { ...base, awp: (ventBrand === "ge" ? SCALE_GE : SCALE_DRAGER).awp };
  }
  return base;
}

// ─── Config voies ────────────────────────────────────────────
interface LaneConfig { key: keyof WaveBuffers; label: string; color: string; height: number; }
const LANES: LaneConfig[] = [
  { key: "ecg",   label: "ECG",  color: "#00e676", height: 90 },
  { key: "pleth", label: "SpO₂", color: "#29b6f6", height: 70 },
  { key: "art",   label: "ART",  color: "#ef5350", height: 70 },
  { key: "co2",   label: "CO₂ RESP",  color: "#ffee58", height: 60 },
  { key: "awp",   label: "PAW RESP",  color: "#80cbc4", height: 60 },
  { key: "eeg",   label: "EEG",  color: "#ce93d8", height: 60 },
];

// ─── Rendu canvas ─────────────────────────────────────────────
// timeWindowSamples : nb d'échantillons couvrant toute la largeur
// gain : multiplicateur (1=défaut, 2=zoom ×2, 0.5=dézoom)
// overlayText : valeur numérique à afficher sur la voie
function drawLane(
  canvas: HTMLCanvasElement,
  data: number[],
  color: string,
  label: string,
  scale: LaneScale,
  gain: number,
  timeWindowSamples: number,
  sampleRate: number,       // ← nouveau : pour curseur time-based
  overlayText?: string,
): void {
  const ctx = canvas.getContext("2d");
  if (!ctx) return;
  const dpr = window.devicePixelRatio || 1;
  const W = canvas.width, H = canvas.height;
  const PAD = 4 * dpr;

  ctx.fillStyle = "#080c0a";
  ctx.fillRect(0, 0, W, H);

  // Échelle verticale avec gain
  let yMin = scale.yMin, yMax = scale.yMax;
  if (scale.autoGain && data.length > 10) {
    let mn = Infinity, mx = -Infinity;
    for (const v of data) { if (v < mn) mn = v; if (v > mx) mx = v; }
    if (mx > mn + 0.001) { const m = (mx - mn) * 0.2; yMin = mn - m; yMax = mx + m; }
  } else if (gain !== 1) {
    const c = (yMin + yMax) / 2, h = (yMax - yMin) / (2 * gain);
    yMin = c - h; yMax = c + h;
  }
  const yRange = yMax - yMin;
  if (yRange === 0) return;
  const toY = (v: number) => H - PAD - ((v - yMin) / yRange) * (H - PAD * 2);

  // Lignes de référence cliniques
  if (scale.refLines) {
    ctx.save();
    ctx.strokeStyle = "rgba(255,255,255,0.07)";
    ctx.lineWidth = dpr;
    for (const rl of scale.refLines) {
      const y = toY(rl); if (y >= 0 && y <= H) {
        ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(W, y); ctx.stroke();
      }
    }
    ctx.restore();
  }
  // Zéro en tirets (ECG, EEG)
  if (scale.zeroLine) {
    const y0 = toY(0);
    if (y0 >= 0 && y0 <= H) {
      ctx.save();
      ctx.strokeStyle = "rgba(255,255,255,0.18)";
      ctx.lineWidth = dpr;
      ctx.setLineDash([4 * dpr, 4 * dpr]);
      ctx.beginPath(); ctx.moveTo(0, y0); ctx.lineTo(W, y0); ctx.stroke();
      ctx.setLineDash([]); ctx.restore();
    }
  }

  // ── Sweep curseur TIME-BASED (comportement scope médical réel) ──
  //  Le curseur avance en fonction de l'horloge murale (performance.now()),
  //  indépendamment du remplissage du buffer.
  //  Le buffer ring est dessiné en anneau : sample le plus récent = position curseur.
  //  Une bande d'effacement (~3.5% W) efface juste devant le curseur.
  const timeWindowMs = (timeWindowSamples / sampleRate) * 1000;
  const sweepPhase   = (performance.now() / timeWindowMs) % 1.0;
  const cursorX      = sweepPhase * W;
  const ERASER_W     = Math.max(6 * dpr, Math.round(0.02 * W));
  const eraserEnd    = cursorX + ERASER_W;

  // Bande noire devant le curseur (wrap-around si nécessaire)
  ctx.fillStyle = "#080c0a";
  if (eraserEnd <= W) {
    ctx.fillRect(cursorX, 0, ERASER_W, H);
  } else {
    ctx.fillRect(cursorX, 0, W - cursorX, H);
    ctx.fillRect(0,       0, eraserEnd - W, H);
  }

  // ── Tracé ring-buffer avec gestion du wrap-around ──
  const samplesAvail = Math.min(data.length, timeWindowSamples);
  if (samplesAvail >= 2) {
    const slice        = data.slice(data.length - samplesAvail);
    const pixPerSample = W / timeWindowSamples;

    ctx.beginPath();
    ctx.strokeStyle = color;
    ctx.lineWidth   = 1.5 * dpr;
    ctx.lineJoin    = "round";
    let penDown = false;
    let prevX   = -9999;

    for (let i = 0; i < samplesAvail; i++) {
      // i=0 oldest, i=samplesAvail-1 newest → placed at cursorX
      const ageSamples = samplesAvail - 1 - i;
      let x = cursorX - ageSamples * pixPerSample;
      if (x < 0) x += W;
      x = ((x % W) + W) % W;

      // À l'intérieur de la bande d'effacement ? → interrompre le tracé
      const inEraser = eraserEnd <= W
        ? (x >= cursorX && x < eraserEnd)
        : (x >= cursorX || x < eraserEnd - W);

      // Saut de bord (wrap visuel) → interrompre plutôt que diagonale
      const jumped = prevX > -9999 && Math.abs(x - prevX) > W * 0.4;

      const y = toY(slice[i] ?? 0);
      if (inEraser || jumped || !penDown) {
        ctx.moveTo(x, y);
        penDown = !inEraser;
      } else {
        ctx.lineTo(x, y);
      }
      prevX = x;
    }
    ctx.stroke();
  }

  // Label + valeur overlay (EN FACE de la courbe — gauche du canvas)
  if (label) {
    ctx.fillStyle = color;
    ctx.font = `bold ${8 * dpr}px "Roboto Mono", monospace`;
    ctx.fillText(label, 4 * dpr, 11 * dpr);
  }
  if (overlayText) {
    ctx.fillStyle = color;
    ctx.font = `bold ${Math.min(14, 12) * dpr}px "Roboto Mono", monospace`;
    ctx.fillText(overlayText, 4 * dpr, 26 * dpr);
  }
  // Indicateur gain (coin sup. droit)
  if (gain !== 1) {
    ctx.fillStyle = "rgba(200,200,200,0.5)";
    ctx.font = `${7 * dpr}px monospace`;
    const gt = gain > 1 ? `×${gain}` : `÷${1 / gain}`;
    ctx.fillText(gt, W - 18 * dpr, 11 * dpr);
  }
}

// ─── WaveLane : une voie, boucle rAF, lit waveRef directement ─
interface SingleLaneProps {
  waveRef: WaveRef;
  roomId: string;
  laneKey: string;
  scaleRef: React.RefObject<LaneScale>;
  gainRef: React.MutableRefObject<Record<string, number>>;
  timeWindowRef: React.MutableRefObject<number>;
  overlayRef: React.MutableRefObject<Record<string, string>>;
  color: string;
  label: string;
  height: number;
}
function WaveLane({
  waveRef, roomId, laneKey, scaleRef, gainRef, timeWindowRef, overlayRef,
  color, label, height,
}: SingleLaneProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const dpr = window.devicePixelRatio || 1;

    const sizeCanvas = () => {
      // Priorité clientWidth/clientHeight du parent (laisser CSS flex décider)
      // Fallback sur height prop si parent pas encore rendu
      const w = Math.max(10, canvas.parentElement?.clientWidth ?? 300);
      const h = Math.max(10, canvas.parentElement?.clientHeight ?? height);
      const nW = Math.round(w * dpr), nH = Math.round(h * dpr);
      if (canvas.width !== nW || canvas.height !== nH) { canvas.width = nW; canvas.height = nH; }
    };
    sizeCanvas();
    const ro = new ResizeObserver(sizeCanvas);
    if (canvas.parentElement) ro.observe(canvas.parentElement);

    let raf = 0, lastTs = 0;
    const FRAME_MS = 33; // ~30 fps

    const frame = (ts: number) => {
      try {
        if (ts - lastTs >= FRAME_MS) {
          lastTs = ts;
          const buf = waveRef.current[roomId];
          const data: number[] = buf ? ((buf as unknown as Record<string, number[]>)[laneKey] ?? []) : [];
          const scale = scaleRef.current ?? FALLBACK_SCALE;
          const gain = gainRef.current[laneKey] ?? 1;
          const tw = timeWindowRef.current;
          const sr = SAMPLE_RATES[laneKey] ?? 500;
          drawLane(canvas, data, color, label, scale, gain, tw * sr, sr, overlayRef.current[laneKey]);
        }
      } catch { /* never break the rAF loop */ }
      raf = requestAnimationFrame(frame);
    };
    raf = requestAnimationFrame(frame);
    return () => { cancelAnimationFrame(raf); ro.disconnect(); };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []); // montage uniquement — tout par ref

  return (
    <canvas ref={canvasRef}
      style={{ display: "block", borderRadius: 2, background: "#080c0a",
               width: "100%", height: height }} />
  );
}

// ─── WaveformCanvas : composant public ───────────────────────
export interface WaveformCanvasProps {
  /** Ref vers les buffers wave (aucun re-render React) */
  waveRef: WaveRef;
  roomId: string;
  /** True quand le premier wave_chunk est arrivé (depuis rooms state) */
  hasWaveData: boolean;
  compact?: boolean;
  scopeBrand?: "drager" | "ge" | "philips";
  ventBrand?: "drager" | "ge";
  /** Valeurs numériques actuelles pour overlay sur les voies */
  vitals?: { hr: number; spo2: number; pas: number; pad: number; etco2: number };
  ventCurrent?: { ppeak?: number };
  bis?: number;
}

type GainMap = Record<string, number>;

export function WaveformCanvas({
  waveRef, roomId, hasWaveData, compact,
  scopeBrand, ventBrand, vitals, ventCurrent, bis,
}: WaveformCanvasProps) {
  const scales = getScaleMap(scopeBrand, ventBrand);

  // Gain par voie (ref pour le rAF + state pour le rendu boutons)
  const GAIN_STEPS = [0.25, 0.5, 1, 2, 4];
  const gainRef = useRef<GainMap>({ ecg: 1, pleth: 1, art: 1, co2: 1, awp: 1, eeg: 1 });
  const [gainState, setGainState] = useState<GainMap>({ ecg: 1, pleth: 1, art: 1, co2: 1, awp: 1, eeg: 1 });

  // Fenêtre temporelle (ref pour rAF + state pour boutons)
  const timeWindowRef = useRef(8); // secondes
  const [timeWindow, setTimeWindow] = useState(8);

  // Valeurs overlay (mis à jour sans re-render)
  const overlayRef = useRef<Record<string, string>>({});

  useLayoutEffect(() => {
    if (vitals) {
      overlayRef.current = {
        ecg:  String(Math.round(vitals.hr)),
        pleth: `${Math.round(vitals.spo2)}%`,
        art:  `${Math.round(vitals.pas)}/${Math.round(vitals.pad)}`,
        co2:  vitals.etco2.toFixed(1),
        awp:  ventCurrent?.ppeak != null ? String(Math.round(ventCurrent.ppeak)) : "",
        eeg:  bis != null ? String(Math.round(bis)) : "",
      };
    }
  });

  function adjustGain(key: string, up: boolean) {
    const cur = gainRef.current[key] ?? 1;
    const idx = GAIN_STEPS.indexOf(cur);
    const base = idx === -1 ? 2 : idx;
    const nIdx = Math.max(0, Math.min(GAIN_STEPS.length - 1, up ? base + 1 : base - 1));
    const ng = GAIN_STEPS[nIdx] ?? 1;
    gainRef.current[key] = ng;
    setGainState(g => ({ ...g, [key]: ng }));
  }
  function setTW(s: number) { timeWindowRef.current = s; setTimeWindow(s); }

  // Refs stables pour chaque voie — MutableRefObject<LaneScale> simulé par objet simple
  const scalerefs = useRef<Record<string, { current: LaneScale }>>({});
  LANES.forEach(({ key }) => {
    const lk = key as string;
    const sc = scales[lk] ?? FALLBACK_SCALE;
    if (!scalerefs.current[lk]) {
      scalerefs.current[lk] = { current: sc };
    } else {
      scalerefs.current[lk]!.current = sc;
    }
  });

  if (!hasWaveData) return (
    <div className={compact ? "waveforms-placeholder-compact" : "waveforms-placeholder"}>
      <span>– Waveforms –</span>
      <span style={{ fontSize: 9, opacity: .5 }}>Lancer un replay VitalDB</span>
    </div>
  );

  const laneH = compact ? 38 : 70;
  void laneH; // utilisé par les WaveLane indirectement via height prop

  return (
    <div className={compact ? "waveforms-compact" : "waveforms-section"}>
      {/* Barre de contrôles — masquée en compact */}
      {!compact && (
        <div className="wf-controls">
          <div className="wf-tw">
            {[4, 8].map(s => (
              <button key={s} className={`wf-tw-btn${timeWindow === s ? " wf-tw-btn--on" : ""}`}
                onClick={() => setTW(s)}>{s}s</button>
            ))}
          </div>
          <span className="wf-badge">HF</span>
        </div>
      )}

      {/* Voies */}
      <div className="waveforms-lanes">
        {LANES.map(({ key, label, color, height }) => {
          const lk = key as string;
          const g = gainState[lk] ?? 1;
          return (
            <div key={lk} className="wave-lane-row">
              {compact && (
                <div className="wf-compact-label" style={{ color, borderLeftColor: color }}>
                  {label}
                </div>
              )}
              <WaveLane
                waveRef={waveRef} roomId={roomId} laneKey={lk}
                scaleRef={scalerefs.current[lk] as React.RefObject<LaneScale>}
                gainRef={gainRef} timeWindowRef={timeWindowRef}
                overlayRef={overlayRef}
                color={color} label={compact ? "" : label}
                height={compact ? laneH : height}
              />
              {/* Contrôle gain — masqué en compact */}
              {!compact && (
                <div className="wf-gain-ctrl">
                  <span className="wf-gain-lbl" style={{ color }}>{label}</span>
                  <button className="wf-gain-btn" onClick={() => adjustGain(lk, true)} title="Gain +">+</button>
                  <span className="wf-gain-val">{g !== 1 ? (g > 1 ? `×${g}` : `÷${Math.round(1/g)}`) : "×1"}</span>
                  <button className="wf-gain-btn" onClick={() => adjustGain(lk, false)} title="Gain −">−</button>
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
