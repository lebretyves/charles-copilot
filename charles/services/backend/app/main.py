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
import pandas as pd  # noqa: F401 — utilisé dans /simulator/control pour pd.notna
from fastapi import Depends, FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel as _BM
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from app.config import settings
from app.models import (
    Alert,
    CaseCreate,
    CaseEvent,
    DrugAdmin,
    FluidBalance,
    MonitoringMessage,
    VitalsFrame,
    WSUpdate,
)
from app.alert_engine import AlertEngine
from app.mqtt_consumer import MQTTConsumer
from app.kb_loader import KnowledgeBase
from app.llm_engine import LLMEngine
from app.scenario_catalog import ScenarioCatalog
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
        self.llm: LLMEngine = LLMEngine()
        self.catalog: ScenarioCatalog = ScenarioCatalog()
        self.rooms: dict[str, dict[str, Any]] = {}  # room_id -> latest data
        self.room_cases: dict[str, str] = {}  # room_id -> case_id actif


state = AppState()


# ── Lifecycle ──────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("CHARLES backend starting...")
    state.redis = aioredis.from_url(settings.redis_url, decode_responses=True)

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
    state.catalog = ScenarioCatalog(metadata_path=metadata_csv, cases_dir=cases_dir)
    state.catalog.load()

    # LLM
    state.llm = LLMEngine(kb=state.kb)
    await state.llm.init()

    # RAG (embeddings KB → nomic-embed-text)
    await state.llm.init_rag(state.kb.data)

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

    yield

    # Shutdown
    if state.mqtt_consumer:
        state.mqtt_consumer.stop()
    await state.llm.close()
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
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins.split(","),
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)


# ── MQTT message handler ──────────────────────────────────────
async def handle_mqtt_message(topic: str, payload: dict):
    """Called by MQTTConsumer for each incoming message."""
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
    if has_critical and state.llm.available:
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


# ── Auth ───────────────────────────────────────────────────────
class LoginRequest(_BM):
    username: str
    password: str

@app.post("/auth/login")
@limiter.limit("5/minute")
async def login(request: Request, req: LoginRequest):
    result = authenticate(req.username, req.password)
    if not result:
        raise HTTPException(status_code=401, detail="Identifiants incorrects")
    return result


@app.get("/auth/me")
async def me(user: dict = Depends(get_current_user)):
    return user


