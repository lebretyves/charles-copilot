from __future__ import annotations

from typing import Any, Callable

from fastapi import APIRouter, Body, Depends, HTTPException


def create_alerting_router(
    *,
    state: Any,
    audit_log: Callable[..., None],
    require_role_factory: Callable[..., Any],
) -> APIRouter:
    router = APIRouter()
    admin_access = require_role_factory("admin")

    @router.get("/admin/alerting/config")
    async def get_alerting_config(user: dict = Depends(admin_access)):
        return state.alert_engine.export_config()

    @router.put("/admin/alerting/config")
    async def update_alerting_config(
        payload: dict[str, Any] = Body(...),
        user: dict = Depends(admin_access),
    ):
        try:
            config = state.alert_engine.save_runtime_config(payload)
        except Exception as exc:
            raise HTTPException(status_code=400, detail=f"Invalid alerting config: {exc}") from exc
        audit_log(
            "admin.alerting.save",
            user=user.get("sub"),
            role=user.get("role"),
            runtime_path=config.get("runtime_path"),
            rule_count=config.get("summary", {}).get("complication_rule_count"),
        )
        return config

    @router.post("/admin/alerting/config/reset")
    async def reset_alerting_config(user: dict = Depends(admin_access)):
        config = state.alert_engine.reset_runtime_config()
        audit_log(
            "admin.alerting.reset",
            user=user.get("sub"),
            role=user.get("role"),
            runtime_path=config.get("runtime_path"),
        )
        return config

    return router
