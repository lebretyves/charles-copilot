// ═══════════════════════════════════════════════════════════════
// CHARLES — Page de connexion
// ═══════════════════════════════════════════════════════════════

import { useState, FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../hooks/useAuth";

export function LoginPage() {
  const { login, loading, error } = useAuth();
  const navigate = useNavigate();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    const ok = await login(username, password);
    if (ok) {
      // Redirection selon le rôle
      const raw = sessionStorage.getItem("charles_user");
      const user = raw ? JSON.parse(raw) : null;
      if (user?.role === "admin") navigate("/admin");
      else if (user?.role === "mar") navigate("/mar");
      else navigate("/");
    }
  }

  return (
    <div className="login-page">
      <div className="login-card">
        <div className="login-header">
          <span className="login-logo">CHARLES</span>
          <span className="login-subtitle">Copilote IA — Vigilance Anesthésique</span>
        </div>

        <form className="login-form" onSubmit={handleSubmit}>
          <div className="login-field">
            <label className="login-label">Identifiant</label>
            <input
              className="login-input"
              type="text"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              placeholder="iade1 / mar1 / admin"
              autoFocus
              required
            />
          </div>

          <div className="login-field">
            <label className="login-label">Mot de passe</label>
            <input
              className="login-input"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="••••••••••"
              required
            />
          </div>

          {error && <div className="login-error">{error}</div>}

          <button className="login-btn" type="submit" disabled={loading}>
            {loading ? "Connexion..." : "Se connecter"}
          </button>
        </form>

        <div className="login-hint">
          <strong>Comptes dev :</strong><br />
          <code>iade1</code> / <code>iade2</code> / <code>mar1</code> → <code>charles2026</code><br />
          <code>admin</code> → <code>admin2026</code>
        </div>
      </div>
    </div>
  );
}
