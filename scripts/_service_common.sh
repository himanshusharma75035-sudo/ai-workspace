#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

managed_pid() {
  local pid_file="$1"
  local expected_a="$2"
  local expected_b="$3"
  [[ -f "$pid_file" ]] || return 1
  local pid
  pid="$(cat "$pid_file" 2>/dev/null || true)"
  [[ "$pid" =~ ^[0-9]+$ ]] || return 1
  kill -0 "$pid" 2>/dev/null || return 1
  [[ -e "/proc/$pid/cwd" && "$(readlink -f "/proc/$pid/cwd")" == "$PROJECT_DIR" ]] || return 1
  local command
  command="$(tr '\0' ' ' < "/proc/$pid/cmdline" 2>/dev/null || true)"
  [[ "$command" == *"$expected_a"* && "$command" == *"$expected_b"* ]] || return 1
  printf '%s' "$pid"
}

wait_for_exit() {
  local pid="$1"
  local attempts="$2"
  for _ in $(seq 1 "$attempts"); do
    kill -0 "$pid" 2>/dev/null || return 0
    sleep 0.25
  done
  return 1
}

