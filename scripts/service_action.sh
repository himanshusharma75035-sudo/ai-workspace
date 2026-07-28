#!/usr/bin/env bash
set -euo pipefail
umask 077
PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PROJECT_DIR"

ACTION="${1:-}"
DELAY="${2:-2}"
[[ "$DELAY" =~ ^[0-9]+$ ]] || { echo "Invalid delay" >&2; exit 2; }
sleep "$DELAY"
printf '%s service action started: %s\n' "$(date -Is)" "$ACTION"

case "$ACTION" in
  start_all) ./scripts/start_all.sh ;;
  stop_all) ./scripts/stop_all.sh ;;
  restart_all) ./scripts/restart_all.sh ;;
  restart_app) ./scripts/restart_app.sh ;;
  start_model) ./scripts/start_ollama.sh ;;
  stop_model) ./scripts/stop_ollama.sh ;;
  restart_model) ./scripts/stop_ollama.sh; ./scripts/start_ollama.sh; ./scripts/status.sh ;;
  *) echo "Unsupported service action: $ACTION" >&2; exit 2 ;;
esac

printf '%s service action completed: %s\n' "$(date -Is)" "$ACTION"

