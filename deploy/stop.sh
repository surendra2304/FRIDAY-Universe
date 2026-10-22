#!/usr/bin/env bash
# ==============================================================================
# FRIDAY Universe - Graceful Shutdown
# ==============================================================================
set -euo pipefail

cd /opt/friday_universe
echo "🛑 Stopping all FRIDAY Universe services..."
docker compose -f docker-compose.yml down
echo "✅ All containers stopped cleanly."
