import type { RoomState } from "../types";
import { useUXConfig } from "../context/UXConfigContext";
import type { WaveRef } from "../hooks/useCharlesWS";
import { ScopeDrager, ScopeGeneric } from "./room-monitor/Scopes";
import { VentilatorDrager, VentilatorGE } from "./room-monitor/Ventilators";
import { BISMedtronic, BISEntropy, IABlock, TOFBlock } from "./room-monitor/AnesthesiaBlocks";
import { PumpBraun, PumpFresenius } from "./room-monitor/Pumps";
import { AlertStrips, PatientBar } from "./room-monitor/Shared";

interface RoomMonitorProps {
  roomId: string;
  data: RoomState;
  waveRef: WaveRef;
  onAcknowledgeAlert?: (alertId: number) => void;
  onRequestAnalysis?: () => void;
}

export function RoomMonitor({ roomId, data, waveRef, onAcknowledgeAlert, onRequestAnalysis }: RoomMonitorProps) {
  const { vitals, ventilator, bis, aivoc_hypnotic, aivoc_opioid, alerts, llm_analysis, llm_status, llm_error } = data;
  const { config } = useUXConfig();
  const hasWaveData = data.hasWaveData ?? false;

  const scope = config.scope === "drager"
    ? (
        <ScopeDrager
          v={vitals}
          waveRef={waveRef}
          roomId={roomId}
          hasWaveData={hasWaveData}
          timestamp={data.timestamp}
          alerts={alerts}
          ventBrand={config.vent}
          vent={ventilator ?? undefined}
          bis={bis?.bis}
        />
      )
    : (
        <ScopeGeneric
          v={vitals}
          waveRef={waveRef}
          roomId={roomId}
          hasWaveData={hasWaveData}
          timestamp={data.timestamp}
          alerts={alerts}
          theme={config.scope}
          ventBrand={config.vent}
          vent={ventilator ?? undefined}
          bis={bis?.bis}
        />
      );

  const vent = config.vent === "drager"
    ? <VentilatorDrager vent={ventilator} />
    : <VentilatorGE vent={ventilator} />;

  const bisBlock = config.bis === "medtronic"
    ? <BISMedtronic bis={bis} />
    : <BISEntropy bis={bis} />;

  const pump = config.pump === "braun"
    ? <PumpBraun hyp={aivoc_hypnotic} opi={aivoc_opioid} />
    : <PumpFresenius hyp={aivoc_hypnotic} opi={aivoc_opioid} />;

  return (
    <div className="rm-root" data-testid="room-monitor">
      <PatientBar data={data} />
      <AlertStrips alerts={alerts} onAck={onAcknowledgeAlert} />

      <div className="rm-main">
        <div className="rm-col-left">
          <div className="rm-scope-area">{scope}</div>
          <div className="rm-vent-area">{vent}</div>
        </div>

        <div className="rm-col-mid">
          <div className="rm-bis-area">{bisBlock}</div>
          <div className="rm-tof-area"><TOFBlock /></div>
          <div className="rm-ia-area">
            <IABlock analysis={llm_analysis} status={llm_status} error={llm_error} onRequest={onRequestAnalysis} />
          </div>
        </div>

        <div className="rm-col-right">{pump}</div>
      </div>
    </div>
  );
}
