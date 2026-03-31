@echo off
chcp 65001 >nul 2>&1
title CHARLES — Lanceur

:: ── Cherche Python dans l'ordre de priorité ──────────────────
set PYTHON=

:: 1. python3
where python3 >nul 2>&1 && set PYTHON=python3 && goto :found

:: 2. python (vérifie que c'est bien Python 3)
where python >nul 2>&1 && (
    python -c "import sys; sys.exit(0 if sys.version_info[0]>=3 else 1)" >nul 2>&1
    if not errorlevel 1 set PYTHON=python && goto :found
)

:: 3. py launcher (Python for Windows)
where py >nul 2>&1 && set PYTHON=py -3 && goto :found

:: ── Python introuvable → proposer l'installation ──────────────
echo.
echo  [ERREUR] Python 3 est introuvable sur ce poste.
echo.
echo  Installez Python 3.x depuis https://www.python.org/downloads/
echo  Cochez bien "Add python.exe to PATH" pendant l'installation.
echo  Puis relancez ce fichier.
echo.
pause
exit /b 1

:found
echo.
echo  CHARLES — Lanceur universel
echo  Python utilise : %PYTHON%
echo.

:: ── Lance start.py ────────────────────────────────────────────
%PYTHON% "%~dp0start.py"

if errorlevel 1 (
    echo.
    echo  [ERREUR] Une erreur est survenue. Voir le message ci-dessus.
    pause
)
