$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $projectRoot

$venvPython = Join-Path $projectRoot ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $venvPython)) {
    throw "The virtual environment is missing. Run scripts\setup_windows.ps1 first."
}

$env:PYTHONPATH = $projectRoot
& $venvPython -m ruff check app scripts tests
if ($LASTEXITCODE -ne 0) {
    throw "Python lint checks failed."
}

& $venvPython -m pytest -q
if ($LASTEXITCODE -ne 0) {
    throw "Python tests failed."
}

if (Get-Command node -ErrorAction SilentlyContinue) {
    & node --check (Join-Path $projectRoot "app\static\app.js")
    if ($LASTEXITCODE -ne 0) {
        throw "JavaScript syntax check failed."
    }
    & node --check (Join-Path $projectRoot "app\static\enhancements.js")
    if ($LASTEXITCODE -ne 0) {
        throw "Enhancement JavaScript syntax check failed."
    }
}
else {
    Write-Warning "Node.js was not found; skipped the JavaScript syntax check."
}

Write-Host "All available checks passed."
