from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field

from app.config import settings
from app.models import Alert, LLMAnalysis, VitalsFrame


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class LLMJob(BaseModel):
    job_id: str
    room_id: str
    case_id: str | None = None
    trigger_type: str
    requested_at: str
    snapshot_at: str
    vitals: VitalsFrame
    alerts: list[Alert] = Field(default_factory=list)
    patient_info: dict[str, Any] | None = None
    requested_by: str | None = None
    status: str = "queued"
    attempt: int = 1


def build_llm_job(
    room_id: str,
    vitals: VitalsFrame,
    alerts: list[Alert],
    case_id: str | None,
    trigger_type: str,
    patient_info: dict[str, Any] | None = None,
    requested_by: str | None = None,
) -> LLMJob:
    now = utc_now_iso()
    return LLMJob(
        job_id=f"llm-{uuid.uuid4().hex}",
        room_id=room_id,
        case_id=case_id,
        trigger_type=trigger_type,
        requested_at=now,
        snapshot_at=now,
        vitals=vitals,
        alerts=alerts,
        patient_info=patient_info,
        requested_by=requested_by,
    )


def parse_llm_job(payload: str | dict[str, Any]) -> LLMJob:
    if isinstance(payload, str):
        return LLMJob.model_validate_json(payload)
    return LLMJob.model_validate(payload)


def room_status_key(room_id: str) -> str:
    return f"charles:room:{room_id}:llm_status"


def room_analysis_key(room_id: str) -> str:
    return f"charles:room:{room_id}:llm_analysis"


def room_active_job_key(room_id: str) -> str:
    return f"charles:room:{room_id}:llm_active_job"


def job_state_key(job_id: str) -> str:
    return f"charles:llm:job:{job_id}"


def job_claim_key(job_id: str) -> str:
    return f"charles:llm:job:{job_id}:claim"


def worker_status_payload(*, consumer_name: str, available: bool, provider: str, model: str, detail: str | None = None) -> dict[str, Any]:
    return {
        "consumer_name": consumer_name,
        "available": available,
        "provider": provider,
        "model": model,
        "detail": detail,
        "timestamp": utc_now_iso(),
    }


def status_event(
    *,
    job: LLMJob,
    status: str,
    detail: str | None = None,
) -> dict[str, Any]:
    return {
        "type": "llm_analysis_status",
        "job_id": job.job_id,
        "room_id": job.room_id,
        "case_id": job.case_id,
        "trigger_type": job.trigger_type,
        "status": status,
        "detail": detail,
        "attempt": job.attempt,
        "timestamp": utc_now_iso(),
    }


def error_event(
    *,
    job: LLMJob,
    detail: str,
    error_kind: str,
) -> dict[str, Any]:
    return {
        "type": "llm_analysis_error",
        "job_id": job.job_id,
        "room_id": job.room_id,
        "case_id": job.case_id,
        "trigger_type": job.trigger_type,
        "detail": detail,
        "error_kind": error_kind,
        "attempt": job.attempt,
        "timestamp": utc_now_iso(),
    }


def analysis_payload(analysis: LLMAnalysis) -> dict[str, Any]:
    return {
        "situation": analysis.situation,
        "risks": analysis.risks,
        "recommendations": analysis.recommendations,
        "confidence": analysis.confidence,
        "call_mar": analysis.call_mar,
        "call_mar_reason": analysis.call_mar_reason,
        "model": analysis.model,
        "latency_ms": analysis.latency_ms,
        "prompt_tokens": analysis.prompt_tokens,
        "completion_tokens": analysis.completion_tokens,
        "prompt_id": analysis.prompt_id,
        "prompt_version": analysis.prompt_version,
        "rag_enabled": analysis.rag_enabled,
        "rag_sources": analysis.rag_sources,
    }


def analysis_event(*, job: LLMJob, analysis: LLMAnalysis) -> dict[str, Any]:
    return {
        "type": "llm_analysis",
        "job_id": job.job_id,
        "room_id": job.room_id,
        "case_id": job.case_id,
        "trigger_type": job.trigger_type,
        "analysis": analysis_payload(analysis),
        "timestamp": utc_now_iso(),
    }


async def _set_json(redis: Any, key: str, payload: dict[str, Any], ttl_s: int | None = None) -> None:
    body = json.dumps(payload, default=str)
    if ttl_s:
        await redis.setex(key, ttl_s, body)
    else:
        await redis.set(key, body)


async def _get_json(redis: Any, key: str) -> dict[str, Any] | None:
    raw = await redis.get(key)
    if not raw:
        return None
    if isinstance(raw, bytes):
        raw = raw.decode()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return None


