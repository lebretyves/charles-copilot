$ErrorActionPreference = 'Stop'

$projectRoot = 'd:\projet Iade\charles'
$pythonExe = 'C:\Users\lebre\AppData\Local\Python\pythoncore-3.14-64\python.exe'
$manifestPath = 'd:\projet Iade\charles\learning\datasets\manifests\vitaldb_waveforms_local50_dense.yaml'
$runDir = 'd:\projet Iade\charles\learning\datasets\exports\vitaldb_waveforms_local50_dense'
$logDir = Join-Path $runDir 'logs'
$logPath = Join-Path $logDir 'background_runner.log'

New-Item -ItemType Directory -Force -Path $logDir | Out-Null

$timestamp = Get-Date -Format s
"[$timestamp] starting dense local50 waveform extraction" | Out-File -FilePath $logPath -Encoding utf8 -Append

Set-Location $projectRoot

& $pythonExe -m learning.pipelines.build_vitaldb_dataset `
  --manifest $manifestPath `
  --limit-cases 50 `
  --case-selection first 2>&1 | Tee-Object -FilePath $logPath -Append

$timestamp = Get-Date -Format s
"[$timestamp] dense local50 waveform extraction finished" | Out-File -FilePath $logPath -Encoding utf8 -Append
