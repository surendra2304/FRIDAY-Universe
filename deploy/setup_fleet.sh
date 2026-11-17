#!/usr/bin/env bash
# ==============================================================================
# FRIDAY Universe - Fleet Deployment & Service Provisioner
# Configures systemd services with exact proper names and per-agent .env isolation:
# Server 1: FRIDAY, Inference, Memora, Stratex, Futuris, IntelX, Forge
# Server 2: VyralX, Sentinel, Cortex
# ==============================================================================
set -euo pipefail

SERVER_ROLE="${1:-}"

if [[ "$SERVER_ROLE" != "1" && "$SERVER_ROLE" != "2" ]]; then
    echo "Usage: export required secrets, then run bash deploy/setup_fleet.sh [1|2]"
    echo "  1 = Deploy Server 1 Core Fleet (FRIDAY, Inference, Memora, Stratex, Futuris, IntelX, Forge)"
    echo "  2 = Deploy Server 2 Specialist Fleet (VyralX, Sentinel, Cortex)"
    exit 1
fi

REPO_DIR="/opt/friday_universe"
# Fleet Python 3.12 upgrade (work item W4): the fleet interpreter is
# CPython 3.12 and the shared venv lives beside the retired 3.10 one
# (/opt/friday_universe/venv, kept untouched for rollback). Both are
# overridable for a deliberate, explicit rollback rebuild only:
#   FLEET_PYTHON=python3.10 VENV_DIR=/opt/friday_universe/venv \
#     FLEET_LOCK_FILE=<3.10-era lock> bash deploy/setup_fleet.sh [1|2]
# Never rely on the host's bare `python3` here: on the Ubuntu 22.04
# hosts that is still 3.10, and creating the fleet venv from it was
# exactly how a rebuild would silently regress the fleet.
FLEET_PYTHON="${FLEET_PYTHON:-python3.12}"
VENV_DIR="${VENV_DIR:-/opt/friday_universe/venv312}"
# Packages install from this server's union lock (work item W5) — the
# single source of package truth for the shared venv. If the lock is
# missing the setup FAILS: the pre-upgrade behaviour (unpinned package
# subsets installed with `|| true`) let the live venvs drift ahead of
# every manifest, and a silent fallback would recreate that drift.
LOCK_FILE="${FLEET_LOCK_FILE:-$REPO_DIR/deploy/requirements-server${SERVER_ROLE}.lock}"

if [ ! -f "$LOCK_FILE" ]; then
    echo "ERROR: union lock not found: $LOCK_FILE" >&2
    echo "Fleet packages install from the per-server union locks" >&2
    echo "(deploy/requirements-server1.lock / requirements-server2.lock)." >&2
    echo "Commit the lock (work item W5) or set FLEET_LOCK_FILE explicitly." >&2
    exit 1
fi

echo "=== [1/4] Ensuring Python Virtual Environment ($FLEET_PYTHON -> $VENV_DIR) ==="
if [ ! -d "$VENV_DIR" ]; then
    "$FLEET_PYTHON" -m venv "$VENV_DIR"
fi

# Guard: never install a lock into a venv built by another interpreter
# line (e.g. VENV_DIR pointed at the retired 3.10 venv during the
# cutover) — pip would happily place pure-Python wheels there and the
# fleet would boot a mixed, unplanned environment.
VENV_PY_VER="$("$VENV_DIR/bin/python" -c 'import sys; print("%d.%d" % sys.version_info[:2])')"
WANT_PY_VER="$("$FLEET_PYTHON" -c 'import sys; print("%d.%d" % sys.version_info[:2])')"
if [ "$VENV_PY_VER" != "$WANT_PY_VER" ]; then
    echo "ERROR: $VENV_DIR runs Python $VENV_PY_VER but FLEET_PYTHON is $WANT_PY_VER." >&2
    echo "Refusing to install $LOCK_FILE into a mismatched venv." >&2
    exit 1
fi

