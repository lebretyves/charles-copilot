"""
CHARLES — VitalDB Fast Parallel Downloader
============================================
Télécharge TOUS les cas VitalDB en parallèle avec retry automatique.
Reprend automatiquement là où il s'est arrêté (skip existing).

Usage:
    python download_fast.py                # Télécharge tous les 6388 cas
    python download_fast.py --workers 6    # 6 workers parallèles
    python download_fast.py --subset 500   # Seulement 500 cas

Prérequis:
    pip install vitaldb pandas pyarrow pyyaml tqdm requests
"""
import argparse
import os
import sys
import time
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from threading import Lock

import pandas as pd
import yaml
from tqdm import tqdm

import vitaldb

BASE_DIR = Path(__file__).parent
CASES_DIR = BASE_DIR / "cases"
FAILED_LOG = BASE_DIR / "failed_cases.txt"
CATALOG_PATH = BASE_DIR / "catalog.yaml"

# 27 tracks clés pour CHARLES
SELECTED_TRACKS = [
    "Solar8000/HR",
    "Solar8000/PLETH_SPO2",
    "Solar8000/ART_SBP",
    "Solar8000/ART_DBP",
    "Solar8000/ART_MBP",
    "Solar8000/NIBP_SBP",
    "Solar8000/NIBP_DBP",
    "Solar8000/NIBP_MBP",
    "Solar8000/ETCO2",
    "Solar8000/BT",
    "Solar8000/RR",
    "Solar8000/RR_CO2",
    "Solar8000/FIO2",
    "Solar8000/VENT_TV",
    "Solar8000/VENT_PIP",
    "Solar8000/VENT_PPLAT",
    "Solar8000/VENT_MEAS_PEEP",
    "Solar8000/VENT_MV",
    "Solar8000/VENT_COMPL",
    "BIS/BIS",
    "BIS/EMG",
    "BIS/SR",
    "Orchestra/PPF20_CE",
    "Orchestra/PPF20_CT",
    "Orchestra/RFTN20_CE",
    "Orchestra/RFTN20_CT",
    "Primus/MAC",
]

# Thread-safe progress tracking
progress_lock = Lock()
catalog_entries = []
failed_cases = []
success_count = 0
skip_count = 0


def download_one_case(caseid: int, max_retries: int = 3) -> dict | None:
    """Télécharge un cas avec retry. Retourne l'entrée catalog ou None."""
    global success_count, skip_count

    out_path = CASES_DIR / f"case_{caseid:05d}.parquet"

    # Skip si déjà téléchargé
    if out_path.exists() and out_path.stat().st_size > 100:
        with progress_lock:
            skip_count += 1
        return {
            "caseid": int(caseid),
            "file": f"cases/case_{caseid:05d}.parquet",
            "status": "skipped",
        }

    for attempt in range(1, max_retries + 1):
        try:
            vals = vitaldb.load_case(caseid, SELECTED_TRACKS, interval=2)
            if vals is None or len(vals) == 0:
                return None

            df = pd.DataFrame(vals, columns=SELECTED_TRACKS)
            df.insert(0, "time_sec", range(0, len(df) * 2, 2))
            df.to_parquet(out_path, engine="pyarrow", compression="snappy")

            with progress_lock:
                success_count += 1

            return {
                "caseid": int(caseid),
                "file": f"cases/case_{caseid:05d}.parquet",
                "n_rows": len(df),
                "duration_min": round(len(df) * 2 / 60, 1),
                "tracks": len(SELECTED_TRACKS),
            }

        except Exception as e:
            if attempt < max_retries:
                # Backoff exponentiel : 5s, 15s, 45s
                wait = 5 * (3 ** (attempt - 1))
                time.sleep(wait)
            else:
                with progress_lock:
                    failed_cases.append(caseid)
                return None

    return None


def save_catalog():
    """Sauvegarde le catalog YAML avec les cas téléchargés."""
    valid_entries = [e for e in catalog_entries if e and e.get("status") != "skipped" and e.get("n_rows")]

    # Inclure aussi les cas déjà sur disque
    existing_files = list(CASES_DIR.glob("case_*.parquet"))
    existing_ids = {int(f.stem.split("_")[1]) for f in existing_files}
    catalog_ids = {e["caseid"] for e in valid_entries}

    for f in existing_files:
        cid = int(f.stem.split("_")[1])
        if cid not in catalog_ids:
            try:
                df = pd.read_parquet(f)
                valid_entries.append({
                    "caseid": cid,
                    "file": f"cases/{f.name}",
                    "n_rows": len(df),
                    "duration_min": round(len(df) * 2 / 60, 1),
                    "tracks": len(SELECTED_TRACKS),
                })
            except Exception:
                pass

    valid_entries.sort(key=lambda x: x["caseid"])

    with open(CATALOG_PATH, "w", encoding="utf-8") as f:
        yaml.dump(
            {
                "vitaldb_cases_downloaded": len(valid_entries),
                "tracks_per_case": SELECTED_TRACKS,
                "interval_sec": 2,
                "cases": valid_entries,
            },
            f,
            default_flow_style=False,
            allow_unicode=True,
        )


