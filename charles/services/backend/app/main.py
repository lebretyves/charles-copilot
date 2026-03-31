"""
CHARLES Backend — FastAPI Application.

Pipeline:  Simulateur → MQTT → mqtt_consumer → Redis + alert_engine + LLM → WebSocket → Tablette
Persistence: PostgreSQL (alerts, cases, drugs, events, fluids, LLM analyses)
KB: 11 YAML files loaded at startup
"""

from __future__ import annotations

import asyncio
import json
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import redis.asyncio as aioredis
from fastapi import Depends, FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel as _BM
from starlette.middleware.trustedhost import TrustedHostMiddleware
try:
    from slowapi import Limiter, _rate_limit_exceeded_handler
    from slowapi.util import get_remote_address
    from slowapi.errors import RateLimitExceeded
    _SLOWAPI_AVAILABLE = True
except ModuleNotFoundError:
    _SLOWAPI_AVAILABLE = False

    class Limiter:  # type: ignore[override]
        def __init__(self, *args: Any, **kwargs: Any):
            pass

        def limit(self, *args: Any, **kwargs: Any):
            def decorator(func):
                return func

            return decorator

    class RateLimitExceeded(Exception):
        pass

    def _rate_limit_exceeded_handler(*args: Any, **kwargs: Any):
        raise HTTPException(status_code=429, detail="Rate limit exceeded")

    def get_remote_address(request: Request) -> str:
        client = getattr(request, "client", None)
        return getattr(client, "host", "local")

from app.config import settings
from app.models import (
    Alert,
    CaseCreate,
    CaseEvent,
    DrugAdmin,
    FluidBalance,
    MonitoringMessage,
    VitalsFrame,
    WaveformChunk,
    WSUpdate,
)
from app.alert_engine import AlertEngine
from app.llm_jobs import (
    build_llm_job,
    enqueue_llm_job,
    queue_depth,
    read_room_llm_state,
    read_worker_status,
    status_event,
)
from app.mqtt_consumer import MQTTConsumer
from app.kb_loader import KnowledgeBase
from app.metrics import MetricsStore
from app.scenario_catalog import ScenarioCatalog
from app.simulator_routes import create_simulator_router
from app import database as db
from app.auth import authenticate, get_current_user, require_role, verify_token

logger = logging.getLogger("charles")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")

limiter = Limiter(key_func=get_remote_address)


# ── State global ───────────────────────────────────────────────
class AppState:
    def __init__(self):
        self.redis: aioredis.Redis | None = None
        self.ws_clients: set[WebSocket] = set()
        self.mqtt_consumer: MQTTConsumer | None = None
        self.alert_engine: AlertEngine = AlertEngine()
        self.kb: KnowledgeBase = KnowledgeBase()
        self.catalog: ScenarioCatalog = ScenarioCatalog()
        self.rooms: dict[str, dict[str, Any]] = {}  # room_id -> latest data
        self.room_cases: dict[str, str] = {}  # room_id -> case_id actif
        self.llm_event_task: asyncio.Task[Any] | None = None
        self.metrics: MetricsStore = MetricsStore()


state = AppState()


# ── Lifecycle ──────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("CHARLES backend starting...")
    if settings.jwt_secret == "charles-dev-secret-2026":
        logger.warning("JWT_SECRET uses the development default. Change it before sharing the stack.")
    state.redis = aioredis.from_url(settings.redis_url, decode_responses=True)
    state.metrics = MetricsStore()

    # KB
    kb_path = Path(settings.kb_path)
    if not kb_path.is_absolute():
        kb_path = Path(__file__).resolve().parent.parent.parent.parent / settings.kb_path
    state.kb = KnowledgeBase(kb_path)
    state.kb.load()

    # Alert engine avec seuils KB
    state.alert_engine = AlertEngine(kb=state.kb)

    # Catalogue scénarios VitalDB
    metadata_csv = Path(settings.vitaldb_metadata)
    cases_dir = Path(settings.vitaldb_cases)
    waveforms_dir = Path(settings.vitaldb_waveforms)
    state.catalog = ScenarioCatalog(
        metadata_path=metadata_csv,
        cases_dir=cases_dir,
        waveforms_dir=waveforms_dir,
    )
    state.catalog.load()

    # LLM

    # RAG (embeddings KB → nomic-embed-text)

    # DB
    await db.init_db()

    # MQTT
    state.mqtt_consumer = MQTTConsumer(
        broker=settings.mqtt_broker,
        port=settings.mqtt_port,
        on_message=handle_mqtt_message,
        username=settings.mqtt_user,
        password=settings.mqtt_password,
    )
    state.mqtt_consumer.start()
    logger.info("MQTT consumer connected to %s:%s", settings.mqtt_broker, settings.mqtt_port)
    if state.redis:
        state.llm_event_task = asyncio.create_task(run_llm_event_listener(), name="charles-llm-event-listener")

    yield

    # Shutdown
    if state.llm_event_task:
        state.llm_event_task.cancel()
        await asyncio.gather(state.llm_event_task, return_exceptions=True)
        state.llm_event_task = None
    if state.mqtt_consumer:
        state.mqtt_consumer.stop()
    await db.close_db()
    if state.redis:
        await state.redis.aclose()
    logger.info("CHARLES backend stopped.")


