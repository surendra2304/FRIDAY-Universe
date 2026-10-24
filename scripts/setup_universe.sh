#!/bin/bash
# scripts/setup_universe.sh — One-command environment setup for FRIDAY Universe
# Usage: ./scripts/setup_universe.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"
cd "$REPO_ROOT"

echo "╔═══════════════════════════════════════════════════════════╗"
echo "║    FRIDAY Universe — Environment Setup                     ║"
echo "╚═══════════════════════════════════════════════════════════╝"
echo ""

# Check Python
if ! command -v python3 &>/dev/null; then
    echo "✗ Python 3 not found. Install Python 3.11+ first."
    exit 1
fi

PYTHON="python3"
PY_VERSION=$($PYTHON --version 2>&1)
echo "✓ Python: $PY_VERSION"

# Check pip
if ! $PYTHON -m pip --version &>/dev/null; then
    echo "✗ pip not found. Install pip."
    exit 1
fi
echo "✓ pip available"

# Create log directories
LOG_DIR="$REPO_ROOT/logs/universe"
PID_DIR="$REPO_ROOT/logs/universe/pids"
mkdir -p "$LOG_DIR" "$PID_DIR"
echo "✓ Log directories created: $LOG_DIR"

# Check for required packages and install if missing
echo ""
echo "Checking Python dependencies..."

REQUIRED_PACKAGES=(
    "fastapi"
    "uvicorn"
    "pydantic"
    "httpx"
    "sqlalchemy"
    "alembic"
    "redis"
    "qdrant-client"
    "pytest"
    "pytest-asyncio"
    "numpy"
    "pandas"
    "ccxt"
    "beautifulsoup4"
    "scipy"
)

for package in "${REQUIRED_PACKAGES[@]}"; do
    if ! $PYTHON -c "import $package" 2>/dev/null; then
        echo "  → Installing $package..."
        $PYTHON -m pip install "$package" --quiet 2>/dev/null || \
            $PYTHON -m pip install "$package" --quiet --break-system-packages 2>/dev/null || \
            echo "  ⚠ Could not install $package automatically. Install manually."
    else
        echo "  ✓ $package"
    fi
done

# Generate environment template if no .env exists
echo ""
echo "Checking environment configuration..."

AGENTS=(
    "FRIDAY:FRIDAY/.env"
    "Inference:Inference/.env"
    "Memora:Memora/.env"
    "Stratex:Stratex/.env"
    "Forge:Forge/.env"
    "Cortex:Cortex/.env"
    "Sentinel:Sentinel/.env"
    "IntelX:IntelX/.env"
    "Futuris:Futuris/.env"
    "VyralX:VyralX/.env"
)

ENV_CREATED=0
for entry in "${AGENTS[@]}"; do
    agent_name="${entry%%:*}"
    env_path="${entry##*:}"
    env_file="$REPO_ROOT/$env_path"

    if [ -f "$env_file" ]; then
        echo "  ✓ $agent_name: .env exists"
    elif [ -f "$env_file.example" ]; then
        cp "$env_file.example" "$env_file"
        echo "  → $agent_name: created .env from .env.example"
        ENV_CREATED=$((ENV_CREATED + 1))
    else
        echo "  ⚠ $agent_name: no .env or .env.example found"
    fi
done

if [ $ENV_CREATED -gt 0 ]; then
    echo ""
    echo "⚠ Created $ENV_CREATED .env files from examples."
    echo "  Edit them with your API keys and configuration."
fi

# Verify all agents compile
echo ""
echo "Verifying agent compilation..."
ALL_OK=true
for agent_path in \
    "FRIDAY/src/friday/api/server.py" \
    "Inference/app/main.py" \
    "Memora/apps/api/main.py" \
    "Stratex/api/master_control_api.py" \
    "Forge/app/main.py" \
    "Cortex/apps/api/src/cortex_api/main.py" \
    "Sentinel/sentinel/apps/api/main.py" \
    "IntelX/intelx/app/main.py" \
    "Futuris/futuris/api/app.py" \
    "VyralX/app/main.py"; do
    if [ -f "$agent_path" ]; then
        if $PYTHON -m py_compile "$agent_path" 2>/dev/null; then
            echo "  ✓ ${agent_path%%/*}"
        else
            echo "  ✗ ${agent_path%%/*}: compilation error"
            ALL_OK=false
        fi
    fi
done

echo ""
echo "╔═══════════════════════════════════════════════════════════╗"
if $ALL_OK; then
    echo "║          Setup Complete                                  ║"
    echo "║                                                            ║"
    echo "║  Next steps:                                              ║"
    echo "║  1. Edit .env files with your API keys                  ║"
    echo "║  2. Run: ./scripts/start_universe.sh                    ║"
    echo "║  3. Check: curl localhost:10000/api/v1/mesh/health       ║"
    echo "║  4. Stop:  ./scripts/stop_universe.sh                   ║"
    echo "║                                                            ║"
    echo "║  Health dashboard: localhost:10000/api/v1/mesh/status    ║"
    echo "╚═══════════════════════════════════════════════════════════╝"
else
    echo "║          Setup Complete with Errors                      ║"
    echo "║  Some agents failed compilation. Check errors above.     ║"
    echo "╚═══════════════════════════════════════════════════════════╝"
    exit 1
fi
