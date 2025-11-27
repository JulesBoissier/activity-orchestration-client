#!/bin/bash
set -euo pipefail

PORT="${PORT:-8050}"
WORKERS="${WEB_CONCURRENCY:-4}"

# Start Dash (Gunicorn) in background and capture PID
gunicorn -w "$WORKERS" -b 127.0.0.1:"$PORT" src.app.app:server &
GUNICORN_PID=$!

cleanup() {
  echo "Shutting down gunicorn (PID $GUNICORN_PID)..."
  kill "$GUNICORN_PID" 2>/dev/null || true
  # Wait for clean shutdown
  wait "$GUNICORN_PID" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

# Start backend runner (blocking)
python -m src.backend.lifecycle