"$VENV_DIR/bin/pip" install --upgrade --no-cache-dir pip setuptools wheel
"$VENV_DIR/bin/pip" install --no-cache-dir -r "$LOCK_FILE"

# The Python 3.10 stdlib compatibility patch that used to be appended
# here (UTC/StrEnum backports into /usr/lib/python3.10) is retired:
# REL-050's code-level shims made it redundant, and on 3.11+ the native
# names exist. It must never run again.

echo "=== [2/4] Configuring Canonical Databases (Oracle Autonomous 23ai) ==="
# TASK-DATA-001 remediation (2026-11-10): this section previously constructed
# ADMIN-privileged DSNs (FRIDAY_UNIVERSE_DB_URL/_ASYNC_URL and
# VYRALX_DB_URL/_ASYNC_URL) that no service ever consumed, and demanded the
# ADMIN passwords up front. Per the AGENTS.yaml policy of one unprivileged
# Oracle login per agent, fleet setup must not construct or seed ADMIN DSNs:
# each agent's $REPO_DIR/<Agent>/.env carries only that agent's own schema-user
# DATABASE_URL (plus agent-specific secondary DSNs such as VyralX's
# MEDIA_DATABASE_URL). Owner-authorized cleanup; evidence in
# docs/ARCHITECTURE_AS_BUILT.md section 20.4.

# Purge legacy global env if present
sudo rm -f /etc/default/friday_universe.env

# Purge any local SQLite files to enforce zero persistent local SQLite
find "$REPO_DIR" -maxdepth 3 \( -name "*.db" -o -name "*.sqlite" -o -name "*.sqlite3" \) -delete 2>/dev/null || true

if [ "$SERVER_ROLE" = "1" ]; then
    echo "=== [3/4] Registering Server 1 Isolated Services ==="
    # Server packages were installed from the union lock in step [1/4].
    # FRIDAY's editable install is interpreter-scoped (its .pth/egg-link
    # lives in the venv), so it is (re)done here for this venv — and it
    # is strict: a failed editable install means FRIDAY cannot boot
    # from this venv, which setup must surface, not swallow.
    "$VENV_DIR/bin/pip" install -e "$REPO_DIR/FRIDAY" --no-deps

    # 1. FRIDAY (Port 10000)
    sudo tee /etc/systemd/system/FRIDAY.service > /dev/null << EOF
[Unit]
Description=FRIDAY Universe - Operating System & Master Dispatcher
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=$REPO_DIR/FRIDAY
Environment="PYTHONPATH=$REPO_DIR/FRIDAY/src:$REPO_DIR/FRIDAY/apps/core/src:$REPO_DIR"
Environment="PORT=10000"
EnvironmentFile=$REPO_DIR/FRIDAY/.env
ExecStart=$VENV_DIR/bin/python -m uvicorn friday.api.server:app --host 0.0.0.0 --port 10000 --workers 1
Restart=always
RestartSec=5
TimeoutStopSec=10
MemoryMax=200M

[Install]
WantedBy=multi-user.target
EOF

    # 2. Inference (Port 8001)
    sudo tee /etc/systemd/system/Inference.service > /dev/null << EOF
[Unit]
Description=FRIDAY Universe - Sovereign Multi-Model Inference Gateway
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=$REPO_DIR/Inference
Environment="PYTHONPATH=$REPO_DIR/Inference:$REPO_DIR"
Environment="PORT=8001"
EnvironmentFile=$REPO_DIR/Inference/.env
ExecStart=$VENV_DIR/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port 8001 --workers 1
Restart=always
RestartSec=5
TimeoutStopSec=10
MemoryMax=180M

[Install]
WantedBy=multi-user.target
EOF

    # 3. Memora (Port 8002)
    sudo tee /etc/systemd/system/Memora.service > /dev/null << EOF
