// ═══════════════════════════════════════════════════════════════
// CHARLES — Configuration UX matériel (admin seulement)
// Persistance localStorage, consommable par useUXConfig()
// Choices : scope(3), vent(2), bis(2), pump(2)
// ═══════════════════════════════════════════════════════════════

import { createContext, useContext, useState, type ReactNode } from "react";

// ── Types ────────────────────────────────────────────────────
export type ScopeBrand = "drager" | "ge" | "philips";
export type VentBrand  = "drager" | "ge";
export type BisBrand   = "medtronic" | "ge";
export type PumpBrand  = "braun" | "fresenius";

export interface UXConfig {
  scope : ScopeBrand;
  vent  : VentBrand;
  bis   : BisBrand;
  pump  : PumpBrand;
}

// ── Catalogue affiché dans l'admin ───────────────────────────
export const UX_CATALOG = {
  scope: [
    { value: "drager"  as ScopeBrand, label: "Dräger Infinity C500",  tag: "Dräger" },
    { value: "ge"      as ScopeBrand, label: "GE B40 Patient Monitor", tag: "GE"     },
    { value: "philips" as ScopeBrand, label: "Philips IntelliVue MX800", tag: "Philips" },
  ],
  vent: [
    { value: "drager" as VentBrand, label: "Dräger Perseus A500",  tag: "Dräger" },
    { value: "ge"     as VentBrand, label: "GE Aisys CS²",         tag: "GE"     },
  ],
  bis: [
    { value: "medtronic" as BisBrand, label: "Medtronic BIS Vista", tag: "Medtronic" },
    { value: "ge"        as BisBrand, label: "GE E-Entropy Module", tag: "GE"        },
  ],
  pump: [
    { value: "braun"     as PumpBrand, label: "B.Braun Space♠ TCI",    tag: "B.Braun"   },
    { value: "fresenius" as PumpBrand, label: "Fresenius Agilia SP TCI", tag: "Fresenius" },
  ],
} as const;

// ── Valeur par défaut ─────────────────────────────────────────
const DEFAULT: UXConfig = { scope: "drager", vent: "drager", bis: "medtronic", pump: "braun" };
const LS_KEY = "charles_ux_cfg";

function loadFromStorage(): UXConfig {
  try {
    const raw = localStorage.getItem(LS_KEY);
    if (raw) return { ...DEFAULT, ...(JSON.parse(raw) as Partial<UXConfig>) };
  } catch { /* ignore */ }
  return DEFAULT;
}

// ── Context ───────────────────────────────────────────────────
interface UXConfigContextType {
  config : UXConfig;
  set    : (patch: Partial<UXConfig>) => void;
}

const UXCtx = createContext<UXConfigContextType>({ config: DEFAULT, set: () => {} });

export function UXConfigProvider({ children }: { children: ReactNode }) {
  const [config, setConfig] = useState<UXConfig>(loadFromStorage);

  function set(patch: Partial<UXConfig>) {
    setConfig((prev) => {
      const next = { ...prev, ...patch };
      try { localStorage.setItem(LS_KEY, JSON.stringify(next)); } catch { /* ignore */ }
      return next;
    });
  }

  return <UXCtx.Provider value={{ config, set }}>{children}</UXCtx.Provider>;
}

export function useUXConfig(): UXConfigContextType {
  return useContext(UXCtx);
}
