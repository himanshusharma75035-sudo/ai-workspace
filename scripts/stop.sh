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

if [[ ! -f run/app.pid ]]; then
  echo "No application PID file found."
  exit 0
fi
RAW_PID="$(cat run/app.pid 2>/dev/null || true)"
if PID="$(managed_pid run/app.pid uvicorn app.main:app 2>/dev/null)"; then
  kill "$PID"
  if ! wait_for_exit "$PID" 40; then
    echo "Application did not stop within 10 seconds." >&2
    exit 1
  fi
elif [[ "$RAW_PID" =~ ^[0-9]+$ ]] && kill -0 "$RAW_PID" 2>/dev/null; then
  echo "Refusing to stop: run/app.pid belongs to an unmanaged live process." >&2
  exit 1
fi
rm -f run/app.pid
echo "$DISPLAY_NAME stopped."
