from __future__ import annotations

from datetime import datetime, timezone
from threading import Lock
from typing import Any


class MetricsStore:
    def __init__(self) -> None:
        self._lock = Lock()
        self._started_at = datetime.now(timezone.utc)
        self._counters: dict[str, int] = {
            "auth_login_success_total": 0,
            "auth_login_failed_total": 0,
            "monitoring_updates_total": 0,
            "wave_chunks_total": 0,
            "alerts_total": 0,
            "critical_alerts_total": 0,
            "llm_requests_total": 0,
            "llm_completed_total": 0,
            "llm_failures_total": 0,
            "llm_timeouts_total": 0,
            "ws_connections_total": 0,
            "ws_disconnects_total": 0,
            "ws_commands_total": 0,
            "simulator_commands_total": 0,
            "manual_alert_ack_total": 0,
        }
        self._timestamps: dict[str, str] = {
            "started_at": self._started_at.isoformat(),
        }
        self._llm_latency_total_ms = 0
        self._llm_latency_samples = 0

    def incr(self, name: str, amount: int = 1) -> None:
        with self._lock:
            self._counters[name] = self._counters.get(name, 0) + amount

    def mark(self, name: str, value: str | None = None) -> None:
        with self._lock:
            self._timestamps[name] = value or datetime.now(timezone.utc).isoformat()

    def observe_llm_latency(self, latency_ms: int | float | None) -> None:
        if latency_ms is None:
            return
        with self._lock:
            self._llm_latency_total_ms += int(latency_ms)
            self._llm_latency_samples += 1

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            counters = dict(self._counters)
            timestamps = dict(self._timestamps)
            llm_latency_total_ms = self._llm_latency_total_ms
            llm_latency_samples = self._llm_latency_samples

        uptime_s = max(0.0, (datetime.now(timezone.utc) - self._started_at).total_seconds())
        return {
            **counters,
            **timestamps,
            "uptime_s": round(uptime_s, 1),
            "llm_avg_latency_ms": round(llm_latency_total_ms / llm_latency_samples, 1) if llm_latency_samples else None,
            "llm_latency_samples": llm_latency_samples,
        }
