// ═══════════════════════════════════════════════════════════════
// CHARLES — ScenarioPanel : sélection de scénario / profil patient
// Interface complète : 11 catégories, 74 colonnes, 4 types de filtres
// Types : single, toggle, range (min/max), search (texte libre)
// ═══════════════════════════════════════════════════════════════

import { useState, useEffect, useCallback } from "react";
import { getStoredToken } from "../hooks/useAuth";

const API_URL = "/api";

function authHeaders(): Record<string, string> {
  const token = getStoredToken();
  return token ? { Authorization: `Bearer ${token}` } : {};
}

interface CatalogOption {
  value: string;
  label: string;
  count: number | null;
}

interface SubCategory {
  label: string;
  type: "single" | "toggle" | "range" | "search";
  options?: CatalogOption[];
  count?: number;
  // range
  min?: number;
  max?: number;
  mean?: number;
  q25?: number;
  q75?: number;
  unit?: string;
  filter_key?: string;
  available?: number;
  // search
  top_values?: CatalogOption[];
  total_unique?: number;
}

interface Category {
  label: string;
  icon: string;
  subcategories: Record<string, SubCategory>;
}

interface Catalog {
  loaded: boolean;
  total_cases: number;
  categories: Record<string, Category>;
}

interface CaseResult {
  caseid: number;
  age: number | null;
  sex: string | null;
  asa: number | null;
  asa_label: string;
  bmi: number | null;
  height: number | null;
  weight: number | null;
  department: string | null;
  optype: string | null;
  opname: string | null;
  dx: string | null;
  approach: string | null;
  position: string | null;
  ane_type: string | null;
  emop: boolean;
  duration_min: number | null;
  preop_htn: boolean;
  preop_dm: boolean;
  ecg_anormal: boolean;
  preop_ecg: string | null;
  pft_anormal: boolean;
  preop_pft: string | null;
  cormack: string | null;
  airway: string | null;
  has_aline: boolean;
  has_cline: boolean;
  has_transfusion: boolean;
  death_inhosp: boolean;
  icu_days: number;
  has_waveform: boolean;
}

interface ScenarioPanelProps {
  onClose: () => void;
  hideClose?: boolean;
  /** "all" = tous les cas  |  "waveforms" = cas avec waveforms HF uniquement */
  mode?: "all" | "waveforms";
}

