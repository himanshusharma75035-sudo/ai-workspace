#!/usr/bin/env bash
set -euo pipefail
PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PROJECT_DIR"
source scripts/_service_common.sh

if [[ ! -f run/ollama.pid ]]; then
  echo "No Ollama PID file found."
  exit 0
fi
RAW_PID="$(cat run/ollama.pid 2>/dev/null || true)"
if PID="$(managed_pid run/ollama.pid ollama serve 2>/dev/null)"; then
  kill "$PID"
  if ! wait_for_exit "$PID" 60; then
    echo "Ollama did not stop within 15 seconds." >&2
    exit 1
  fi
elif [[ "$RAW_PID" =~ ^[0-9]+$ ]] && kill -0 "$RAW_PID" 2>/dev/null; then
  echo "Refusing to stop: run/ollama.pid belongs to an unmanaged live process." >&2
  exit 1
fi
rm -f run/ollama.pid
echo "Project-local Ollama stopped."
