import "../../styles/admin-learning.css";

export interface LearningSnapshot {
  dataset_id: string;
  snapshot_path: string | null;
  tracked_path: string | null;
  md5: string | null;
  size_bytes?: number | null;
  file_count?: number | null;
  cases_scanned?: number | null;
  cases_with_segments?: number | null;
  segments_written?: number | null;
  samples_exported?: number | null;
  export_mode?: string | null;
  run_count: number;
  latest_run_id?: string | null;
  latest_run_at?: string | null;
}

export interface LearningAdapter {
  run_id: string;
  dataset_id: string;
  base_model: string;
  runtime_target_tag: string;
  status: "draft" | "reviewed" | "validated" | "runtime-ready";
  human_review_status?: string | null;
  approved_for_runtime: "yes" | "no";
  train_rows: number;
  eval_rows: number;
  input_variants: string[];
  input_variant_counts: Record<string, number>;
  train_loss?: number | null;
  train_runtime_s?: number | null;
  overall_score?: number | null;
  json_parse_ok?: number | null;
  schema_valid?: number | null;
  call_mar_accuracy?: number | null;
  samples_evaluated?: number | null;
  updated_at?: string | null;
  run_path?: string | null;
  model_card_path?: string | null;
  comparison_path?: string | null;
  training_summary_path?: string | null;
  dataset_dvc_md5?: string | null;
  dataset_snapshot_path?: string | null;
}

export interface LearningDashboardData {
  available: boolean;
  learning_root: string;
  generated_at: string;
  registry: {
    exists: boolean;
    path: string | null;
    adapter_count: number;
    status_counts: Record<string, number>;
    runtime_ready_count: number;
  };
  dvc: {
    snapshot_count: number;
    snapshots: LearningSnapshot[];
  };
  tracking: {
    store_path: string | null;
    exists: boolean;
    experiment_count: number;
    run_count: number;
    latest_update_at?: string | null;
  };
  adapters: LearningAdapter[];
  notes: string[];
}

interface LearningDashboardProps {
  data: LearningDashboardData | null;
  loading: boolean;
  error: string | null;
  onRefresh: () => void;
}

function formatNumber(value?: number | null, digits = 0): string {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return "--";
  }
  return new Intl.NumberFormat("fr-FR", {
    maximumFractionDigits: digits,
    minimumFractionDigits: digits,
  }).format(value);
}

