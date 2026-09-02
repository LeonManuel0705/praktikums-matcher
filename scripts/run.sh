#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if [ ! -d frontend/dist ]; then
  echo "Frontend bauen..."
  (cd frontend && npm run build)
fi

echo "Backend startet auf http://127.0.0.1:8000"
exec ./.venv/bin/python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 "$@"
