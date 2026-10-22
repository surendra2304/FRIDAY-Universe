#!/usr/bin/env bash
set -e
cd /opt/friday_universe

SERVICES=("forge" "futuris" "inference" "intelx" "memora" "sentinel" "stratex" "friday")

for svc in "${SERVICES[@]}"; do
    echo "=========================================================="
    echo "🚀 [$(date '+%H:%M:%S')] Building and restarting: $svc"
    echo "=========================================================="
    docker compose build "$svc"
    docker compose up -d --no-deps "$svc"
    echo "✅ $svc deployed successfully"
    sleep 2
done

echo "🎉 All services deployed successfully!"
