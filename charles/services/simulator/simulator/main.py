"""
CHARLES — Simulateur clinique peropératoire.

Rejoue exclusivement des données réelles VitalDB avec historique complet.
Publie sur MQTT topic `bloc/{room_id}/full` avec données patient réelles.
"""

from __future__ import annotations

import json
import logging
import os
import random
import time
from pathlib import Path

import paho.mqtt.client as mqtt

from simulator.vitaldb_support import load_vitaldb_patient_info

logging.basicConfig(level=logging.INFO, format="%(asctime)s [SIMULATOR] %(message)s")
logger = logging.getLogger("charles.simulator")


def _read_secret_env(name: str, file_name: str) -> str:
    direct = os.getenv(name, "")
    if direct:
        return direct

    file_path = os.getenv(file_name, "")
    if not file_path:
        return ""

    try:
        return Path(file_path).read_text(encoding="utf-8").strip()
    except OSError as exc:
        logger.warning("Unable to read %s from %s: %s", name, file_path, exc)
        return ""


MQTT_BROKER = os.getenv("MQTT_BROKER", "localhost")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))
MQTT_USER = os.getenv("MQTT_USER", "")
MQTT_PASSWORD = _read_secret_env("MQTT_PASSWORD", "MQTT_PASSWORD_FILE")

CONTROL_TOPIC = "charles/simulator/control"
EVENT_TOPIC = "charles/simulator/events"
VITALDB_DIR = os.getenv("VITALDB_DIR", "/data/vitaldb/cases")
VITALDB_DEFAULT_ROOMS = os.getenv("VITALDB_DEFAULT_ROOMS", "salle_1:1,salle_2:2,salle_3:3")


def parse_default_rooms(default_rooms: str) -> list[tuple[str, int]]:
    rooms: list[tuple[str, int]] = []
    for item in default_rooms.split(","):
        item = item.strip()
        if not item:
            continue
        if ":" not in item:
            logger.warning("Ignoré default room config invalide : %s", item)
            continue
        room_id, caseid_text = item.split(":", 1)
        try:
            rooms.append((room_id.strip(), int(caseid_text.strip())))
        except ValueError:
            logger.warning("Ignoré default room caseid invalide : %s", item)
    return rooms


def start_default_vitaldb_rooms(controller: "SimulatorController") -> None:
    default_rooms = parse_default_rooms(VITALDB_DEFAULT_ROOMS)
    if not default_rooms:
        return

    logger.info("Démarrage automatique des salles VitalDB : %s", VITALDB_DEFAULT_ROOMS)
    for room_id, caseid in default_rooms:
        controller.start_vitaldb(room_id, caseid, with_waveforms=True)

# ══════════════════════════════════════════════════════════════
#  SIMULATEUR VITALDB UNIQUEMENT
# ══════════════════════════════════════════════════════════════

