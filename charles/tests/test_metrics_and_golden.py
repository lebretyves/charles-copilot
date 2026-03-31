import json
import sys
from contextlib import asynccontextmanager
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest
from fastapi.testclient import TestClient


ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / "services" / "backend"))
sys.path.insert(0, str(ROOT / "services" / "simulator"))


from app.metrics import MetricsStore
from app.auth import authenticate
from simulator.waveforms import N_25, N_128, N_500, generate_synth_waves


def _client_no_lifespan():
    try:
        from app.main import app, state
    except ModuleNotFoundError as exc:
        pytest.skip(f"Backend dependency missing for metrics test: {exc}")

    @asynccontextmanager
    async def _noop_lifespan(_app):
        yield

    app.router.lifespan_context = _noop_lifespan
    state.metrics = MetricsStore()
    return TestClient(app), state


class TestMetricsStore:
    def test_metrics_store_tracks_counters_and_latency(self):
        store = MetricsStore()
        store.incr("monitoring_updates_total", 3)
        store.incr("wave_chunks_total", 2)
        store.observe_llm_latency(1200)
        store.observe_llm_latency(800)
        store.mark("last_monitoring_update_at", "2026-03-30T08:00:00+00:00")

        snapshot = store.snapshot()

        assert snapshot["monitoring_updates_total"] == 3
        assert snapshot["wave_chunks_total"] == 2
        assert snapshot["llm_avg_latency_ms"] == 1000.0
        assert snapshot["last_monitoring_update_at"] == "2026-03-30T08:00:00+00:00"
        assert snapshot["uptime_s"] >= 0

    def test_metrics_endpoint_exposes_operational_counters(self):
        client, state = _client_no_lifespan()

        bad = client.post("/auth/login", json={"username": "iade1", "password": "wrong"})
        assert bad.status_code == 401

        login = authenticate("admin", "admin2026")
        assert login is not None
        headers = {"Authorization": f"Bearer {login['access_token']}"}

        state.metrics.incr("monitoring_updates_total", 4)
        state.metrics.incr("wave_chunks_total", 12)
        state.metrics.incr("simulator_commands_total", 1)
        state.metrics.observe_llm_latency(900)

        response = client.get("/metrics", headers=headers)
        assert response.status_code == 200
        payload = response.json()

        assert payload["auth_login_failed_total"] >= 1
        assert payload["monitoring_updates_total"] == 4
        assert payload["wave_chunks_total"] == 12
        assert payload["simulator_commands_total"] == 1
        assert payload["llm_avg_latency_ms"] == 900.0
        assert payload["data_scope"] == "public_anonymized_waveforms"


class TestGoldenWaveforms:
    @staticmethod
    def _load_golden_cases():
        return json.loads((ROOT / "tests" / "golden_waveforms.json").read_text(encoding="utf-8"))

    def test_golden_waveforms_match_reference_cases(self):
        golden = self._load_golden_cases()
        specs = {
            "baseline": {
                "seed": 42,
                "state": dict(hr=72.0, spo2=98.0, pas=122.0, pad=76.0, etco2=35.0, fr=14.0, ppeak=18.0, pplat=14.0, peep=5.0, bis=45.0),
                "t_start": 1.25,
            },
            "hypotension_low_bis": {
                "seed": 7,
                "state": dict(hr=108.0, spo2=92.0, pas=78.0, pad=42.0, etco2=29.0, fr=18.0, ppeak=24.0, pplat=20.0, peep=8.0, bis=28.0),
                "t_start": 3.0,
            },
        }

        for name, spec in specs.items():
            generated = generate_synth_waves(
                SimpleNamespace(**spec["state"]),
                "golden_room",
                spec["t_start"],
                rng=np.random.default_rng(spec["seed"]),
            )
            assert generated == golden[name]

    def test_golden_waveforms_have_expected_lengths(self):
        golden = self._load_golden_cases()
        for case in golden.values():
            assert len(case["ecg"]) == N_500
            assert len(case["pleth"]) == N_500
            assert len(case["art"]) == N_500
            assert len(case["co2"]) == N_25
            assert len(case["awp"]) == N_25
            assert len(case["eeg"]) == N_128
