param(
    [switch]$IngestWebsites
)

$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $projectRoot

$venvPython = Join-Path $projectRoot ".venv\Scripts\python.exe"

if (-not (Test-Path -LiteralPath $venvPython)) {
    if (Get-Command py -ErrorAction SilentlyContinue) {
        & py -3 -m venv (Join-Path $projectRoot ".venv")
    }
    elseif (Get-Command python -ErrorAction SilentlyContinue) {
        & python -m venv (Join-Path $projectRoot ".venv")
    }
    else {
        throw "Python 3 was not found. Install Python 3.11 or 3.12 and run this script again."
    }
}

& $venvPython -m pip install --disable-pip-version-check --progress-bar off -r (Join-Path $projectRoot "requirements-dev.txt")

foreach ($directory in @("logs", "run", "data\uploads")) {
    New-Item -ItemType Directory -Force -Path (Join-Path $projectRoot $directory) | Out-Null
}

$envPath = Join-Path $projectRoot ".env"
$envExamplePath = Join-Path $projectRoot ".env.example"
if (-not (Test-Path -LiteralPath $envPath)) {
    if (-not (Test-Path -LiteralPath $envExamplePath)) {
        throw ".env.example is missing."
    }

    $sessionSecret = ([guid]::NewGuid().ToString("N") + [guid]::NewGuid().ToString("N"))
    $envContent = Get-Content -LiteralPath $envExamplePath -Raw
    $envContent = $envContent -replace '(?m)^SESSION_SECRET=.*$', "SESSION_SECRET=`"$sessionSecret`""
    Set-Content -LiteralPath $envPath -Value $envContent -Encoding UTF8
    Write-Host "Created a local .env with a new session secret."
}
else {
    Write-Host "Kept the existing .env unchanged."
}

$env:PYTHONPATH = $projectRoot
if ($IngestWebsites) {
    & $venvPython (Join-Path $projectRoot "scripts\ingest_websites.py")
    if ($LASTEXITCODE -ne 0) {
        throw "Website ingestion failed."
    }
}

& (Join-Path $PSScriptRoot "test_windows.ps1")
Write-Host "Setup complete. Start Ollama, pull the models, then run scripts\run_windows.ps1."
