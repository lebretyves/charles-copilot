import { useEffect, useState } from "react";

import "../../styles/admin-alerting.css";

type Level = "info" | "warning" | "critical";

interface ThresholdConfig {
  label?: string;
  unit?: string;
  enabled?: boolean;
  info_low?: number;
  warning_low?: number;
  critical_low?: number;
  target_low?: number;
  target_high?: number;
  info_high?: number;
  warning_high?: number;
  critical_high?: number;
}

interface RuleCondition {
  field: string;
  op: string;
  value: number | string;
}

interface ComplicationRule {
  id: string;
  title: string;
  family: string;
  level: Level;
  enabled: boolean;
  logic: "all" | "any";
  detail: string;
  conditions: RuleCondition[];
}

interface TrendRule {
  id: string;
  title: string;
  level: Level;
  enabled: boolean;
  field: string;
  delta_op: "lt" | "gt";
  delta: number;
  window_points: number;
  detail: string;
  complication_id?: string;
}

interface ProfileOverride {
  label: string;
  enabled: boolean;
  overrides: Record<string, number>;
  source_keys?: string[];
  system?: string;
}

interface RoomProfile {
  populations: string[];
  terrains: string[];
  patient_info: Record<string, unknown>;
  updated_at?: string;
}

interface CatalogComplication {
  id: string;
  family: string;
  label: string;
  detector_status: string;
  linked_rule_id?: string | null;
}

export interface AlertingDashboardData {
  updated_at?: string | null;
  runtime_path?: string | null;
  loaded_from_disk?: string | null;
  hysteresis_seconds: number;
  thresholds: Record<string, ThresholdConfig>;
  bis_rules: Record<string, ThresholdConfig>;
  ppeak_rules: ThresholdConfig;
  complication_rules: ComplicationRule[];
  trend_rules: TrendRule[];
  population_overrides: Record<string, ProfileOverride>;
  terrain_overrides: Record<string, ProfileOverride>;
  room_profiles: Record<string, RoomProfile>;
  complication_catalog: CatalogComplication[];
  summary: Record<string, number>;
}

interface AlertingDashboardProps {
  data: AlertingDashboardData | null;
  loading: boolean;
  saving: boolean;
  error: string | null;
  onRefresh: () => void;
  onSave: (payload: AlertingDashboardData) => void;
  onReset: () => void;
}

function clone<T>(value: T): T {
  return JSON.parse(JSON.stringify(value)) as T;
}

function formatDate(value?: string | null): string {
  if (!value) {
    return "--";
  }
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? value : parsed.toLocaleString("fr-FR");
}

function setThresholdValue(
  draft: AlertingDashboardData,
  section: "thresholds" | "bis_rules",
  key: string,
  field: keyof ThresholdConfig,
  value: string,
) {
  const next = clone(draft);
  const target = next[section][key];
  if (!target) {
    return next;
  }
  (target as Record<string, number | string | boolean | undefined>)[field] = value === "" ? undefined : Number(value);
  return next;
}

function setProfileOverrideValue(
  draft: AlertingDashboardData,
  section: "population_overrides" | "terrain_overrides",
  profileId: string,
  overrideKey: string,
  value: string,
) {
  const next = clone(draft);
  const profile = next[section][profileId];
  if (!profile) {
    return next;
  }
  profile.overrides[overrideKey] = Number(value);
  return next;
}

function updateComplicationRule(
  draft: AlertingDashboardData,
  index: number,
  mutate: (rule: ComplicationRule) => void,
) {
  const next = clone(draft);
  const rule = next.complication_rules[index];
  if (!rule) {
    return next;
  }
  mutate(rule);
  return next;
}

function updateComplicationCondition(
  draft: AlertingDashboardData,
  index: number,
  conditionIndex: number,
  mutate: (condition: RuleCondition) => void,
) {
  const next = clone(draft);
  const rule = next.complication_rules[index];
  const condition = rule?.conditions[conditionIndex];
  if (!condition) {
    return next;
  }
  mutate(condition);
  return next;
}

function updateTrendRule(
  draft: AlertingDashboardData,
  index: number,
  mutate: (rule: TrendRule) => void,
) {
  const next = clone(draft);
  const rule = next.trend_rules[index];
  if (!rule) {
    return next;
  }
  mutate(rule);
  return next;
}

function updateProfileOverride(
  draft: AlertingDashboardData,
  section: "population_overrides" | "terrain_overrides",
  profileId: string,
  mutate: (profile: ProfileOverride) => void,
) {
  const next = clone(draft);
  const profile = next[section][profileId];
  if (!profile) {
    return next;
  }
  mutate(profile);
  return next;
}

