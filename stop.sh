#!/bin/bash
# =============================================================================
# Graph RAG — Stop Script
# =============================================================================
# Stops the FastAPI backend and React frontend.
#
# Usage:
#   ./stop.sh
# =============================================================================

RED='\033[0;31m'
GREEN='\033[0;32m'
CYAN='\033[0;36m'
NC='\033[0m'

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$PROJECT_DIR"

PID_FILE=".graph_rag_pids"

echo ""
echo -e "${CYAN}▶ Stopping Graph RAG...${NC}"

# Kill from PID file
if [ -f "$PID_FILE" ]; then
    while read -r pid; do
        if kill -0 "$pid" 2>/dev/null; then
            kill "$pid" 2>/dev/null
            echo -e "${GREEN}  ✓ Stopped process $pid${NC}"
        fi
    done < "$PID_FILE"
    rm -f "$PID_FILE"
fi

# Also kill by port (belt and suspenders)
for port in 8000 5173; do
    PIDS=$(lsof -ti:$port 2>/dev/null)
    if [ -n "$PIDS" ]; then
        kill $PIDS 2>/dev/null
        echo -e "${GREEN}  ✓ Freed port $port${NC}"
    fi
done

# Clean up log files (optional)
rm -f .logs_backend.txt .logs_frontend.txt .graph_rag_state.json

echo ""
echo -e "${GREEN}✅ Graph RAG stopped.${NC}"
echo ""
