#!/usr/bin/env bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$SCRIPT_DIR/backend"
FRONTEND_DIR="$SCRIPT_DIR/frontend"

# Activate the backend venv
source "$BACKEND_DIR/.venv/bin/activate"

# Start local backend (only handles fetch-amex — everything else goes to fly.dev)
echo "==> Starting local backend..."
cd "$BACKEND_DIR"
uvicorn app.main:app --reload &
BACKEND_PID=$!

# Start frontend
echo "==> Starting frontend..."
cd "$FRONTEND_DIR"
npm run dev &
FRONTEND_PID=$!

echo ""
echo "Split app running:"
echo "  Frontend : http://localhost:5173"
echo "  Backend  : http://localhost:8000  (fetch-amex only)"
echo "  Data     : https://split-app-api.fly.dev"
echo ""
echo "Press Ctrl+C to stop."

sleep 2 && open "http://localhost:5173" &

cleanup() {
    echo ""
    echo "Shutting down..."
    kill "$BACKEND_PID" "$FRONTEND_PID" 2>/dev/null || true
    exit 0
}
trap cleanup INT TERM

wait
