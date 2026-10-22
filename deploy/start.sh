#!/usr/bin/env bash
# ==============================================================================
# FRIDAY Universe - Launch / Rebuild All 9 Microservices
# ==============================================================================
set -euo pipefail

cd /opt/friday_universe

echo "🚀 Starting FRIDAY Universe Mesh..."
docker compose -f docker-compose.yml up -d --build

echo "🔄 Reloading Caddy Reverse Proxy..."
sudo systemctl reload caddy || sudo systemctl restart caddy

echo "⏳ Waiting 10s for containers to initialize..."
sleep 10

bash ./status.sh
