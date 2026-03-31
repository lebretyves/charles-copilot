"""
CHARLES — Téléchargeur de waveforms VitalDB
============================================
Télécharge les signaux haute fréquence pour un sous-ensemble de cas VitalDB.

Stockage : vitaldb/waveforms/wave_XXXXX_<freq>.parquet

Tracks téléchargés :
  — 500 Hz ——————————————————————————————————————
  - SNUADC/ECG_II   : ECG voie II      (500 Hz) — 6355 cas
  - SNUADC/PLETH    : Pleth SpO2       (500 Hz) — 6157 cas
  - SNUADC/ART      : PA invasive      (500 Hz) — 3645 cas
  — 128 Hz ——————————————————————————————————————
  - BIS/EEG1_WAV    : EEG brut ch1     (128 Hz) — 5871 cas
  — 25 Hz ———————————————————————————————————————
  - Primus/CO2      : Capnographie     ( 25 Hz) — 6362 cas
  - Primus/AWP      : Pression VAE     ( 25 Hz) — 6360 cas

Usage :
    python download_waveforms.py               # 50 premiers cas
    python download_waveforms.py --n 100       # 100 cas
    python download_waveforms.py --workers 8   # 8 téléchargements parallèles
    python download_waveforms.py --caselist 1,42,100,500  # cas spécifiques

Prérequis :
    pip install vitaldb pandas pyarrow tqdm
"""

import argparse
import os
import time
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
from tqdm import tqdm

import vitaldb

# ── Configuration ──────────────────────────────────────────────
BASE_DIR    = Path(__file__).parent
CASES_DIR   = BASE_DIR / "cases"          # parquet numériques existants
WAVE_DIR    = BASE_DIR / "waveforms"      # waveforms haute fréquence (nouveau)
TRACK_INDEX = BASE_DIR / "track_index.csv"
FAILED_LOG  = BASE_DIR / "failed_waveforms.txt"

WAVE_DIR.mkdir(exist_ok=True)

# Tracks waveforms — séparés par fréquence pour éviter l'erreur inhomogène
TRACKS_500HZ = [
    "SNUADC/ECG_II",   # ECG voie II — 500 Hz
    "SNUADC/PLETH",    # Pleth SpO2  — 500 Hz
    "SNUADC/ART",      # PA invasive — 500 Hz
]
TRACKS_128HZ = [
    "BIS/EEG1_WAV",    # EEG brut    — 128 Hz
]
TRACKS_25HZ = [
    "Primus/CO2",      # Capnographie courbe — 25 Hz
    "Primus/AWP",      # Pression voies aériennes — 25 Hz
]
WAVEFORM_TRACKS = TRACKS_500HZ + TRACKS_128HZ + TRACKS_25HZ

INTERVAL_500 = 1 / 500
INTERVAL_128 = 1 / 128
INTERVAL_25  = 1 / 25


# ── Sélection des cas ──────────────────────────────────────────
def select_cases(n: int, caselist: list[int] | None) -> list[int]:
    """Retourne la liste des caseid à télécharger."""
    if caselist:
        return sorted(caselist)

    ti = pd.read_csv(TRACK_INDEX)
    all_cases = sorted(ti["caseid"].unique())
    return all_cases[:n]


