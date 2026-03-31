// ═══════════════════════════════════════════════════════════════
// CHARLES — Types partagés frontend
// Correspondent aux Pydantic models du backend
// ═══════════════════════════════════════════════════════════════

export interface VitalsFrame {
  hr: number;
  spo2: number;
  pas: number;
  pad: number;
  pam: number;
  etco2: number;
  fr: number;
  temp: number;
}

export interface VentilatorFrame {
  mode: string;
  vt: number;
  vt_kg?: number;
  mv: number;
  ppeak: number;
  pplat?: number;
  peep: number;
  fio2: number;
  ratio_ie?: string;
}

export interface BISFrame {
  bis: number;
  sqi: number;
  emg: number;
  sr: number;
}

export interface AIVOCFrame {
  drug: string;
  model: string;
  target_type: string;
  target: number;
  predicted_plasma: number;
  predicted_effect: number;
  infusion_rate: number;
}

export interface Alert {
  rule_id: string;
  level: "info" | "warning" | "critical";
  title: string;
  detail: string;
  parameters: Record<string, unknown>;
  timestamp: string;
  id?: number;       // DB id for acknowledge
  acknowledged?: boolean;
}

export interface LLMAnalysis {
  situation: string;
  risks: string[];
  recommendations: string[];
  confidence: number;
  call_mar: boolean;
  call_mar_reason?: string;
  model: string;
  latency_ms: number;
  prompt_id?: string;
  prompt_version?: string;
  rag_enabled?: boolean;
  rag_sources?: string[];
}

export interface TransportMetrics {
  reconnects: number;
  messagesReceived: number;
  waveChunksReceived: number;
  droppedWaveChunks: number;
  analysisRequests: number;
  analysisErrors: number;
  approxLagMs: number | null;
  roomsWithWaveData: number;
  connectedSince?: string | null;
  lastMessageAt?: string | null;
}

export interface WSUpdate {
  type: "update" | "init" | "llm_analysis" | "llm_analysis_status" | "llm_analysis_error";
  room_id: string;
  vitals: VitalsFrame;
  ventilator?: VentilatorFrame;
  bis?: BISFrame;
  aivoc_hypnotic?: AIVOCFrame;
  aivoc_opioid?: AIVOCFrame;
  alerts: Alert[];
  llm_analysis?: LLMAnalysis;
  status?: "queued" | "running" | "completed" | "error";
  detail?: string;
  trigger_type?: string;
  job_id?: string;
  timestamp: string;
  // ── Phase anesthésique ──
  phase?: string;
  phase_label?: string;
  macro_phase?: string;
  elapsed_s?: number;
  elapsed_fmt?: string;
  patient_info?: PatientInfo;
}

export interface PatientInfo {
  age?: number;
  sex?: string;
  weight?: number;
  height?: number;
  asa?: number;
  department?: string;
  optype?: string;
  opname?: string;
  ane_type?: string;
  antecedents?: string;
  allergies?: string;
  traitement?: string;
  jeune?: string;
  mallampati?: number;
  imc?: number;
  // VitalDB enrichi
  emop?: boolean;
  dx?: string;
  approach?: string;
  position?: string;
  preop_htn?: boolean;
  preop_dm?: boolean;
  preop_ecg?: string;
  preop_pft?: string;
  cormack?: string;
  airway?: string;
  tubesize?: number;
  iv1?: string;
  iv2?: string;
  aline1?: string;
  cline1?: string;
  bilan_preop?: Record<string, number>;
  gds_preop?: Record<string, number>;
  perop?: Record<string, number>;
  drogues?: Record<string, number>;
  icu_days?: number;
  death_inhosp?: boolean;
}

export interface RoomState {
  vitals: VitalsFrame;
  ventilator?: VentilatorFrame;
  bis?: BISFrame;
  aivoc_hypnotic?: AIVOCFrame;
  aivoc_opioid?: AIVOCFrame;
  alerts: Alert[];
  llm_analysis?: LLMAnalysis;
  llm_status?: "queued" | "running" | "completed" | "error";
  llm_error?: string;
  llm_job_id?: string;
  timestamp: string;
  history: VitalsFrame[];
  // ── Phase anesthésique ──
  phase?: string;
  phase_label?: string;
  macro_phase?: string;
  elapsed_s?: number;
  elapsed_fmt?: string;
  patient_info?: PatientInfo;
  // ── Waveforms HF ──
  waveBuffers?: WaveBuffers;
  hasWaveData?: boolean;  // positionné une seule fois au 1er wave_chunk
}

// ── Waveforms haute fréquence ──────────────────────────────────
export interface WaveformChunk {
  type: "wave_chunk";
  room_id: string;
  t: number;
  ecg?: number[];    // 500 Hz
  pleth?: number[];  // 500 Hz
  art?: number[];    // 500 Hz
  co2?: number[];    // 25 Hz
  awp?: number[];    // 25 Hz
  eeg?: number[];    // 128 Hz
}

/** Buffers glissants de waveforms par signal (5 secondes max). */
export interface WaveBuffers {
  ecg: number[];    // max 2500 pts (5s @ 500Hz)
  pleth: number[];
  art: number[];
  co2: number[];    // max 125 pts (5s @ 25Hz)
  awp: number[];
  eeg: number[];    // max 640 pts (5s @ 128Hz)
  hasData: boolean;
}
