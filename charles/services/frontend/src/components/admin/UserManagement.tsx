import { useState, type FormEvent } from "react";

export interface AdminUserRecord {
  username: string;
  role: "iade" | "mar" | "admin";
  name: string;
  is_active: boolean;
  must_change_password: boolean;
  source: string;
  created_by?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
}

export interface AdminUserCreatePayload {
  username: string;
  name: string;
  role: "iade" | "mar" | "admin";
  password: string;
  must_change_password: boolean;
}

interface UserManagementProps {
  users: AdminUserRecord[];
  loading: boolean;
  creating: boolean;
  error: string | null;
  feedback: string | null;
  onRefresh: () => void;
  onCreate: (payload: AdminUserCreatePayload) => Promise<boolean>;
}

const INITIAL_FORM: AdminUserCreatePayload = {
  username: "",
  name: "",
  role: "iade",
  password: "",
  must_change_password: true,
};

function formatDate(value?: string | null): string {
  if (!value) {
    return "--";
  }
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString("fr-FR");
}

export function UserManagement({
  users,
  loading,
  creating,
  error,
  feedback,
  onRefresh,
  onCreate,
}: UserManagementProps) {
  const [form, setForm] = useState<AdminUserCreatePayload>(INITIAL_FORM);

  const builtinCount = users.filter((user) => user.source === "builtin").length;
  const managedCount = users.filter((user) => user.source !== "builtin").length;

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const ok = await onCreate({
      ...form,
      username: form.username.trim().toLowerCase(),
      name: form.name.trim(),
    });
    if (ok) {
      setForm((current) => ({
        ...INITIAL_FORM,
        role: current.role,
      }));
    }
  }

  return (
    <div className="admin-system">
      <div className="section-header">
        <div>
          <h2 className="section-title">Utilisateurs</h2>
          <div className="admin-hint">Pas d&apos;inscription publique. Les comptes sont crees ici par un admin.</div>
        </div>
        <button className="refresh-btn" onClick={onRefresh}>Rafraichir</button>
      </div>

      <div className="admin-cards">
        <div className="admin-card">
          <div className="admin-card-title">Synthese</div>
          <div className="admin-card-body">
            <div className="stat-row"><span>Total comptes</span><span className="stat-val">{users.length}</span></div>
            <div className="stat-row"><span>Comptes natifs</span><span className="stat-val">{builtinCount}</span></div>
            <div className="stat-row"><span>Comptes admin</span><span className="stat-val">{managedCount}</span></div>
          </div>
        </div>
      </div>

      <div className="user-admin-grid">
        <form className="admin-card user-form" onSubmit={handleSubmit}>
          <div className="admin-card-title">Creer un utilisateur</div>
          <div className="user-form-grid">
            <label className="user-form-field">
              <span>Identifiant</span>
              <input
                className="user-form-input"
                value={form.username}
                onChange={(event) => setForm((current) => ({ ...current, username: event.target.value }))}
                placeholder="ex: iade3"
                autoComplete="off"
              />
            </label>
            <label className="user-form-field">
              <span>Nom affiche</span>
              <input
                className="user-form-input"
                value={form.name}
                onChange={(event) => setForm((current) => ({ ...current, name: event.target.value }))}
                placeholder="ex: IADE 3"
              />
            </label>
            <label className="user-form-field">
              <span>Role</span>
              <select
                className="user-form-input"
                value={form.role}
                onChange={(event) => setForm((current) => ({ ...current, role: event.target.value as AdminUserCreatePayload["role"] }))}
              >
                <option value="iade">IADE</option>
                <option value="mar">MAR</option>
                <option value="admin">Admin</option>
              </select>
            </label>
            <label className="user-form-field">
              <span>Mot de passe initial</span>
              <input
                className="user-form-input"
                type="password"
                value={form.password}
                onChange={(event) => setForm((current) => ({ ...current, password: event.target.value }))}
                placeholder="8 caracteres minimum"
                autoComplete="new-password"
              />
            </label>
          </div>

          <label className="user-form-checkbox">
            <input
              type="checkbox"
              checked={form.must_change_password}
              onChange={(event) => setForm((current) => ({ ...current, must_change_password: event.target.checked }))}
            />
            <span>Demander un changement de mot de passe au prochain login</span>
          </label>

          <div className="user-form-actions">
            <button className="action-btn action-btn--primary" type="submit" disabled={creating}>
              {creating ? "Creation..." : "Creer le compte"}
            </button>
          </div>

          {feedback && <div className="admin-feedback">{feedback}</div>}
          {error && <div className="admin-feedback admin-feedback--error">{error}</div>}
        </form>

        <div className="admin-card">
          <div className="admin-card-title">Comptes disponibles</div>
          {loading ? (
            <div className="learning-empty">Chargement des utilisateurs...</div>
          ) : (
            <div className="user-table-wrap">
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Login</th>
                    <th>Nom</th>
                    <th>Role</th>
                    <th>Source</th>
                    <th>Statut</th>
                    <th>Maj</th>
                  </tr>
                </thead>
                <tbody>
                  {users.map((user) => (
                    <tr key={user.username}>
                      <td className="mono">{user.username}</td>
                      <td>{user.name}</td>
                      <td><span className={`level-badge level-badge--${user.role === "admin" ? "critical" : user.role === "mar" ? "warning" : "info"}`}>{user.role}</span></td>
                      <td><span className="user-source-badge">{user.source}</span></td>
                      <td>{user.is_active ? "actif" : "inactif"}</td>
                      <td className="small">{formatDate(user.updated_at ?? user.created_at)}</td>
                    </tr>
                  ))}
                  {users.length === 0 && (
                    <tr>
                      <td colSpan={6} className="text-muted">Aucun utilisateur disponible.</td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
