"""
CHARLES — Database layer (async SQLAlchemy + asyncpg).

Gère la connexion PostgreSQL et les opérations CRUD.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings

logger = logging.getLogger("charles.db")

# ── Compteur de pannes de persistance ─────────────────────────
_db_failures: list[int] = [0]  # liste mutable — pas de 'global' nécessaire


def get_failure_count() -> int:
    """Nombre cumulé d'échecs de persistance depuis le démarrage."""
    return _db_failures[0]


engine = create_async_engine(
    settings.database_url,
    pool_size=10,
    max_overflow=5,
    pool_pre_ping=True,
)

async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def init_db():
    """Vérifie la connexion à la base. Lève une exception si PostgreSQL est inaccessible."""
    async with engine.begin() as conn:
        await conn.execute(text("SELECT 1"))
    logger.info("PostgreSQL connected")


async def close_db():
    await engine.dispose()


def generate_case_id() -> str:
    return f"CAS-{uuid.uuid4().hex[:8].upper()}"


# ── Cases ──────────────────────────────────────────────────────

async def create_case(data: dict) -> dict:
    case_id = generate_case_id()
    async with async_session() as session:
        await session.execute(
            text("""
                INSERT INTO cases (case_id, patient_age, patient_sex, patient_weight,
                    patient_height, asa_score, surgery_type, surgery_approach,
                    anesthesia_type, room_id)
                VALUES (:case_id, :patient_age, :patient_sex, :patient_weight,
                    :patient_height, :asa_score, :surgery_type, :surgery_approach,
                    :anesthesia_type, :room_id)
            """),
            {"case_id": case_id, **data},
        )
        await session.commit()
    return {"case_id": case_id, **data, "status": "active"}


async def end_case(case_id: str) -> bool:
    async with async_session() as session:
        result = await session.execute(
            text("UPDATE cases SET status = 'ended', ended_at = NOW() WHERE case_id = :cid AND status = 'active'"),
            {"cid": case_id},
        )
        await session.commit()
        return result.rowcount > 0


async def get_case(case_id: str) -> dict | None:
    async with async_session() as session:
        result = await session.execute(
            text("SELECT * FROM cases WHERE case_id = :cid"),
            {"cid": case_id},
        )
        row = result.mappings().first()
        return dict(row) if row else None


async def list_cases(limit: int = 50, room_id: str | None = None, status: str | None = None) -> list[dict]:
    async with async_session() as session:
        conditions = []
        params: dict[str, Any] = {"lim": limit}
        if room_id:
            conditions.append("room_id = :room_id")
            params["room_id"] = room_id
        if status:
            conditions.append("status = :status")
            params["status"] = status
        where = "WHERE " + " AND ".join(conditions) if conditions else ""
        result = await session.execute(
            text(f"SELECT * FROM cases {where} ORDER BY started_at DESC LIMIT :lim"),
            params,
        )
        return [dict(r) for r in result.mappings().all()]


# ── Alerts ─────────────────────────────────────────────────────

async def save_alert(alert_data: dict) -> int | None:
    try:
        async with async_session() as session:
            result = await session.execute(
                text("""
                    INSERT INTO alerts (case_id, room_id, timestamp, level, rule_id, title, detail, parameters)
                    VALUES (:case_id, :room_id, :timestamp, :level, :rule_id, :title, :detail, CAST(:parameters AS jsonb))
                    RETURNING id
                """),
                alert_data,
            )
            await session.commit()
            row = result.first()
            return row[0] if row else None
    except Exception as e:
        _db_failures[0] += 1
        logger.critical("DB PERSISTENCE FAILURE — alerte perdue: %s", e)
        return None


async def acknowledge_alert(alert_id: int, acknowledged_by: str) -> bool:
    async with async_session() as session:
        result = await session.execute(
            text("""
                UPDATE alerts SET acknowledged = TRUE, acknowledged_at = NOW(), acknowledged_by = :by
                WHERE id = :id AND acknowledged = FALSE
            """),
            {"id": alert_id, "by": acknowledged_by},
        )
        await session.commit()
        return result.rowcount > 0


async def get_alerts(case_id: str | None = None, room_id: str | None = None, level: str | None = None, limit: int = 100) -> list[dict]:
    async with async_session() as session:
        conditions = []
        params: dict[str, Any] = {"lim": limit}
        if case_id:
            conditions.append("case_id = :case_id")
            params["case_id"] = case_id
        if room_id:
            conditions.append("room_id = :room_id")
            params["room_id"] = room_id
        if level:
            conditions.append("level = :level")
            params["level"] = level
        where = "WHERE " + " AND ".join(conditions) if conditions else ""
        result = await session.execute(
            text(f"SELECT * FROM alerts {where} ORDER BY timestamp DESC LIMIT :lim"),
            params,
        )
        return [dict(r) for r in result.mappings().all()]