app = FastAPI(
    title="CHARLES — Copilote IA Vigilance Anesthésique",
    version="0.1.0",
    lifespan=lifespan,
)
app.state.limiter = limiter
if _SLOWAPI_AVAILABLE:
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=settings.trusted_hosts_list,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)


def audit_log(action: str, status: str = "ok", **fields: Any) -> None:
    if not settings.audit_log_enabled:
        return

    parts = [f"{key}={json.dumps(value, default=str, ensure_ascii=True)}" for key, value in fields.items() if value is not None]
    logger.info("AUDIT action=%s status=%s %s", action, status, " ".join(parts))


def llm_unavailable_detail() -> str:
    if settings.llm_provider == "ollama":
        return f"LLM not available. Run 'ollama pull {settings.ollama_model}' or configure OPENAI_API_KEY"
    return "LLM not available. Configure OPENAI_API_KEY or switch LLM_PROVIDER to ollama"


def require_saved_id(result_id: int | None, resource_name: str) -> int:
    if result_id is None:
        raise HTTPException(status_code=503, detail=f"Persistence failed while saving {resource_name}")
    return result_id


async def broadcast_text(message: str) -> None:
    disconnected = set()
    for ws in state.ws_clients:
        try:
            await ws.send_text(message)
        except Exception:
            disconnected.add(ws)
    state.ws_clients -= disconnected


async def broadcast_json(payload: dict[str, Any]) -> None:
    await broadcast_text(json.dumps(payload, default=str))


def build_room_snapshot(
    msg: MonitoringMessage,
    alerts: list[Alert],
    previous_room: dict[str, Any] | None = None,
) -> dict[str, Any]:
    previous = previous_room or {}
    return {
        "vitals": msg.vitals.model_dump(),
        "ventilator": msg.ventilator.model_dump() if msg.ventilator else None,
        "bis": msg.bis.model_dump() if msg.bis else None,
        "aivoc_hypnotic": msg.aivoc_hypnotic.model_dump() if msg.aivoc_hypnotic else None,
        "aivoc_opioid": msg.aivoc_opioid.model_dump() if msg.aivoc_opioid else None,
        "alerts": [alert.model_dump() for alert in alerts],
        "llm_analysis": previous.get("llm_analysis"),
        "llm_status": previous.get("llm_status"),
        "llm_error": previous.get("llm_error"),
        "llm_job_id": previous.get("llm_job_id"),
        "timestamp": msg.timestamp.isoformat(),
        "phase": msg.phase,
        "phase_label": msg.phase_label,
        "macro_phase": msg.macro_phase,
        "elapsed_s": msg.elapsed_s,
        "elapsed_fmt": msg.elapsed_fmt,
        "patient_info": msg.patient_info,
    }


async def apply_llm_status_update(payload: dict[str, Any]) -> None:
    room_id = payload.get("room_id")
    room = state.rooms.get(room_id) if room_id else None
    if room is not None:
        room["llm_status"] = payload.get("status")
        room["llm_error"] = payload.get("detail") if payload.get("status") == "error" else None
        room["llm_job_id"] = payload.get("job_id")
    await broadcast_json(payload)


async def apply_llm_analysis_update(payload: dict[str, Any]) -> None:
    room_id = payload.get("room_id")
    room = state.rooms.get(room_id) if room_id else None
    if room is not None:
        room["llm_analysis"] = payload.get("analysis")
        room["llm_status"] = "completed"
        room["llm_error"] = None
        room["llm_job_id"] = payload.get("job_id")
    await broadcast_json(payload)