# ── REST endpoints ─────────────────────────────────────────────
@app.get("/health")
async def health():
    failures = db.get_failure_count()
    return {
        "status": "degraded" if failures > 0 else "ok",
        "service": "charles-backend",
        "rooms_active": len(state.rooms),
        "ws_clients": len(state.ws_clients),
        "db_persistence_failures": failures,
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
    return {"status": "ended", "case_id": case_id}


# ── Drug Administrations ──────────────────────────────────────
@app.post("/cases/{case_id}/drugs")
async def add_drug(case_id: str, drug: DrugAdmin, user: dict = Depends(require_role("iade", "mar", "admin"))):
    data = drug.model_dump()
    data["case_id"] = case_id
    result_id = await db.save_drug_admin(data)
    return {"id": result_id, "case_id": case_id}


@app.get("/cases/{case_id}/drugs")
async def get_drugs(case_id: str, user: dict = Depends(require_role("iade", "mar", "admin"))):
    return await db.get_drug_admins(case_id)


# ── Case Events ───────────────────────────────────────────────
@app.post("/cases/{case_id}/events")
async def add_event(case_id: str, event: CaseEvent, user: dict = Depends(require_role("iade", "mar", "admin"))):
    data = event.model_dump()
    data["case_id"] = case_id
    result_id = await db.save_event(data)
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
    result_id = await db.save_fluid(data)
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
    result_id = await db.save_alert_feedback({
        "alert_id": alert_id,
        "case_id": None,  # resolved from alert in DB if needed
        "label": feedback.label,
        "comment": feedback.comment,
    })
    return {"id": result_id, "alert_id": alert_id}


# ── LLM manual trigger ────────────────────────────────────────
@app.post("/rooms/{room_id}/analyze")
async def trigger_llm_analysis(room_id: str, user: dict = Depends(require_role("iade", "mar", "admin"))):
    """Déclenche manuellement une analyse LLM pour une salle."""
    data = state.rooms.get(room_id)
    if not data:
        raise HTTPException(status_code=404, detail="Room not found")
    if not state.llm.available:
        raise HTTPException(status_code=503, detail="LLM not available. Run 'ollama pull llama3.1:8b' or configure OPENAI_API_KEY")

    vitals = VitalsFrame(**data["vitals"])
    alerts = [Alert(**a) for a in data.get("alerts", [])]
    case_id = state.room_cases.get(room_id)
    case_context = await db.get_case(case_id) if case_id else None

    analysis = await state.llm.analyze(vitals, alerts, room_id, case_context)
    if not analysis:
        return {"error": "LLM analysis failed"}

    return analysis.model_dump()


# ── KB info endpoint ───────────────────────────────────────────
@app.get("/kb/status")
async def kb_status(user: dict = Depends(require_role("admin"))):
    return {
        "loaded": state.kb.loaded,
        "files": list(state.kb.data.keys()),
        "llm_available": state.llm.available,
        "llm_provider": state.llm.provider,
    }


# ── Scénarios / Catalogue VitalDB ─────────────────────────────
@app.get("/scenarios/catalog")
async def get_scenario_catalog(user: dict = Depends(require_role("iade", "mar", "admin"))):
    """Catalogue structuré : profils patient, chirurgies, anesthésies..."""
    return state.catalog.get_catalog()


class ScenarioFilter(_BM):
    model_config = {"extra": "allow"}  # accepte tout filtre dynamique


@app.post("/scenarios/search")
async def search_scenarios(filters: ScenarioFilter, user: dict = Depends(require_role("iade", "mar", "admin"))):
    """Recherche de cas VitalDB selon les critères sélectionnés (74 colonnes)."""
    return state.catalog.search_cases(filters.model_dump())


class SimulatorCommand(_BM):
    action: str  # "start_vitaldb" | "start_synthetic" | "stop"
    room_id: str = "salle_1"
    caseid: int | None = None        # pour VitalDB
    scenario: str | None = None      # pour synthétique
    speed: float = 1.0


@app.post("/simulator/control")
async def control_simulator(cmd: SimulatorCommand, user: dict = Depends(require_role("iade", "mar", "admin"))):
    """Envoie une commande de contrôle au simulateur via MQTT."""
    if not state.mqtt_consumer:
        raise HTTPException(status_code=503, detail="MQTT non connecté")

    payload = {
        "action": cmd.action,
        "room_id": cmd.room_id,
        "speed": cmd.speed,
    }
    if cmd.action == "start_vitaldb" and cmd.caseid is not None:
        payload["caseid"] = cmd.caseid
        # Enrichir avec les métadonnées du cas
        if state.catalog.loaded and state.catalog.df is not None:
            row = state.catalog.df[state.catalog.df["caseid"] == cmd.caseid]
            if not row.empty:
                r = row.iloc[0]
                payload["patient_info"] = {
                    "age": int(r["age"]) if pd.notna(r["age"]) else None,
                    "sex": r["sex"] if pd.notna(r["sex"]) else None,
                    "asa": int(r["asa"]) if pd.notna(r["asa"]) else None,
                    "department": r["department"] if pd.notna(r["department"]) else None,
                    "optype": r["optype"] if pd.notna(r["optype"]) else None,
                    "opname": r["opname"] if pd.notna(r["opname"]) else None,
                    "ane_type": r["ane_type"] if pd.notna(r["ane_type"]) else None,
                }
    elif cmd.action == "start_synthetic" and cmd.scenario:
        payload["scenario"] = cmd.scenario

    state.mqtt_consumer.publish("charles/simulator/control", payload)
    return {"status": "sent", "command": payload}


# ── WebSocket ──────────────────────────────────────────────────
@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    # Auth via premier message — le token NE transité PAS dans l'URL (ni logs nginx ni logs uvicorn)
    await ws.accept()
    try:
        raw = await asyncio.wait_for(ws.receive_text(), timeout=5.0)
        auth_msg = json.loads(raw)
    except (asyncio.TimeoutError, json.JSONDecodeError, Exception):
        await ws.close(code=1008, reason="Authentication required")
        return

    if auth_msg.get("type") != "auth":
        await ws.close(code=1008, reason="Auth message expected")
        return

    user = verify_token(auth_msg.get("token", ""))
    if not user:
        await ws.close(code=1008, reason="Invalid token")
        return

    state.ws_clients.add(ws)
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
                if cmd.get("action") == "acknowledge_alert":
                    if user.get("role") in ("iade", "mar", "admin"):
                        await db.acknowledge_alert(cmd["alert_id"], user.get("name", "IADE"))
                elif cmd.get("action") == "request_analysis":
                    rid = cmd.get("room_id")
                    if rid and state.llm.available and user.get("role") in ("iade", "mar", "admin"):
                        room_data = state.rooms.get(rid)
                        if room_data:
                            vitals = VitalsFrame(**room_data["vitals"])
                            alerts_list = [Alert(**a) for a in room_data.get("alerts", [])]
                            case_id = state.room_cases.get(rid)
                            ctx = await db.get_case(case_id) if case_id else None
                            analysis = await state.llm.analyze(vitals, alerts_list, rid, ctx)
                            if analysis:
                                await ws.send_text(json.dumps({
                                    "type": "llm_analysis",
                                    "room_id": rid,
                                    "analysis": analysis.model_dump(),
                                }, default=str))
            except (json.JSONDecodeError, KeyError):
                pass
    except WebSocketDisconnect:
        pass
    finally:
        state.ws_clients.discard(ws)
        logger.info("WS client disconnected (total: %d)", len(state.ws_clients))
