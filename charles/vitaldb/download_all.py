"""
CHARLES — VitalDB Dataset Downloader
=====================================
Télécharge les données cliniques et numériques de VitalDB
pour alimenter la KB et le mode replay du simulateur.

Usage:
    python download_all.py --metadata       # Télécharge clinical + labs + tracks (~50 Mo)
    python download_all.py --cases 200      # Télécharge 200 cas numériques sélectifs (~50 Mo)
    python download_all.py --all            # Tout d'un coup (~100 Mo)

Prérequis:
    pip install vitaldb pandas pyarrow pyyaml tqdm requests
"""
import argparse
import io
import os
import sys
from pathlib import Path

import pandas as pd
import requests
import yaml
from tqdm import tqdm

import vitaldb  # pour load_case (téléchargement cas numériques)

BASE_DIR = Path(__file__).parent
CASES_DIR = BASE_DIR / "cases"

# 25 tracks clés pour CHARLES (numériques, pas waveforms)
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


VITALDB_API = "https://api.vitaldb.net"


def download_metadata():
    """Télécharge les 3 fichiers via l'API REST VitalDB (fiable sur toutes versions Python)."""
    print("\n=== Téléchargement des métadonnées cliniques ===")

    # 1) Clinical metadata (6 388 cas × 74 colonnes)
    print("[1/3] clinical_metadata.csv ...")
    r = requests.get(f"{VITALDB_API}/cases", timeout=120)
    r.raise_for_status()
    csv_path = BASE_DIR / "clinical_metadata.csv"
    csv_path.write_bytes(r.content)
    df_cases = pd.read_csv(csv_path)
    size_mb = csv_path.stat().st_size / (1024 * 1024)
    print(f"       → {len(df_cases)} cas, {len(df_cases.columns)} colonnes, {size_mb:.1f} Mo")

    # 2) Lab results (peropératoires avec timestamp)
    print("[2/3] intraop_labs.csv ...")
    r = requests.get(f"{VITALDB_API}/labs", timeout=120)
    r.raise_for_status()
    labs_path = BASE_DIR / "intraop_labs.csv"
    labs_path.write_bytes(r.content)
    df_labs = pd.read_csv(labs_path)
    size_mb = labs_path.stat().st_size / (1024 * 1024)
    print(f"       → {len(df_labs)} résultats labo, {size_mb:.1f} Mo")

    # 3) Track index (caseid, tname, tid)
    print("[3/3] track_index.csv ...")
    r = requests.get(f"{VITALDB_API}/trks", timeout=120)
    r.raise_for_status()
    trks_path = BASE_DIR / "track_index.csv"
    trks_path.write_bytes(r.content)
    df_trks = pd.read_csv(trks_path)
    size_mb = trks_path.stat().st_size / (1024 * 1024)
    print(f"       → {len(df_trks)} tracks indexés, {size_mb:.1f} Mo")

    return df_cases


