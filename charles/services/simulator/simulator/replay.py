"""
CHARLES — Replay VitalDB.

Lit les fichiers parquet téléchargés par download_all.py
et publie les signaux vitaux réels sur MQTT, dans le même format
que le simulateur synthétique.

Utilisation :
    python -m simulator.replay                  # cas aléatoire
    python -m simulator.replay --case 42        # cas VitalDB #42
    python -m simulator.replay --speed 2.0      # x2 playback
    python -m simulator.replay --loop           # boucle infinie
    python -m simulator.replay --room salle_4   # salle custom
"""

from __future__ import annotations

import json
import logging
import os
import sys
import time
import argparse
import glob
import random
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd
import paho.mqtt.client as mqtt

logging.basicConfig(level=logging.INFO, format="%(asctime)s [REPLAY] %(message)s")
logger = logging.getLogger("charles.replay")

MQTT_BROKER = os.getenv("MQTT_BROKER", "localhost")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))
VITALDB_DIR = os.getenv("VITALDB_DIR", "/data/vitaldb/cases")
VITALDB_WAVES_DIR = os.getenv("VITALDB_WAVES_DIR", "/data/vitaldb/waveforms")

# Taille d'un chunk waveform : 250 ms
# 500Hz → 125 échantillons ; 25Hz → 6 échantillons ; 128Hz → 32 échantillons
WAVE_CHUNK_MS = 250

# Note : les mappings colonnes Parquet → CHARLES sont faits inline
# dans row_to_message() avec extract_value() pour plus de flexibilité
# (fallback NIBP quand invasive absente, etc.)

# ── Phases anesthésiques ──────────────────────────────────────
PHASE_DEFS = [
    ("installation",      "Installation",                0.00),
    ("preinduction",      "Pré-induction",               0.02),
    ("induction",         "Induction",                   0.05),
    ("intubation",        "Intubation / VA sécurisée",   0.08),
    ("installation_chir", "Installation chirurgicale",   0.12),
    ("incision",          "Incision",                    0.15),
    ("maintenance",       "Maintenance",                 0.20),
    ("fin_chirurgie",     "Fin de chirurgie",            0.85),
    ("emergence",         "Émergence / Réveil",          0.90),
    ("extubation",        "Extubation",                  0.95),
    ("sspi_transfert",    "Transfert SSPI",              0.98),
]

REPLAY_MACRO_PHASE = {
    "installation": "PRE", "preinduction": "PRE",
    "induction": "PER", "intubation": "PER",
    "installation_chir": "PER", "incision": "PER",
    "maintenance": "PER", "fin_chirurgie": "PER",
    "emergence": "POST", "extubation": "POST",
    "sspi_transfert": "POST",
}


def compute_phase(elapsed_s: float, total_s: float) -> tuple[str, str]:
    """Retourne (phase_id, phase_label) en fonction de la progression."""
    if total_s <= 0:
        return "maintenance", "Maintenance"
    ratio = elapsed_s / total_s
    phase_id, phase_label = PHASE_DEFS[0][0], PHASE_DEFS[0][1]
    for pid, plabel, threshold in PHASE_DEFS:
        if ratio >= threshold:
            phase_id, phase_label = pid, plabel
    return phase_id, phase_label


def fmt_elapsed(seconds: float) -> str:
    """Formate un nombre de secondes en durée lisible."""
    h, r = divmod(int(seconds), 3600)
    m, s = divmod(r, 60)
    return f"{h}h{m:02d}" if h else f"{m}min{s:02d}"


def find_cases(vitaldb_dir: str) -> list[Path]:
    """Trouve tous les fichiers parquet de cas VitalDB."""
    pattern = os.path.join(vitaldb_dir, "case_*.parquet")
    files = sorted(glob.glob(pattern))
    return [Path(f) for f in files]


def find_waveform_files(case_id: str, waves_dir: str) -> dict[str, Path | None]:
    """Trouve les fichiers waveform pour un cas donné."""
    num = int(case_id)
    base = Path(waves_dir)
    return {
        "500hz": base / f"wave_{num:05d}_500hz.parquet",
        "25hz":  base / f"wave_{num:05d}_25hz.parquet",
        "128hz": base / f"wave_{num:05d}_128hz.parquet",
    }


