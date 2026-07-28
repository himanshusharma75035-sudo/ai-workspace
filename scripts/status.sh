#!/usr/bin/env bash
set -euo pipefail
PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PROJECT_DIR"
source scripts/_service_common.sh
if [[ -f .env ]]; then
  set -a
  source ./.env
  set +a
fi
DISPLAY_NAME="${APP_NAME:-AI Workspace}"

if PID="$(managed_pid run/app.pid uvicorn app.main:app 2>/dev/null)"; then
  printf '%s application: running (PID %s)\n' "$DISPLAY_NAME" "$PID"
else
  printf '%s application: stopped or unmanaged\n' "$DISPLAY_NAME"
fi

if PID="$(managed_pid run/ollama.pid ollama serve 2>/dev/null)"; then
  printf 'Ollama model server: running (PID %s)\n' "$PID"
else
  printf 'Ollama model server: stopped or unmanaged\n'
fi