[Unit]
Description=FRIDAY Universe - Cognitive Memory Fabric
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=$REPO_DIR/Memora
Environment="PYTHONPATH=$REPO_DIR/Memora:$REPO_DIR"
Environment="PORT=8002"
EnvironmentFile=$REPO_DIR/Memora/.env
# TASK-MEM-009: apply Alembic migrations before EVERY start. On
# 2026-11-17 a merged migration never ran because nothing in the
# deploy/start path ran Alembic, and every memory query failed while
# /health stayed green. The runner logs before/after revisions, is
# idempotent at head, holds an flock against concurrent runs, and
# exits non-zero on failure — systemd then fails the start loudly
# instead of booting on a stale schema.
ExecStartPre=$VENV_DIR/bin/python $REPO_DIR/Memora/scripts/run_migrations.py
ExecStart=$VENV_DIR/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port 8002 --workers 1
Restart=always
RestartSec=5
TimeoutStopSec=60
MemoryMax=180M

[Install]
WantedBy=multi-user.target
EOF

    # 4. Stratex (Port 8003)
    sudo tee /etc/systemd/system/Stratex.service > /dev/null << EOF
[Unit]
Description=FRIDAY Universe - 24/7 Autonomous Algorithmic Trading
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=$REPO_DIR/Stratex
Environment="PYTHONPATH=$REPO_DIR/Stratex:$REPO_DIR"
Environment="PORT=8003"
EnvironmentFile=$REPO_DIR/Stratex/.env
ExecStart=$VENV_DIR/bin/python dashboard.py
Restart=always
RestartSec=5
TimeoutStopSec=10
MemoryMax=180M

[Install]
WantedBy=multi-user.target
EOF

    # 5. Futuris (Port 8004)
    sudo tee /etc/systemd/system/Futuris.service > /dev/null << EOF
[Unit]
Description=FRIDAY Universe - Predictive Forecasting Engine
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=$REPO_DIR/Futuris
Environment="PYTHONPATH=$REPO_DIR/Futuris:$REPO_DIR"
Environment="PORT=8004"
EnvironmentFile=$REPO_DIR/Futuris/.env
ExecStart=$VENV_DIR/bin/python -m uvicorn futuris.api.app:app --host 0.0.0.0 --port 8004 --workers 1
Restart=always
RestartSec=5
TimeoutStopSec=10
MemoryMax=180M

[Install]
WantedBy=multi-user.target
EOF

    # 6. IntelX (Port 8005)
    sudo tee /etc/systemd/system/IntelX.service > /dev/null << EOF
[Unit]
Description=FRIDAY Universe - Evidence & Intelligence Research Engine
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=$REPO_DIR/IntelX
Environment="PYTHONPATH=$REPO_DIR/IntelX:$REPO_DIR"
Environment="PORT=8005"
EnvironmentFile=$REPO_DIR/IntelX/.env
ExecStart=$VENV_DIR/bin/python -m uvicorn intelx.app.main:app --host 0.0.0.0 --port 8005 --workers 1
Restart=always
RestartSec=5
TimeoutStopSec=10
MemoryMax=180M

[Install]
WantedBy=multi-user.target
EOF

    # 7. Forge (Port 8006)
    sudo tee /etc/systemd/system/Forge.service > /dev/null << EOF
[Unit]
Description=FRIDAY Universe - Autonomous Software Engineering
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=$REPO_DIR/Forge
Environment="PYTHONPATH=$REPO_DIR/Forge:$REPO_DIR"
Environment="PORT=8006"
EnvironmentFile=$REPO_DIR/Forge/.env
ExecStart=$VENV_DIR/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port 8006 --workers 1
Restart=always
RestartSec=5
TimeoutStopSec=10
MemoryMax=180M

[Install]
WantedBy=multi-user.target
EOF

    sudo systemctl daemon-reload
    SERVICES=("FRIDAY" "Inference" "Memora" "Stratex" "Futuris" "IntelX" "Forge")
    for svc in "${SERVICES[@]}"; do
        sudo systemctl enable "$svc"
        sudo systemctl restart "$svc"
    done