def select_cases(df_cases: pd.DataFrame, n_cases: int) -> list:
    """Sélectionne N cas diversifiés (départements, ASA, urgences)."""
    selected = []

    # Récupérer le nom des colonnes réelles (caseid ou caseid)
    id_col = "caseid" if "caseid" in df_cases.columns else df_cases.columns[0]
    dept_col = "department" if "department" in df_cases.columns else None
    asa_col = "asa" if "asa" in df_cases.columns else None
    emop_col = "emop" if "emop" in df_cases.columns else None

    if dept_col and asa_col:
        # Stratification par département
        departments = df_cases[dept_col].dropna().unique()
        per_dept = max(1, n_cases // max(len(departments), 1))

        for dept in departments:
            dept_df = df_cases[df_cases[dept_col] == dept]

            # Mix ASA 1-2 (stable) et ASA 3-4 (complexe)
            for asa_group in [[1, 2], [3, 4, 5]]:
                sub = dept_df[dept_df[asa_col].isin(asa_group)]
                if len(sub) == 0:
                    continue
                n_pick = min(len(sub), per_dept // 2)
                if n_pick > 0:
                    picked = sub.sample(n=n_pick, random_state=42)
                    selected.extend(picked[id_col].tolist())
    else:
        # Pas de colonne département — sélection aléatoire
        n_pick = min(len(df_cases), n_cases)
        selected = df_cases.sample(n=n_pick, random_state=42)[id_col].tolist()

    # Compléter avec des urgences si pas assez
    if len(selected) < n_cases and emop_col:
        emergencies = df_cases[
            (df_cases[emop_col] == True) & (~df_cases[id_col].isin(selected))
        ]
        n_extra = min(len(emergencies), n_cases - len(selected))
        if n_extra > 0:
            selected.extend(
                emergencies.sample(n=n_extra, random_state=42)[id_col].tolist()
            )

    # Compléter avec des cas aléatoires si encore pas assez
    if len(selected) < n_cases:
        remaining = df_cases[~df_cases[id_col].isin(selected)]
        n_extra = min(len(remaining), n_cases - len(selected))
        if n_extra > 0:
            selected.extend(
                remaining.sample(n=n_extra, random_state=42)[id_col].tolist()
            )

    return selected[:n_cases]


def download_cases(case_ids: list):
    """Télécharge les données numériques pour les cas sélectionnés."""
    CASES_DIR.mkdir(exist_ok=True)

    print(f"\n=== Téléchargement de {len(case_ids)} cas numériques ===")
    print(f"    Tracks: {len(SELECTED_TRACKS)} paramètres par cas")

    catalog_entries = []

    for caseid in tqdm(case_ids, desc="Cas téléchargés"):
        out_path = CASES_DIR / f"case_{caseid:05d}.parquet"
        if out_path.exists():
            continue

        try:
            vals = vitaldb.load_case(caseid, SELECTED_TRACKS, interval=2)
            if vals is None or len(vals) == 0:
                continue

            df = pd.DataFrame(vals, columns=SELECTED_TRACKS)
            df.insert(0, "time_sec", range(0, len(df) * 2, 2))
            df.to_parquet(out_path, engine="pyarrow", compression="snappy")

            catalog_entries.append(
                {
                    "caseid": int(caseid),
                    "file": f"cases/case_{caseid:05d}.parquet",
                    "n_rows": len(df),
                    "duration_min": round(len(df) * 2 / 60, 1),
                    "tracks": len(SELECTED_TRACKS),
                }
            )
        except Exception as e:
            print(f"\n  ⚠ Cas {caseid}: {e}")
            continue

    # Générer le catalog YAML
    catalog_path = BASE_DIR / "catalog.yaml"
    with open(catalog_path, "w", encoding="utf-8") as f:
        yaml.dump(
            {
                "vitaldb_cases_downloaded": len(catalog_entries),
                "tracks_per_case": SELECTED_TRACKS,
                "interval_sec": 2,
                "cases": catalog_entries,
            },
            f,
            default_flow_style=False,
            allow_unicode=True,
        )
    print(f"\n✅ {len(catalog_entries)} cas sauvegardés dans {CASES_DIR}")


def print_summary():
    """Affiche un résumé de ce qui est téléchargé."""
    total_size = 0
    for f in BASE_DIR.rglob("*"):
        if f.is_file() and f.name != "download_all.py":
            total_size += f.stat().st_size

    n_cases = len(list(CASES_DIR.glob("*.parquet"))) if CASES_DIR.exists() else 0
    print(f"\n{'='*50}")
    print(f"  VitalDB dataset — Résumé")
    print(f"{'='*50}")
    print(f"  Métadonnées cliniques : {'✅' if (BASE_DIR / 'clinical_metadata.csv').exists() else '❌'}")
    print(f"  Résultats labo perop  : {'✅' if (BASE_DIR / 'intraop_labs.csv').exists() else '❌'}")
    print(f"  Index des tracks      : {'✅' if (BASE_DIR / 'track_index.csv').exists() else '❌'}")
    print(f"  Cas numériques        : {n_cases}")
    print(f"  Taille totale         : {total_size / (1024*1024):.1f} Mo")
    print(f"{'='*50}")


def main():
    parser = argparse.ArgumentParser(description="CHARLES — VitalDB Downloader")
    parser.add_argument("--metadata", action="store_true", help="Télécharger métadonnées cliniques")
    parser.add_argument("--cases", type=int, default=0, help="Nombre de cas numériques à télécharger")
    parser.add_argument("--all", action="store_true", help="Tout télécharger (metadata + 200 cas)")
    args = parser.parse_args()

    if not any([args.metadata, args.cases, args.all]):
        parser.print_help()
        return

    df_cases = None

    if args.metadata or args.all:
        df_cases = download_metadata()

    if args.cases > 0 or args.all:
        n = args.cases if args.cases > 0 else 200
        if df_cases is None:
            csv_path = BASE_DIR / "clinical_metadata.csv"
            if csv_path.exists():
                df_cases = pd.read_csv(csv_path)
            else:
                print("Téléchargement des métadonnées d'abord...")
                df_cases = download_metadata()

        case_ids = select_cases(df_cases, n)
        download_cases(case_ids)

    print_summary()


if __name__ == "__main__":
    main()