async def apply_llm_error_update(payload: dict[str, Any]) -> None:
    room_id = payload.get("room_id")
    room = state.rooms.get(room_id) if room_id else None
    if room is not None:
        room["llm_status"] = "error"
        room["llm_error"] = payload.get("detail")
        room["llm_job_id"] = payload.get("job_id")
    await broadcast_json(payload)


async def handle_llm_worker_event(payload: dict[str, Any]) -> None:
    event_type = payload.get("type")
    if event_type == "llm_analysis_status":
        await apply_llm_status_update(payload)
        return
    if event_type == "llm_analysis":
        state.metrics.incr("llm_completed_total")
        state.metrics.mark("last_llm_completed_at")
        analysis = payload.get("analysis") or {}
        state.metrics.observe_llm_latency(analysis.get("latency_ms"))
        await apply_llm_analysis_update(payload)
        return
    if event_type == "llm_analysis_error":
        state.metrics.incr("llm_failures_total")
        if payload.get("error_kind") == "timeout":
            state.metrics.incr("llm_timeouts_total")
        state.metrics.mark("last_llm_error_at")
        await apply_llm_error_update(payload)


async def run_llm_event_listener() -> None:
    if not state.redis:
        return
    pubsub = state.redis.pubsub()
    await pubsub.subscribe(settings.llm_event_channel)
    try:
        async for message in pubsub.listen():
            if message.get("type") != "message":
                continue
            raw = message.get("data")
            if isinstance(raw, bytes):
                raw = raw.decode()
            try:
                payload = json.loads(raw)
            except (TypeError, json.JSONDecodeError):
                continue
            await handle_llm_worker_event(payload)
    except asyncio.CancelledError:
        raise
    finally:
        await pubsub.unsubscribe(settings.llm_event_channel)
        await pubsub.aclose()


async def enqueue_llm_analysis_for_room(
    room_id: str,
    vitals: VitalsFrame,
    alerts: list[Alert],
    case_id: str | None,
    trigger_type: str,
    patient_info: dict[str, Any] | None = None,
    requested_by: str | None = None,
) -> dict[str, Any]:
    if not state.redis:
        raise HTTPException(status_code=503, detail="Redis not available for LLM queue")

    job = build_llm_job(
        room_id=room_id,
        vitals=vitals,
        alerts=alerts,
        case_id=case_id,
        trigger_type=trigger_type,
        patient_info=patient_info,
        requested_by=requested_by,
    )
    result = await enqueue_llm_job(state.redis, job)
    if not result.get("deduplicated"):
        state.metrics.incr("llm_requests_total")
        await apply_llm_status_update(status_event(job=job, status="queued"))
    return result


async def get_llm_runtime_status() -> dict[str, Any]:
    worker_status: dict[str, Any] = {}
    queue_len = 0
    if state.redis:
        worker_status = await read_worker_status(state.redis) or {}
        queue_len = await queue_depth(state.redis)
    return {
        "llm_worker_online": bool(worker_status),
        "llm_available": bool(worker_status.get("available")),
        "llm_provider": worker_status.get("provider", settings.llm_provider),
        "llm_model": worker_status.get("model", settings.ollama_model if settings.llm_provider == "ollama" else settings.openai_model),
        "llm_worker_detail": worker_status.get("detail"),
        "llm_worker_timestamp": worker_status.get("timestamp"),
        "llm_queue_depth": queue_len,
    }


