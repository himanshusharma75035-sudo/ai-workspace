$ErrorActionPreference = "Stop"
if (-not (Get-Command ollama -ErrorAction SilentlyContinue)) {
    throw "Ollama was not found. Install Ollama for Windows and try again."
}

$env:OLLAMA_HOST = "http://127.0.0.1:11445"
Write-Host "Starting Ollama at $($env:OLLAMA_HOST). Keep this terminal open."
& ollama serve

