#!/usr/bin/env python3
"""Live-path verification: Friday -> Stratex balance query against a REAL local
HTTP server speaking Stratex's actual contract (POST /v1/task/execute).

Proves the LIVE path of StratexPortfolioTool works when Stratex is reachable —
complementing scripts/demo_balance_query_fix.py which proves the honest
fallback path when it is not. No mocks of the tool itself: the REAL routing
(FleetClient.dispatch_task -> circuit breaker -> httpx POST) is exercised.
"""
from __future__ import annotations

import json
import os
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
os.environ.setdefault("FRIDAY_MEMORY_BACKEND", "sqlite")
os.environ.setdefault("FRIDAY_ENV", "testing")
sys.path.insert(0, str(REPO / "FRIDAY" / "src"))

# Realistic Stratex engine snapshot (shape mirrors Stratex's own status action
# in Stratex/api/friday_supervision.py — including the ActionReceipt the
# cognitive mesh verifier requires: requested_action, target, decision,
# no failure_reason, non-empty verification_evidence)
PORTFOLIO = {
    "task_id": "tsk_mock_0001",
    "state": "completed",
    "result": {
        "engine": "Stratex",
        "trading_mode": "testnet",
        "balance": 10423.87,
        "cash_balance": 9911.02,
        "current_positions": [
            {"symbol": "BTCUSDT", "side": "long", "entry_price": 67150.0, "unrealized_pnl": 212.4},
            {"symbol": "ETHUSDT", "side": "long", "entry_price": 3512.5, "unrealized_pnl": -37.55},
        ],
        "active_strategies": ["momentum_breakout_v2", "mean_reversion_grid"],
    },
    "receipt": {
        "requested_action": "status",
        "target": "stratex",
        "authorization_decision": "AUTHORIZED",
        "execution_timestamp": "2026-11-13T09:00:00+00:00",
        "result": {},
        "verification_evidence": {
            "source": "cTrader demo engine snapshot",
            "snapshot_id": "snap_mock_0001",
            "engine_alive": True,
        },
        "failure_reason": None,
    },
}

class StratexContractHandler(BaseHTTPRequestHandler):
    def log_message(self, *a):  # silence
        pass
    def do_POST(self):
        if self.path != "/v1/task/execute":
            self.send_error(404)
            return
        length = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(length) or b"{}")
        # Echo parts of the envelope so we assert Friday sent the right thing
        assert body.get("target_agent", "").lower() == "stratex", body
        assert body.get("action") in ("status", "analyze"), body
        payload = json.dumps(PORTFOLIO).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

def main() -> int:
    server = HTTPServer(("127.0.0.1", 0), StratexContractHandler)
    port = server.server_address[1]
    threading.Thread(target=server.serve_forever, daemon=True).start()

    os.environ["FRIDAY_STRATEX_URL"] = f"http://127.0.0.1:{port}"
    os.environ["STRATEX_URL"] = f"http://127.0.0.1:{port}"
    os.environ["FRIDAY_STRATEX_API_KEY"] = "test-key"

    from friday.tools.builtin.stratex_portfolio import StratexPortfolioTool

    tool = StratexPortfolioTool()
    result = tool.execute(question="friday, check my stratex balance", kind="portfolio")

    print("=" * 72)
    print("LIVE PATH — Friday's answer with Stratex actually reachable:")
    print("=" * 72)
    print(result.content)
    print("=" * 72)
    print(f"is_error: {result.is_error}")
    checks = {
        "no error": result.is_error is False,
        "balance rendered": "10,423.87" in result.content,
        "positions listed": "BTCUSDT" in result.content and "ETHUSDT" in result.content,
        "strategies listed": "momentum_breakout_v2" in result.content,
        "mode shown": "testnet" in result.content,
        "fail-closed note": "D-015" in result.content,
    }
    for name, ok in checks.items():
        print(f"  {'PASS' if ok else 'FAIL'}: {name}")
    verdict = all(checks.values())
    print("VERDICT:", "PASS - live balance query works end-to-end" if verdict else "FAIL")
    server.shutdown()
    return 0 if verdict else 1

if __name__ == "__main__":
    raise SystemExit(main())
