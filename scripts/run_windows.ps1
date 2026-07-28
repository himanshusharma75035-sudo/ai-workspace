$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $projectRoot

$venvPython = Join-Path $projectRoot ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $venvPython)) {
    throw "The virtual environment is missing. Run scripts\setup_windows.ps1 first."
}

$envPath = Join-Path $projectRoot ".env"
if (Test-Path -LiteralPath $envPath) {
    foreach ($rawLine in Get-Content -LiteralPath $envPath) {
        $line = $rawLine.Trim()
        if (-not $line -or $line.StartsWith("#") -or -not $line.Contains("=")) {
            continue
        }

        $parts = $line.Split("=", 2)
        $key = $parts[0].Trim()
        $value = $parts[1].Trim().Trim('"').Trim("'")
        if ($key -match '^[A-Za-z_][A-Za-z0-9_]*$') {
            Set-Item -Path "Env:$key" -Value $value
        }
    }
}

if (-not $env:APP_HOST) { $env:APP_HOST = "127.0.0.1" }
if (-not $env:APP_PORT) { $env:APP_PORT = "8181" }
$env:PYTHONPATH = $projectRoot

Write-Host "Starting the configured assistant at http://$($env:APP_HOST):$($env:APP_PORT)"
& $venvPython -m uvicorn app.main:app --host $env:APP_HOST --port $env:APP_PORT