elif [ "$SERVER_ROLE" = "2" ]; then
    echo "=== [3/4] Registering Server 2 Isolated Services ==="
    # Server packages were installed from the union lock in step [1/4].

    # 1. VyralX (Port 8010)
    sudo tee /etc/systemd/system/VyralX.service > /dev/null << EOF
[Unit]
Description=FRIDAY Universe - Autonomous Video Creation Studio
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=$REPO_DIR/VyralX
Environment="PYTHONPATH=$REPO_DIR/VyralX:$REPO_DIR"
Environment="PORT=8010"
EnvironmentFile=$REPO_DIR/VyralX/.env
ExecStart=$VENV_DIR/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port 8010 --workers 1
Restart=always
RestartSec=5
TimeoutStopSec=10
MemoryMax=250M

[Install]
WantedBy=multi-user.target
EOF

    # 2. Sentinel (Port 8008)
    sudo tee /etc/systemd/system/Sentinel.service > /dev/null << EOF
[Unit]
Description=FRIDAY Universe - Cybersecurity Defense Shield
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=$REPO_DIR/Sentinel
Environment="PYTHONPATH=$REPO_DIR/Sentinel:$REPO_DIR"
Environment="PORT=8008"
Environment="STORAGE_BACKEND=sqlite"
EnvironmentFile=$REPO_DIR/Sentinel/.env
ExecStart=$VENV_DIR/bin/python -m uvicorn sentinel.apps.api.main:app --host 0.0.0.0 --port 8008 --workers 1
Restart=always
RestartSec=5
TimeoutStopSec=10
MemoryMax=200M

[Install]
WantedBy=multi-user.target
EOF

    # 3. Cortex (Port 8009)
    sudo tee /etc/systemd/system/Cortex.service > /dev/null << EOF
[Unit]
Description=FRIDAY Universe - Autonomous Operations Engine
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=$REPO_DIR/Cortex
Environment="PYTHONPATH=$REPO_DIR/Cortex:$REPO_DIR"
Environment="PORT=8009"
EnvironmentFile=$REPO_DIR/Cortex/.env
ExecStart=$VENV_DIR/bin/python -m uvicorn apps.api.src.cortex_api.main:app --host 0.0.0.0 --port 8009 --workers 1
Restart=always
RestartSec=5
TimeoutStopSec=10
MemoryMax=200M

[Install]
WantedBy=multi-user.target
EOF

    sudo systemctl daemon-reload
    SERVICES=("VyralX" "Sentinel" "Cortex")
    for svc in "${SERVICES[@]}"; do
        sudo systemctl enable "$svc"
        sudo systemctl restart "$svc"
    done
fi

echo "=== [4/4] Verifying Service Liveness ==="
sleep 5
if [ "$SERVER_ROLE" = "1" ]; then
    declare -A S1_NAMES=([10000]="FRIDAY" [8001]="Inference" [8002]="Memora" [8003]="Stratex" [8004]="Futuris" [8005]="IntelX" [8006]="Forge")
    for p in 10000 8001 8002 8003 8004 8005 8006; do
        echo -n "${S1_NAMES[$p]} (Port $p): "
        CODE=$(curl -s -o /dev/null -w "%{http_code}" "http://127.0.0.1:$p/health" || echo "ERR")
        echo "HTTP $CODE"
    done
elif [ "$SERVER_ROLE" = "2" ]; then
    declare -A S2_NAMES=([8010]="VyralX" [8008]="Sentinel" [8009]="Cortex")
    for p in 8010 8008 8009; do
        echo -n "${S2_NAMES[$p]} (Port $p): "
        CODE=$(curl -s -o /dev/null -w "%{http_code}" "http://127.0.0.1:$p/health" || echo "ERR")
        echo "HTTP $CODE"
    done
fi

echo "Fleet setup complete for Server $SERVER_ROLE!"
