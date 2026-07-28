#!/usr/bin/env bash
set -euo pipefail
umask 077

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PROJECT_DIR"
MODEL="qwen3:1.7b"
if [[ "$#" -gt 0 ]]; then
  MODEL="$1"
fi

export HOME="$PROJECT_DIR/.home"
export OLLAMA_MODELS="$PROJECT_DIR/models/ollama"
export OLLAMA_HOST="127.0.0.1:11445"

/usr/local/bin/ollama pull "$MODEL"
/usr/local/bin/ollama list