export function AlertingDashboard({
  data,
  loading,
  saving,
  error,
  onRefresh,
  onSave,
  onReset,
}: AlertingDashboardProps) {
  const [draft, setDraft] = useState<AlertingDashboardData | null>(data);

  useEffect(() => {
    setDraft(data ? clone(data) : null);
  }, [data]);

  if (loading && !draft) {
    return <div className="learning-empty">Chargement du dashboard complications...</div>;
  }

  if (error && !draft) {
    return <div className="learning-empty learning-empty--error">{error}</div>;
  }

  if (!draft) {
    return null;
  }

  return (
    <div className="admin-system alerting-dashboard" data-testid="admin-alerting-dashboard">
      <div className="section-header">
        <div>
          <h2 className="section-title">Complications / Seuils</h2>
          <div className="learning-subtitle">
            Parametrage complet du moteur d&apos;alertes, par seuil, complication, tendance et profil patient.
          </div>
        </div>
        <div className="alerting-actions">
          <button className="refresh-btn" onClick={onRefresh}>Rafraichir</button>
          <button className="refresh-btn" onClick={onReset} disabled={saving}>Reset</button>
          <button className="action-btn" onClick={() => onSave(draft)} disabled={saving}>Sauvegarder</button>
        </div>
      </div>

      {error && <div className="learning-empty learning-empty--error">{error}</div>}

      <div className="learning-meta-bar">
        <span><strong>Runtime</strong> {draft.runtime_path ?? "--"}</span>
        <span><strong>Derniere maj</strong> {formatDate(draft.updated_at)}</span>
        <span><strong>Hysteresis</strong> {draft.hysteresis_seconds}s</span>
        <span><strong>KB couvertes</strong> {draft.summary.supported_complication_count} / {draft.summary.kb_complication_count}</span>
      </div>

      <div className="admin-cards learning-kpis">
        <div className="admin-card"><div className="admin-card-title">Seuils simples</div><div className="admin-card-body"><div className="stat-row"><span>Parametres</span><span className="stat-val">{Object.keys(draft.thresholds).length}</span></div></div></div>
        <div className="admin-card"><div className="admin-card-title">Regles complications</div><div className="admin-card-body"><div className="stat-row"><span>Configurables</span><span className="stat-val">{draft.complication_rules.length}</span></div></div></div>
        <div className="admin-card"><div className="admin-card-title">Regles tendance</div><div className="admin-card-body"><div className="stat-row"><span>Actives</span><span className="stat-val">{draft.trend_rules.filter((rule) => rule.enabled).length}</span></div></div></div>
        <div className="admin-card"><div className="admin-card-title">Profils detects</div><div className="admin-card-body"><div className="stat-row"><span>Salles profilees</span><span className="stat-val">{Object.keys(draft.room_profiles).length}</span></div></div></div>
      </div>

      <div className="learning-panel">
        <div className="learning-panel-head">
          <h3>Reglages generaux</h3>
          <span>moteur live</span>
        </div>
        <div className="alerting-inline-grid">
          <label className="alerting-field">
            <span>Hysteresis (s)</span>
            <input type="number" value={draft.hysteresis_seconds} onChange={(event) => setDraft({ ...draft, hysteresis_seconds: Number(event.target.value) })} />
          </label>
        </div>
      </div>

      <div className="learning-panel">
        <div className="learning-panel-head"><h3>Seuils simples</h3><span>vitaux, BIS et ventilation</span></div>
        <div className="learning-table-wrap">
          <table className="learning-table alerting-table">
            <thead>
              <tr>
                <th>Parametre</th>
                <th>Info bas</th>
                <th>Warning bas</th>
                <th>Critique bas</th>
                <th>Info haut</th>
                <th>Warning haut</th>
                <th>Critique haut</th>
              </tr>
            </thead>
            <tbody>
              {Object.entries(draft.thresholds).map(([key, threshold]) => (
                <tr key={key}>
                  <td><div className="learning-primary">{threshold.label ?? key}</div><div className="learning-secondary">{key} · {threshold.unit ?? ""}</div></td>
                  {(["info_low", "warning_low", "critical_low", "info_high", "warning_high", "critical_high"] as const).map((field) => (
                    <td key={field}><input className="alerting-input" type="number" value={threshold[field] ?? ""} onChange={(event) => setDraft(setThresholdValue(draft, "thresholds", key, field, event.target.value))} /></td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <div className="learning-grid learning-grid--details">
        {Object.entries(draft.bis_rules).map(([key, rule]) => (
          <div key={key} className="learning-panel">
            <div className="learning-panel-head"><h3>{rule.label ?? key}</h3><span>{rule.unit ?? ""}</span></div>
            <div className="alerting-inline-grid">
              <label className="alerting-field"><span>Active</span><input type="checkbox" checked={Boolean(rule.enabled)} onChange={(event) => setDraft({ ...draft, bis_rules: { ...draft.bis_rules, [key]: { ...rule, enabled: event.target.checked } } })} /></label>
              {(["target_low", "target_high", "warning_low", "critical_low", "warning_high", "critical_high"] as const).map((field) => (
                <label key={field} className="alerting-field"><span>{field}</span><input type="number" value={rule[field] ?? ""} onChange={(event) => setDraft(setThresholdValue(draft, "bis_rules", key, field, event.target.value))} /></label>
              ))}
            </div>
          </div>
        ))}

        <div className="learning-panel">
          <div className="learning-panel-head"><h3>Ppeak</h3><span>{draft.ppeak_rules.unit ?? ""}</span></div>
          <div className="alerting-inline-grid">
            <label className="alerting-field"><span>Active</span><input type="checkbox" checked={Boolean(draft.ppeak_rules.enabled)} onChange={(event) => setDraft({ ...draft, ppeak_rules: { ...draft.ppeak_rules, enabled: event.target.checked } })} /></label>
            <label className="alerting-field"><span>Warning haut</span><input type="number" value={draft.ppeak_rules.warning_high ?? ""} onChange={(event) => setDraft({ ...draft, ppeak_rules: { ...draft.ppeak_rules, warning_high: Number(event.target.value) } })} /></label>
            <label className="alerting-field"><span>Critique haut</span><input type="number" value={draft.ppeak_rules.critical_high ?? ""} onChange={(event) => setDraft({ ...draft, ppeak_rules: { ...draft.ppeak_rules, critical_high: Number(event.target.value) } })} /></label>
          </div>
        </div>
      </div>

      <div className="learning-panel">
        <div className="learning-panel-head"><h3>Regles complications</h3><span>{draft.complication_rules.length} cartes</span></div>
        <div className="alerting-rule-grid">
          {draft.complication_rules.map((rule, index) => (
            <div key={rule.id} className="alerting-rule-card">
              <div className="alerting-rule-head">
                <div>
                  <div className="learning-primary">{rule.title}</div>
                  <div className="learning-secondary">{rule.id} · {rule.family}</div>
                </div>
                <label className="learning-pill learning-pill--muted"><input type="checkbox" checked={rule.enabled} onChange={(event) => setDraft(updateComplicationRule(draft, index, (target) => { target.enabled = event.target.checked; }))} /> active</label>
              </div>
              <div className="alerting-inline-grid">
                <label className="alerting-field"><span>Niveau</span><select value={rule.level} onChange={(event) => setDraft(updateComplicationRule(draft, index, (target) => { target.level = event.target.value as Level; }))}><option value="info">info</option><option value="warning">warning</option><option value="critical">critical</option></select></label>
                <label className="alerting-field"><span>Logique</span><select value={rule.logic} onChange={(event) => setDraft(updateComplicationRule(draft, index, (target) => { target.logic = event.target.value as "all" | "any"; }))}><option value="all">all</option><option value="any">any</option></select></label>
              </div>
              <label className="alerting-field"><span>Detail</span><textarea value={rule.detail} onChange={(event) => setDraft(updateComplicationRule(draft, index, (target) => { target.detail = event.target.value; }))} /></label>
              <div className="alerting-condition-list">
                {rule.conditions.map((condition, conditionIndex) => (
                  <div key={`${rule.id}-${condition.field}-${conditionIndex}`} className="alerting-condition-row">
                    <input value={condition.field} onChange={(event) => setDraft(updateComplicationCondition(draft, index, conditionIndex, (target) => { target.field = event.target.value; }))} />
                    <select value={condition.op} onChange={(event) => setDraft(updateComplicationCondition(draft, index, conditionIndex, (target) => { target.op = event.target.value; }))}>
                      <option value="lt">{"<"}</option>
                      <option value="lte">{"<="}</option>
                      <option value="gt">{">"}</option>
                      <option value="gte">{">="}</option>
                      <option value="eq">=</option>
                    </select>
                    <input type="number" value={condition.value} onChange={(event) => setDraft(updateComplicationCondition(draft, index, conditionIndex, (target) => { target.value = Number(event.target.value); }))} />
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      </div>

      <div className="learning-panel">
        <div className="learning-panel-head"><h3>Regles tendance</h3><span>{draft.trend_rules.length} regles</span></div>
        <div className="learning-table-wrap">
          <table className="learning-table alerting-table">
            <thead>
              <tr><th>Regle</th><th>Active</th><th>Field</th><th>Delta op</th><th>Delta</th><th>Fenetre</th><th>Niveau</th></tr>
            </thead>
            <tbody>
              {draft.trend_rules.map((rule, index) => (
                <tr key={rule.id}>
                  <td><div className="learning-primary">{rule.title}</div><div className="learning-secondary">{rule.id}</div></td>
                  <td><input type="checkbox" checked={rule.enabled} onChange={(event) => setDraft(updateTrendRule(draft, index, (target) => { target.enabled = event.target.checked; }))} /></td>
                  <td><input className="alerting-input" value={rule.field} onChange={(event) => setDraft(updateTrendRule(draft, index, (target) => { target.field = event.target.value; }))} /></td>
                  <td><select value={rule.delta_op} onChange={(event) => setDraft(updateTrendRule(draft, index, (target) => { target.delta_op = event.target.value as "lt" | "gt"; }))}><option value="lt">lt</option><option value="gt">gt</option></select></td>
                  <td><input className="alerting-input" type="number" value={rule.delta} onChange={(event) => setDraft(updateTrendRule(draft, index, (target) => { target.delta = Number(event.target.value); }))} /></td>
                  <td><input className="alerting-input" type="number" value={rule.window_points} onChange={(event) => setDraft(updateTrendRule(draft, index, (target) => { target.window_points = Number(event.target.value); }))} /></td>
                  <td><select value={rule.level} onChange={(event) => setDraft(updateTrendRule(draft, index, (target) => { target.level = event.target.value as Level; }))}><option value="info">info</option><option value="warning">warning</option><option value="critical">critical</option></select></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <div className="learning-grid learning-grid--details">
        {(["population_overrides", "terrain_overrides"] as const).map((section) => (
          <div key={section} className="learning-panel">
            <div className="learning-panel-head"><h3>{section === "population_overrides" ? "Profils population" : "Profils terrain"}</h3><span>{Object.keys(draft[section]).length}</span></div>
            {Object.entries(draft[section]).map(([profileId, profile]) => (
              <div key={profileId} className="alerting-profile-card">
                <div className="alerting-rule-head">
                  <div>
                    <div className="learning-primary">{profile.label}</div>
                    <div className="learning-secondary">{profileId}</div>
                  </div>
                  <label className="learning-pill learning-pill--muted"><input type="checkbox" checked={profile.enabled} onChange={(event) => setDraft(updateProfileOverride(draft, section, profileId, (target) => { target.enabled = event.target.checked; }))} /> active</label>
                </div>
                {Object.entries(profile.overrides).map(([overrideKey, overrideValue]) => (
                  <label key={overrideKey} className="alerting-field">
                    <span>{overrideKey}</span>
                    <input type="number" value={overrideValue} onChange={(event) => setDraft(setProfileOverrideValue(draft, section, profileId, overrideKey, event.target.value))} />
                  </label>
                ))}
              </div>
            ))}
          </div>
        ))}
      </div>

      <div className="learning-grid">
        <div className="learning-panel">
          <div className="learning-panel-head"><h3>Catalogue complications</h3><span>{draft.complication_catalog.length}</span></div>
          <div className="learning-table-wrap">
            <table className="learning-table">
              <thead><tr><th>Complication</th><th>Famille</th><th>Detecteur</th><th>Regle</th></tr></thead>
              <tbody>
                {draft.complication_catalog.map((row) => (
                  <tr key={row.id}>
                    <td><div className="learning-primary">{row.label}</div><div className="learning-secondary">{row.id}</div></td>
                    <td>{row.family}</td>
                    <td><span className={`learning-pill ${row.detector_status === "supported" ? "learning-pill--good" : row.detector_status === "trend-only" ? "learning-pill--warn" : "learning-pill--muted"}`}>{row.detector_status}</span></td>
                    <td>{row.linked_rule_id ?? "--"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        <div className="learning-panel">
          <div className="learning-panel-head"><h3>Profils detectes par salle</h3><span>{Object.keys(draft.room_profiles).length}</span></div>
          <div className="learning-table-wrap">
            <table className="learning-table">
              <thead><tr><th>Salle</th><th>Populations</th><th>Terrains</th><th>Maj</th></tr></thead>
              <tbody>
                {Object.entries(draft.room_profiles).map(([roomId, profile]) => (
                  <tr key={roomId}>
                    <td>{roomId}</td>
                    <td>{profile.populations.join(", ") || "--"}</td>
                    <td>{profile.terrains.join(", ") || "--"}</td>
                    <td>{formatDate(profile.updated_at)}</td>
                  </tr>
                ))}
                {Object.keys(draft.room_profiles).length === 0 && (
                  <tr><td colSpan={4} className="learning-empty-row">Aucun profil patient detecte pour l&apos;instant.</td></tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  );
}
