param(
    [switch]$Force = $true
)

$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $projectRoot

$venvPython = Join-Path $projectRoot ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $venvPython)) {
    throw "The virtual environment is missing. Run scripts\setup_windows.ps1 first."
}

$env:PYTHONPATH = $projectRoot
$arguments = @((Join-Path $projectRoot "scripts\rebuild_embeddings.py"))
if ($Force) { $arguments += "--force" }

& $venvPython @arguments
if ($LASTEXITCODE -ne 0) {
    throw "Embedding rebuild failed."
}

