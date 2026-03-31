// ═══════════════════════════════════════════════════════════════
// CHARLES — Hook WebSocket
// Connexion persistante au backend, auto-reconnect
// ═══════════════════════════════════════════════════════════════

import { useEffect, useRef, useCallback, useState } from "react";
import type { WSUpdate, RoomState, VitalsFrame, LLMAnalysis, WaveformChunk, WaveBuffers, TransportMetrics } from "../types";
import { getStoredToken } from "./useAuth";

const MAX_HISTORY = 120; // 10 min @ 5s interval
const RECONNECT_DELAY = 3000;
// Buffers waveforms glissants : 8 secondes max par signal
const MAX_WAVE_500HZ = 4000;   // 8s @ 500Hz
const MAX_WAVE_25HZ  = 200;    // 8s @ 25Hz
const MAX_WAVE_128HZ = 1024;   // 8s @ 128Hz

export type WaveRef = React.MutableRefObject<Record<string, WaveBuffers>>;

function appendBuf(prev: number[], incoming: number[] | undefined | null, max: number): number[] {
  if (!incoming || incoming.length === 0) return prev;
  const combined = [...prev, ...incoming];
  return combined.length > max ? combined.slice(combined.length - max) : combined;
}

export function useCharlesWS(url: string) {
  const [rooms, setRooms] = useState<Record<string, RoomState>>({});
  const [connected, setConnected] = useState(false);
  const [transportMetrics, setTransportMetrics] = useState<TransportMetrics>({
    reconnects: 0,
    messagesReceived: 0,
    waveChunksReceived: 0,
    droppedWaveChunks: 0,
    analysisRequests: 0,
    analysisErrors: 0,
    approxLagMs: null,
    roomsWithWaveData: 0,
    connectedSince: null,
    lastMessageAt: null,
  });
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimer = useRef<ReturnType<typeof setTimeout>>();
  const transportRef = useRef<TransportMetrics>({
    reconnects: 0,
    messagesReceived: 0,
    waveChunksReceived: 0,
    droppedWaveChunks: 0,
    analysisRequests: 0,
    analysisErrors: 0,
    approxLagMs: null,
    roomsWithWaveData: 0,
    connectedSince: null,
    lastMessageAt: null,
  });
  const lastWaveTRef = useRef<Record<string, number>>({});

  // ────────────────────────────────────────────────────────
  // waveRef : les wave_chunks sont écrits ici SANS setRooms
  // → aucun re-render React sur les composants Ventilateur/Pompe/BIS
  // Le canvas rAF lit directement waveRef.current[roomId]
  // ────────────────────────────────────────────────────────
  const waveRef = useRef<Record<string, WaveBuffers>>({});
  const waveSeenRef = useRef<Set<string>>(new Set()); // rooms déjà signalées comme "hasWaveData"

  const sendCommand = useCallback((cmd: Record<string, unknown>) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(cmd));
    }
  }, []);

  const acknowledgeAlert = useCallback((alertId: number) => {
    sendCommand({ action: "acknowledge_alert", alert_id: alertId, by: "IADE" });
  }, [sendCommand]);

  const requestAnalysis = useCallback((roomId: string) => {
    transportRef.current.analysisRequests += 1;
    sendCommand({ action: "request_analysis", room_id: roomId });
  }, [sendCommand]);

  const connect = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) return;

    const token = getStoredToken();
    if (!token) {
      setConnected(false);
      return;
    }

    const ws = new WebSocket(url);
    wsRef.current = ws;

    ws.onopen = () => {
      // Auth via premier message — le token ne transite pas dans l'URL (pas dans les logs serveur)
      ws.send(JSON.stringify({ type: "auth", token }));
      transportRef.current.connectedSince = new Date().toISOString();
      setConnected(true);
    };

    ws.onclose = () => {
      transportRef.current.reconnects += 1;
      transportRef.current.connectedSince = null;
      setConnected(false);
      reconnectTimer.current = setTimeout(connect, RECONNECT_DELAY);
    };

    ws.onerror = () => {
      ws.close();
    };

    ws.onmessage = (event: MessageEvent) => {
      let data: WSUpdate;
      try {
        data = JSON.parse(event.data as string) as WSUpdate;
      } catch {
        return;
      }
      transportRef.current.messagesReceived += 1;
      transportRef.current.lastMessageAt = new Date().toISOString();

      if ("timestamp" in data && data.timestamp) {
        const lagMs = Date.now() - new Date(data.timestamp).getTime();
        transportRef.current.approxLagMs = Number.isFinite(lagMs) ? Math.max(0, lagMs) : transportRef.current.approxLagMs;
      }

      if (data.type === "init" && "rooms" in data) {
        const initRooms: Record<string, RoomState> = {};
        const raw = data as WSUpdate & { rooms?: Record<string, RoomState> };
        const roomsData = raw.rooms ?? {};
        for (const [rid, rdata] of Object.entries(roomsData)) {
          initRooms[rid] = { ...rdata, history: rdata.vitals ? [rdata.vitals] : [] };
          if (rdata.hasWaveData) {
            waveSeenRef.current.add(rid);
          }
        }
        transportRef.current.roomsWithWaveData = waveSeenRef.current.size;
        setRooms(initRooms);
        return;
      }

      if (data.type === "llm_analysis" && data.room_id) {
        const raw = data as WSUpdate & { analysis?: LLMAnalysis };
        const analysis = raw.analysis;
        if (!analysis) return;
        setRooms((prev) => {
          const existing = prev[data.room_id];
          if (!existing) return prev;
          return {
            ...prev,
            [data.room_id]: {
              ...existing,
              llm_analysis: analysis,
              llm_status: "completed",
              llm_error: undefined,
            },
          };
        });
        return;
      }

      if (data.type === "llm_analysis_status" && data.room_id) {
        setRooms((prev) => {
          const existing = prev[data.room_id];
          if (!existing) return prev;
          return {
            ...prev,
            [data.room_id]: {
              ...existing,
              llm_status: data.status,
              llm_error: data.status === "error" ? data.detail : undefined,
            },
          };
        });
        return;
      }

      if (data.type === "llm_analysis_error" && data.room_id) {
        transportRef.current.analysisErrors += 1;
        setRooms((prev) => {
          const existing = prev[data.room_id];
          if (!existing) return prev;
          return {
            ...prev,
            [data.room_id]: {
              ...existing,
              llm_status: "error",
              llm_error: data.detail ?? "Erreur d'analyse",
            },
          };
        });
        return;
      }

      if (data.type === "update" && data.room_id) {
        setRooms((prev) => {
          const existing = prev[data.room_id];
          const newVitals: VitalsFrame = data.vitals;
          const history = existing?.history
            ? [...existing.history, newVitals].slice(-MAX_HISTORY)
            : [newVitals];

          return {
            ...prev,
            [data.room_id]: {
              vitals: newVitals,
              // ═ Fallback sur valeur existante si absente du message (prévient le clignotement) ═
              ventilator: data.ventilator ?? existing?.ventilator,
              bis: data.bis ?? existing?.bis,
              aivoc_hypnotic: data.aivoc_hypnotic ?? existing?.aivoc_hypnotic,
              aivoc_opioid: data.aivoc_opioid ?? existing?.aivoc_opioid,
              alerts: data.alerts,
              llm_analysis: data.llm_analysis ?? existing?.llm_analysis,
              llm_status: existing?.llm_status,
              llm_error: existing?.llm_error,
              timestamp: data.timestamp,
              history,
              // ── Phase ──
              phase: data.phase ?? existing?.phase,
              phase_label: data.phase_label ?? existing?.phase_label,
              macro_phase: data.macro_phase ?? existing?.macro_phase,
              elapsed_s: data.elapsed_s ?? existing?.elapsed_s,
              elapsed_fmt: data.elapsed_fmt ?? existing?.elapsed_fmt,
              patient_info: data.patient_info ?? existing?.patient_info,
              waveBuffers: existing?.waveBuffers,
              // ═ CRITIQUE : préserver hasWaveData — sinon réinitialisé à
              // chaque update et waveSeenRef ne le redonne plus jamais ═
              hasWaveData: existing?.hasWaveData,
            },
          };
        });
        return;
      }

      // ── Waveform chunk HF ──
      if ((data as unknown as WaveformChunk).type === "wave_chunk") {
        const chunk = data as unknown as WaveformChunk;
        if (!chunk.room_id) return;
        transportRef.current.waveChunksReceived += 1;

        const previousT = lastWaveTRef.current[chunk.room_id];
        if (typeof previousT === "number" && typeof chunk.t === "number") {
          const delta = chunk.t - previousT;
          if (delta > 0.251) {
            transportRef.current.droppedWaveChunks += Math.max(0, Math.round(delta / 0.25) - 1);
          }
        }
        lastWaveTRef.current[chunk.room_id] = chunk.t;

        // Écriture directe dans le ref — AUCUNE mise à jour React state
        const prev: WaveBuffers = waveRef.current[chunk.room_id] ?? {
          ecg: [], pleth: [], art: [], co2: [], awp: [], eeg: [], hasData: false,
        };
        waveRef.current[chunk.room_id] = {
          ecg:   appendBuf(prev.ecg,   chunk.ecg,   MAX_WAVE_500HZ),
          pleth: appendBuf(prev.pleth, chunk.pleth, MAX_WAVE_500HZ),
          art:   appendBuf(prev.art,   chunk.art,   MAX_WAVE_500HZ),
          co2:   appendBuf(prev.co2,   chunk.co2,   MAX_WAVE_25HZ),
          awp:   appendBuf(prev.awp,   chunk.awp,   MAX_WAVE_25HZ),
          eeg:   appendBuf(prev.eeg,   chunk.eeg,   MAX_WAVE_128HZ),
          hasData: true,
        };

        // Premier chunk pour cette room : un seul setRooms pour signaler hasWaveData
        if (!waveSeenRef.current.has(chunk.room_id)) {
          waveSeenRef.current.add(chunk.room_id);
          transportRef.current.roomsWithWaveData = waveSeenRef.current.size;
          setRooms(prev => {
            const existing = prev[chunk.room_id];
            if (!existing) return prev;
            return { ...prev, [chunk.room_id]: { ...existing, hasWaveData: true } };
          });
        }
      }
    };
  }, [url]);

  useEffect(() => {
    connect();
    return () => {
      clearTimeout(reconnectTimer.current);
      wsRef.current?.close();
    };
  }, [connect]);

  useEffect(() => {
    const timer = setInterval(() => {
      setTransportMetrics({ ...transportRef.current });
    }, 1000);
    return () => clearInterval(timer);
  }, []);

  return { rooms, connected, waveRef, acknowledgeAlert, requestAnalysis, transportMetrics };
}
