#!/usr/bin/env python3
"""
CHARLES - Lanceur universel (Windows / macOS / Linux)
python start.py

Ce script :
  1. Verifie / installe Docker si absent
  2. Demarre Docker Desktop (Win/Mac) ou le daemon (Linux)
  3. Cree le .env depuis .env.example si manquant
  4. Lance docker compose up --build
  5. Attend que le frontend soit pret
  6. Ouvre le navigateur sur http://localhost:3000
"""

import os
import sys
import platform
import subprocess
import shutil
import ssl
import time
import urllib.request
import webbrowser
from pathlib import Path

# ── Configuration ──────────────────────────────────────────────
FRONTEND_URL   = "http://localhost:3000"
FRONTEND_HEALTH_URL = f"{FRONTEND_URL}/health"
BACKEND_URL    = "http://localhost:8000"
HEALTHCHECK_TIMEOUT = 180  # secondes
COMPOSE_FILE   = Path(__file__).parent / "docker-compose.yml"
ENV_FILE       = Path(__file__).parent / ".env"
ENV_EXAMPLE    = Path(__file__).parent / ".env.example"


# ── Couleurs ANSI (fonctionne partout dès Python 3.8+) ────────
def _ansi(code: str) -> str:
    if os.name == "nt":
        # Active le support ANSI sur Windows 10+
        try:
            import ctypes
            kernel = ctypes.windll.kernel32
            kernel.SetConsoleMode(kernel.GetStdHandle(-11), 7)
        except Exception:
            return ""
    return f"\033[{code}m"

RESET   = _ansi("0")
BOLD    = _ansi("1")
RED     = _ansi("91")
GREEN   = _ansi("92")
YELLOW  = _ansi("93")
BLUE    = _ansi("94")
CYAN    = _ansi("96")
WHITE   = _ansi("97")
DIM     = _ansi("2")


def header():
    print(
        f"\n{CYAN}{BOLD}=============================================================={RESET}\n"
        f"{CYAN}{BOLD}  {WHITE}CHARLES{CYAN} - Lanceur universel v1.0{RESET}\n"
        f"{DIM}  Copilote IA Vigilance Anesthesique Perioperatoire{RESET}\n"
        f"{CYAN}{BOLD}=============================================================={RESET}\n"
    )


def info(msg: str):
    print(f"  {BLUE}[INFO]{RESET} {msg}")


def ok(msg: str):
    print(f"  {GREEN}[ OK ]{RESET} {msg}")


def warn(msg: str):
    print(f"  {YELLOW}[WARN]{RESET} {msg}")


def err(msg: str):
    print(f"  {RED}[ERR ]{RESET} {msg}")


def step(msg: str):
    print(f"\n{BOLD}{CYAN}== {msg}{RESET}")


def fatal(msg: str):
    err(msg)
    print(f"\n{RED}{BOLD}Impossible de continuer. Corrigez le problème et relancez start.py{RESET}")
    sys.exit(1)


# ── Détection OS ───────────────────────────────────────────────
def detect_os() -> str:
    s = platform.system().lower()
    if s == "windows":
        return "windows"
    if s == "darwin":
        return "mac"
    return "linux"


OS = detect_os()

# ── Utilitaires système ────────────────────────────────────────
def run(cmd: list[str], capture: bool = False, check: bool = True, **kwargs):
    """Lance une commande. Si capture=True, retourne (returncode, stdout, stderr)."""
    if capture:
        result = subprocess.run(
            cmd, capture_output=True, text=True,
            encoding="utf-8", errors="replace", **kwargs
        )
        if check and result.returncode != 0:
            raise subprocess.CalledProcessError(result.returncode, cmd, result.stdout, result.stderr)
        return result.returncode, result.stdout, result.stderr
    else:
        return subprocess.run(cmd, check=check, **kwargs)


def cmd_exists(name: str) -> bool:
    return shutil.which(name) is not None


def url_is_ready(url: str, timeout: float = 2.0) -> bool:
    try:
        if url.startswith("https://"):
            ssl_context = ssl.create_default_context()
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE
            with urllib.request.urlopen(url, timeout=timeout, context=ssl_context) as response:
                return 200 <= response.status < 400
        with urllib.request.urlopen(url, timeout=timeout) as response:
            return 200 <= response.status < 400
    except Exception:
        return False


# ── Vérification Python ────────────────────────────────────────
def check_python():
    step("Python")
    major, minor = sys.version_info[:2]
    if major < 3 or (major == 3 and minor < 8):
        fatal(f"Python 3.8+ requis — version actuelle : {major}.{minor}")
    ok(f"Python {major}.{minor} OK")


