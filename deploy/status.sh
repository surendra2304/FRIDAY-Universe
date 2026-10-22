#!/usr/bin/env bash
# ==============================================================================
# FRIDAY Universe - Live System & Multi-Agent Health Monitor
# ==============================================================================
set -euo pipefail

echo "=========================================================="
echo "   📊 FRIDAY UNIVERSE - LIVE STATUS MONITOR               "
echo "=========================================================="

echo -e "\n[1] SYSTEM RESOURCE UTILIZATION:"
echo "----------------------------------------------------------"
free -h
echo ""
uptime -p

echo -e "\n[2] DOCKER CONTAINERS STATUS:"
echo "----------------------------------------------------------"
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"

echo -e "\n[3] MICROSERVICE HEALTH CHECKS:"
echo "----------------------------------------------------------"
services=(
    "FRIDAY:10000"
    "Cortex:8001"
    "Forge:8002"
    "Futuris:8003"
    "Inference:8004"
    "IntelX:8005"
    "Memora:8006"
    "Sentinel:8007"
    "Stratex:8008"
)

for svc in "${services[@]}"; do
    name="${svc%%:*}"
    port="${svc##*:}"
    code=$(curl -s -o /dev/null -w "%{http_code}" "http://localhost:${port}/health" || echo "ERR")
    if [ "$code" = "200" ]; then
        echo -e "  ✅ $name (Port $port): HEALTHY (HTTP 200)"
    else
        echo -e "  ⚠️ $name (Port $port): HTTP $code"
    fi
done

echo "=========================================================="
