#!/usr/bin/env bash
set -euo pipefail
umask 077

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PROJECT_DIR"
source scripts/_service_common.sh
mkdir -p logs run

set -a
source ./.env
set +a
DISPLAY_NAME="${APP_NAME:-AI Workspace}"

if PID="$(managed_pid run/app.pid uvicorn app.main:app 2>/dev/null)"; then
  echo "$DISPLAY_NAME is already running with PID $PID"
  exit 0
fi
if [[ -f run/app.pid ]]; then
  STALE_PID="$(cat run/app.pid 2>/dev/null || true)"
  if [[ "$STALE_PID" =~ ^[0-9]+$ ]] && kill -0 "$STALE_PID" 2>/dev/null; then
    echo "Refusing to start: run/app.pid belongs to an unmanaged live process." >&2
    exit 1
  fi
  rm -f run/app.pid
fi

nohup .venv/bin/python -m uvicorn app.main:app \
  --host "$APP_HOST" \
  --port "$APP_PORT" \
  > logs/app.log 2>&1 &
echo $! > run/app.pid

sleep 2
if ! kill -0 "$(cat run/app.pid)" 2>/dev/null; then
  echo "Application failed to start. Check logs/app.log."
  exit 1
fi
echo "$DISPLAY_NAME started on http://$APP_HOST:$APP_PORT"
