#!/usr/bin/env bash
# ==============================================================================
# FRIDAY Universe - Fleet Deployment & Service Provisioner
# Configures systemd services with exact proper names:
# Server 1: FRIDAY, Inference, Memora, Stratex, Futuris, IntelX, Forge
# Server 2: VyralX, Sentinel, Cortex
# ==============================================================================
set -euo pipefail

SERVER_ROLE="${1:-}"

if [[ "$SERVER_ROLE" != "1" && "$SERVER_ROLE" != "2" ]]; then
    echo "Usage: sudo bash deploy/setup_fleet.sh [1|2]"
    echo "  1 = Deploy Server 1 Core Fleet (FRIDAY, Inference, Memora, Stratex, Futuris, IntelX, Forge)"
    echo "  2 = Deploy Server 2 Specialist Fleet (VyralX, Sentinel, Cortex)"
    exit 1
fi

REPO_DIR="/opt/friday_universe"
VENV_DIR="/opt/friday_universe/venv"

echo "=== [1/4] Ensuring Python Virtual Environment ==="
if [ ! -d "$VENV_DIR" ]; then
    python3 -m venv "$VENV_DIR"
fi

"$VENV_DIR/bin/pip" install --upgrade --no-cache-dir pip setuptools wheel
"$VENV_DIR/bin/pip" install --no-cache-dir \
    fastapi uvicorn pydantic pydantic-settings oracledb sqlalchemy httpx requests python-dotenv \
    cryptography rich psutil aiohttp aiosqlite asyncpg jinja2 python-multipart aiofiles

# Compatibility patch for Python 3.10
echo "UTC = timezone.utc" | sudo tee -a /usr/lib/python3.10/datetime.py 2>/dev/null || true
echo "class StrEnum(str, Enum): pass" | sudo tee -a /usr/lib/python3.10/enum.py 2>/dev/null || true

echo "=== [2/4] Configuring Database DSNs (Oracle Autonomous 23ai) ==="
ORACLE_CORE_DSN="(description=(retry_count=20)(retry_delay=3)(address=(protocol=tcps)(port=1521)(host=adb.ap-hyderabad-1.oraclecloud.com))(connect_data=(service_name=g7e6177242670c3_fridaycore_medium.adb.oraclecloud.com))(security=(ssl_server_dn_match=yes)))"
ORACLE_CORE_URL="oracle+oracledb://ADMIN:FridayUniverse2026%21%23Core@${ORACLE_CORE_DSN}"
ORACLE_CORE_ASYNC_URL="oracle+oracledb_async://ADMIN:FridayUniverse2026%21%23Core@${ORACLE_CORE_DSN}"

ORACLE_VYRAL_DSN="(description=(retry_count=20)(retry_delay=3)(address=(protocol=tcps)(port=1521)(host=adb.ap-hyderabad-1.oraclecloud.com))(connect_data=(service_name=g7e6177242670c3_fridayvyralx_medium.adb.oraclecloud.com))(security=(ssl_server_dn_match=yes)))"
ORACLE_VYRAL_URL="oracle+oracledb://ADMIN:FridayUniverse2026%21%23Vyral@${ORACLE_VYRAL_DSN}"
ORACLE_VYRAL_ASYNC_URL="oracle+oracledb_async://ADMIN:FridayUniverse2026%21%23Vyral@${ORACLE_VYRAL_DSN}"

ENV_FILE="/etc/default/friday_universe.env"
if [ "$SERVER_ROLE" = "1" ]; then
    sudo tee "$ENV_FILE" > /dev/null << EOF
DATABASE_URL=$ORACLE_CORE_URL
ORACLE_CORE_URL=$ORACLE_CORE_URL
ORACLE_CORE_ASYNC_URL=$ORACLE_CORE_ASYNC_URL
ORACLE_VYRAL_URL=$ORACLE_VYRAL_URL
EOF
elif [ "$SERVER_ROLE" = "2" ]; then
    sudo tee "$ENV_FILE" > /dev/null << EOF
