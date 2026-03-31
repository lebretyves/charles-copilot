from __future__ import annotations

from typing import Any, Callable

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel


class ScenarioFilter(BaseModel):
    model_config = {"extra": "allow"}


class SimulatorCommand(BaseModel):
    action: str
    room_id: str = "salle_1"
    caseid: int | None = None
    scenario: str | None = None
    speed: float = 1.0
    with_waveforms: bool = False


def _build_patient_info(state: Any, caseid: int) -> dict[str, Any] | None:
    if not state.catalog.loaded or state.catalog.df is None:
        return None

    row = state.catalog.df[state.catalog.df["caseid"] == caseid]
    if row.empty:
        return None

    record = row.iloc[0]
    return {
        "age": int(record["age"]) if pd.notna(record["age"]) else None,
        "sex": record["sex"] if pd.notna(record["sex"]) else None,
        "asa": int(record["asa"]) if pd.notna(record["asa"]) else None,
        "department": record["department"] if pd.notna(record["department"]) else None,
        "optype": record["optype"] if pd.notna(record["optype"]) else None,
        "opname": record["opname"] if pd.notna(record["opname"]) else None,
        "ane_type": record["ane_type"] if pd.notna(record["ane_type"]) else None,
    }


def create_simulator_router(
    *,
    state: Any,
    audit_log: Callable[..., None],
    require_role_factory: Callable[..., Any],
) -> APIRouter:
    router = APIRouter()
    simulator_access = require_role_factory("iade", "mar", "admin")

    @router.get("/scenarios/catalog")
    async def get_scenario_catalog(user: dict = Depends(simulator_access)):
        return state.catalog.get_catalog()

    @router.get("/scenarios/catalog/waveforms/all")
    async def get_wave_catalog_all(user: dict = Depends(simulator_access)):
        return state.catalog.get_wave_catalog()

    @router.get("/scenarios/catalog/waveforms")
    async def get_wave_catalog(user: dict = Depends(simulator_access)):
        return state.catalog.get_wave_catalog()

    @router.post("/scenarios/search")
    async def search_scenarios(filters: ScenarioFilter, user: dict = Depends(simulator_access)):
        return state.catalog.search_cases(filters.model_dump())

    @router.post("/simulator/control")
    async def control_simulator(cmd: SimulatorCommand, user: dict = Depends(simulator_access)):
        if not state.mqtt_consumer:
            raise HTTPException(status_code=503, detail="MQTT non connecte")

        payload: dict[str, Any] = {
            "action": cmd.action,
            "room_id": cmd.room_id,
            "speed": cmd.speed,
        }
        if cmd.action == "start_vitaldb" and cmd.caseid is not None:
            payload["caseid"] = cmd.caseid
            payload["with_waveforms"] = cmd.with_waveforms
            patient_info = _build_patient_info(state, cmd.caseid)
            if patient_info:
                payload["patient_info"] = patient_info
        elif cmd.action == "start_synthetic" and cmd.scenario:
            payload["scenario"] = cmd.scenario

        state.metrics.incr("simulator_commands_total")
        state.metrics.mark("last_simulator_command_at")
        state.mqtt_consumer.publish("charles/simulator/control", payload)
        audit_log(
            "simulator.control",
            user=user.get("sub"),
            role=user.get("role"),
            action_name=cmd.action,
            room_id=cmd.room_id,
            caseid=cmd.caseid,
            with_waveforms=cmd.with_waveforms,
        )
        return {"status": "sent", "command": payload}

    return router