def save_failed():
    """Sauvegarde les cas échoués pour retry ultérieur."""
    if failed_cases:
        with open(FAILED_LOG, "w") as f:
            for cid in sorted(failed_cases):
                f.write(f"{cid}\n")


def get_all_case_ids() -> list:
    """Récupère tous les case IDs depuis les métadonnées."""
    csv_path = BASE_DIR / "clinical_metadata.csv"
    if not csv_path.exists():
        print("clinical_metadata.csv manquant — téléchargement...")
        import requests
        r = requests.get("https://api.vitaldb.net/cases", timeout=120)
        r.raise_for_status()
        csv_path.write_bytes(r.content)

    df = pd.read_csv(csv_path)
    id_col = "caseid" if "caseid" in df.columns else df.columns[0]
    return sorted(df[id_col].dropna().astype(int).tolist())


def main():
    parser = argparse.ArgumentParser(description="CHARLES — VitalDB Fast Downloader")
    parser.add_argument("--workers", type=int, default=4, help="Nombre de workers parallèles (default: 4)")
    parser.add_argument("--subset", type=int, default=0, help="Limiter à N cas (0 = tous)")
    parser.add_argument("--retry-failed", action="store_true", help="Relancer uniquement les cas échoués")
    args = parser.parse_args()

    CASES_DIR.mkdir(exist_ok=True)

    # Déterminer quels cas télécharger
    if args.retry_failed and FAILED_LOG.exists():
        case_ids = [int(line.strip()) for line in FAILED_LOG.read_text().splitlines() if line.strip()]
        print(f"🔄 Retry de {len(case_ids)} cas échoués")
    else:
        case_ids = get_all_case_ids()
        if args.subset > 0:
            case_ids = case_ids[:args.subset]

    # Compter les cas déjà téléchargés
    existing = {int(f.stem.split("_")[1]) for f in CASES_DIR.glob("case_*.parquet")}
    remaining = [cid for cid in case_ids if cid not in existing]

    print(f"📊 Total cas: {len(case_ids)}")
    print(f"✅ Déjà téléchargés: {len(existing)}")
    print(f"⬇️  À télécharger: {len(remaining)}")
    print(f"🔧 Workers: {args.workers}")
    print(f"{'='*50}")

    if not remaining:
        print("Tous les cas sont déjà téléchargés !")
        save_catalog()
        return

    # Téléchargement parallèle
    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = {executor.submit(download_one_case, cid): cid for cid in remaining}

        with tqdm(total=len(remaining), desc="Téléchargement", unit="cas") as pbar:
            for future in as_completed(futures):
                cid = futures[future]
                try:
                    result = future.result()
                    if result:
                        catalog_entries.append(result)
                except Exception as e:
                    with progress_lock:
                        failed_cases.append(cid)
                finally:
                    pbar.update(1)

                # Sauvegarde intermédiaire tous les 100 cas
                if (pbar.n % 100) == 0 and pbar.n > 0:
                    save_catalog()
                    save_failed()

    # Sauvegarde finale
    save_catalog()
    save_failed()

    # Résumé
    total_files = len(list(CASES_DIR.glob("case_*.parquet")))
    total_size = sum(f.stat().st_size for f in CASES_DIR.glob("case_*.parquet"))

    print(f"\n{'='*50}")
    print(f"  RÉSULTAT FINAL")
    print(f"{'='*50}")
    print(f"  Cas sur disque     : {total_files}")
    print(f"  Nouveaux téléchargés: {success_count}")
    print(f"  Skippés (existants): {skip_count}")
    print(f"  Échoués            : {len(failed_cases)}")
    print(f"  Taille totale      : {total_size / (1024*1024):.0f} Mo")
    print(f"{'='*50}")

    if failed_cases:
        print(f"\n⚠️  {len(failed_cases)} cas échoués → voir failed_cases.txt")
        print(f"    Relancer avec: py download_fast.py --retry-failed")


if __name__ == "__main__":
    main()
