import sys
from pathlib import Path
from types import SimpleNamespace

import pandas as pd
from fastapi import FastAPI
from fastapi.testclient import TestClient


ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / "services" / "backend"))


from app.metrics import MetricsStore
from app.simulator_routes import create_simulator_router


class FakeMQTTConsumer:
    def __init__(self):
        self.messages: list[tuple[str, dict]] = []

    def publish(self, topic: str, payload: dict):
        self.messages.append((topic, payload))


def _catalog_state():
    df = pd.DataFrame(
        [
            {
                "caseid": 42,
                "age": 63,
                "sex": "F",
                "asa": 2,
                "department": "general",
                "optype": "major",
                "opname": "laparotomy",
                "ane_type": "GA",
            }
        ]
    )
    return SimpleNamespace(
        loaded=True,
        df=df,
        get_catalog=lambda: {"loaded": True},
        get_wave_catalog=lambda: {"loaded": True},
        search_cases=lambda _filters: {"total_matches": 1, "cases": [{"caseid": 42}]},
    )


def _build_client():
    state = SimpleNamespace(
        mqtt_consumer=FakeMQTTConsumer(),
        metrics=MetricsStore(),
        catalog=_catalog_state(),
    )
    audit_events: list[tuple[str, dict]] = []

    def audit_log(event_name: str, **kwargs):
        audit_events.append((event_name, kwargs))

    def require_role_factory(*_roles):
        async def _dependency():
            return {"sub": "admin", "role": "admin"}

        return _dependency

    app = FastAPI()
    app.include_router(
        create_simulator_router(
            state=state,
            audit_log=audit_log,
            require_role_factory=require_role_factory,
        )
    )
    return TestClient(app, base_url="http://localhost"), state, audit_events


def test_simulator_control_rejects_start_vitaldb_without_caseid():
    client, _state, _audit_events = _build_client()

    response = client.post(
        "/simulator/control",
        json={"action": "start_vitaldb", "room_id": "salle_1"},
    )

    assert response.status_code == 422
    assert "caseid" in response.text


def test_simulator_control_rejects_start_synthetic_without_scenario():
    client, _state, _audit_events = _build_client()

    response = client.post(
        "/simulator/control",
        json={"action": "start_synthetic", "room_id": "salle_1"},
    )

    assert response.status_code == 422
    assert "scenario" in response.text


def test_simulator_control_rejects_non_positive_speed():
    client, _state, _audit_events = _build_client()

    response = client.post(
        "/simulator/control",
        json={"action": "start_vitaldb", "room_id": "salle_1", "caseid": 42, "speed": 0},
    )

    assert response.status_code == 422
    assert "greater than 0" in response.text


def test_simulator_control_publishes_valid_vitaldb_command():
    client, state, audit_events = _build_client()

    response = client.post(
        "/simulator/control",
        json={
            "action": "start_vitaldb",
            "room_id": "salle_2",
            "caseid": 42,
            "speed": 1.5,
            "with_waveforms": True,
        },
    )

    assert response.status_code == 200
    payload = response.json()["command"]
    assert payload["action"] == "start_vitaldb"
    assert payload["room_id"] == "salle_2"
    assert payload["caseid"] == 42
    assert payload["with_waveforms"] is True
    assert payload["patient_info"]["age"] == 63
    assert state.mqtt_consumer.messages == [("charles/simulator/control", payload)]
    assert audit_events[0][0] == "simulator.control"