async def enqueue_llm_job(redis: Any, job: LLMJob) -> dict[str, Any]:
    active = await _get_json(redis, room_active_job_key(job.room_id))
    if active and active.get("status") in {"queued", "running"}:
        return {
            "job_id": active.get("job_id"),
            "room_id": job.room_id,
            "status": active.get("status"),
            "trigger_type": active.get("trigger_type"),
            "attempt": active.get("attempt", 1),
            "deduplicated": True,
        }

    state_payload = {
        **job.model_dump(mode="json"),
        "detail": None,
    }
    await _set_json(redis, job_state_key(job.job_id), state_payload, settings.llm_job_ttl_s)
    await _set_json(
        redis,
        room_active_job_key(job.room_id),
        {
            "job_id": job.job_id,
            "status": "queued",
            "trigger_type": job.trigger_type,
            "attempt": job.attempt,
            "timestamp": utc_now_iso(),
        },
        settings.llm_job_ttl_s,
    )
    await _set_json(redis, room_status_key(job.room_id), status_event(job=job, status="queued"), settings.llm_job_ttl_s)
    await redis.xadd(
        settings.llm_job_stream,
        {"payload": job.model_dump_json()},
        maxlen=settings.llm_job_stream_maxlen,
        approximate=True,
    )
    return {
        "job_id": job.job_id,
        "room_id": job.room_id,
        "status": "queued",
        "trigger_type": job.trigger_type,
        "attempt": job.attempt,
        "deduplicated": False,
    }


async def mark_job_status(redis: Any, job: LLMJob, status: str, detail: str | None = None) -> dict[str, Any]:
    event = status_event(job=job, status=status, detail=detail)
    await _set_json(redis, room_status_key(job.room_id), event, settings.llm_job_ttl_s)
    await _set_json(
        redis,
        job_state_key(job.job_id),
        {
            **job.model_dump(mode="json"),
            "status": status,
            "detail": detail,
        },
        settings.llm_job_ttl_s,
    )
    if status in {"queued", "running"}:
        await _set_json(
            redis,
            room_active_job_key(job.room_id),
            {
                "job_id": job.job_id,
                "status": status,
                "trigger_type": job.trigger_type,
                "attempt": job.attempt,
                "timestamp": utc_now_iso(),
            },
            settings.llm_job_ttl_s,
        )
    return event


async def store_job_result(redis: Any, job: LLMJob, analysis: LLMAnalysis) -> dict[str, Any]:
    event = analysis_event(job=job, analysis=analysis)
    await _set_json(redis, room_analysis_key(job.room_id), event["analysis"], settings.llm_job_ttl_s)
    await _set_json(redis, room_status_key(job.room_id), status_event(job=job, status="completed"), settings.llm_job_ttl_s)
    await _set_json(
        redis,
        job_state_key(job.job_id),
        {
            **job.model_dump(mode="json"),
            "status": "completed",
            "analysis": event["analysis"],
            "detail": None,
        },
        settings.llm_job_ttl_s,
    )
    active = await _get_json(redis, room_active_job_key(job.room_id))
    if active and active.get("job_id") == job.job_id:
        await redis.delete(room_active_job_key(job.room_id))
    return event


async def store_job_error(redis: Any, job: LLMJob, detail: str, error_kind: str, *, clear_active_job: bool = True) -> dict[str, Any]:
    event = error_event(job=job, detail=detail, error_kind=error_kind)
    await _set_json(redis, room_status_key(job.room_id), status_event(job=job, status="error", detail=detail), settings.llm_job_ttl_s)
    await _set_json(
        redis,
        job_state_key(job.job_id),
        {
            **job.model_dump(mode="json"),
            "status": "error",
            "detail": detail,
            "error_kind": error_kind,
        },
        settings.llm_job_ttl_s,
    )
    if clear_active_job:
        active = await _get_json(redis, room_active_job_key(job.room_id))
        if active and active.get("job_id") == job.job_id:
            await redis.delete(room_active_job_key(job.room_id))
    return event


async def publish_event(redis: Any, payload: dict[str, Any]) -> None:
    await redis.publish(settings.llm_event_channel, json.dumps(payload, default=str))


async def read_room_llm_state(redis: Any, room_id: str) -> dict[str, Any]:
    status_payload = await _get_json(redis, room_status_key(room_id))
    analysis = await _get_json(redis, room_analysis_key(room_id))
    merged: dict[str, Any] = {}
    if analysis:
        merged["llm_analysis"] = analysis
    if status_payload:
        merged["llm_status"] = status_payload.get("status")
        merged["llm_error"] = status_payload.get("detail") if status_payload.get("status") == "error" else None
        merged["llm_job_id"] = status_payload.get("job_id")
    return merged


async def read_worker_status(redis: Any) -> dict[str, Any] | None:
    return await _get_json(redis, settings.llm_worker_status_key)


async def write_worker_status(redis: Any, payload: dict[str, Any]) -> None:
    await _set_json(redis, settings.llm_worker_status_key, payload, settings.llm_worker_heartbeat_s * 3)


async def queue_depth(redis: Any) -> int:
    try:
        return int(await redis.xlen(settings.llm_job_stream))
    except Exception:
        return 0


async def acquire_job_claim(redis: Any, job_id: str, worker_name: str) -> bool:
    claim_value = json.dumps({"worker": worker_name, "timestamp": utc_now_iso()})
    return bool(
        await redis.set(
            job_claim_key(job_id),
            claim_value,
            ex=settings.llm_worker_claim_ttl_s,
            nx=True,
        )
    )


async def release_job_claim(redis: Any, job_id: str) -> None:
    await redis.delete(job_claim_key(job_id))
