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
}

export interface WSUpdate {
  type: "update" | "init" | "llm_analysis";
  room_id: string;
  vitals: VitalsFrame;
  ventilator?: VentilatorFrame;
  bis?: BISFrame;
  aivoc_hypnotic?: AIVOCFrame;
  aivoc_opioid?: AIVOCFrame;
  alerts: Alert[];
  llm_analysis?: LLMAnalysis;
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
  timestamp: string;
  history: VitalsFrame[];
  // ── Phase anesthésique ──
  phase?: string;
  phase_label?: string;
  macro_phase?: string;
  elapsed_s?: number;
  elapsed_fmt?: string;
  patient_info?: PatientInfo;
}
