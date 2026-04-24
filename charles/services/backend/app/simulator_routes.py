from __future__ import annotations

from typing import Literal
from typing import Any, Callable

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, model_validator

from app import database as db


class ScenarioFilter(BaseModel):
    model_config = {"extra": "allow"}


class SimulatorCommand(BaseModel):
    action: Literal["start_vitaldb", "stop"]
    room_id: str = "salle_1"
    caseid: int | None = None
    speed: float = Field(default=1.0, gt=0)
    with_waveforms: bool = False

    @model_validator(mode="after")
    def validate_action_payload(self) -> "SimulatorCommand":
        if self.action == "start_vitaldb" and self.caseid is None:
            raise ValueError("caseid is required for start_vitaldb")
        return self


def _build_patient_info(state: Any, caseid: int) -> dict[str, Any] | None:
    if not state.catalog.loaded or state.catalog.df is None:
        return None

    row = state.catalog.df[state.catalog.df["caseid"] == caseid]
    if row.empty:
        return None

    record = row.iloc[0]
    return {
        "caseid": int(record["caseid"]) if pd.notna(record["caseid"]) else caseid,
        "age": int(record["age"]) if pd.notna(record["age"]) else None,
        "sex": record["sex"] if pd.notna(record["sex"]) else None,
        "asa": int(record["asa"]) if pd.notna(record["asa"]) else None,
        "height": round(float(record["height"]), 1) if pd.notna(record.get("height")) else None,
        "weight": round(float(record["weight"]), 1) if pd.notna(record.get("weight")) else None,
        "department": record["department"] if pd.notna(record["department"]) else None,
        "optype": record["optype"] if pd.notna(record["optype"]) else None,
        "opname": record["opname"] if pd.notna(record["opname"]) else None,
        "dx": record["dx"] if pd.notna(record.get("dx")) else None,
        "approach": record["approach"] if pd.notna(record.get("approach")) else None,
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

    async def close_room_case(room_id: str) -> str | None:
        active_case = state.room_cases.pop(room_id, None)
        if not active_case:
            existing = await db.get_active_case_for_room(room_id)
            active_case = existing["case_id"] if existing else None
        if active_case:
            await db.end_case(active_case)
        state.alert_engine.reset_room(room_id)
        state.rooms.pop(room_id, None)
        if hasattr(state, "room_histories"):
            state.room_histories.pop(room_id, None)
        if hasattr(state, "room_historical_alerts"):
            state.room_historical_alerts.pop(room_id, None)
        return active_case

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

        previous_case_id = await close_room_case(cmd.room_id)
        payload: dict[str, Any] = {
            "action": cmd.action,
            "room_id": cmd.room_id,
            "speed": cmd.speed,
        }
        if cmd.action == "start_vitaldb":
            payload["caseid"] = cmd.caseid
            payload["with_waveforms"] = cmd.with_waveforms
            patient_info = _build_patient_info(state, cmd.caseid)
            if patient_info:
                payload["patient_info"] = patient_info
            replay_case = await db.create_replay_case(
                {
                    "room_id": cmd.room_id,
                    "source_caseid": cmd.caseid,
                    "patient_age": patient_info.get("age") if patient_info else None,
                    "patient_sex": patient_info.get("sex") if patient_info else None,
                    "patient_weight": patient_info.get("weight") if patient_info else None,
                    "patient_height": patient_info.get("height") if patient_info else None,
                    "asa_score": patient_info.get("asa") if patient_info else None,
                    "surgery_type": (patient_info.get("opname") or patient_info.get("optype")) if patient_info else f"VitalDB {cmd.caseid}",
                    "surgery_approach": patient_info.get("approach") if patient_info else None,
                    "anesthesia_type": patient_info.get("ane_type") if patient_info else None,
                }
            )
            state.room_cases[cmd.room_id] = replay_case["case_id"]
            payload["case_id"] = replay_case["case_id"]

        state.metrics.incr("simulator_commands_total")
        state.metrics.mark("last_simulator_command_at")
        state.mqtt_consumer.publish("charles/simulator/control", payload)
        audit_log(
            "simulator.control",
            user=user.get("sub"),
            role=user.get("role"),
            action_name=cmd.action,
            room_id=cmd.room_id,
            previous_case_id=previous_case_id,
            case_id=payload.get("case_id"),
            caseid=cmd.caseid,
            with_waveforms=cmd.with_waveforms,
        )
        return {"status": "sent", "command": payload}

    return router