def stream_waveforms(
    client: mqtt.Client,
    case_id: str,
    room_id: str,
    waves_dir: str,
    speed: float = 1.0,
    stop_event=None,
    start_offset_s: float = 0.0,
):
    """Thread dédié au streaming waveforms HF (500Hz ECG/PLETH/ART, 25Hz CO2/AWP, 128Hz EEG)."""
    files = find_waveform_files(case_id, waves_dir)

    # Charger les fichiers disponibles
    df500 = df25 = df128 = None
    if files["500hz"].exists():
        df500 = pd.read_parquet(files["500hz"])
        logger.info("[WAVES] %s : 500Hz chargé %d lignes", case_id, len(df500))
    if files["25hz"].exists():
        df25 = pd.read_parquet(files["25hz"])
        logger.info("[WAVES] %s : 25Hz chargé %d lignes", case_id, len(df25))
    if files["128hz"].exists():
        df128 = pd.read_parquet(files["128hz"])
        logger.info("[WAVES] %s : 128Hz chargé %d lignes", case_id, len(df128))

    if df500 is None and df25 is None and df128 is None:
        logger.warning("[WAVES] Aucun fichier waveform trouvé pour cas %s", case_id)
        return

    # Convertir en arrays numpy pour vitesse
    t500 = df500["time_sec"].values if df500 is not None else np.array([])
    ecg  = df500["SNUADC/ECG_II"].values if df500 is not None and "SNUADC/ECG_II" in df500.columns else None
    pleth = df500["SNUADC/PLETH"].values if df500 is not None and "SNUADC/PLETH" in df500.columns else None
    art  = df500["SNUADC/ART"].values if df500 is not None and "SNUADC/ART" in df500.columns else None

    t25  = df25["time_sec"].values if df25 is not None else np.array([])
    co2  = df25["Primus/CO2"].values if df25 is not None and "Primus/CO2" in df25.columns else None
    awp  = df25["Primus/AWP"].values if df25 is not None and "Primus/AWP" in df25.columns else None

    t128 = df128["time_sec"].values if df128 is not None else np.array([])
    eeg  = df128["BIS/EEG1_WAV"].values if df128 is not None and "BIS/EEG1_WAV" in df128.columns else None

    # Durée totale
    total_t = float(t500[-1]) if len(t500) > 0 else float(t25[-1]) if len(t25) > 0 else float(t128[-1])

    # Indices courants
    i500 = i25 = i128 = 0
    CHUNK_S = WAVE_CHUNK_MS / 1000.0

    t_current = max(0.0, float(start_offset_s))
    logger.info("[WAVES] Streaming waveforms cas %s sur %s (depart %.0fs / duree %.0fs)", case_id, room_id, t_current, total_t)

    while t_current < total_t:
        if stop_event and stop_event.is_set():
            logger.info("[WAVES] Stop demandé pour cas %s", case_id)
            break

        t_end = t_current + CHUNK_S

        # Extraire chunk 500Hz
        chunk_ecg = chunk_pleth = chunk_art = None
        if ecg is not None and len(t500) > 0:
            mask = (t500 >= t_current) & (t500 < t_end)
            if mask.any():
                chunk_ecg   = [round(float(v), 4) for v in ecg[mask] if not np.isnan(v)]
                chunk_pleth = [round(float(v), 4) for v in pleth[mask]] if pleth is not None else None
                chunk_art   = [round(float(v), 2) for v in art[mask]] if art is not None else None

        # Extraire chunk 25Hz
        chunk_co2 = chunk_awp = None
        if co2 is not None and len(t25) > 0:
            mask25 = (t25 >= t_current) & (t25 < t_end)
            if mask25.any():
                chunk_co2 = [round(float(v), 3) for v in co2[mask25] if not np.isnan(v)]
                chunk_awp = [round(float(v), 3) for v in awp[mask25]] if awp is not None else None

        # Extraire chunk 128Hz
        chunk_eeg = None
        if eeg is not None and len(t128) > 0:
            mask128 = (t128 >= t_current) & (t128 < t_end)
            if mask128.any():
                chunk_eeg = [round(float(v), 4) for v in eeg[mask128] if not np.isnan(v)]

        # Publier seulement si au moins un signal
        if any(x is not None for x in [chunk_ecg, chunk_co2, chunk_eeg]):
            wave_payload = {
                "type":  "wave_chunk",
                "room_id": room_id,
                "t": round(t_current, 3),
                "ecg":   chunk_ecg,
                "pleth": chunk_pleth,
                "art":   chunk_art,
                "co2":   chunk_co2,
                "awp":   chunk_awp,
                "eeg":   chunk_eeg,
            }
            topic = f"bloc/{room_id}/waves"
            client.publish(topic, json.dumps(wave_payload), qos=0)

        t_current = t_end
        time.sleep(CHUNK_S / speed)

    logger.info("[WAVES] Streaming waveforms cas %s terminé", case_id)


