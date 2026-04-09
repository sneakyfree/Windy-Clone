#!/usr/bin/env bash
# Start both frontend and backend dev servers.
# Usage: ./scripts/dev.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"

echo "🌊 Starting Windy Clone development servers..."

# Start API server in background
echo "   Starting API server on :8400..."
cd "$ROOT_DIR"
uv run uvicorn api.app.main:app --reload --port 8400 &
API_PID=$!

# Start frontend dev server
echo "   Starting frontend dev server on :5173..."
cd "$ROOT_DIR/web"
npm run dev &
WEB_PID=$!

echo ""
echo "🌊 Windy Clone is running!"
echo "   Frontend: http://localhost:5173"
echo "   API:      http://localhost:8400"
echo "   API docs: http://localhost:8400/docs"
echo ""
echo "   Press Ctrl+C to stop both servers."

# Cleanup on exit
cleanup() {
    echo ""
    echo "🛑 Shutting down..."
    kill $API_PID 2>/dev/null || true
    kill $WEB_PID 2>/dev/null || true
    wait
    echo "   Done."
}
trap cleanup EXIT INT TERM

# Wait for either to exit
wait