# ── MQTT message handler ──────────────────────────────────────
async def _legacy_blocking_handle_mqtt_message(topic: str, payload: dict):
    """Legacy handler kept only for reference; the non-blocking handler is used."""
    # Routage waveforms vs vitals
    if topic.endswith("/waves"):
        await handle_wave_message(topic, payload)
        return

    try:
        msg = MonitoringMessage(**payload)
    except Exception as e:
        logger.warning("Invalid MQTT message: %s", e)
        return

    room_id = msg.room_id

    # 1. Cache dans Redis (TTL 30s)
    if state.redis:
        await state.redis.setex(
            f"charles:room:{room_id}:latest",
            30,
            json.dumps(payload, default=str),
        )

    # 2. Alertes
    alerts = state.alert_engine.evaluate(msg)

    # 3. Persister les alertes en DB
    case_id = state.room_cases.get(room_id)
    for alert in alerts:
        await db.save_alert({
            "case_id": case_id,
            "room_id": room_id,
            "timestamp": alert.timestamp,
            "level": alert.level,
            "rule_id": alert.rule_id,
            "title": alert.title,
            "detail": alert.detail,
            "parameters": json.dumps(alert.parameters),
        })

    # 4. LLM sur alertes critiques (async, non-bloquant)
    llm_analysis = None
    has_critical = any(a.level == "critical" for a in alerts)
    if has_critical and getattr(getattr(state, "llm", None), "available", False):
        case_context = None
        if case_id:
            case_context = await db.get_case(case_id)
        llm_analysis = await state.llm.analyze(
            vitals=msg.vitals,
            alerts=alerts,
            room_id=room_id,
            case_context=case_context,
        )
        # Persister l'analyse LLM
        if llm_analysis and case_id:
            await db.save_llm_analysis({
                "case_id": case_id,
                "trigger_type": "alert",
                "model": llm_analysis.model,
                "prompt_tokens": llm_analysis.prompt_tokens,
                "completion_tokens": llm_analysis.completion_tokens,
                "latency_ms": llm_analysis.latency_ms,
                "analysis": json.dumps({
                    "situation": llm_analysis.situation,
                    "risks": llm_analysis.risks,
                    "recommendations": llm_analysis.recommendations,
                    "confidence": llm_analysis.confidence,
                }),
            })

    # 5. Stocker en mémoire
    state.rooms[room_id] = {
        "vitals": msg.vitals.model_dump(),
        "ventilator": msg.ventilator.model_dump() if msg.ventilator else None,
        "bis": msg.bis.model_dump() if msg.bis else None,
        "aivoc_hypnotic": msg.aivoc_hypnotic.model_dump() if msg.aivoc_hypnotic else None,
        "aivoc_opioid": msg.aivoc_opioid.model_dump() if msg.aivoc_opioid else None,
        "alerts": [a.model_dump() for a in alerts],
        "llm_analysis": llm_analysis.model_dump() if llm_analysis else None,
        "timestamp": msg.timestamp.isoformat(),
        # ── Phase ──
        "phase": msg.phase,
        "phase_label": msg.phase_label,
        "macro_phase": msg.macro_phase,
        "elapsed_s": msg.elapsed_s,
        "elapsed_fmt": msg.elapsed_fmt,
        "patient_info": msg.patient_info,
    }

    # 6. Push WebSocket à tous les clients
    ws_update = WSUpdate(
        room_id=room_id,
        vitals=msg.vitals,
        ventilator=msg.ventilator,
        bis=msg.bis,
        aivoc_hypnotic=msg.aivoc_hypnotic,
        aivoc_opioid=msg.aivoc_opioid,
        alerts=alerts,
        llm_analysis=llm_analysis,
        timestamp=msg.timestamp,
        # ── Phase ──
        phase=msg.phase,
        phase_label=msg.phase_label,
        macro_phase=msg.macro_phase,
        elapsed_s=msg.elapsed_s,
        elapsed_fmt=msg.elapsed_fmt,
        patient_info=msg.patient_info,
    )

    payload_str = ws_update.model_dump_json()
    disconnected = set()
    for ws in state.ws_clients:
        try:
            await ws.send_text(payload_str)
        except Exception:
            disconnected.add(ws)
    state.ws_clients -= disconnected


