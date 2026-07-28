#!/usr/bin/env bash
set -euo pipefail
umask 077

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PROJECT_DIR"
source scripts/_service_common.sh

if PID="$(managed_pid run/ollama.pid ollama serve 2>/dev/null)"; then
  echo "Project-local Ollama is already running with PID $PID"
  exit 0
fi
if [[ -f run/ollama.pid ]]; then
  STALE_PID="$(cat run/ollama.pid 2>/dev/null || true)"
  if [[ "$STALE_PID" =~ ^[0-9]+$ ]] && kill -0 "$STALE_PID" 2>/dev/null; then
    echo "Refusing to start: run/ollama.pid belongs to an unmanaged live process." >&2
    exit 1
  fi
  rm -f run/ollama.pid
fi

mkdir -p .home models/ollama logs run
export HOME="$PROJECT_DIR/.home"
export OLLAMA_MODELS="$PROJECT_DIR/models/ollama"
export OLLAMA_HOST="127.0.0.1:11445"

nohup /usr/local/bin/ollama serve > logs/ollama.log 2>&1 &
echo $! > run/ollama.pid
sleep 2
kill -0 "$(cat run/ollama.pid)"
echo "Project-local Ollama started on $OLLAMA_HOST"
