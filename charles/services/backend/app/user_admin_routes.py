from __future__ import annotations

import re
from typing import Any, Callable, Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, field_validator

from app import auth

USERNAME_RE = re.compile(r"^[a-z0-9._-]{3,64}$")


class AdminUserCreateRequest(BaseModel):
    username: str = Field(min_length=3, max_length=64)
    name: str = Field(min_length=1, max_length=128)
    role: Literal["iade", "mar", "admin"]
    password: str = Field(min_length=8, max_length=128)
    must_change_password: bool = True

    @field_validator("username")
    @classmethod
    def validate_username(cls, value: str) -> str:
        normalized = auth.normalize_username(value)
        if not USERNAME_RE.fullmatch(normalized):
            raise ValueError("Username must use 3-64 chars among a-z, 0-9, dot, underscore or dash")
        return normalized

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("Display name is required")
        return stripped


def create_user_admin_router(
    *,
    audit_log: Callable[..., None],
    require_role_factory: Callable[..., Any],
) -> APIRouter:
    router = APIRouter()
    admin_access = require_role_factory("admin")

    @router.get("/admin/users")
    async def list_admin_users(user: dict = Depends(admin_access)):
        return await auth.list_users_for_admin()

    @router.post("/admin/users", status_code=status.HTTP_201_CREATED)
    async def create_admin_user(payload: AdminUserCreateRequest, user: dict = Depends(admin_access)):
        try:
            created = await auth.create_user_for_admin(
                username=payload.username,
                password=payload.password,
                role=payload.role,
                name=payload.name,
                created_by=user.get("sub"),
                must_change_password=payload.must_change_password,
            )
        except ValueError as exc:
            detail = str(exc)
            status_code = status.HTTP_409_CONFLICT if "existe deja" in detail else status.HTTP_400_BAD_REQUEST
            raise HTTPException(status_code=status_code, detail=detail) from exc

        audit_log(
            "admin.user.create",
            user=user.get("sub"),
            role=user.get("role"),
            created_username=created.get("username"),
            created_role=created.get("role"),
        )
        return created

    return router
