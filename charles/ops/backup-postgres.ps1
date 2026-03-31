param(
    [string]$ComposeFile = "docker-compose.prod.yml",
    [string]$EnvFile = ".env.prod",
    [string]$BackupDir = ""
)

$repoRoot = Split-Path -Parent $PSScriptRoot
if (-not $BackupDir) {
    $BackupDir = Join-Path $PSScriptRoot "backups"
}

New-Item -ItemType Directory -Force -Path $BackupDir | Out-Null
$timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
$target = Join-Path $BackupDir "charles-postgres-$timestamp.sql"

Push-Location $repoRoot
try {
    docker compose -f $ComposeFile --env-file $EnvFile exec -T postgres pg_dump -U charles -d charles > $target
    Write-Host "Backup written to $target"
}
finally {
    Pop-Location
}