export function ScenarioPanel({ onClose, hideClose = false, mode = "all" }: ScenarioPanelProps) {
  const isWaveMode = mode === "waveforms";
  const [catalog, setCatalog] = useState<Catalog | null>(null);
  const [loading, setLoading] = useState(true);
  const [expandedCat, setExpandedCat] = useState<string | null>(null);
  const [filters, setFilters] = useState<Record<string, unknown>>({});
  const [results, setResults] = useState<{ total_matches: number; cases: CaseResult[] } | null>(null);
  const [searching, setSearching] = useState(false);
  const [launching, setLaunching] = useState<number | string | null>(null);
  const [targetRoom, setTargetRoom] = useState("salle_1");
  const [speed, setSpeed] = useState(2.0);

  // Charger le catalogue (endpoint différent selon le mode)
  useEffect(() => {
    const endpoint = isWaveMode ? `${API_URL}/scenarios/catalog/waveforms` : `${API_URL}/scenarios/catalog`;
    fetch(endpoint, { headers: authHeaders() })
      .then((r) => r.json())
      .then((data) => {
        setCatalog(data);
        setLoading(false);
      })
      .catch(() => setLoading(false));
  }, [isWaveMode]);

  // En mode waveforms : charger automatiquement les 50 premiers cas
  useEffect(() => {
    if (isWaveMode && !loading) {
      void searchCases();
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isWaveMode, loading]);

  // Rechercher les cas correspondants
  const searchCases = useCallback(async () => {
    setSearching(true);
    try {
      // En mode waveforms, forcer le filtre has_waveform=true
      const payload = isWaveMode ? { ...filters, has_waveform: true } : filters;
      const resp = await fetch(`${API_URL}/scenarios/search`, {
        method: "POST",
        headers: { "Content-Type": "application/json", ...authHeaders() },
        body: JSON.stringify(payload),
      });
      const data = await resp.json();
      setResults(data);
    } catch {
      /* ignore */
    }
    setSearching(false);
  }, [filters, isWaveMode]);

  // Lancer un cas VitalDB
  const launchVitalDB = async (caseid: number) => {
    setLaunching(caseid);
    try {
      await fetch(`${API_URL}/simulator/control`, {
        method: "POST",
        headers: { "Content-Type": "application/json", ...authHeaders() },
        body: JSON.stringify({
          action: "start_vitaldb",
          room_id: targetRoom,
          caseid,
          speed,
          with_waveforms: isWaveMode,
        }),
      });
    } catch {
      /* ignore */
    }
    setTimeout(() => setLaunching(null), 1500);
  };

  const setFilter = (key: string, value: unknown) => {
    setFilters((prev) => {
      const next = { ...prev };
      if (value === null || value === undefined || value === "" || value === false) {
        delete next[key];
      } else {
        next[key] = value;
      }
      return next;
    });
    setResults(null);
  };

  const activeFilterCount = Object.keys(filters).length;

  if (loading) {
    return (
      <div className="scenario-panel">
        <div className="scenario-header">
          <h2>Chargement du catalogue...</h2>
          {!hideClose && <button className="scenario-close" onClick={onClose}>✕</button>}
        </div>
      </div>
    );
  }

  if (!catalog?.loaded) {
    return (
      <div className="scenario-panel">
        <div className="scenario-header">
          <h2>Catalogue non disponible</h2>
          {!hideClose && <button className="scenario-close" onClick={onClose}>✕</button>}
        </div>
        <p className="scenario-empty">clinical_metadata.csv non trouvé.</p>
      </div>
    );
  }

  return (
    <div className={`scenario-panel ${isWaveMode ? "scenario-panel--wave" : ""}`} data-testid="scenario-panel">
      {/* Header */}
      <div className={`scenario-header ${isWaveMode ? "scenario-header--wave" : ""}`}>
        <div className="scenario-header-copy">
          <span className="scenario-eyebrow">
            {isWaveMode ? "Replay waveform haute frequence" : "Catalogue VitalDB"}
          </span>
          <h2>
            {isWaveMode ? "📈 Scénarios Waveforms Réels" : "Sélection de Scénario"}
          </h2>
          <span className="scenario-count">
            {catalog.total_cases} cas VitalDB{isWaveMode ? " avec waveforms haute fréquence" : ""} disponibles
          </span>
          {isWaveMode && (
            <div className="wave-signals-info">
              {["ECG DII 500Hz", "SpO₂ Pleth 500Hz", "PA invasive 500Hz", "Capno CO₂ 25Hz", "Pression VA 25Hz", "EEG 128Hz"].map((sig) => (
                <span key={sig} className="wave-signal-tag">📡 {sig}</span>
              ))}
            </div>
          )}
        </div>
        {!hideClose && <button className="scenario-close" onClick={onClose}>✕</button>}
      </div>

      {/* Salle cible + vitesse */}
      <div className="scenario-controls">
        <div className="scenario-control-group">
          <label>Salle cible</label>
          <select data-testid="scenario-target-room" value={targetRoom} onChange={(e) => setTargetRoom(e.target.value)}>
            <option value="salle_1">Salle 1</option>
            <option value="salle_2">Salle 2</option>
            <option value="salle_3">Salle 3</option>
          </select>
        </div>
        <div className="scenario-control-group">
          <label>Vitesse replay</label>
          <select data-testid="scenario-speed" value={speed} onChange={(e) => setSpeed(parseFloat(e.target.value))}>
            <option value="1">×1 (temps réel)</option>
            <option value="2">×2</option>
            <option value="5">×5</option>
            <option value="10">×10</option>
          </select>
        </div>
      </div>

      {/* Catégories */}
      <div className="scenario-categories">
        {Object.entries(catalog.categories).map(([catKey, cat]) => (
          <div key={catKey} className="scenario-category">
            <button
              data-testid={`scenario-category-${catKey}`}
              className={`scenario-cat-header ${expandedCat === catKey ? "scenario-cat-header--open" : ""}`}
              onClick={() => setExpandedCat(expandedCat === catKey ? null : catKey)}
            >
              <span className="scenario-cat-icon">{cat.icon}</span>
              <span className="scenario-cat-label">{cat.label}</span>
              <span className="scenario-cat-arrow">{expandedCat === catKey ? "▼" : "▶"}</span>
            </button>

            {expandedCat === catKey && (
              <div className="scenario-subcategories">
                {Object.entries(cat.subcategories).map(([subKey, sub]) => (
                  <div key={subKey} className="scenario-subcategory">
                    <div className="scenario-sub-label">{sub.label}</div>

                    {/* Filtres par sous-catégorie */}
                      /* Toggle (checkbox) */
                      <label className="scenario-toggle">
                        <input
                          type="checkbox"
                          checked={!!filters[subKey]}
                          onChange={(e) => setFilter(subKey, e.target.checked)}
                        />
                        <span>
                          Oui ({sub.count} cas)
                        </span>
                      </label>
                    ) : sub.type === "range" ? (
                      /* Range (min / max inputs) */
                      <div className="scenario-range">
                        <span className="scenario-range-info">
                          {sub.available} cas — {sub.min} à {sub.max} {sub.unit}
                          {sub.mean !== undefined && ` (moy. ${sub.mean})`}
                        </span>
                        <div className="scenario-range-inputs">
                          <input
                            type="number"
                            className="scenario-range-input"
                            placeholder={`Min (${sub.min})`}
                            step="any"
                            value={filters[`${sub.filter_key}_min`] as string ?? ""}
                            onChange={(e) =>
                              setFilter(
                                `${sub.filter_key}_min`,
                                e.target.value !== "" ? parseFloat(e.target.value) : null,
                              )
                            }
                          />
                          <span className="scenario-range-sep">—</span>
                          <input
                            type="number"
                            className="scenario-range-input"
                            placeholder={`Max (${sub.max})`}
                            step="any"
                            value={filters[`${sub.filter_key}_max`] as string ?? ""}
                            onChange={(e) =>
                              setFilter(
                                `${sub.filter_key}_max`,
                                e.target.value !== "" ? parseFloat(e.target.value) : null,
                              )
                            }
                          />
                          <span className="scenario-range-unit">{sub.unit}</span>
                        </div>
                      </div>
                    ) : sub.type === "search" ? (
                      /* Search (text input + top values) */
                      <div className="scenario-search-field">
                        <input
                          type="text"
                          className="scenario-search-input"
                          placeholder={`Rechercher parmi ${sub.total_unique} valeurs…`}
                          value={(filters[subKey] as string) ?? ""}
                          onChange={(e) => setFilter(subKey, e.target.value || null)}
                        />
                        {sub.top_values && (
                          <div className="scenario-options scenario-options--wrap">
                            {sub.top_values.map((opt) => (
                              <button
                                key={opt.value}
                                className={`scenario-option scenario-option--small ${filters[subKey] === opt.value ? "scenario-option--active" : ""}`}
                                onClick={() =>
                                  setFilter(subKey, filters[subKey] === opt.value ? null : opt.value)
                                }
                              >
                                {opt.label}
                                {opt.count !== null && (
                                  <span className="scenario-opt-count">{opt.count}</span>
                                )}
                              </button>
                            ))}
                          </div>
                        )}
                      </div>
                    ) : sub.options ? (
                      /* Single select */
                      <div className="scenario-options">
                        <button
                          className={`scenario-option ${!filters[subKey] ? "scenario-option--active" : ""}`}
                          onClick={() => setFilter(subKey, null)}
                        >
                          Tous
                        </button>
                        {sub.options?.map((opt) => (
                          <button
                            key={opt.value}
                            className={`scenario-option ${filters[subKey] === opt.value ? "scenario-option--active" : ""}`}
                            onClick={() => setFilter(subKey, opt.value)}
                          >
                            {opt.label}
                            {opt.count !== null && (
                              <span className="scenario-opt-count">{opt.count}</span>
                            )}
                          </button>
                        ))}
                      </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        ))}
      </div>

      {/* Barre de recherche */}
      {activeFilterCount > 0 && (
        <div className="scenario-search-bar">
          <div className="scenario-filter-tags">
            {Object.entries(filters).map(([key, val]) => (
              <span key={key} className="scenario-filter-tag">
                {key}: {String(val)}
                <button onClick={() => setFilter(key, null)}>×</button>
              </span>
            ))}
          </div>
          <button
            className="scenario-search-btn"
            onClick={searchCases}
            disabled={searching}
          >
            {searching ? "Recherche..." : `Rechercher (${activeFilterCount} filtre${activeFilterCount > 1 ? "s" : ""})`}
          </button>
        </div>
      )}

      {/* Résultats */}
      {results && (
        <div className="scenario-results">
          <div className="scenario-results-header">
            {results.total_matches} cas trouvé{results.total_matches > 1 ? "s" : ""}
            {results.total_matches > 50 && " (50 premiers affichés)"}
          </div>
          <div className="scenario-results-list">
            {results.cases.map((c) => (
              <div key={c.caseid} className="scenario-case-card">
                <div className="scenario-case-info">
                  <div className="scenario-case-id">VitalDB #{c.caseid}</div>
                  <div className="scenario-case-details">
                    {c.sex === "M" ? "♂" : "♀"} {c.age}ans
                    {c.asa && ` · ASA ${c.asa}`}
                    {c.bmi && ` · IMC ${c.bmi}`}
                    {c.height && ` · ${c.height}cm`}
                    {c.weight && ` · ${c.weight}kg`}
                  </div>
                  <div className="scenario-case-surgery">
                    {c.department} — {c.optype}
                    {c.opname && ` (${c.opname})`}
                  </div>
                  {c.dx && (
                    <div className="scenario-case-dx">Dx: {c.dx}</div>
                  )}
                  <div className="scenario-case-tags">
                    <span className="tag tag--ane">{c.ane_type}</span>
                    {c.approach && <span className="tag tag--approach">{c.approach}</span>}
                    {c.position && c.position !== "Supine" && (
                      <span className="tag tag--position">{c.position}</span>
                    )}
                    {c.duration_min != null && (
                      <span className="tag tag--duration">{c.duration_min} min</span>
                    )}
                    {c.emop && <span className="tag tag--urgence">Urgence</span>}
                    {c.preop_htn && <span className="tag tag--hta">HTA</span>}
                    {c.preop_dm && <span className="tag tag--dm">Diabète</span>}
                    {c.ecg_anormal && (
                      <span className="tag tag--ecg">ECG↗ {c.preop_ecg}</span>
                    )}
                    {c.pft_anormal && (
                      <span className="tag tag--pft">EFR↗ {c.preop_pft}</span>
                    )}
                    {c.cormack && c.cormack !== "I" && (
                      <span className="tag tag--cormack">Cormack {c.cormack}</span>
                    )}
                    {c.has_aline && <span className="tag tag--access">Art.</span>}
                    {c.has_cline && <span className="tag tag--access">VVC</span>}
                    {c.has_transfusion && <span className="tag tag--transfusion">CGR</span>}
                    {c.death_inhosp && <span className="tag tag--death">Décès</span>}
                    {c.icu_days > 0 && (
                      <span className="tag tag--icu">Réa {c.icu_days}j</span>
                    )}
                    {c.has_waveform && (
                      <span className="tag tag--wave">📈 Waveforms HF</span>
                    )}
                  </div>
                </div>
                <button
                  data-testid={`launch-vitaldb-${c.caseid}`}
                  className={`scenario-launch-btn ${launching === c.caseid ? "scenario-launch-btn--active" : ""} ${isWaveMode ? "scenario-launch-btn--wave" : ""}`}
                  onClick={() => launchVitalDB(c.caseid)}
                  disabled={launching !== null}
                >
                  {launching === c.caseid
                    ? "⏳ Lancement..."
                    : isWaveMode
                      ? "📈 Lancer + Waves"
                      : "▶ Lancer"
                  }
                </button>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