function formatDate(value?: string | null): string {
  if (!value) {
    return "--";
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return date.toLocaleString("fr-FR");
}

function formatDuration(seconds?: number | null): string {
  if (!seconds && seconds !== 0) {
    return "--";
  }
  if (seconds < 60) {
    return `${formatNumber(seconds, 0)} s`;
  }
  const minutes = seconds / 60;
  if (minutes < 60) {
    return `${formatNumber(minutes, 1)} min`;
  }
  const hours = minutes / 60;
  return `${formatNumber(hours, 1)} h`;
}

function formatBytes(bytes?: number | null): string {
  if (!bytes && bytes !== 0) {
    return "--";
  }
  const units = ["B", "KB", "MB", "GB", "TB"];
  let value = bytes;
  let unitIndex = 0;
  while (value >= 1024 && unitIndex < units.length - 1) {
    value /= 1024;
    unitIndex += 1;
  }
  return `${formatNumber(value, value >= 100 || unitIndex === 0 ? 0 : 1)} ${units[unitIndex]}`;
}

function statusClass(status: string): string {
  if (status === "runtime-ready" || status === "validated") {
    return "learning-pill--good";
  }
  if (status === "reviewed") {
    return "learning-pill--warn";
  }
  return "learning-pill--muted";
}

export function LearningDashboard({ data, loading, error, onRefresh }: LearningDashboardProps) {
  if (loading && !data) {
    return (
      <div className="admin-system">
        <div className="section-header">
          <h2 className="section-title">Learning / MLOps</h2>
        </div>
        <div className="learning-empty">Chargement du dashboard learning...</div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="admin-system">
        <div className="section-header">
          <h2 className="section-title">Learning / MLOps</h2>
          <button className="refresh-btn" onClick={onRefresh}>Rafraichir</button>
        </div>
        <div className="learning-empty learning-empty--error">{error}</div>
      </div>
    );
  }

  if (!data) {
    return null;
  }

  const totalTrackedSize = data.dvc.snapshots.reduce((total, snapshot) => total + (snapshot.size_bytes ?? 0), 0);
  const totalSegments = data.dvc.snapshots.reduce((total, snapshot) => total + (snapshot.segments_written ?? 0), 0);
  const latestAdapter = data.adapters[0];

  return (
    <div className="admin-system learning-dashboard" data-testid="admin-learning-dashboard">
      <div className="section-header">
        <div>
          <h2 className="section-title">Learning / MLOps</h2>
          <div className="learning-subtitle">
            Dashboard admin du pipeline datasets - runs - evaluation - promotion.
          </div>
        </div>
        <button className="refresh-btn" onClick={onRefresh}>Rafraichir</button>
      </div>

      <div className="learning-meta-bar">
        <span><strong>Workspace</strong> {data.learning_root}</span>
        <span><strong>Genere le</strong> {formatDate(data.generated_at)}</span>
      </div>

      {data.notes.length > 0 && (
        <div className="learning-note-list">
          {data.notes.map((note) => (
            <div key={note} className="learning-note">{note}</div>
          ))}
        </div>
      )}

      <div className="admin-cards learning-kpis">
        <div className="admin-card">
          <div className="admin-card-title">Registry modele</div>
          <div className="admin-card-body">
            <div className="stat-row"><span>Registry present</span><span className={`stat-val ${data.registry.exists ? "stat-ok" : "stat-warn"}`}>{data.registry.exists ? "oui" : "non"}</span></div>
            <div className="stat-row"><span>Adapters suivis</span><span className="stat-val">{formatNumber(data.registry.adapter_count)}</span></div>
            <div className="stat-row"><span>Runtime-ready</span><span className="stat-val">{formatNumber(data.registry.runtime_ready_count)}</span></div>
            <div className="learning-status-row">
              {Object.entries(data.registry.status_counts).map(([status, count]) => (
                <span key={status} className={`learning-pill ${statusClass(status)}`}>
                  {status}: {count}
                </span>
              ))}
            </div>
            <div className="learning-path">{data.registry.path ?? "--"}</div>
          </div>
        </div>

        <div className="admin-card">
          <div className="admin-card-title">Datasets DVC</div>
          <div className="admin-card-body">
            <div className="stat-row"><span>Snapshots</span><span className="stat-val">{formatNumber(data.dvc.snapshot_count)}</span></div>
            <div className="stat-row"><span>Taille suivie</span><span className="stat-val">{formatBytes(totalTrackedSize)}</span></div>
            <div className="stat-row"><span>Segments reperes</span><span className="stat-val">{formatNumber(totalSegments)}</span></div>
            <div className="stat-row"><span>Dernier dataset</span><span className="stat-val">{data.dvc.snapshots[0]?.dataset_id ?? "--"}</span></div>
          </div>
        </div>

        <div className="admin-card">
          <div className="admin-card-title">MLflow local</div>
          <div className="admin-card-body">
            <div className="stat-row"><span>Store present</span><span className={`stat-val ${data.tracking.exists ? "stat-ok" : "stat-warn"}`}>{data.tracking.exists ? "oui" : "non"}</span></div>
            <div className="stat-row"><span>Experiences</span><span className="stat-val">{formatNumber(data.tracking.experiment_count)}</span></div>
            <div className="stat-row"><span>Runs traces</span><span className="stat-val">{formatNumber(data.tracking.run_count)}</span></div>
            <div className="stat-row"><span>Derniere activite</span><span className="stat-val">{formatDate(data.tracking.latest_update_at)}</span></div>
            <div className="learning-path">{data.tracking.store_path ?? "--"}</div>
          </div>
        </div>

        <div className="admin-card">
          <div className="admin-card-title">Dernier run</div>
          <div className="admin-card-body">
            <div className="stat-row"><span>Run</span><span className="stat-val">{latestAdapter?.run_id ?? "--"}</span></div>
            <div className="stat-row"><span>Statut</span><span className={`stat-val ${latestAdapter && (latestAdapter.status === "validated" || latestAdapter.status === "runtime-ready") ? "stat-ok" : "stat-warn"}`}>{latestAdapter?.status ?? "--"}</span></div>
            <div className="stat-row"><span>Overall score</span><span className="stat-val">{latestAdapter?.overall_score !== undefined && latestAdapter?.overall_score !== null ? formatNumber(latestAdapter.overall_score, 4) : "--"}</span></div>
            <div className="stat-row"><span>Train runtime</span><span className="stat-val">{formatDuration(latestAdapter?.train_runtime_s)}</span></div>
            <div className="stat-row"><span>Maj</span><span className="stat-val">{formatDate(latestAdapter?.updated_at)}</span></div>
          </div>
        </div>
      </div>

      <div className="learning-grid">
        <div className="learning-panel">
          <div className="learning-panel-head">
            <h3>Datasets suivis</h3>
            <span>{data.dvc.snapshots.length} snapshot(s)</span>
          </div>
          <div className="learning-table-wrap">
            <table className="learning-table">
              <thead>
                <tr>
                  <th>Dataset</th>
                  <th>Taille</th>
                  <th>Fichiers</th>
                  <th>Segments</th>
                  <th>Runs</th>
                  <th>Maj</th>
                </tr>
              </thead>
              <tbody>
                {data.dvc.snapshots.map((snapshot) => (
                  <tr key={snapshot.dataset_id}>
                    <td>
                      <div className="learning-primary">{snapshot.dataset_id}</div>
                      <div className="learning-secondary">{snapshot.snapshot_path ?? "--"}</div>
                      <div className="learning-secondary">{snapshot.md5 ?? "--"}</div>
                    </td>
                    <td>{formatBytes(snapshot.size_bytes)}</td>
                    <td>{formatNumber(snapshot.file_count)}</td>
                    <td>{formatNumber(snapshot.segments_written)}</td>
                    <td>{formatNumber(snapshot.run_count)}</td>
                    <td>{formatDate(snapshot.latest_run_at)}</td>
                  </tr>
                ))}
                {data.dvc.snapshots.length === 0 && (
                  <tr>
                    <td colSpan={6} className="learning-empty-row">Aucun snapshot DVC detecte.</td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>

        <div className="learning-panel">
          <div className="learning-panel-head">
            <h3>Adapters et promotion</h3>
            <span>{data.adapters.length} run(s)</span>
          </div>
          <div className="learning-table-wrap">
            <table className="learning-table">
              <thead>
                <tr>
                  <th>Run</th>
                  <th>Statut</th>
                  <th>Train / Eval</th>
                  <th>Score</th>
                  <th>Runtime</th>
                  <th>Maj</th>
                </tr>
              </thead>
              <tbody>
                {data.adapters.map((adapter) => (
                  <tr key={adapter.run_id}>
                    <td>
                      <div className="learning-primary">{adapter.run_id}</div>
                      <div className="learning-secondary">{adapter.base_model}</div>
                      <div className="learning-secondary">{adapter.model_card_path ?? "--"}</div>
                    </td>
                    <td><span className={`learning-pill ${statusClass(adapter.status)}`}>{adapter.status}</span></td>
                    <td>{formatNumber(adapter.train_rows)} / {formatNumber(adapter.eval_rows)}</td>
                    <td>{adapter.overall_score !== undefined && adapter.overall_score !== null ? formatNumber(adapter.overall_score, 4) : "--"}</td>
                    <td><span className={`learning-pill ${adapter.approved_for_runtime === "yes" ? "learning-pill--good" : "learning-pill--muted"}`}>{adapter.approved_for_runtime}</span></td>
                    <td>{formatDate(adapter.updated_at)}</td>
                  </tr>
                ))}
                {data.adapters.length === 0 && (
                  <tr>
                    <td colSpan={6} className="learning-empty-row">Aucun adapter detecte.</td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      </div>

      <div className="learning-grid learning-grid--details">
        {data.adapters.slice(0, 3).map((adapter) => (
          <div key={adapter.run_id} className="learning-panel">
            <div className="learning-panel-head">
              <h3>{adapter.run_id}</h3>
              <span className={`learning-pill ${statusClass(adapter.status)}`}>{adapter.status}</span>
            </div>
            <div className="learning-detail-list">
              <div className="stat-row"><span>Dataset</span><span className="stat-val">{adapter.dataset_id}</span></div>
              <div className="stat-row"><span>Variants</span><span className="stat-val">{adapter.input_variants.join(", ") || "--"}</span></div>
              <div className="stat-row"><span>Train loss</span><span className="stat-val">{formatNumber(adapter.train_loss, 4)}</span></div>
              <div className="stat-row"><span>JSON parse</span><span className="stat-val">{formatNumber(adapter.json_parse_ok, 3)}</span></div>
              <div className="stat-row"><span>Schema valid</span><span className="stat-val">{formatNumber(adapter.schema_valid, 3)}</span></div>
              <div className="stat-row"><span>Call MAR</span><span className="stat-val">{formatNumber(adapter.call_mar_accuracy, 3)}</span></div>
              <div className="stat-row"><span>Eval samples</span><span className="stat-val">{formatNumber(adapter.samples_evaluated)}</span></div>
              <div className="stat-row"><span>DVC</span><span className="stat-val mono">{adapter.dataset_dvc_md5 ?? "--"}</span></div>
            </div>
            <div className="learning-path-block">
              <div>{adapter.run_path ?? "--"}</div>
              <div>{adapter.training_summary_path ?? "--"}</div>
              <div>{adapter.comparison_path ?? "--"}</div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
