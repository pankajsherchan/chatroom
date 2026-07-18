#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
VENV_PYTHON="$ROOT/backend/.venv/bin/python"

if [[ ! -x "$VENV_PYTHON" ]]; then
  echo "Backend virtualenv not found. Run: cd backend && uv sync" >&2
  exit 1
fi

exec "$VENV_PYTHON" "$ROOT/mock_services/external_api/main.py"
