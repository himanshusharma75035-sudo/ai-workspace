# Windows Setup

Use these steps from the project root in a PowerShell terminal.

## Prerequisites

- Windows 10 or 11
- Python 3.11 or 3.12 available as `py` or `python`
- Ollama for local model execution
- Optional: Node.js, used only for JavaScript syntax checks and browser tooling
- Enough free disk space for the selected Ollama models

The setup script installs both runtime and development dependencies from `requirements-dev.txt`.

## Automated project setup

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\scripts\setup_windows.ps1
```

This creates a Windows virtual environment, installs Python dependencies, creates local runtime directories, produces a secret-safe `.env` if one does not exist, and runs the test suite. It does not overwrite an existing `.env`.

To rebuild the public website knowledge during setup:

```powershell
.\scripts\setup_windows.ps1 -IngestWebsites
```

Website ingestion requires internet access and should only be run when the approved source list is still correct.

## Start Ollama on the prototype port

Open a separate PowerShell terminal:

```powershell
.\scripts\start_ollama_windows.ps1
```

The script sets Ollama to `127.0.0.1:11445`, which matches `.env`.

In another terminal, download the configured models once:

```powershell
.\scripts\pull_models_windows.ps1
```

Model downloads are intentionally not stored in this project folder.

## Start the configured assistant

```powershell
.\scripts\run_windows.ps1
```

Open [http://127.0.0.1:8181](http://127.0.0.1:8181). Check health at [http://127.0.0.1:8181/api/health](http://127.0.0.1:8181/api/health).

## Test without starting the app

```powershell
.\scripts\test_windows.ps1
```

## Contributor workspace instructions

Open the cloned repository as the workspace root. Coding agents should read `AGENTS.md`, `docs/PROJECT_CONTEXT.md` and the relevant technical documentation before making changes.

## Common issues

### PowerShell blocks scripts

Use this only for the current terminal:

```powershell
Set-ExecutionPolicy -Scope Process Bypass
```

### Port 8181 is already occupied

Find the listener:

```powershell
Get-NetTCPConnection -LocalPort 8181 -State Listen
```

Change `APP_PORT` in `.env` only if a different port is intended.

### Ollama is unreachable

Confirm the model server is running on the same port as `OLLAMA_BASE_URL`:

```powershell
Invoke-RestMethod http://127.0.0.1:11445/api/tags
```

### Voice input does not work

Speech recognition depends on browser support and microphone permission. Use a current Chrome or Edge build, open the site from localhost or HTTPS, and allow microphone access.