DATABASE_URL=$ORACLE_VYRAL_URL
ORACLE_CORE_URL=$ORACLE_CORE_URL
ORACLE_VYRAL_URL=$ORACLE_VYRAL_URL
ORACLE_VYRAL_ASYNC_URL=$ORACLE_VYRAL_ASYNC_URL
SENTINEL_AUDIT_HMAC_KEY=c36209e9fbe54d008d51a660d2ecb0b023f9906649f8269e8bb95b217dc3ad3e
SENTINEL_AUDIT_SIGNING_KEY=c36209e9fbe54d008d51a660d2ecb0b023f9906649f8269e8bb95b217dc3ad3e
SENTINEL_API_KEY=sentinel_jF-bgAo6XWDQqV-TaRW1MiG36QbC3YUY6c
EOF
fi
sudo chmod 600 "$ENV_FILE"

# Purge any local SQLite files to enforce zero persistent local SQLite
find "$REPO_DIR" -maxdepth 3 \( -name "*.db" -o -name "*.sqlite" -o -name "*.sqlite3" \) -delete 2>/dev/null || true

if [ "$SERVER_ROLE" = "1" ]; then
    echo "=== [3/4] Installing Server 1 Packages & Registering Services ==="
    "$VENV_DIR/bin/pip" install --no-cache-dir structlog flask flask-cors alembic apscheduler prometheus-client websockets beautifulsoup4 pypdf python-docx pandas numpy scipy python-binance ccxt openai anthropic google-genai || true
    "$VENV_DIR/bin/pip" install -e "$REPO_DIR/FRIDAY" --no-deps 2>/dev/null || true

    # 1. FRIDAY (Port 10000)
    sudo tee /etc/systemd/system/FRIDAY.service > /dev/null << EOF
[Unit]
Description=FRIDAY Universe - Operating System & Core Gateway
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=$REPO_DIR/FRIDAY
Environment="PYTHONPATH=$REPO_DIR/FRIDAY/src:$REPO_DIR"
Environment="PORT=10000"
EnvironmentFile=/etc/default/friday_universe.env
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
EnvironmentFile=/etc/default/friday_universe.env
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
EnvironmentFile=/etc/default/friday_universe.env
ExecStart=$VENV_DIR/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port 8002 --workers 1
Restart=always
RestartSec=5
TimeoutStopSec=10
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
EnvironmentFile=/etc/default/friday_universe.env
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
EnvironmentFile=/etc/default/friday_universe.env
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
EnvironmentFile=/etc/default/friday_universe.env
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
EnvironmentFile=/etc/default/friday_universe.env
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
    echo "=== [3/4] Installing Server 2 Packages & Registering Services ==="
    "$VENV_DIR/bin/pip" install --no-cache-dir pyjwt google-api-python-client google-auth google-auth-oauthlib google-auth-httplib2 redis sse-starlette structlog pyyaml || true

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
EnvironmentFile=/etc/default/friday_universe.env
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
Environment="STORAGE_BACKEND=memory"
EnvironmentFile=/etc/default/friday_universe.env
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
EnvironmentFile=/etc/default/friday_universe.env
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
        CODE=$(curl -s -o /dev/null -w "%{http_code}" "http://localhost:$p/health" || echo "ERR")
        echo "HTTP $CODE"
    done
elif [ "$SERVER_ROLE" = "2" ]; then
    declare -A S2_NAMES=([8010]="VyralX" [8008]="Sentinel" [8009]="Cortex")
    for p in 8010 8008 8009; do
        echo -n "${S2_NAMES[$p]} (Port $p): "
        CODE=$(curl -s -o /dev/null -w "%{http_code}" "http://localhost:$p/health" || echo "ERR")
        echo "HTTP $CODE"
    done
fi

echo "🎉 Fleet setup complete for Server $SERVER_ROLE!"