# ── MQTT waveform handler ──────────────────────────────────────
async def handle_mqtt_message(topic: str, payload: dict):
    """Latest non-blocking handler used by the MQTT consumer."""
    if topic.endswith("/waves"):
        await handle_wave_message(topic, payload)
        return

    try:
        msg = MonitoringMessage(**payload)
    except Exception as e:
        logger.warning("Invalid MQTT message: %s", e)
        return

    room_id = msg.room_id
    state.metrics.incr("monitoring_updates_total")
    state.metrics.mark("last_monitoring_update_at", msg.timestamp.isoformat())

    if state.redis:
        await state.redis.setex(
            f"charles:room:{room_id}:latest",
            30,
            json.dumps(payload, default=str),
        )

    alerts = state.alert_engine.evaluate(msg)
    state.metrics.incr("alerts_total", len(alerts))
    state.metrics.incr("critical_alerts_total", sum(1 for alert in alerts if alert.level == "critical"))
    case_id = state.room_cases.get(room_id)
    for alert in alerts:
        await db.save_alert({
            "case_id": case_id,
            "room_id": room_id,
            "timestamp": alert.timestamp,
            "level": alert.level,
            "rule_id": alert.rule_id,
            "title": alert.title,
            "detail": alert.detail,
            "parameters": json.dumps(alert.parameters),
        })

    previous_room = state.rooms.get(room_id)
    if state.redis and (
        previous_room is None
        or (previous_room.get("llm_analysis") is None and previous_room.get("llm_status") is None)
    ):
        previous_room = {
            **(previous_room or {}),
            **(await read_room_llm_state(state.redis, room_id)),
        }
    state.rooms[room_id] = build_room_snapshot(msg, alerts, previous_room)

    ws_update = WSUpdate(
        room_id=room_id,
        vitals=msg.vitals,
        ventilator=msg.ventilator,
        bis=msg.bis,
        aivoc_hypnotic=msg.aivoc_hypnotic,
        aivoc_opioid=msg.aivoc_opioid,
        alerts=alerts,
        llm_analysis=None,
        timestamp=msg.timestamp,
        phase=msg.phase,
        phase_label=msg.phase_label,
        macro_phase=msg.macro_phase,
        elapsed_s=msg.elapsed_s,
        elapsed_fmt=msg.elapsed_fmt,
        patient_info=msg.patient_info,
    )
    await broadcast_text(ws_update.model_dump_json())

    if any(alert.level == "critical" for alert in alerts):
        try:
            await enqueue_llm_analysis_for_room(
                room_id=room_id,
                vitals=msg.vitals,
                alerts=alerts,
                case_id=case_id,
                trigger_type="alert",
                patient_info=msg.patient_info,
            )
        except HTTPException:
            logger.warning("Unable to queue LLM analysis for room %s", room_id)


_wave_fwd_count: int = 0

async def handle_wave_message(topic: str, payload: dict):
    """Reçoit un chunk waveform HF et le broadcast aux clients WS."""
    global _wave_fwd_count
    room_id = payload.get("room_id")
    if not room_id:
        logger.warning("[WAVES] chunk sans room_id sur %s", topic)
        return

    _wave_fwd_count += 1
    state.metrics.incr("wave_chunks_total")
    state.metrics.mark("last_wave_chunk_at")
    if _wave_fwd_count <= 3 or _wave_fwd_count % 100 == 0:
        logger.info("[WAVES] forward #%d room=%s clients=%d", _wave_fwd_count, room_id, len(state.ws_clients))

    ws_msg = json.dumps({
        "type": "wave_chunk",
        "room_id": room_id,
        "t": payload.get("t", 0),
        "ecg":   payload.get("ecg"),
        "pleth": payload.get("pleth"),
        "art":   payload.get("art"),
        "co2":   payload.get("co2"),
        "awp":   payload.get("awp"),
        "eeg":   payload.get("eeg"),
    })
    disconnected = set()
    for ws in state.ws_clients:
        try:
            await ws.send_text(ws_msg)
        except Exception:
            disconnected.add(ws)
    state.ws_clients -= disconnected


# ── Auth ───────────────────────────────────────────────────────
class LoginRequest(_BM):
    username: str
    password: str

@app.post("/auth/login")
@limiter.limit("5/minute")
async def login(request: Request):
    raw = await request.body()
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, ValueError):
        raise HTTPException(status_code=422, detail="JSON body required")
    username = data.get("username", "")
    password = data.get("password", "")
    if not username or not password:
        raise HTTPException(status_code=422, detail="username and password required")
    result = authenticate(username, password)
    if not result:
        state.metrics.incr("auth_login_failed_total")
        audit_log("auth.login", status="rejected", username=username, client=get_remote_address(request))
        raise HTTPException(status_code=401, detail="Identifiants incorrects")
    state.metrics.incr("auth_login_success_total")
    state.metrics.mark("last_auth_login_at")
    audit_log("auth.login", username=username, role=result["role"], client=get_remote_address(request))
    return result


@app.get("/auth/me")
async def me(user: dict = Depends(get_current_user)):
    return user


# ── REST endpoints ─────────────────────────────────────────────
@app.get("/health")
async def health():
    failures = db.get_failure_count()
    metrics = state.metrics.snapshot()
    llm_runtime = await get_llm_runtime_status()
    return {
        "status": "degraded" if failures > 0 else "ok",
        "service": "charles-backend",
        "app_env": settings.app_env,
        "frontend_public_url": settings.frontend_public_url,
        "rooms_active": len(state.rooms),
        "ws_clients": len(state.ws_clients),
        "db_persistence_failures": failures,
        "data_scope": "public_anonymized_waveforms",
        "uptime_s": metrics["uptime_s"],
        "last_monitoring_update_at": metrics.get("last_monitoring_update_at"),
        "last_wave_chunk_at": metrics.get("last_wave_chunk_at"),
        **llm_runtime,
    }


