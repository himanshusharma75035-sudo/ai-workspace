#!/usr/bin/env bash
set -euo pipefail
umask 077

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PROJECT_DIR"

python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/pip install -r requirements-dev.txt

mkdir -p data/knowledge data/uploads logs run models .home
.venv/bin/python scripts/ingest_websites.py
.venv/bin/python -m pytest -q