# ── Docker : installation ──────────────────────────────────────
def install_docker_windows():
    warn("Docker Desktop non trouvé — tentative d'installation via winget …")
    if not cmd_exists("winget"):
        fatal(
            "winget introuvable. Installez Docker Desktop manuellement :\n"
            "  https://docs.docker.com/desktop/install/windows-install/"
        )
    info("Installation de Docker Desktop (peut prendre quelques minutes) …")
    run(["winget", "install", "--id", "Docker.DockerDesktop",
         "-e", "--accept-source-agreements", "--accept-package-agreements"])
    ok("Docker Desktop installé — un redémarrage peut être nécessaire.")
    warn("Relancez start.py après le redémarrage si Docker ne s'ouvre pas.")
    sys.exit(0)


def install_docker_mac():
    warn("Docker Desktop non trouvé — tentative d'installation via Homebrew …")
    if not cmd_exists("brew"):
        fatal(
            "Homebrew introuvable. Installez-le depuis https://brew.sh\n"
            "puis relancez start.py"
        )
    info("Installation de Docker Desktop via brew …")
    run(["brew", "install", "--cask", "docker"])
    ok("Docker Desktop installé.")


def install_docker_linux():
    warn("Docker non trouvé — installation via le script officiel Docker …")
    if not cmd_exists("curl"):
        fatal("curl est requis pour l'installation automatique de Docker.")
    info("Téléchargement et exécution du script d'installation Docker …")
    rc, _, _ = run(
        ["bash", "-c", "curl -fsSL https://get.docker.com | sh"],
        capture=True, check=False
    )
    if rc != 0:
        fatal(
            "L'installation automatique a échoué.\n"
            "Installez Docker manuellement : https://docs.docker.com/engine/install/"
        )
    # Ajouter l'utilisateur courant au groupe docker
    user = os.environ.get("USER", "")
    if user:
        run(["sudo", "usermod", "-aG", "docker", user], check=False)
    ok("Docker installé. Vous devrez peut-être vous déconnecter/reconnecter pour le groupe docker.")
    run(["sudo", "systemctl", "enable", "--now", "docker"], check=False)


def ensure_docker_installed():
    step("Vérification de l'installation Docker")
    if cmd_exists("docker"):
        ok("Docker trouvé : " + shutil.which("docker"))
        return
    # Docker absent — proposer l'installation
    if OS == "windows":
        install_docker_windows()
    elif OS == "mac":
        install_docker_mac()
    else:
        install_docker_linux()
    # Rechargement du PATH après installation
    if not cmd_exists("docker"):
        fatal("Docker n'est toujours pas accessible après installation.\n"
              "Ouvrez un nouveau terminal et relancez start.py")


# ── Docker : démarrage du daemon / Desktop ─────────────────────
def docker_is_running() -> bool:
    rc, _, _ = run(["docker", "info"], capture=True, check=False)
    return rc == 0


def start_docker_windows():
    desktop = Path(os.environ.get("ProgramFiles", "C:\\Program Files")) / "Docker" / "Docker" / "Docker Desktop.exe"
    if not desktop.exists():
        # Chercher dans Program Files (x86) aussi
        alt = Path("C:\\Program Files\\Docker\\Docker\\Docker Desktop.exe")
        if not alt.exists():
            fatal(f"Docker Desktop introuvable dans {desktop}\nInstallez-le depuis https://www.docker.com")
        desktop = alt
    info("Lancement de Docker Desktop …")
    subprocess.Popen([str(desktop)], creationflags=subprocess.DETACHED_PROCESS)


def start_docker_mac():
    app = Path("/Applications/Docker.app")
    if not app.exists():
        fatal("Docker Desktop introuvable dans /Applications/Docker.app")
    info("Lancement de Docker Desktop …")
    subprocess.Popen(["open", str(app)])


def start_docker_linux():
    info("Démarrage du daemon Docker …")
    # Essaie systemctl puis service
    rc = run(["sudo", "systemctl", "start", "docker"], check=False).returncode
    if rc != 0:
        run(["sudo", "service", "docker", "start"], check=False)


def wait_for_docker(timeout: int = 60):
    deadline = time.time() + timeout
    dots = 0
    while time.time() < deadline:
        if docker_is_running():
            print()
            return True
        print(f"\r  {BLUE}[INFO]{RESET} Attente de Docker {'.' * (dots % 4 + 1)}   ", end="", flush=True)
        dots += 1
        time.sleep(2)
    print()
    return False


def ensure_docker_running():
    step("Démarrage de Docker")
    if docker_is_running():
        ok("Docker daemon actif")
        return
    warn("Docker n'est pas démarré — lancement automatique …")
    if OS == "windows":
        start_docker_windows()
    elif OS == "mac":
        start_docker_mac()
    else:
        start_docker_linux()
    info("Attente que Docker soit prêt (60 s max) …")
    if not wait_for_docker(60):
        fatal(
            "Docker n'a pas démarré dans le délai imparti.\n"
            "Lancez Docker Desktop manuellement puis relancez start.py"
        )
    ok("Docker pret")


