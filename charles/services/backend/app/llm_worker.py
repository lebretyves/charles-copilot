from __future__ import annotations

import asyncio
import json
import logging
import os
from pathlib import Path
from typing import Any

import redis.asyncio as aioredis

from app import database as db
from app.config import settings
from app.kb_loader import KnowledgeBase
from app.llm_engine import LLMEngine
from app.llm_jobs import (
    LLMJob,
    acquire_job_claim,
    analysis_payload,
    mark_job_status,
    parse_llm_job,
    publish_event,
    queue_depth,
    release_job_claim,
    status_event,
    store_job_error,
    store_job_result,
    worker_status_payload,
    write_worker_status,
)

logger = logging.getLogger("charles.llm_worker")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")

HEARTBEAT_FILE = Path("/tmp/llm-worker.hb")


async def _save_analysis(job: LLMJob, analysis: Any) -> None:
    if not job.case_id:
        return
    result_id = await db.save_llm_analysis({
        "case_id": job.case_id,
        "trigger_type": job.trigger_type,
        "model": analysis.model,
        "prompt_tokens": analysis.prompt_tokens,
        "completion_tokens": analysis.completion_tokens,
        "latency_ms": analysis.latency_ms,
        "analysis": json.dumps(analysis_payload(analysis)),
    })
    if result_id is None:
        raise RuntimeError("Persistence failed while saving llm analysis")


async def _heartbeat_loop(redis: Any, llm: LLMEngine, consumer_name: str) -> None:
    while True:
        payload = worker_status_payload(
            consumer_name=consumer_name,
            available=llm.available,
            provider=llm.provider,
            model=llm.ollama_model if llm.provider == "ollama" else llm.openai_model,
            detail=None if llm.available else "LLM provider unavailable",
        )
        await write_worker_status(redis, payload)
        HEARTBEAT_FILE.parent.mkdir(parents=True, exist_ok=True)
        HEARTBEAT_FILE.touch()
        await asyncio.sleep(settings.llm_worker_heartbeat_s)


async def _requeue_job(redis: Any, job: LLMJob, *, detail: str) -> None:
    retry_job = job.model_copy(update={"attempt": job.attempt + 1, "status": "queued"})
    await mark_job_status(redis, retry_job, "queued", detail=detail)
    await redis.xadd(
        settings.llm_job_stream,
        {"payload": retry_job.model_dump_json()},
        maxlen=settings.llm_job_stream_maxlen,
        approximate=True,
    )
    await publish_event(redis, status_event(job=retry_job, status="queued", detail=detail))


async def _process_job(redis: Any, llm: LLMEngine, consumer_name: str, entry_id: str, fields: dict[str, Any]) -> None:
    payload = fields.get("payload")
    if not payload:
        await redis.xdel(settings.llm_job_stream, entry_id)
        return

    try:
        job = parse_llm_job(payload)
    except Exception:
        logger.exception("Invalid LLM job payload: %s", payload)
        await redis.xdel(settings.llm_job_stream, entry_id)
        return

    if not await acquire_job_claim(redis, job.job_id, consumer_name):
        return

    try:
        job_state_raw = await redis.get(f"charles:llm:job:{job.job_id}")
        if job_state_raw:
            try:
                job_state = json.loads(job_state_raw)
            except json.JSONDecodeError:
                job_state = {}
            if job_state.get("status") == "completed":
                await redis.xdel(settings.llm_job_stream, entry_id)
                return

        await mark_job_status(redis, job, "running")
        await publish_event(redis, status_event(job=job, status="running"))

        if not llm.available:
            raise RuntimeError("LLM unavailable")

        case_context = await db.get_case(job.case_id) if job.case_id else None
        analysis = await asyncio.wait_for(
            llm.analyze(
                vitals=job.vitals,
                alerts=job.alerts,
                room_id=job.room_id,
                case_context=case_context,
            ),
            timeout=settings.llm_analysis_timeout_s,
        )
        if not analysis:
            raise RuntimeError("LLM analysis unavailable")

        await _save_analysis(job, analysis)
        event = await store_job_result(redis, job, analysis)
        await publish_event(redis, event)
        logger.info("LLM job completed room=%s job_id=%s attempt=%s", job.room_id, job.job_id, job.attempt)
        await redis.xdel(settings.llm_job_stream, entry_id)
    except asyncio.TimeoutError:
        if job.attempt < settings.llm_worker_max_retries:
            detail = f"Retry scheduled after timeout ({job.attempt + 1}/{settings.llm_worker_max_retries + 1})"
            await _requeue_job(redis, job, detail=detail)
        else:
            event = await store_job_error(redis, job, "LLM analysis timed out", "timeout")
            await publish_event(redis, event)
        await redis.xdel(settings.llm_job_stream, entry_id)
    except Exception as exc:
        logger.exception("LLM job failed room=%s job_id=%s", job.room_id, job.job_id)
        detail = str(exc) or "LLM analysis failed"
        error_kind = "unavailable" if "unavailable" in detail.lower() else "failure"
        if error_kind == "failure" and job.attempt < settings.llm_worker_max_retries:
            retry_detail = f"Retry scheduled after failure ({job.attempt + 1}/{settings.llm_worker_max_retries + 1})"
            await _requeue_job(redis, job, detail=retry_detail)
        else:
            event = await store_job_error(redis, job, detail, error_kind)
            await publish_event(redis, event)
        await redis.xdel(settings.llm_job_stream, entry_id)
    finally:
        await release_job_claim(redis, job.job_id)


async def _worker_loop(redis: Any, llm: LLMEngine, consumer_name: str) -> None:
    while True:
        messages = await redis.xread(
            {settings.llm_job_stream: "0-0"},
            count=1,
            block=settings.llm_worker_poll_block_ms,
        )
        if not messages:
            continue
        for _stream_name, entries in messages:
            for entry_id, fields in entries:
                await _process_job(redis, llm, consumer_name, entry_id, fields)


async def _run() -> None:
    redis = aioredis.from_url(settings.redis_url, decode_responses=True)
    consumer_name = f"charles-llm-worker-{os.getpid()}"
    kb_path = Path(settings.kb_path)
    if not kb_path.is_absolute():
        kb_path = Path(__file__).resolve().parent.parent.parent.parent / settings.kb_path
    kb = KnowledgeBase(kb_path)
    kb.load()

    llm = LLMEngine(kb=kb)
    await llm.init()
    await llm.init_rag(kb.data)
    await db.init_db()

    heartbeat_task = asyncio.create_task(_heartbeat_loop(redis, llm, consumer_name), name="charles-llm-worker-heartbeat")
    logger.info("LLM worker ready queue_depth=%s", await queue_depth(redis))

    try:
        await _worker_loop(redis, llm, consumer_name)
    finally:
        heartbeat_task.cancel()
        await asyncio.gather(heartbeat_task, return_exceptions=True)
        await llm.close()
        await db.close_db()
        await redis.aclose()


def main() -> None:
    asyncio.run(_run())


if __name__ == "__main__":
    main()