@app.get("/metrics")
async def metrics(user: dict = Depends(require_role("admin", "mar", "iade"))):
    llm_runtime = await get_llm_runtime_status()
    return {
        **state.metrics.snapshot(),
        "rooms_active": len(state.rooms),
        "ws_clients": len(state.ws_clients),
        "db_persistence_failures": db.get_failure_count(),
        "data_scope": "public_anonymized_waveforms",
        **llm_runtime,
    }


@app.get("/rooms")
async def list_rooms(user: dict = Depends(require_role("iade", "mar", "admin"))):
    """Liste des salles actives avec dernières valeurs."""
    return {
        room_id: {
            "vitals": data["vitals"],
            "alerts_count": len(data.get("alerts", [])),
            "has_critical": any(
                a.get("level") == "critical" for a in data.get("alerts", [])
            ),
            "timestamp": data["timestamp"],
        }
        for room_id, data in state.rooms.items()
    }


@app.get("/rooms/{room_id}")
async def get_room(room_id: str, user: dict = Depends(require_role("iade", "mar", "admin"))):
    """Détail complet d'une salle."""
    data = state.rooms.get(room_id)
    if not data:
        raise HTTPException(status_code=404, detail="Room not found")
    return data


@app.get("/rooms/{room_id}/alerts")
async def get_room_alerts(room_id: str, user: dict = Depends(require_role("iade", "mar", "admin"))):
    """Alertes actives pour une salle."""
    data = state.rooms.get(room_id)
    if not data:
        raise HTTPException(status_code=404, detail="Room not found")
    return data.get("alerts", [])


# ── CRUD Cases ─────────────────────────────────────────────────
@app.post("/cases")
async def create_case(case: CaseCreate, user: dict = Depends(require_role("iade", "mar", "admin"))):
    """Créer un nouveau cas opératoire."""
    result = await db.create_case(case.model_dump())
    # Associer la salle au cas
    state.room_cases[case.room_id] = result["case_id"]
    audit_log("case.create", user=user.get("sub"), role=user.get("role"), case_id=result["case_id"], room_id=case.room_id)
    return result


@app.get("/cases")
async def list_cases(
    room_id: str | None = None,
    status: str | None = None,
    limit: int = 50,
    user: dict = Depends(require_role("iade", "mar", "admin")),
):
    return await db.list_cases(limit=limit, room_id=room_id, status=status)


@app.get("/cases/{case_id}")
async def get_case(case_id: str, user: dict = Depends(require_role("iade", "mar", "admin"))):
    result = await db.get_case(case_id)
    if not result:
        raise HTTPException(status_code=404, detail="Case not found")
    return result


