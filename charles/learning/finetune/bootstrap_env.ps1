$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $PSScriptRoot
$VenvPath = Join-Path $RepoRoot ".venv-finetune"
$PythonExe = "py"

if (-not (Test-Path $VenvPath)) {
    & $PythonExe -m venv $VenvPath
}

$VenvPython = Join-Path $VenvPath "Scripts\python.exe"

& $VenvPython -m pip install --upgrade pip
& $VenvPython -m pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu128
& $VenvPython -m pip install -r (Join-Path $PSScriptRoot "requirements.txt")

Write-Host "Fine-tuning environment ready in $VenvPath"
