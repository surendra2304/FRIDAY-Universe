#!/bin/bash
# scripts/start_universe.sh — Unified FRIDAY Universe Startup
# Starts all 10 agents as background services with mesh networking.
# Usage: ./scripts/start_universe.sh [--dev|--prod|--test]

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"
cd "$REPO_ROOT"

MODE="${1:---dev}"
LOG_DIR="$REPO_ROOT/logs/universe"
PID_DIR="$REPO_ROOT/logs/universe/pids"
mkdir -p "$LOG_DIR" "$PID_DIR"

# Agent port mapping (internal mesh ports per spec)
FRIDAY_PORT=10000
INFERENCE_PORT=8000
MEMORA_PORT=8000
STRATEX_PORT=8000
FORGE_PORT=8000
CORTEX_PORT=8000
SENTINEL_PORT=8000
INTELX_PORT=8000
FUTURIS_PORT=8000
VYRALX_PORT=8000

# Mesh network base URL (internal Docker bridge or localhost for dev)
MESH_HOST="${MESH_HOST:-localhost}"

echo "╔═══════════════════════════════════════════════════════════╗"
echo "║         FRIDAY Universe — Unified Startup                ║"
echo "║         Mode: $MODE                                        ║"
echo "║         Host: $MESH_HOST                                    ║"
echo "╚═══════════════════════════════════════════════════════════╝"
echo ""

# Check Python
if ! command -v python3 &>/dev/null; then
    echo "✗ Python 3 not found. Install Python 3.11+ first."
    exit 1
fi

PYTHON="python3"

# Check if running inside Docker (use container hostnames)
if [ -f /.dockerenv ]; then
    MESH_HOST="localhost"
    echo "Running inside Docker container"
fi

# Startup order: infrastructure → core → specialists → orchestrator
# 1. Inference (model gateway) — everything depends on this
# 2. Memora (memory) — everything reads/writes here
# 3. Sentinel (security) — must be running before anything else executes
# 4. Forge (code/testing)
# 5. Stratex (trading)
# 6. Cortex (marketing)
# 7. IntelX (research)
# 8. Futuris (prediction)
# 9. VyralX (YouTube)
# 10. FRIDAY (orchestrator) — last, starts everything else

start_agent() {
    local name="$1"
    local module="$2"
    local port="$3"
    local workdir="$4"

    local pid_file="$PID_DIR/${name}.pid"
    local log_file="$LOG_DIR/${name}.log"

    # Check if already running
    if [ -f "$pid_file" ]; then
        local old_pid
        old_pid=$(cat "$pid_file")
        if kill -0 "$old_pid" 2>/dev/null; then
            echo "  • $name already running (PID $old_pid)"
            return 0
        fi
        rm -f "$pid_file"
    fi

    echo "  → Starting $name on port $port..."
    cd "$workdir"

    nohup $PYTHON -m uvicorn "$module" --host 0.0.0.0 --port "$port" \
        > "$log_file" 2>&1 &

    local pid=$!
    echo "$pid" > "$pid_file"
    cd "$REPO_ROOT"

    # Wait briefly and check if it started
    sleep 2
    if kill -0 "$pid" 2>/dev/null; then
        echo "  ✓ $name started (PID $pid, port $port)"
        echo "    Logs: $log_file"
    else
        echo "  ✗ $name failed to start. Check logs: $log_file"
        return 1
    fi
}

start_flask() {
    local name="$1"
    local script="$2"
    local port="$3"
    local workdir="$4"

    local pid_file="$PID_DIR/${name}.pid"
    local log_file="$LOG_DIR/${name}.log"

    if [ -f "$pid_file" ]; then
        local old_pid
        old_pid=$(cat "$pid_file")
        if kill -0 "$old_pid" 2>/dev/null; then
            echo "  • $name already running (PID $old_pid)"
            return 0
        fi
        rm -f "$pid_file"
    fi

    echo "  → Starting $name on port $port..."
    cd "$workdir"

    nohup $PYTHON "$script" --host 0.0.0.0 --port "$port" \
        > "$log_file" 2>&1 &

    local pid=$!
    echo "$pid" > "$pid_file"
    cd "$REPO_ROOT"

    sleep 2
    if kill -0 "$pid" 2>/dev/null; then
        echo "  ✓ $name started (PID $pid, port $port)"
        echo "    Logs: $log_file"
    else
        echo "  ✗ $name failed to start. Check logs: $log_file"
        return 1
    fi
}

