// ═══════════════════════════════════════════════════════════════
// CHARLES — Hook WebSocket
// Connexion persistante au backend, auto-reconnect
// ═══════════════════════════════════════════════════════════════

import { useEffect, useRef, useCallback, useState } from "react";
import type { WSUpdate, RoomState, VitalsFrame, LLMAnalysis } from "../types";
import { getStoredToken } from "./useAuth";

const MAX_HISTORY = 120; // 10 min @ 5s interval
const RECONNECT_DELAY = 3000;

export function useCharlesWS(url: string) {
  const [rooms, setRooms] = useState<Record<string, RoomState>>({});
  const [connected, setConnected] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimer = useRef<ReturnType<typeof setTimeout>>();

  const sendCommand = useCallback((cmd: Record<string, unknown>) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(cmd));
    }
  }, []);

  const acknowledgeAlert = useCallback((alertId: number) => {
    sendCommand({ action: "acknowledge_alert", alert_id: alertId, by: "IADE" });
  }, [sendCommand]);

  const requestAnalysis = useCallback((roomId: string) => {
    sendCommand({ action: "request_analysis", room_id: roomId });
  }, [sendCommand]);

  const connect = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) return;

    const token = getStoredToken();
    if (!token) {
      setConnected(false);
      return;
    }

    const separator = url.includes("?") ? "&" : "?";
    const ws = new WebSocket(`${url}${separator}token=${encodeURIComponent(token)}`);
    wsRef.current = ws;

    ws.onopen = () => {
      setConnected(true);
    };

    ws.onclose = () => {
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

      if (data.type === "init" && "rooms" in data) {
        const initRooms: Record<string, RoomState> = {};
        const raw = data as WSUpdate & { rooms?: Record<string, RoomState> };
        const roomsData = raw.rooms ?? {};
        for (const [rid, rdata] of Object.entries(roomsData)) {
          initRooms[rid] = { ...rdata, history: rdata.vitals ? [rdata.vitals] : [] };
        }
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
          return { ...prev, [data.room_id]: { ...existing, llm_analysis: analysis } };
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
              ventilator: data.ventilator,
              bis: data.bis,
              aivoc_hypnotic: data.aivoc_hypnotic,
              aivoc_opioid: data.aivoc_opioid,
              alerts: data.alerts,
              llm_analysis: data.llm_analysis ?? existing?.llm_analysis,
              timestamp: data.timestamp,
              history,
              // ── Phase ──
              phase: data.phase,
              phase_label: data.phase_label,
              macro_phase: data.macro_phase,
              elapsed_s: data.elapsed_s,
              elapsed_fmt: data.elapsed_fmt,
              patient_info: data.patient_info ?? existing?.patient_info,
            },
          };
        });
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

  return { rooms, connected, acknowledgeAlert, requestAnalysis };
}
