#!/bin/bash

# ── Colors ─────────────────────────────────────────────────────────────────────
GOLD='\033[0;33m'
GREEN='\033[0;32m'
RED='\033[0;31m'
DIM='\033[2m'
RESET='\033[0m'

# ── Cleanup ────────────────────────────────────────────────────────────────────
cleanup() {
    echo ""
    echo -e "${GOLD}Shutting down servers...${RESET}"
    kill $API_PID $FRONTEND_PID 2>/dev/null
    wait $API_PID 2>/dev/null
    wait $FRONTEND_PID 2>/dev/null
    echo -e "${DIM}Done.${RESET}"
    exit 0
}

trap cleanup SIGINT SIGTERM

# ── Root check ─────────────────────────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# ── FastAPI Backend (:8000) ────────────────────────────────────────────────────
echo -e "${GOLD}▶ Starting FastAPI backend on port 8000...${RESET}"
PYTHONPATH=src uv run uvicorn marketing_agent.server:app --port 8000 --reload &
API_PID=$!

# Wait for backend to be ready
echo -e "${DIM}  Waiting for backend...${RESET}"
for i in {1..15}; do
    if curl -s http://localhost:8000/health > /dev/null 2>&1 || \
       curl -s http://localhost:8000/docs    > /dev/null 2>&1 || \
       curl -s http://localhost:8000/        > /dev/null 2>&1; then
        echo -e "${GREEN}  Backend ready.${RESET}"
        break
    fi
    sleep 1
done

# ── Vite Frontend (:5173) ──────────────────────────────────────────────────────
echo -e "${GOLD}▶ Starting Vite frontend on port 5173...${RESET}"
cd frontend && npm run dev &
FRONTEND_PID=$!
cd "$SCRIPT_DIR"

# ── Summary ────────────────────────────────────────────────────────────────────
echo ""
echo -e "${GREEN}All servers running!${RESET}"
echo -e "  ${DIM}Backend  →${RESET}  http://localhost:8000"
echo -e "  ${DIM}Frontend →${RESET}  http://localhost:5173"
echo -e "  ${DIM}Press Ctrl+C to stop.${RESET}"
echo ""

wait