echo "Starting infrastructure..."
echo ""

# Phase 1: Core dependencies
echo "┌─ Phase 1: Core Dependencies ─────────────────────────────────┐"
start_agent "Inference" "app.main:app" "$INFERENCE_PORT" "$REPO_ROOT/Inference" || true
start_agent "Memora" "apps.api.main:app" "$MEMORA_PORT" "$REPO_ROOT/Memora" || true
echo "└───────────────────────────────────────────────────────────────┘"
echo ""

# Phase 2: Security & Foundation
echo "┌─ Phase 2: Security & Foundation ─────────────────────────────┐"
start_agent "Sentinel" "sentinel.apps.api.main:app" "$SENTINEL_PORT" "$REPO_ROOT/Sentinel" || true
start_agent "Forge" "app.main:app" "$FORGE_PORT" "$REPO_ROOT/Forge" || true
echo "└───────────────────────────────────────────────────────────────┘"
echo ""

# Phase 3: Specialists
echo "┌─ Phase 3: Specialist Agents ────────────────────────────────┐"
start_agent "Stratex" "api.master_control_api:app" "$STRATEX_PORT" "$REPO_ROOT/Stratex" || true
start_agent "Cortex" "cortex_api.main:app" "$CORTEX_PORT" "$REPO_ROOT/Cortex/apps/api/src" || true
start_agent "IntelX" "intelx.app.main:app" "$INTELX_PORT" "$REPO_ROOT/IntelX" || true
start_agent "Futuris" "futuris.api.app:app" "$FUTURIS_PORT" "$REPO_ROOT/Futuris" || true
start_agent "VyralX" "app.main:app" "$VYRALX_PORT" "$REPO_ROOT/VyralX" || true
echo "└───────────────────────────────────────────────────────────────┘"
echo ""

# Phase 4: Orchestrator (last)
echo "┌─ Phase 4: Orchestrator ──────────────────────────────────────┐"
start_agent "FRIDAY" "friday.api.server:app" "$FRIDAY_PORT" "$REPO_ROOT/FRIDAY/src" || true
echo "└───────────────────────────────────────────────────────────────┘"
echo ""

# Summary
echo "╔═══════════════════════════════════════════════════════════╗"
echo "║         Universe Startup Complete                          ║"
echo "║                                                            ║"
echo "║  FRIDAY (Orchestrator)    → localhost:$FRIDAY_PORT          ║"
echo "║  Inference (Models)       → localhost:$INFERENCE_PORT        ║"
echo "║  Memora (Memory)          → localhost:$MEMORA_PORT          ║"
echo "║  Stratex (Trading)        → localhost:$STRATEX_PORT         ║"
echo "║  Forge (Code/Testing)     → localhost:$FORGE_PORT           ║"
echo "║  Cortex (Marketing)       → localhost:$CORTEX_PORT          ║"
echo "║  Sentinel (Security)      → localhost:$SENTINEL_PORT        ║"
echo "║  IntelX (Research)        → localhost:$INTELX_PORT          ║"
echo "║  Futuris (Prediction)     → localhost:$FUTURIS_PORT         ║"
echo "║  VyralX (YouTube)         → localhost:$VYRALX_PORT          ║"
echo "║                                                            ║"
echo "║  Health:  curl localhost:$FRIDAY_PORT/api/v1/mesh/health   ║"
echo "║  Stop:    ./scripts/stop_universe.sh                       ║"
echo "╚═══════════════════════════════════════════════════════════╝"