class SimulatorController:
    """Contrôleur VitalDB : gère uniquement les replays de données réelles."""

    def __init__(self, mqtt_client: mqtt.Client):
        self.client = mqtt_client
        self.vitaldb_threads: dict[str, dict] = {}  # room_id → {"stop": Event}
        self._lock = __import__("threading").Lock()

    def _stop_wave_thread(self, room_id: str):
        """Arrête un éventuel thread de waveforms sur cette salle."""
        # Implémentation temporaire - peut être étendue plus tard
        pass

    def _stop_vitaldb(self, room_id: str):
        """Arrête un éventuel replay VitalDB sur cette salle."""
        info = self.vitaldb_threads.pop(room_id, None)
        if info:
            info["stop"].set()
            logger.info("⏹ VitalDB replay arrêté sur %s", room_id)
        self._stop_wave_thread(room_id)

    def start_vitaldb(
        self,
        room_id: str,
        caseid: int,
        speed: float = 1.0,
        patient_info: dict = None,
        with_waveforms: bool = False,
        case_id: str | None = None,
    ):
        """Lance un replay VitalDB dans un thread dédié."""
        import threading
        from simulator.replay import find_cases, replay_case

        # Arrêter l'ancien replay s'il existe
        with self._lock:
            self._stop_vitaldb(room_id)

        # Construire patient_info depuis VitalDB metadata si non fourni
        if not patient_info:
            patient_info = load_vitaldb_patient_info(VITALDB_DIR, caseid, logger)
            if patient_info:
                logger.info("Patient VitalDB#%d: %sans %s ASA%s — %s",
                           caseid, patient_info.get('age','?'),
                           patient_info.get('sex','?'),
                           patient_info.get('asa','?'),
                           patient_info.get('opname','?'))

        # Trouver le fichier parquet
        cases = find_cases(VITALDB_DIR)
        matching = [c for c in cases if f"case_{caseid:05d}" in c.name or f"case_{caseid:04d}" in c.name]
        if not matching:
            logger.error("Cas VitalDB %d non trouvé dans %s", caseid, VITALDB_DIR)
            return False

        stop_event = threading.Event()
        self.vitaldb_threads[room_id] = {"stop": stop_event, "caseid": caseid}

        def _replay_thread():
            try:
                replay_case(
                    client=self.client,
                    case_path=matching[0],
                    room_id=room_id,
                    speed=speed,
                    loop=False,
                    stop_event=stop_event,
                    patient_info=patient_info,
                    with_waveforms=with_waveforms,
                    waves_dir=os.getenv("VITALDB_WAVES_DIR", "/data/vitaldb/waveforms"),
                )
            except Exception as e:
                logger.error("Erreur replay VitalDB %d: %s", caseid, e)
            finally:
                self.vitaldb_threads.pop(room_id, None)
                if case_id:
                    self.client.publish(
                        EVENT_TOPIC,
                        json.dumps(
                            {
                                "type": "replay_finished",
                                "room_id": room_id,
                                "case_id": case_id,
                            }
                        ),
                        qos=1,
                    )
                logger.info("✓ VitalDB replay terminé pour %s (case %d)", room_id, caseid)

        t = threading.Thread(target=_replay_thread, daemon=True)
        t.start()
        logger.info("▶ VitalDB case %d lancé sur %s (speed x%.1f)", caseid, room_id, speed)
        return True

    def handle_command(self, payload: dict):
        """Traite une commande de contrôle reçue via MQTT."""
        action = payload.get("action")
        room_id = payload.get("room_id", "salle_1")
        speed = payload.get("speed", 1.0)

        if action == "start_vitaldb":
            caseid = payload.get("caseid")
            if caseid is None:
                logger.warning("Pas de caseid dans la commande")
                return
            patient_info = payload.get("patient_info")
            with_waveforms = bool(payload.get("with_waveforms", False))
            case_id = payload.get("case_id")
            self.start_vitaldb(room_id, caseid, speed, patient_info, with_waveforms, case_id)

        elif action == "stop":
            self._stop_vitaldb(room_id)
            logger.info("⏹ Salle %s arrêtée", room_id)

    def log_status(self):
        for rid, info in self.vitaldb_threads.items():
            logger.info("[%s] VitalDB replay case %d en cours", rid, info["caseid"])


def main():
    logger.info("Connecting to MQTT %s:%s", MQTT_BROKER, MQTT_PORT)

    client = mqtt.Client(
        client_id="charles-simulator",
        callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
    )

    controller = SimulatorController(client)

    def on_connect(c, userdata, flags, reason_code, properties=None):
        logger.info("MQTT connected (rc=%s), subscribing to %s", reason_code, CONTROL_TOPIC)
        c.subscribe(CONTROL_TOPIC, qos=1)

    def on_disconnect(c, userdata, disconnect_flags, reason_code, properties=None):
        if reason_code != 0:
            logger.warning("MQTT disconnected (rc=%s) — auto-reconnect en cours", reason_code)

    def on_message(c, userdata, msg):
        if msg.topic == CONTROL_TOPIC:
            try:
                payload = json.loads(msg.payload.decode("utf-8"))
                logger.info("📩 Commande reçue: %s", payload)
                controller.handle_command(payload)
            except (json.JSONDecodeError, UnicodeDecodeError) as e:
                logger.warning("Commande MQTT invalide: %s", e)

    client.on_connect = on_connect
    client.on_disconnect = on_disconnect
    client.on_message = on_message
    client.reconnect_delay_set(min_delay=1, max_delay=30)
    if MQTT_USER:
        client.username_pw_set(MQTT_USER, MQTT_PASSWORD)
    for attempt in range(1, 11):
        try:
            client.connect(MQTT_BROKER, MQTT_PORT, keepalive=60)
            break
        except Exception as e:
            logger.warning("MQTT connect attempt %d/10 failed: %s — retry in 5s", attempt, e)
            time.sleep(5)
    client.loop_start()

    start_default_vitaldb_rooms(controller)
    logger.info("Simulation started — VitalDB uniquement")

    cycle = 0
    try:
        while True:
            Path("/tmp/sim.hb").touch()  # heartbeat pour Docker HEALTHCHECK

            cycle += 1
            if cycle % 12 == 0:
                controller.log_status()

            time.sleep(5)

    except KeyboardInterrupt:
        logger.info("Simulation stopped.")
    finally:
        client.loop_stop()
        client.disconnect()


if __name__ == "__main__":
    main()