# ── Téléchargement d'un cas ────────────────────────────────────
def download_case(caseid: int) -> tuple[int, str]:
    """Télécharge les waveforms d'un cas. Retourne (caseid, status)."""
    out_500 = WAVE_DIR / f"wave_{caseid:05d}_500hz.parquet"
    out_128 = WAVE_DIR / f"wave_{caseid:05d}_128hz.parquet"
    out_25  = WAVE_DIR / f"wave_{caseid:05d}_25hz.parquet"

    if out_500.exists() and out_128.exists() and out_25.exists():
        return caseid, "skip"

    try:
        frames = []

        # Groupe 1 : tracks 500 Hz
        if not out_500.exists():
            try:
                vf = vitaldb.VitalFile(caseid, TRACKS_500HZ)
                avail_500 = [t for t in TRACKS_500HZ if t in vf.get_track_names()]
                if avail_500:
                    df500 = vf.to_pandas(avail_500, INTERVAL_500)
                    df500.columns = avail_500
                    df500.insert(0, "time_sec", [i * INTERVAL_500 for i in range(len(df500))])
                    frames.append(("500hz", df500))
            except Exception:
                pass

        # Groupe 2 : EEG 128 Hz
        if not out_128.exists():
            try:
                vf2 = vitaldb.VitalFile(caseid, TRACKS_128HZ)
                avail_128 = [t for t in TRACKS_128HZ if t in vf2.get_track_names()]
                if avail_128:
                    df128 = vf2.to_pandas(avail_128, INTERVAL_128)
                    df128.columns = avail_128
                    df128.insert(0, "time_sec", [i * INTERVAL_128 for i in range(len(df128))])
                    frames.append(("128hz", df128))
            except Exception:
                pass

        # Groupe 3 : Respiratoire 25 Hz (CO2 capno + AWP pression VAE)
        if not out_25.exists():
            try:
                vf3 = vitaldb.VitalFile(caseid, TRACKS_25HZ)
                avail_25 = [t for t in TRACKS_25HZ if t in vf3.get_track_names()]
                if avail_25:
                    df25 = vf3.to_pandas(avail_25, INTERVAL_25)
                    df25.columns = avail_25
                    df25.insert(0, "time_sec", [i * INTERVAL_25 for i in range(len(df25))])
                    frames.append(("25hz", df25))
            except Exception:
                pass

        if not frames:
            return caseid, "no_tracks"

        total_pts = 0
        total_mb = 0
        track_count = 0

        for suffix, df in frames:
            path = WAVE_DIR / f"wave_{caseid:05d}_{suffix}.parquet"
            if not path.exists():
                table = pa.Table.from_pandas(df, preserve_index=False)
                pq.write_table(table, path, compression="snappy")
            total_pts += len(df)
            total_mb += path.stat().st_size / 1e6
            track_count += len(df.columns) - 1  # -1 pour time_sec

        return caseid, f"ok ({track_count} tracks, {total_pts:,} pts, {total_mb:.1f} Mo)"

    except Exception as e:
        return caseid, f"error: {e}"


# ── Main ───────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="Télécharge les waveforms VitalDB 500Hz")
    parser.add_argument("--n",        type=int, default=50,  help="Nombre de cas (défaut: 50)")
    parser.add_argument("--workers",  type=int, default=4,   help="Workers parallèles (défaut: 4)")
    parser.add_argument("--caselist", type=str, default=None, help="Ex: 1,42,100,500")
    args = parser.parse_args()

    caselist = [int(x) for x in args.caselist.split(",")] if args.caselist else None
    cases = select_cases(args.n, caselist)

    print(f"╔══════════════════════════════════════════════════════╗")
    print(f"║  CHARLES — Téléchargement waveforms VitalDB          ║")
    print(f"╚══════════════════════════════════════════════════════╝")
    print(f"  Dossier de sortie : {WAVE_DIR}")
    print(f"  Cas à télécharger : {len(cases)}")
    print(f"  Workers parallèles: {args.workers}")
    print(f"  Groupes           : 500Hz (ECG/Pleth/ART) | 128Hz (EEG) | 25Hz (CO2/AWP)")
    print()

    t_start = time.time()
    results = {"ok": 0, "skip": 0, "error": 0, "no_tracks": 0}
    failed = []

    with ThreadPoolExecutor(max_workers=args.workers) as exe:
        futures = {exe.submit(download_case, cid): cid for cid in cases}
        with tqdm(total=len(cases), unit="cas", ncols=80) as pbar:
            for fut in as_completed(futures):
                caseid, status = fut.result()
                if status == "skip":
                    results["skip"] += 1
                    pbar.set_postfix(skip=results["skip"])
                elif status.startswith("ok"):
                    results["ok"] += 1
                    pbar.set_postfix(ok=results["ok"])
                elif status == "no_tracks":
                    results["no_tracks"] += 1
                else:
                    results["error"] += 1
                    failed.append(f"{caseid}: {status}")
                pbar.update(1)

    elapsed = time.time() - t_start

    # Log des échecs
    if failed:
        FAILED_LOG.write_text("\n".join(failed))
        print(f"\n⚠ {len(failed)} cas en erreur → {FAILED_LOG}")

    # Résumé
    total_size = sum(f.stat().st_size for f in WAVE_DIR.glob("wave_*.parquet")) / 1e9
    print(f"\n{'─'*54}")
    print(f"  ✅ Téléchargés  : {results['ok']}")
    print(f"  ⏭  Déjà présents: {results['skip']}")
    print(f"  ⚠  Sans tracks  : {results['no_tracks']}")
    print(f"  ❌ Erreurs      : {results['error']}")
    print(f"  ⏱  Durée        : {elapsed:.0f}s")
    print(f"  💾 Taille totale: {total_size:.2f} Go")
    print(f"  📁 Dossier      : {WAVE_DIR}")
    print(f"{'─'*54}")


if __name__ == "__main__":
    main()
