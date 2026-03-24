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
from datetime import datetime, timezone
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


def load_case(path: Path) -> pd.DataFrame:
    """Charge un cas parquet et retourne un DataFrame."""
    df = pd.read_parquet(path)
    logger.info("Loaded %s — %d rows, columns: %s", path.name, len(df), list(df.columns))
    return df


def extract_value(row: dict, col_names: list[str]) -> Optional[float]:
    """Extrait la première valeur non-NaN parmi les colonnes candidates."""
    for col in col_names:
        if col in row:
            val = row[col]
            if val is not None and not (isinstance(val, float) and np.isnan(val)):
                return float(val)
    return None


def row_to_message(row: dict, case_id: str, room_id: str, row_time: float,
                   total_duration_s: float = 0, patient_info: dict = None) -> dict:
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
        "case_id": f"vitaldb_{case_id}",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "scenario": f"vitaldb_replay_{case_id}",
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
):
    """Lit un cas VitalDB parquet et publie sur MQTT."""
    df = load_case(case_path)

    # Déterminer le cas ID depuis le nom de fichier (case_0042.parquet → 42)
    case_id = case_path.stem.replace("case_", "")

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