def load_case(path: Path) -> pd.DataFrame:
    """Charge un cas parquet et retourne un DataFrame."""
    df = pd.read_parquet(path)
    logger.info("Loaded %s — %d rows, columns: %s", path.name, len(df), list(df.columns))
    return df


def build_publish_schedule(times: np.ndarray, sample_interval: float) -> list[tuple[int, float]]:
    if len(times) == 0:
        return []

    base_time = float(times[0])
    schedule: list[tuple[int, float]] = []
    previous_elapsed: float | None = None
    for index, raw_time in enumerate(times):
        elapsed = max(0.0, float(raw_time) - base_time)
        if previous_elapsed is not None and (elapsed - previous_elapsed) < sample_interval:
            continue
        schedule.append((index, elapsed))
        previous_elapsed = elapsed
    return schedule


def choose_random_start_position(
    schedule: list[tuple[int, float]],
    total_duration_s: float,
    min_history_s: float = 15 * 60,
    min_remaining_s: float = 5 * 60,
) -> int:
    if len(schedule) <= 1:
        return 0

    eligible_positions = [
        position
        for position, (_, elapsed_s) in enumerate(schedule)
        if elapsed_s >= min_history_s and (total_duration_s - elapsed_s) >= min_remaining_s
    ]
    if not eligible_positions:
        fallback_start = max(1, len(schedule) // 3)
        fallback_end = max(fallback_start, len(schedule) - 1)
        eligible_positions = list(range(fallback_start, fallback_end))
    if not eligible_positions:
        return min(1, len(schedule) - 1)
    return random.choice(eligible_positions)


def extract_value(row: dict, col_names: list[str]) -> Optional[float]:
    """Extrait la première valeur non-NaN parmi les colonnes candidates."""
    for col in col_names:
        if col in row:
            val = row[col]
            if val is not None and not (isinstance(val, float) and np.isnan(val)):
                return float(val)
    return None


def row_to_message(
    row: dict,
    source_case_id: str,
    room_id: str,
    row_time: float,
    total_duration_s: float = 0,
    patient_info: dict = None,
    *,
    timestamp: datetime | None = None,
    case_id_override: str | None = None,
) -> dict:
    """Convertit une ligne parquet en message MQTT format CHARLES."""
    # ── Vitals ──
    hr = extract_value(row, ["Solar8000/HR"])
    spo2 = extract_value(row, ["Solar8000/PLETH_SPO2"])
    # PA : priorité invasive, sinon NIBP
    pas = extract_value(row, ["Solar8000/ART_SBP", "Solar8000/NIBP_SBP"])
    pad = extract_value(row, ["Solar8000/ART_DBP", "Solar8000/NIBP_DBP"])
    pam = extract_value(row, ["Solar8000/ART_MBP", "Solar8000/NIBP_MBP"])
    etco2 = extract_value(row, ["Solar8000/ETCO2"])
    fr = extract_value(row, ["Solar8000/RR", "Solar8000/RR_CO2"])
    temp = extract_value(row, ["Solar8000/BT"])

    # Defaults (si le capteur n'est pas branché dans ce cas VitalDB)
    vitals = {
        "hr":    round(hr, 1) if hr is not None else 72.0,
        "spo2":  round(spo2, 1) if spo2 is not None else 98.0,
        "pas":   round(pas, 0) if pas is not None else 120.0,
        "pad":   round(pad, 0) if pad is not None else 70.0,
        "pam":   round(pam, 0) if pam is not None else 87.0,
        "etco2": round(etco2, 1) if etco2 is not None else 35.0,
        "fr":    round(fr, 0) if fr is not None else 14.0,
        "temp":  round(temp, 1) if temp is not None else 36.6,
    }

    # ── Ventilator ──
    vent = None
    vt = extract_value(row, ["Primus/TV"])
    if vt is not None:
        mv = extract_value(row, ["Primus/MVENT"])
        ppeak = extract_value(row, ["Primus/PPEAK"])
        pplat = extract_value(row, ["Primus/PPLAT"])
        peep = extract_value(row, ["Primus/PEEP"])
        fio2 = extract_value(row, ["Primus/FIO2"])
        vent = {
            "mode": "VACI",
            "vt": round(vt) if vt else 0,
            "vt_kg": round(vt / 70, 1) if vt else 0,
            "mv": round(mv, 1) if mv else 0,
            "ppeak": round(ppeak, 1) if ppeak else 0,
            "pplat": round(pplat, 1) if pplat else 0,
            "peep": round(peep, 1) if peep else 0,
            "fio2": round(fio2) if fio2 else 50,
            "ratio_ie": "1:2",
        }

    # ── BIS ──
    bis_data = None
    bis_val = extract_value(row, ["BIS/BIS"])
    if bis_val is not None:
        bis_data = {
            "bis": round(bis_val),
            "sqi": round(extract_value(row, ["BIS/SQI"]) or 90),
            "emg": round(extract_value(row, ["BIS/EMG"]) or 30, 1),
            "sr": round(extract_value(row, ["BIS/SR"]) or 0, 1),
        }

    # ── AIVOC Propofol ──
    aivoc_hyp = None
    ppf_ce = extract_value(row, ["Orchestra/PPF20_CE"])
    if ppf_ce is not None:
        ppf_ct = extract_value(row, ["Orchestra/PPF20_CT"]) or ppf_ce
        ppf_cp = extract_value(row, ["Orchestra/PPF20_CP"]) or ppf_ce
        aivoc_hyp = {
            "drug": "propofol",
            "model": "Schnider",
            "target_type": "effect_site",
            "target": round(ppf_cp, 1),
            "predicted_plasma": round(ppf_ct, 2),
            "predicted_effect": round(ppf_ce, 2),
            "infusion_rate": 0.0,
        }

    # ── AIVOC Remifentanil ──
    aivoc_opi = None
    rftn_ce = extract_value(row, ["Orchestra/RFTN20_CE"])
    if rftn_ce is not None:
        rftn_ct = extract_value(row, ["Orchestra/RFTN20_CT"]) or rftn_ce
        aivoc_opi = {
            "drug": "remifentanil",
            "model": "Minto",
            "target_type": "effect_site",
            "target": round(rftn_ce, 1),
            "predicted_plasma": round(rftn_ct, 2),
            "predicted_effect": round(rftn_ce, 2),
            "infusion_rate": 0.0,
        }

    phase_id, phase_label = compute_phase(row_time, total_duration_s)

    return {
        "room_id": room_id,
        "case_id": case_id_override or f"vitaldb_{source_case_id}",
        "timestamp": (timestamp or datetime.now(timezone.utc)).isoformat(),
        "scenario": f"vitaldb_replay_{source_case_id}",
        "phase": phase_id,
        "phase_label": phase_label,
        "macro_phase": REPLAY_MACRO_PHASE.get(phase_id, "PER"),
        "elapsed_s": int(row_time),
        "elapsed_fmt": fmt_elapsed(row_time),
        "patient_info": patient_info,
        "vitals": vitals,
        "ventilator": vent,
        "bis": bis_data,
        "aivoc_hypnotic": aivoc_hyp,
        "aivoc_opioid": aivoc_opi,
    }


def replay_case(
    client: mqtt.Client,
    case_path: Path,
    room_id: str,
    speed: float = 1.0,
    loop: bool = False,
    stop_event=None,
    patient_info: dict = None,
    with_waveforms: bool = False,
    waves_dir: str = VITALDB_WAVES_DIR,
):
    """Lit un cas VitalDB parquet et publie sur MQTT."""
    df = load_case(case_path)

    # Déterminer le cas ID depuis le nom de fichier (case_0042.parquet → 42)
    case_id = case_path.stem.replace("case_", "")

    # Lancer thread waveforms en parallèle si demandé
    import threading as _threading
    wave_thread = None
    if with_waveforms:
        wave_thread = _threading.Thread(
            target=stream_waveforms,
            args=(client, case_id, room_id, waves_dir, speed, stop_event),
            daemon=True,
        )
        wave_thread.start()
        logger.info("[WAVES] Thread waveforms démarré pour cas %s", case_id)

    # La première colonne est souvent le temps (index ou "time")
    if "time" in df.columns:
        time_col = "time"
    else:
        time_col = df.columns[0]

    # Rééchantillonner à 5 secondes (les données VitalDB sont ~1-7s)
    sample_interval = 5  # secondes en données source
    times = df[time_col].values if time_col in df.columns else np.arange(len(df))
    total_duration_s = float(times[-1] - times[0]) if len(times) > 1 else 0

    # Convertir en liste de dicts (plus rapide que iterrows)
    rows = df.to_dict('records')

    while True:
        if stop_event and stop_event.is_set():
            logger.info("⏹ Replay case %s arrêté par commande", case_id)
            break

        logger.info("▶ Replay case %s (%d data points, speed x%.1f)", case_id, len(df), speed)

        prev_time = None
        for idx, row in enumerate(rows):
            if stop_event and stop_event.is_set():
                logger.info("⏹ Replay case %s arrêté par commande", case_id)
                return

            current_time = times[idx] if idx < len(times) else idx * sample_interval

            # Sauter les lignes trop rapprochées (publier ~toutes les 5s de données)
            if prev_time is not None and (current_time - prev_time) < sample_interval:
                continue
            prev_time = current_time

            msg = row_to_message(row, case_id, room_id, current_time, total_duration_s, patient_info)
            topic = f"bloc/{room_id}/full"
            client.publish(topic, json.dumps(msg), qos=1)

            # Log toutes les 60s de données
            if int(current_time) % 60 < sample_interval:
                v = msg["vitals"]
                logger.info(
                    "[%s] VitalDB#%s t=%ds | FC=%s SpO2=%s PAS=%s PAM=%s EtCO2=%s",
                    room_id, case_id, int(current_time),
                    v["hr"], v["spo2"], v["pas"], v["pam"], v["etco2"],
                )

            # Dormir proportionnellement à l'intervalle réel ajusté par la vitesse
            time.sleep(sample_interval / speed)

        if not loop:
            logger.info("✓ Replay case %s terminé", case_id)
            break
        logger.info("↻ Replay case %s — rebouclage...", case_id)


def main():
    parser = argparse.ArgumentParser(description="CHARLES — VitalDB Replay")
    parser.add_argument("--case", type=int, default=None, help="Numéro de cas VitalDB")
    parser.add_argument("--speed", type=float, default=1.0, help="Vitesse de lecture (1.0 = temps réel)")
    parser.add_argument("--loop", action="store_true", help="Boucle infinie")
    parser.add_argument("--room", type=str, default="salle_vitaldb", help="ID de salle MQTT")
    parser.add_argument("--dir", type=str, default=VITALDB_DIR, help="Dossier des cas parquet")
    args = parser.parse_args()

    # Trouver les fichiers cas
    cases = find_cases(args.dir)
    if not cases:
        logger.error("Aucun fichier parquet trouvé dans %s", args.dir)
        logger.info("Exécutez d'abord : python -m vitaldb.download_all --cases 200")
        sys.exit(1)

    # Sélectionner un cas
    if args.case is not None:
        matching = [c for c in cases if f"case_{args.case:04d}" in c.name or f"case_{args.case}" in c.name]
        if not matching:
            logger.error("Cas %d non trouvé. Cas disponibles: %s", args.case, [c.stem for c in cases[:10]])
            sys.exit(1)
        case_path = matching[0]
    else:
        import random
        case_path = random.choice(cases)

    # Connexion MQTT
    logger.info("Connecting to MQTT %s:%s", MQTT_BROKER, MQTT_PORT)
    client = mqtt.Client(
        client_id="charles-replay-vitaldb",
        callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
    )
    client.connect(MQTT_BROKER, MQTT_PORT, keepalive=60)
    client.loop_start()

    try:
        replay_case(
            client=client,
            case_path=case_path,
            room_id=args.room,
            speed=args.speed,
            loop=args.loop,
        )
    except KeyboardInterrupt:
        logger.info("Replay arrêté.")
    finally:
        client.loop_stop()
        client.disconnect()


if __name__ == "__main__":
    main()