# ── Drug Administrations ───────────────────────────────────────

async def save_drug_admin(data: dict) -> int | None:
    try:
        async with async_session() as session:
            result = await session.execute(
                text("""
                    INSERT INTO drug_administrations (case_id, drug_name, dose, dose_unit, route,
                        bolus_or_continuous, rate, rate_unit)
                    VALUES (:case_id, :drug_name, :dose, :dose_unit, :route,
                        :bolus_or_continuous, :rate, :rate_unit)
                    RETURNING id
                """),
                data,
            )
            await session.commit()
            row = result.first()
            return row[0] if row else None
    except Exception as e:
        _db_failures[0] += 1
        logger.critical("DB PERSISTENCE FAILURE — drug admin perdu: %s", e)
        return None


# ── Case Events ────────────────────────────────────────────────

async def save_event(data: dict) -> int | None:
    try:
        async with async_session() as session:
            result = await session.execute(
                text("""
                    INSERT INTO case_events (case_id, event_type, detail)
                    VALUES (:case_id, :event_type, :detail)
                    RETURNING id
                """),
                data,
            )
            await session.commit()
            row = result.first()
            return row[0] if row else None
    except Exception as e:
        _db_failures[0] += 1
        logger.critical("DB PERSISTENCE FAILURE — event perdu: %s", e)
        return None


# ── Fluid Balance ──────────────────────────────────────────────

async def save_fluid(data: dict) -> int | None:
    try:
        async with async_session() as session:
            result = await session.execute(
                text("""
                    INSERT INTO fluid_balance (case_id, type, category, volume_ml, product_name)
                    VALUES (:case_id, :type, :category, :volume_ml, :product_name)
                    RETURNING id
                """),
                data,
            )
            await session.commit()
            row = result.first()
            return row[0] if row else None
    except Exception as e:
        _db_failures[0] += 1
        logger.critical("DB PERSISTENCE FAILURE — fluid perdu: %s", e)
        return None


async def get_fluid_balance(case_id: str) -> dict:
    async with async_session() as session:
        result = await session.execute(
            text("SELECT type, category, volume_ml, product_name, timestamp FROM fluid_balance WHERE case_id = :cid ORDER BY timestamp"),
            {"cid": case_id},
        )
        rows = [dict(r) for r in result.mappings().all()]
        total_in = sum(r["volume_ml"] for r in rows if r["type"] == "input")
        total_out = sum(r["volume_ml"] for r in rows if r["type"] == "output")
        return {"inputs": total_in, "outputs": total_out, "balance": total_in - total_out, "details": rows}


# ── LLM Analyses ──────────────────────────────────────────────

async def save_llm_analysis(data: dict) -> int | None:
    try:
        async with async_session() as session:
            result = await session.execute(
                text("""
                    INSERT INTO llm_analyses (case_id, trigger_type, model, prompt_tokens,
                        completion_tokens, latency_ms, analysis)
                    VALUES (:case_id, :trigger_type, :model, :prompt_tokens,
                        :completion_tokens, :latency_ms, CAST(:analysis AS jsonb))
                    RETURNING id
                """),
                data,
            )
            await session.commit()
            row = result.first()
            return row[0] if row else None
    except Exception as e:
        _db_failures[0] += 1
        logger.critical("DB PERSISTENCE FAILURE — LLM analysis perdu: %s", e)
        return None


# ── GET queries for drugs, events, LLM analyses ──────────────

async def get_drug_admins(case_id: str) -> list[dict]:
    async with async_session() as session:
        result = await session.execute(
            text("SELECT * FROM drug_administrations WHERE case_id = :cid ORDER BY administered_at"),
            {"cid": case_id},
        )
        return [dict(r) for r in result.mappings().all()]


async def get_events(case_id: str) -> list[dict]:
    async with async_session() as session:
        result = await session.execute(
            text("SELECT * FROM case_events WHERE case_id = :cid ORDER BY timestamp"),
            {"cid": case_id},
        )
        return [dict(r) for r in result.mappings().all()]


async def get_llm_analyses(case_id: str) -> list[dict]:
    async with async_session() as session:
        result = await session.execute(
            text("SELECT * FROM llm_analyses WHERE case_id = :cid ORDER BY created_at DESC"),
            {"cid": case_id},
        )
        return [dict(r) for r in result.mappings().all()]


async def save_alert_feedback(data: dict) -> int | None:
    try:
        async with async_session() as session:
            result = await session.execute(
                text("""
                    INSERT INTO alert_feedback (alert_id, case_id, label, comment)
                    VALUES (:alert_id, :case_id, :label, :comment)
                    RETURNING id
                """),
                data,
            )
            await session.commit()
            row = result.first()
            return row[0] if row else None
    except Exception as e:
        _db_failures[0] += 1
        logger.critical("DB PERSISTENCE FAILURE — alert feedback perdu: %s", e)
        return None