# ── Docker Compose : vérification ─────────────────────────────
def get_compose_cmd() -> list[str]:
    """Retourne la commande docker compose disponible."""
    # Docker Compose v2 (intégré à docker)
    rc, _, _ = run(["docker", "compose", "version"], capture=True, check=False)
    if rc == 0:
        return ["docker", "compose"]
    # Docker Compose v1 (binaire séparé)
    if cmd_exists("docker-compose"):
        return ["docker-compose"]
    fatal(
        "docker compose introuvable.\n"
        "Mettez à jour Docker Desktop ou installez docker-compose :\n"
        "  https://docs.docker.com/compose/install/"
    )


# ── Fichier .env ───────────────────────────────────────────────
def ensure_env():
    step("Fichier de configuration .env")
    if ENV_FILE.exists():
        ok(f".env trouvé : {ENV_FILE}")
        return
    if not ENV_EXAMPLE.exists():
        warn(".env.example absent — le .env ne sera pas créé automatiquement.")
        return
    import shutil as _sh
    _sh.copy(ENV_EXAMPLE, ENV_FILE)
    ok(f".env créé depuis .env.example : {ENV_FILE}")
    warn("Pensez à éditer .env pour adapter JWT_SECRET et les mots de passe en production.")


# ── Lancement de la stack ──────────────────────────────────────
def launch_stack(compose_cmd: list[str]):
    step("Lancement de la stack CHARLES")
    info("docker compose up --build (première fois : ~5 à 10 min) …")
    print(f"\n{DIM}{'-' * 64}{RESET}\n")

    cmd = compose_cmd + [
        "--file", str(COMPOSE_FILE),
        "up", "--build", "--detach",
        "--remove-orphans"
    ]
    result = subprocess.run(cmd)
    print(f"\n{DIM}{'-' * 64}{RESET}")
    if result.returncode != 0:
        fatal("docker compose up a échoué — consultez les logs ci-dessus.")
    ok("Tous les services sont lances en arriere-plan")


# ── Attente du frontend ────────────────────────────────────────
def wait_for_frontend():
    step(f"Attente du frontend ({FRONTEND_URL})")
    deadline = time.time() + HEALTHCHECK_TIMEOUT
    dots = 0
    while time.time() < deadline:
        if url_is_ready(FRONTEND_HEALTH_URL):
            print()
            ok(f"Frontend pret - {FRONTEND_URL}")
            return
        remaining = int(deadline - time.time())
        print(
            f"\r  {BLUE}[INFO]{RESET} Demarrage des containers {'.' * (dots % 4 + 1)} "
            f"({remaining}s restantes)   ",
            end="", flush=True
        )
        dots += 1
        time.sleep(3)
    print()
    warn(f"Le frontend n'est pas encore disponible après {HEALTHCHECK_TIMEOUT}s.")
    warn("Vous pouvez tout de meme ouvrir http://localhost:3000 dans quelques instants.")


# ── Commandes utiles ───────────────────────────────────────────
def show_useful_commands(compose_cmd: list[str]):
    cmd_str = " ".join(compose_cmd)
    print(f"{DIM}Commandes utiles :{RESET}")
    print(f"  {DIM}Voir les logs      :{RESET}  {cmd_str} logs -f")
    print(f"  {DIM}Arrêter            :{RESET}  {cmd_str} down")
    print(f"  {DIM}Réinitialiser BDD  :{RESET}  {cmd_str} down -v && {cmd_str} up --build")
    print(f"  {DIM}Relancer simulateur:{RESET}  {cmd_str} restart simulator")
    print()


# ── Point d'entrée ─────────────────────────────────────────────
def print_summary():
    print(
        f"""
{CYAN}{BOLD}=============================================================={RESET}
{CYAN}{BOLD}  CHARLES est demarre{RESET}

  {GREEN}Frontend{RESET}   {FRONTEND_URL}
  {BLUE}Backend{RESET}    {BACKEND_URL}/docs

  Identifiants par defaut:
    login    : admin
    password : admin2026

  Utilisez docker compose down pour arreter la stack.
"""
    )


def main():
    # Changer le répertoire de travail vers celui du script
    os.chdir(Path(__file__).parent)

    header()
    info(f"Système détecté : {platform.system()} {platform.release()} ({OS})")
    info(f"Répertoire      : {Path(__file__).parent}")

    check_python()
    ensure_docker_installed()
    ensure_docker_running()

    compose_cmd = get_compose_cmd()
    ok(f"docker compose trouve : {' '.join(compose_cmd)}")

    ensure_env()
    launch_stack(compose_cmd)
    wait_for_frontend()
    print_summary()
    show_useful_commands(compose_cmd)

    # Ouvrir le navigateur
    info(f"Ouverture de {FRONTEND_URL} dans votre navigateur …")
    time.sleep(1)
    webbrowser.open(FRONTEND_URL)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print(f"\n\n{YELLOW}Interruption utilisateur — la stack Docker continue de tourner en arrière-plan.{RESET}")
        print(f"{DIM}Pour arrêter : docker compose down{RESET}\n")
        sys.exit(0)
