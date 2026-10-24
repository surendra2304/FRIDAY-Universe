#!/bin/bash
# scripts/stop_universe.sh — Stop all FRIDAY Universe agents
# Usage: ./scripts/stop_universe.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"
PID_DIR="$REPO_ROOT/logs/universe/pids"

echo "Stopping FRIDAY Universe..."

# Stop in reverse order (orchestrator first, then specialists, then core)
AGENTS=(
    "FRIDAY"
    "VyralX"
    "Futuris"
    "IntelX"
    "Cortex"
    "Stratex"
    "Forge"
    "Sentinel"
    "Memora"
    "Inference"
)

for agent in "${AGENTS[@]}"; do
    pid_file="$PID_DIR/${agent}.pid"
    if [ -f "$pid_file" ]; then
        pid=$(cat "$pid_file")
        if kill -0 "$pid" 2>/dev/null; then
            echo "  → Stopping $agent (PID $pid)..."
            kill "$pid" 2>/dev/null || true
            # Wait up to 5 seconds
            for i in {1..5}; do
                kill -0 "$pid" 2>/dev/null || break
                sleep 1
            done
            # Force kill if still running
            if kill -0 "$pid" 2>/dev/null; then
                kill -9 "$pid" 2>/dev/null || true
            fi
            echo "  ✓ $agent stopped"
        else
            echo "  • $agent not running (stale PID file)"
        fi
        rm -f "$pid_file"
    fi
done

echo "Universe stopped. All agents have been shut down."
