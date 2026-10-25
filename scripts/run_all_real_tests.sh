#!/bin/bash
# FRIDAY Universe — Unified Test Runner
# Runs all real functional tests across all layers

set -e

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT"

# Set PYTHONPATH
export PYTHONPATH="FRIDAY/apps/core/src:Inference/app:Inference:Memora:Stratex:Forge/app/services:Sentinel/app/services:IntelX/intelx/services:Futuris/futuris/core:VyralX/app/services"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

TOTAL_TESTS=0
TOTAL_PASS=0
TOTAL_FAIL=0

echo "${BLUE}╔══════════════════════════════════════════════════════════════╗${NC}"
echo "${BLUE}║  FRIDAY Universe — Unified Test Runner v3.0                  ║${NC}"
echo "${BLUE}║  All Layers: Basic + Advanced + Deep + HTTP + Realtime      ║${NC}"
echo "${BLUE}╚══════════════════════════════════════════════════════════════╝${NC}"
echo ""

# Test suites (non-HTTP)
NON_HTTP_SUITES=(
    "tests/test_real_functional_engines.py"
    "tests/test_real_cross_agent_integration.py"
    "tests/test_real_advanced_engines.py"
    "test_real_deep_engines.py"
    "tests/test_real_universe_orchestrator.py"
    "tests/test_real_realtime_pipeline.py"
    "tests/test_real_universe_dashboard.py"
)

for suite in "${NON_HTTP_SUITES[@]}"; do
    if [ -f "$suite" ]; then
        SUITE_NAME=$(basename "$suite")
        echo "${YELLOW}▶ Running $SUITE_NAME...${NC}"
        RESULT=$(python3 -m pytest "$suite" -v --tb=short 2>&1)
        PASS_COUNT=$(echo "$RESULT" | grep -oP '\d+(?= passed)' | tail -1 || echo "0")
        FAIL_COUNT=$(echo "$RESULT" | grep -oP '\d+(?= failed)' | tail -1 || echo "0")
        TOTAL_TESTS=$((TOTAL_TESTS + PASS_COUNT + FAIL_COUNT))
        TOTAL_PASS=$((TOTAL_PASS + PASS_COUNT))
        TOTAL_FAIL=$((TOTAL_FAIL + FAIL_COUNT))
        if [ "$FAIL_COUNT" -eq 0 ]; then
            echo "${GREEN}  ✓ $PASS_COUNT passed${NC}"
        else
            echo "${RED}  ✗ $FAIL_COUNT failed${NC}"
            echo "$RESULT" | tail -20
        fi
        echo ""
    fi
done

# HTTP tests (need server running)
HTTP_SUITES=(
    "tests/test_real_http_api.py"
    "tests/test_real_deep_http_api.py"
    "tests/test_real_deep_workflow_http.py"
    "tests/test_real_dashboard_http.py"
)

echo "${YELLOW}▶ Starting API server for HTTP tests...${NC}"
python3 -m uvicorn friday_core.real_api_server:app --host 0.0.0.0 --port 8000 &
SERVER_PID=$!
sleep 5

# Verify server is up
if curl -s http://127.0.0.1:8000/health > /dev/null 2>&1; then
    echo "${GREEN}  ✓ Server is running${NC}"
else
    echo "${RED}  ✗ Server failed to start${NC}"
    kill $SERVER_PID 2>/dev/null
    exit 1
fi

for suite in "${HTTP_SUITES[@]}"; do
    if [ -f "$suite" ]; then
        SUITE_NAME=$(basename "$suite")
        echo "${YELLOW}▶ Running $SUITE_NAME...${NC}"
        RESULT=$(python3 -m pytest "$suite" -v --tb=short 2>&1)
        PASS_COUNT=$(echo "$RESULT" | grep -oP '\d+(?= passed)' | tail -1 || echo "0")
        FAIL_COUNT=$(echo "$RESULT" | grep -oP '\d+(?= failed)' | tail -1 || echo "0")
        TOTAL_TESTS=$((TOTAL_TESTS + PASS_COUNT + FAIL_COUNT))
        TOTAL_PASS=$((TOTAL_PASS + PASS_COUNT))
        TOTAL_FAIL=$((TOTAL_FAIL + FAIL_COUNT))
        if [ "$FAIL_COUNT" -eq 0 ]; then
            echo "${GREEN}  ✓ $PASS_COUNT passed${NC}"
        else
            echo "${RED}  ✗ $FAIL_COUNT failed${NC}"
        fi
        echo ""
    fi
done

kill $SERVER_PID 2>/dev/null

# Summary
echo ""
echo "${BLUE}╔══════════════════════════════════════════════════════════════╗${NC}"
echo "${BLUE}║  TEST SUMMARY                                                ║${NC}"
echo "${BLUE}║  Total: $TOTAL_TESTS   Passed: ${GREEN}$TOTAL_PASS${NC}   Failed: ${RED}$TOTAL_FAIL${NC}                           ║${NC}"
echo "${BLUE}╚══════════════════════════════════════════════════════════════╝${NC}"

if [ "$TOTAL_FAIL" -eq 0 ]; then
    echo "${GREEN}✓ All tests passed! FRIDAY Universe is at 100% dream.${NC}"
    exit 0
else
    echo "${RED}✗ $TOTAL_FAIL test(s) failed.${NC}"
    exit 1
fi
