#!/usr/bin/env python3
"""HTTP auth-matrix check for the FRIDAY MCP gateway.

The token is never stored in the repository. Export it first:

    FRIDAY_MCP_TOKEN=... python scripts/test_auth_matrix.py

Set FRIDAY_MCP_URL to target a different gateway.
"""

from __future__ import annotations

import json
import os
import ssl
import sys
import urllib.error
import urllib.request

CTX = ssl.create_default_context()
BASE_URL = os.getenv("FRIDAY_MCP_URL", "https://friday-universe.duckdns.org/mcp")
TOKEN = os.getenv("FRIDAY_MCP_TOKEN", "").strip()


def rpc_call(url: str, method: str, params: dict | None = None, headers: dict | None = None):
    payload = {"jsonrpc": "2.0", "id": 1, "method": method}
    if params:
        payload["params"] = params
    hdrs = {"Content-Type": "application/json"}
    if headers:
        hdrs.update(headers)
    req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers=hdrs)
    try:
        with urllib.request.urlopen(req, context=CTX, timeout=10) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8")
        try:
            return exc.code, json.loads(body)
        except Exception:
            return exc.code, body


def main() -> int:
    if not TOKEN:
        print("FRIDAY_MCP_TOKEN is not set; refusing to probe the gateway.", file=sys.stderr)
        return 2

    print("=" * 60)
    print("TEST 1: Unauthenticated 'initialize'")
    code, res = rpc_call(BASE_URL, "initialize")
    print(f"Status: {code}, ServerInfo: {res.get('result', {}).get('serverInfo')}")
    assert code == 200, f"Expected 200, got {code}"

    print("=" * 60)
    print("TEST 2: Unauthenticated 'tools/list'")
    code, res = rpc_call(BASE_URL, "tools/list")
    tools = res.get("result", {}).get("tools", [])
    print(f"Status: {code}, Tool count: {len(tools)}")
    assert code == 200, f"Expected 200, got {code}"
    assert len(tools) == 15, f"Expected 15 tools, got {len(tools)}"

    print("=" * 60)
    print("TEST 3: Unauthenticated write tool call (dokploy_deploy_app)")
    code, res = rpc_call(
        BASE_URL, "tools/call", {"name": "dokploy_deploy_app", "arguments": {"app_id": "app_friday"}}
    )
    print(f"Status: {code}, Result: {res}")
    text_block = res.get("result", {}).get("content", [{}])[0].get("text", "")
    assert "Unauthorized" in text_block, "Expected Unauthorized error for write tool"

    print("=" * 60)
    print("TEST 4: Authenticated write tool call via ?token= URL parameter")
    auth_url = f"{BASE_URL}?token={TOKEN}"
    code, res = rpc_call(
        auth_url,
        "tools/call",
        {"name": "dokploy_deploy_app", "arguments": {"app_id": "app_friday", "confirmation": False}},
    )
    print(f"Status: {code}, Result: {res}")
    text_block = res.get("result", {}).get("content", [{}])[0].get("text", "")
    assert "Safety Guard" in text_block, f"Expected Safety Guard message, got {text_block}"

    print("=" * 60)
    print("TEST 5: Authenticated write tool call via Bearer header")
    code, res = rpc_call(
        BASE_URL,
        "tools/call",
        {"name": "dokploy_deploy_app", "arguments": {"app_id": "app_friday", "confirmation": False}},
        headers={"Authorization": f"Bearer {TOKEN}"},
    )
    print(f"Status: {code}, Result: {res}")
    text_block = res.get("result", {}).get("content", [{}])[0].get("text", "")
    assert "Safety Guard" in text_block, f"Expected Safety Guard message, got {text_block}"

    print("=" * 60)
    print("ALL AUTHENTICATION TESTS PASSED!")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
