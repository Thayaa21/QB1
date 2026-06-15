#!/bin/bash
# =============================================================================
# Graph RAG — Start Script
# =============================================================================
# Starts everything in one command:
#   1. Checks prerequisites (Ollama, Python, Node)
#   2. Starts the FastAPI backend on port 8000
#   3. Starts the React frontend on port 5173
#   4. Opens the browser automatically
#
# Usage:
#   chmod +x start.sh   (only needed once)
#   ./start.sh
# =============================================================================

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# PID file location
PID_FILE=".graph_rag_pids"

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$PROJECT_DIR"

echo ""
echo -e "${BLUE}╔══════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║        🕸  Graph RAG — Starting          ║${NC}"
echo -e "${BLUE}╚══════════════════════════════════════════╝${NC}"
echo ""

# -----------------------------------------------------------------------------
# 1. Check prerequisites
# -----------------------------------------------------------------------------
echo -e "${CYAN}▶ Checking prerequisites...${NC}"

# Python
if ! command -v python3 &>/dev/null && ! command -v python &>/dev/null; then
    echo -e "${RED}✗ Python not found. Install Python 3.10+${NC}"
    exit 1
fi
PYTHON=$(command -v python3 || command -v python)
echo -e "${GREEN}  ✓ Python: $($PYTHON --version)${NC}"

# Node
if ! command -v node &>/dev/null; then
    echo -e "${RED}✗ Node.js not found. Install from https://nodejs.org${NC}"
    exit 1
fi
echo -e "${GREEN}  ✓ Node: $(node --version)${NC}"

# npm
if ! command -v npm &>/dev/null; then
    echo -e "${RED}✗ npm not found${NC}"
    exit 1
fi

# Ollama (optional — warn if not running)
if ! curl -s http://localhost:11434/api/tags &>/dev/null; then
    echo -e "${YELLOW}  ⚠ Ollama not running on port 11434${NC}"
    echo -e "${YELLOW}    LangChain extraction will fail. Start with: ollama serve${NC}"
    echo -e "${YELLOW}    UiPath extraction (.json files) will work fine without it.${NC}"
else
    echo -e "${GREEN}  ✓ Ollama: running${NC}"
fi

echo ""

# -----------------------------------------------------------------------------
# 2. Install Python dependencies if needed
# -----------------------------------------------------------------------------
echo -e "${CYAN}▶ Checking Python dependencies...${NC}"
MISSING_PKGS=""
for pkg in fastapi uvicorn networkx rapidfuzz click python_dotenv; do
    if ! $PYTHON -c "import ${pkg//-/_}" &>/dev/null 2>&1; then
        MISSING_PKGS="$MISSING_PKGS $pkg"
    fi
done

if [ -n "$MISSING_PKGS" ]; then
    echo -e "${YELLOW}  Installing missing packages:$MISSING_PKGS${NC}"
    $PYTHON -m pip install fastapi uvicorn networkx rapidfuzz click python-dotenv \
        pyvis sentence-transformers openai python-dateutil python-multipart --quiet
else
    echo -e "${GREEN}  ✓ All Python packages installed${NC}"
fi

echo ""

# -----------------------------------------------------------------------------
# 3. Install frontend dependencies if needed
# -----------------------------------------------------------------------------
echo -e "${CYAN}▶ Checking frontend dependencies...${NC}"
if [ ! -d "frontend/node_modules" ]; then
    echo -e "${YELLOW}  Installing npm packages (first time only)...${NC}"
    cd frontend && npm install --silent && cd ..
    echo -e "${GREEN}  ✓ npm packages installed${NC}"
else
    echo -e "${GREEN}  ✓ node_modules present${NC}"
fi

echo ""

# -----------------------------------------------------------------------------
# 4. Start FastAPI backend
# -----------------------------------------------------------------------------
echo -e "${CYAN}▶ Starting FastAPI backend on http://localhost:8000 ...${NC}"

# Kill any existing process on port 8000
if lsof -ti:8000 &>/dev/null; then
    echo -e "${YELLOW}  Port 8000 in use — killing old process${NC}"
    kill $(lsof -ti:8000) 2>/dev/null || true
    sleep 1
fi

$PYTHON -m uvicorn graph_rag.api.app:app \
    --host 0.0.0.0 \
    --port 8000 \
    --log-level warning \
    > .logs_backend.txt 2>&1 &
BACKEND_PID=$!

# Wait for backend to be ready
echo -n "  Waiting for backend"
for i in {1..20}; do
    if curl -s http://localhost:8000/ &>/dev/null; then
        echo ""
        echo -e "${GREEN}  ✓ Backend ready (PID: $BACKEND_PID)${NC}"
        break
    fi
    echo -n "."
    sleep 0.5
done
echo ""

# -----------------------------------------------------------------------------
# 5. Start React frontend
# -----------------------------------------------------------------------------
echo -e "${CYAN}▶ Starting React frontend on http://localhost:5173 ...${NC}"

# Kill any existing process on port 5173
if lsof -ti:5173 &>/dev/null; then
    echo -e "${YELLOW}  Port 5173 in use — killing old process${NC}"
    kill $(lsof -ti:5173) 2>/dev/null || true
    sleep 1
fi

cd frontend
npm run dev -- --port 5173 > ../.logs_frontend.txt 2>&1 &
FRONTEND_PID=$!
cd ..

# Wait for frontend
echo -n "  Waiting for frontend"
for i in {1..20}; do
    if curl -s http://localhost:5173 &>/dev/null; then
        echo ""
        echo -e "${GREEN}  ✓ Frontend ready (PID: $FRONTEND_PID)${NC}"
        break
    fi
    echo -n "."
    sleep 0.5
done
echo ""

# -----------------------------------------------------------------------------
# 6. Save PIDs for stop.sh
# -----------------------------------------------------------------------------
echo "$BACKEND_PID" > "$PID_FILE"
echo "$FRONTEND_PID" >> "$PID_FILE"

# -----------------------------------------------------------------------------
# 7. Open browser
# -----------------------------------------------------------------------------
echo -e "${CYAN}▶ Opening browser...${NC}"
sleep 1
open "http://localhost:5173" 2>/dev/null || \
    xdg-open "http://localhost:5173" 2>/dev/null || \
    echo -e "${YELLOW}  Open manually: http://localhost:5173${NC}"

# -----------------------------------------------------------------------------
# Done
# -----------------------------------------------------------------------------
echo ""
echo -e "${GREEN}╔══════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║         ✅  Graph RAG is Running         ║${NC}"
echo -e "${GREEN}╠══════════════════════════════════════════╣${NC}"
echo -e "${GREEN}║  Frontend:  http://localhost:5173        ║${NC}"
echo -e "${GREEN}║  API:       http://localhost:8000        ║${NC}"
echo -e "${GREEN}║  API Docs:  http://localhost:8000/docs   ║${NC}"
echo -e "${GREEN}╠══════════════════════════════════════════╣${NC}"
echo -e "${GREEN}║  Logs:  .logs_backend.txt                ║${NC}"
echo -e "${GREEN}║         .logs_frontend.txt               ║${NC}"
echo -e "${GREEN}║  Stop:  ./stop.sh                        ║${NC}"
echo -e "${GREEN}╚══════════════════════════════════════════╝${NC}"
echo ""