@app.put("/cases/{case_id}/end")
async def end_case(
    case_id: str,
    user: dict = Depends(require_role("mar", "admin")),
):
    ok = await db.end_case(case_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Case not found or already ended")
    # Retirer l'association salle
    state.room_cases = {k: v for k, v in state.room_cases.items() if v != case_id}
    audit_log("case.end", user=user.get("sub"), role=user.get("role"), case_id=case_id)
    return {"status": "ended", "case_id": case_id}


# ── Drug Administrations ──────────────────────────────────────
@app.post("/cases/{case_id}/drugs")
async def add_drug(case_id: str, drug: DrugAdmin, user: dict = Depends(require_role("iade", "mar", "admin"))):
    data = drug.model_dump()
    data["case_id"] = case_id
    result_id = require_saved_id(await db.save_drug_admin(data), "drug administration")
    audit_log("case.drug.add", user=user.get("sub"), role=user.get("role"), case_id=case_id, record_id=result_id, drug_name=drug.drug_name)
    return {"id": result_id, "case_id": case_id}


@app.get("/cases/{case_id}/drugs")
async def get_drugs(case_id: str, user: dict = Depends(require_role("iade", "mar", "admin"))):
    return await db.get_drug_admins(case_id)


# ── Case Events ───────────────────────────────────────────────
@app.post("/cases/{case_id}/events")
async def add_event(case_id: str, event: CaseEvent, user: dict = Depends(require_role("iade", "mar", "admin"))):
    data = event.model_dump()
    data["case_id"] = case_id
    result_id = require_saved_id(await db.save_event(data), "case event")
    audit_log("case.event.add", user=user.get("sub"), role=user.get("role"), case_id=case_id, record_id=result_id, event_type=event.event_type)
    return {"id": result_id, "case_id": case_id}


@app.get("/cases/{case_id}/events")
async def get_events(case_id: str, user: dict = Depends(require_role("iade", "mar", "admin"))):
    return await db.get_events(case_id)


# ── LLM Analyses per case ─────────────────────────────────────
@app.get("/cases/{case_id}/llm")
async def get_llm_analyses(
    case_id: str,
    user: dict = Depends(require_role("mar", "admin")),
):
    return await db.get_llm_analyses(case_id)


# ── Fluid Balance ─────────────────────────────────────────────
@app.post("/cases/{case_id}/fluids")
async def add_fluid(case_id: str, fluid: FluidBalance, user: dict = Depends(require_role("iade", "mar", "admin"))):
    data = {
        "case_id": case_id,
        "type": fluid.type,
        "category": fluid.category,
        "volume_ml": fluid.volume_ml,
        "product_name": fluid.product_name,
    }
    result_id = require_saved_id(await db.save_fluid(data), "fluid balance")
    audit_log("case.fluid.add", user=user.get("sub"), role=user.get("role"), case_id=case_id, record_id=result_id, direction=fluid.type, volume_ml=fluid.volume_ml)
    return {"id": result_id, "case_id": case_id}


@app.get("/cases/{case_id}/fluids")
async def get_fluids(case_id: str, user: dict = Depends(require_role("iade", "mar", "admin"))):
    return await db.get_fluid_balance(case_id)


# ── Alert management ──────────────────────────────────────────
@app.get("/alerts")
async def list_alerts(
    room_id: str | None = None,
    case_id: str | None = None,
    level: str | None = None,
    limit: int = 100,
    user: dict = Depends(require_role("mar", "admin")),
):
    return await db.get_alerts(case_id=case_id, room_id=room_id, level=level, limit=limit)


@app.put("/alerts/{alert_id}/acknowledge")
async def acknowledge_alert(alert_id: int, acknowledged_by: str = "IADE", user: dict = Depends(require_role("iade", "mar", "admin"))):
    ok = await db.acknowledge_alert(alert_id, acknowledged_by)
    if not ok:
        raise HTTPException(status_code=404, detail="Alert not found or already acknowledged")
    state.metrics.incr("manual_alert_ack_total")
    audit_log("alert.acknowledge", user=user.get("sub"), role=user.get("role"), alert_id=alert_id, acknowledged_by=acknowledged_by)
    return {"status": "acknowledged", "alert_id": alert_id}


# ── Alert Feedback (for ML training) ──────────────────────────
class AlertFeedbackRequest(_BM):
    label: str  # true_positive, false_positive, missed
    comment: str | None = None


@app.post("/alerts/{alert_id}/feedback")
async def submit_alert_feedback(
    alert_id: int,
    feedback: AlertFeedbackRequest,
    user: dict = Depends(get_current_user),
):
    result_id = require_saved_id(await db.save_alert_feedback({
        "alert_id": alert_id,
        "case_id": None,  # resolved from alert in DB if needed
        "label": feedback.label,
        "comment": feedback.comment,
    }), "alert feedback")
    audit_log("alert.feedback", user=user.get("sub"), role=user.get("role"), alert_id=alert_id, record_id=result_id, label=feedback.label)
    return {"id": result_id, "alert_id": alert_id}


# ── LLM manual trigger ────────────────────────────────────────
@app.post("/rooms/{room_id}/analyze")
async def trigger_llm_analysis(room_id: str, user: dict = Depends(require_role("iade", "mar", "admin"))):
    """Déclenche manuellement une analyse LLM pour une salle."""
    data = state.rooms.get(room_id)
    if not data:
        raise HTTPException(status_code=404, detail="Room not found")
    vitals = VitalsFrame(**data["vitals"])
    alerts = [Alert(**a) for a in data.get("alerts", [])]
    case_id = state.room_cases.get(room_id)
    job = await enqueue_llm_analysis_for_room(
        room_id=room_id,
        vitals=vitals,
        alerts=alerts,
        case_id=case_id,
        trigger_type="manual",
        patient_info=data.get("patient_info"),
        requested_by=user.get("sub"),
    )
    audit_log(
        "llm.analyze.manual",
        user=user.get("sub"),
        role=user.get("role"),
        room_id=room_id,
        case_id=case_id,
        job_id=job.get("job_id"),
        deduplicated=job.get("deduplicated"),
    )
    return job


# ── KB info endpoint ───────────────────────────────────────────
@app.get("/kb/status")
async def kb_status(user: dict = Depends(require_role("admin"))):
    llm_runtime = await get_llm_runtime_status()
    return {
        "loaded": state.kb.loaded,
        "files": list(state.kb.data.keys()),
        "llm_available": llm_runtime["llm_available"],
        "llm_provider": llm_runtime["llm_provider"],
        "llm_model": llm_runtime["llm_model"],
        "llm_worker_online": llm_runtime["llm_worker_online"],
        "llm_worker_detail": llm_runtime["llm_worker_detail"],
    }


app.include_router(
    create_simulator_router(
        state=state,
        audit_log=audit_log,
        require_role_factory=require_role,
    )
)

# ── WebSocket ──────────────────────────────────────────────────
@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    # Auth via premier message — le token NE transité PAS dans l'URL (ni logs nginx ni logs uvicorn)
    await ws.accept()
    user = None
    try:
        raw = await asyncio.wait_for(ws.receive_text(), timeout=5.0)
        auth_msg = json.loads(raw)
    except (asyncio.TimeoutError, json.JSONDecodeError, Exception):
        audit_log("ws.connect", status="rejected", reason="missing_or_invalid_auth_message")
        await ws.close(code=1008, reason="Authentication required")
        return

    if auth_msg.get("type") != "auth":
        audit_log("ws.connect", status="rejected", reason="auth_message_expected")
        await ws.close(code=1008, reason="Auth message expected")
        return

    user = verify_token(auth_msg.get("token", ""))
    if not user:
        audit_log("ws.connect", status="rejected", reason="invalid_token")
        await ws.close(code=1008, reason="Invalid token")
        return

    state.ws_clients.add(ws)
    state.metrics.incr("ws_connections_total")
    audit_log("ws.connect", user=user.get("sub"), role=user.get("role"), clients=len(state.ws_clients))
    logger.info("WS client connected (total: %d)", len(state.ws_clients))

    # Envoyer l'état initial de toutes les salles
    try:
        await ws.send_text(json.dumps({
            "type": "init",
            "rooms": {
                rid: data for rid, data in state.rooms.items()
            },
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }, default=str))
    except Exception:
        pass

    try:
        while True:
            raw = await ws.receive_text()
            # Commandes depuis le frontend
            try:
                cmd = json.loads(raw)
                state.metrics.incr("ws_commands_total")
                if cmd.get("action") == "acknowledge_alert":
                    if user.get("role") in ("iade", "mar", "admin"):
                        await db.acknowledge_alert(cmd["alert_id"], user.get("name", "IADE"))
                        state.metrics.incr("manual_alert_ack_total")
                        audit_log("ws.alert.acknowledge", user=user.get("sub"), role=user.get("role"), alert_id=cmd["alert_id"])
                elif cmd.get("action") == "request_analysis":
                    rid = cmd.get("room_id")
                    if rid and user.get("role") in ("iade", "mar", "admin"):
                        room_data = state.rooms.get(rid)
                        if room_data:
                            vitals = VitalsFrame(**room_data["vitals"])
                            alerts_list = [Alert(**a) for a in room_data.get("alerts", [])]
                            case_id = state.room_cases.get(rid)
                            job = await enqueue_llm_analysis_for_room(
                                room_id=rid,
                                vitals=vitals,
                                alerts=alerts_list,
                                case_id=case_id,
                                trigger_type="manual",
                                patient_info=room_data.get("patient_info"),
                                requested_by=user.get("sub"),
                            )
                            audit_log(
                                "ws.llm.analyze",
                                user=user.get("sub"),
                                role=user.get("role"),
                                room_id=rid,
                                case_id=case_id,
                                job_id=job.get("job_id"),
                                deduplicated=job.get("deduplicated"),
                            )
            except (json.JSONDecodeError, KeyError):
                pass
    except WebSocketDisconnect:
        pass
    finally:
        state.ws_clients.discard(ws)
        state.metrics.incr("ws_disconnects_total")
        audit_log("ws.disconnect", user=user.get("sub") if isinstance(user, dict) else None, clients=len(state.ws_clients))
        logger.info("WS client disconnected (total: %d)", len(state.ws_clients))
