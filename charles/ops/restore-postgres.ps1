param(
    [Parameter(Mandatory = $true)]
    [string]$DumpFile,
    [string]$ComposeFile = "docker-compose.prod.yml",
    [string]$EnvFile = ".env.prod"
)

if (-not (Test-Path $DumpFile)) {
    throw "Dump file not found: $DumpFile"
}

$repoRoot = Split-Path -Parent $PSScriptRoot

Push-Location $repoRoot
try {
    Get-Content -Path $DumpFile | docker compose -f $ComposeFile --env-file $EnvFile exec -T postgres psql -U charles -d charles
    Write-Host "Restore completed from $DumpFile"
}
finally {
    Pop-Location
}
