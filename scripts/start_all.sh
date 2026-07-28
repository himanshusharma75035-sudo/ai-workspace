#!/usr/bin/env bash
set -euo pipefail
PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PROJECT_DIR"
./scripts/start_ollama.sh
./scripts/run.sh
./scripts/status.sh

