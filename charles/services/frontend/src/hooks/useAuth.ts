// ═══════════════════════════════════════════════════════════════
// CHARLES — Hook Auth (JWT, rôles : iade | mar | admin)
// ═══════════════════════════════════════════════════════════════

import { useState, useCallback } from "react";

const API_URL = "/api";
const TOKEN_KEY = "charles_token";
const USER_KEY = "charles_user";

export interface AuthUser {
  username: string;
  role: "iade" | "mar" | "admin";
  name: string;
  access_token: string;
}

function loadUser(): AuthUser | null {
  try {
    const raw = sessionStorage.getItem(USER_KEY);
    return raw ? (JSON.parse(raw) as AuthUser) : null;
  } catch {
    return null;
  }
}

export function useAuth() {
  const [user, setUser] = useState<AuthUser | null>(loadUser);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const login = useCallback(async (username: string, password: string): Promise<boolean> => {
    setLoading(true);
    setError(null);
    try {
      const resp = await fetch(`${API_URL}/auth/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username, password }),
      });
      if (!resp.ok) {
        setError("Identifiants incorrects");
        return false;
      }
      const data = (await resp.json()) as AuthUser;
      sessionStorage.setItem(TOKEN_KEY, data.access_token);
      sessionStorage.setItem(USER_KEY, JSON.stringify(data));
      setUser(data);
      return true;
    } catch {
      setError("Impossible de contacter le serveur");
      return false;
    } finally {
      setLoading(false);
    }
  }, []);

  const logout = useCallback(() => {
    sessionStorage.removeItem(TOKEN_KEY);
    sessionStorage.removeItem(USER_KEY);
    setUser(null);
  }, []);

  const getToken = useCallback(() => sessionStorage.getItem(TOKEN_KEY), []);

  return { user, loading, error, login, logout, getToken };
}

export function getStoredToken(): string | null {
  return sessionStorage.getItem(TOKEN_KEY);
}
