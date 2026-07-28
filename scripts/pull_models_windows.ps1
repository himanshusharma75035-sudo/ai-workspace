$ErrorActionPreference = "Stop"
if (-not (Get-Command ollama -ErrorAction SilentlyContinue)) {
    throw "Ollama was not found. Install Ollama for Windows and try again."
}

$env:OLLAMA_HOST = "http://127.0.0.1:11445"
$models = @("qwen3:4b", "qwen3:1.7b", "qwen3:0.6b", "embeddinggemma")

try {
    & ollama list | Out-Null
}
catch {
    throw "Ollama is not reachable at $($env:OLLAMA_HOST). Run scripts\start_ollama_windows.ps1 in another terminal first."
}

if ($LASTEXITCODE -ne 0) {
    throw "Ollama is not reachable at $($env:OLLAMA_HOST). Run scripts\start_ollama_windows.ps1 in another terminal first."
}

foreach ($model in $models) {
    Write-Host "Pulling $model..."
    & ollama pull $model
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to pull $model."
    }
}

Write-Host "All prototype models are available."

