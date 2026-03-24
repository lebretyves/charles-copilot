// ═══════════════════════════════════════════════════════════════
// CHARLES — ErrorBoundary
// Capture les crashs React et affiche un écran de secours propre
// au lieu de la page blanche par défaut.
// ═══════════════════════════════════════════════════════════════

import { Component, type ErrorInfo, type ReactNode } from "react";

interface Props {
  children: ReactNode;
}

interface State {
  hasError: boolean;
  message: string;
}

export class ErrorBoundary extends Component<Props, State> {
  state: State = { hasError: false, message: "" };

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, message: error.message };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    // Logguer dans la console pour faciliter le debug en prod
    console.error("[CHARLES] Uncaught React error:", error, info.componentStack);
  }

  render() {
    if (this.state.hasError) {
      return (
        <div
          style={{
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            justifyContent: "center",
            height: "100vh",
            background: "#0d1117",
            color: "#f0f6fc",
            fontFamily: "monospace",
            gap: "1.2rem",
            padding: "2rem",
            textAlign: "center",
          }}
        >
          <div style={{ fontSize: "2rem" }}>⚠️</div>
          <h1 style={{ margin: 0, color: "#ff7b72" }}>Erreur inattendue CHARLES</h1>
          <p style={{ maxWidth: 480, color: "#8b949e" }}>{this.state.message}</p>
          <button
            onClick={() => window.location.reload()}
            style={{
              padding: "0.6rem 1.4rem",
              background: "#238636",
              border: "none",
              borderRadius: 6,
              color: "#fff",
              cursor: "pointer",
              fontSize: "0.95rem",
            }}
          >
            Recharger
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}
