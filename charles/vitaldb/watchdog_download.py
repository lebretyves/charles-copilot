"""
CHARLES — Watchdog : surveille et relance le download VitalDB automatiquement.
Lance-le et oublie-le. Il tourne jusqu'à ce que TOUS les cas soient téléchargés.

Usage:
    python watchdog_download.py
"""
import subprocess
import sys
import time
from pathlib import Path

BASE_DIR = Path(__file__).parent
CASES_DIR = BASE_DIR / "cases"
SCRIPT = BASE_DIR / "download_fast.py"

# Nombre total de cas attendus
EXPECTED_CASES = 6388
MAX_RETRIES = 50  # max 50 relances


def count_cases():
    if not CASES_DIR.exists():
        return 0
    return len(list(CASES_DIR.glob("case_*.parquet")))


def run_download(workers=4):
    """Lance download_fast.py et attend qu'il finisse."""
    cmd = [sys.executable, str(SCRIPT), "--workers", str(workers)]
    print(f"\n{'='*60}")
    print(f"  🚀 Lancement download — {count_cases()}/{EXPECTED_CASES} cas sur disque")
    print(f"  Commande: {' '.join(cmd)}")
    print(f"{'='*60}\n")

    result = subprocess.run(cmd, cwd=str(BASE_DIR))
    return result.returncode


def main():
    attempt = 0

    while attempt < MAX_RETRIES:
        n_before = count_cases()

        if n_before >= EXPECTED_CASES:
            print(f"\n✅ TERMINÉ — {n_before} cas téléchargés sur disque !")
            break

        attempt += 1
        print(f"\n--- Tentative {attempt}/{MAX_RETRIES} ---")

        returncode = run_download()

        n_after = count_cases()
        gained = n_after - n_before

        print(f"\n  Résultat: code={returncode}, cas avant={n_before}, après={n_after}, +{gained}")

        if n_after >= EXPECTED_CASES:
            print(f"\n✅ TERMINÉ — {n_after} cas téléchargés !")
            break

        if gained == 0 and returncode != 0:
            # Rien de nouveau + crash → attendre avant de réessayer
            print(f"  ⚠️ Aucun nouveau cas — pause 60s avant retry...")
            time.sleep(60)
        elif gained == 0:
            # Script terminé normalement mais pas assez de cas
            # Probablement des cas vides/invalides → on lance --retry-failed
            print(f"  ℹ️ Script terminé, tentative retry des cas échoués...")
            subprocess.run(
                [sys.executable, str(SCRIPT), "--retry-failed", "--workers", "2"],
                cwd=str(BASE_DIR),
            )
            n_final = count_cases()
            if n_final == n_after:
                print(f"  Pas de progrès supplémentaire. Download terminé avec {n_final} cas.")
                break
        else:
            # Progrès mais pas fini → petite pause puis relance
            print(f"  ↻ Progrès (+{gained} cas) — relance dans 10s...")
            time.sleep(10)

    # Résumé final
    total = count_cases()
    total_size = sum(f.stat().st_size for f in CASES_DIR.glob("case_*.parquet")) if CASES_DIR.exists() else 0
    print(f"\n{'='*60}")
    print(f"  WATCHDOG TERMINÉ")
    print(f"  Cas sur disque : {total}")
    print(f"  Taille totale  : {total_size / (1024*1024):.0f} Mo")
    print(f"  Tentatives     : {attempt}")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
