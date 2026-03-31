"""
CHARLES — Simulateur clinique peropératoire.

Simule un bloc opératoire complet avec scénarios réalistes :
- Scénario normal : ASA 1, cholécystectomie coelioscopique
- Scénario hypotension : chute progressive PAS après induction
- Scénario désaturation : SpO2 qui chute lors d'intubation difficile
- Scénario anaphylaxie : réaction allergique brutale
- Scénario hémorragique : pertes sanguines progressives

Publie sur MQTT topic `bloc/{room_id}/full` toutes les 5 secondes.
"""

from __future__ import annotations

import json
import logging
import os
import random
import time
from pathlib import Path

import paho.mqtt.client as mqtt

from simulator.scenarios import SCENARIOS, SimulatedRoom
from simulator.vitaldb_support import load_vitaldb_patient_info
from simulator.waveforms import WAVE_CHUNK_S, generate_synth_waves

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
VITALDB_DIR = os.getenv("VITALDB_DIR", "/data/vitaldb/cases")


# ══════════════════════════════════════════════════════════════
#  GÉNÉRATION ONDES SYNTHÉTIQUES (250 ms par chunk)
# ══════════════════════════════════════════════════════════════

class SimulatorController:
    """Contrôleur central : gère les salles synthétiques et VitalDB."""

    def __init__(self, mqtt_client: mqtt.Client):
        self.client = mqtt_client
        self.rooms: dict[str, SimulatedRoom] = {}
        self.vitaldb_threads: dict[str, dict] = {}  # room_id → {"stop": Event}
        self._wave_stops: dict[str, __import__("threading").Event] = {}
        self._lock = __import__("threading").Lock()

        # Salles par défaut
        self._add_synthetic("salle_1", "normal")
        self._add_synthetic("salle_2", "hypotension")
        self._add_synthetic("salle_3", "desaturation")

    def _start_wave_thread(self, room_id: str):
        """Démarre un thread 250 ms publiant les wave_chunks synthétiques pour room_id."""
        import threading

        # Arrêter le thread précédent s'il existe
        old = self._wave_stops.pop(room_id, None)
        if old:
            old.set()

        stop_ev = threading.Event()
        self._wave_stops[room_id] = stop_ev

        def _wave_loop():
            t_ref = time.time()
            while not stop_ev.is_set():
                t_start = time.time() - t_ref
                # Lire l'état courant sans verrou (lecture seule des champs float)
                with self._lock:
                    room = self.rooms.get(room_id)
                if room is None:
                    break   # salle supprimée → arrêter
                try:
                    payload = generate_synth_waves(room.state, room_id, t_start)
                    topic   = f"bloc/{room_id}/waves"
                    self.client.publish(topic, json.dumps(payload), qos=0)
                except Exception as e:
                    logger.debug("wave_thread %s error: %s", room_id, e)
                stop_ev.wait(WAVE_CHUNK_S)

        t = threading.Thread(target=_wave_loop, daemon=True, name=f"wave-{room_id}")
        t.start()
        logger.info("🌊 Wave thread démarré pour %s", room_id)

    def _stop_wave_thread(self, room_id: str):
        ev = self._wave_stops.pop(room_id, None)
        if ev:
            ev.set()

    def _add_synthetic(self, room_id: str, scenario_name: str):
        with self._lock:
            self._stop_vitaldb(room_id)
            self.rooms[room_id] = SimulatedRoom(room_id=room_id, scenario_name=scenario_name)
            logger.info("➕ %s → scénario synthétique: %s", room_id, scenario_name)
        self._start_wave_thread(room_id)

    def _stop_vitaldb(self, room_id: str):
        """Arrête un éventuel replay VitalDB sur cette salle."""
        info = self.vitaldb_threads.pop(room_id, None)
        if info:
            info["stop"].set()
            logger.info("⏹ VitalDB replay arrêté sur %s", room_id)
        self._stop_wave_thread(room_id)

    def start_vitaldb(self, room_id: str, caseid: int, speed: float = 1.0,
                      patient_info: dict = None, with_waveforms: bool = False):
        """Lance un replay VitalDB dans un thread dédié."""
        import threading
        from simulator.replay import find_cases, replay_case

        # Arrêter la salle synthétique et/ou l'ancien replay
        with self._lock:
            self.rooms.pop(room_id, None)
            self._stop_vitaldb(room_id)
        # Arrêter aussi le thread wave synthétique (le replay a les siennes)
        self._stop_wave_thread(room_id)

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
                logger.info("✓ VitalDB replay terminé pour %s (case %d)", room_id, caseid)
                # Revenir au synthétique normal
                with self._lock:
                    if room_id not in self.rooms:
                        self.rooms[room_id] = SimulatedRoom(room_id=room_id, scenario_name="normal")
                self._start_wave_thread(room_id)

        t = threading.Thread(target=_replay_thread, daemon=True)
        t.start()
        logger.info("▶ VitalDB case %d lancé sur %s (speed x%.1f)", caseid, room_id, speed)
        return True

    def handle_command(self, payload: dict):
        """Traite une commande de contrôle reçue via MQTT."""
        action = payload.get("action")
        room_id = payload.get("room_id", "salle_1")
        speed = payload.get("speed", 1.0)

        if action == "start_synthetic":
            scenario = payload.get("scenario", "normal")
            if scenario not in SCENARIOS:
                logger.warning("Scénario inconnu: %s", scenario)
                return
            self._add_synthetic(room_id, scenario)

        elif action == "start_vitaldb":
            caseid = payload.get("caseid")
            if caseid is None:
                logger.warning("Pas de caseid dans la commande")
                return
            patient_info = payload.get("patient_info")
            with_waveforms = bool(payload.get("with_waveforms", False))
            self.start_vitaldb(room_id, caseid, speed, patient_info, with_waveforms)

        elif action == "stop":
            with self._lock:
                self.rooms.pop(room_id, None)
                self._stop_vitaldb(room_id)
            self._stop_wave_thread(room_id)
            logger.info("⏹ Salle %s arrêtée", room_id)

    def tick_all(self):
        """Tick toutes les salles synthétiques actives."""
        with self._lock:
            for room_id, room in list(self.rooms.items()):
                msg = room.tick()
                topic = f"bloc/{room.room_id}/full"
                self.client.publish(topic, json.dumps(msg), qos=1)

                # Rotation auto quand le scénario se termine
                if room.scenario.step >= room.scenario.duration_steps:
                    next_scenario = random.choice(list(SCENARIOS.keys()))
                    self.rooms[room_id] = SimulatedRoom(
                        room_id=room.room_id,
                        scenario_name=next_scenario,
                    )
                    logger.info("🔄 %s → nouveau scénario: %s", room.room_id, next_scenario)
                    # Le wave thread tourne déjà — pas besoin de le redémarrer

    def log_status(self):
        with self._lock:
            for r in self.rooms.values():
                v = r.state
                logger.info(
                    "[%s] %s | FC=%d SpO2=%.0f PAS=%d PAM=%d EtCO2=%.0f BIS=%d | %s",
                    r.room_id, r.scenario.name,
                    v.hr, v.spo2, v.pas, v.pam, v.etco2, v.bis, r.phase,
                )
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

    logger.info("Simulation started — %d salles synthétiques", len(controller.rooms))

    cycle = 0
    try:
        while True:
            controller.tick_all()
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

