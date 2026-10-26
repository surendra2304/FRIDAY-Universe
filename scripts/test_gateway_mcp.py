#!/usr/bin/env python3
"""
End-to-End MCP Client Test Suite for FRIDAY Universe Consolidated Gateway.
Connects over public HTTPS without TLS bypass, runs initialize, tools/list,
and executes all registered tools against the live production gateway.
"""

import json
import os
import urllib.request

GATEWAY_URL = os.getenv("FRIDAY_MCP_URL", "https://friday-universe.duckdns.org/mcp")
# Never commit tokens. Export FRIDAY_MCP_TOKEN before running this verifier.
AUTH_TOKEN = os.getenv("FRIDAY_MCP_TOKEN", "").strip()

def rpc_call(method: str, params: dict = None, rpc_id: int = 1):
    payload = {
        "jsonrpc": "2.0",
        "id": rpc_id,
        "method": method,
        "params": params or {}
    }
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        GATEWAY_URL,
        data=body,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {AUTH_TOKEN}",
            "User-Agent": "FRIDAY-MCP-Client-Verifier"
        }
    )
    with urllib.request.urlopen(req, timeout=12) as resp:
        return json.loads(resp.read().decode())

def main():
    if not AUTH_TOKEN:
        raise SystemExit("FRIDAY_MCP_TOKEN is not set; refusing to probe the gateway.")
    print("=" * 65)
    print("FRIDAY UNIFIED MCP GATEWAY — END-TO-END VERIFICATION")
    print(f"Target: {GATEWAY_URL}")
    print("=" * 65)

    # 1. Initialize
    print("\n--- 1. Testing 'initialize' ---")
    init_res = rpc_call("initialize", {"protocolVersion": "2024-11-05", "capabilities": {}, "clientInfo": {"name": "TestClient", "version": "1.0"}})
    print("Server Info:", json.dumps(init_res.get("result", {}).get("serverInfo", {})))

    # 2. Tools List
    print("\n--- 2. Testing 'tools/list' ---")
    list_res = rpc_call("tools/list")
    tools = list_res.get("result", {}).get("tools", [])
    print(f"Registered Tools Count: {len(tools)}")
    for t in tools:
        print(f"  • {t['name']}: {t['description'][:60]}...")

    # 3. Tool Calls
    tools_to_test = [
        ("oci_check_auth", {}),
        ("oci_list_instances", {}),
        ("oci_get_instance_details", {}),
        ("get_cloud_vm_status", {}),
        ("postgres_read_diagnostic", {"query_type": "summary"}),
        ("dokploy_check_health", {}),
        ("dokploy_list_apps", {}),
        ("dokploy_get_app_details", {"app_id": "app_friday"}),
        ("laptop_system_info", {})
    ]

    print("\n--- 3. Testing 'tools/call' on Registered Tools ---")
    for name, args in tools_to_test:
        print(f"\n[CALL] {name} (args: {args})")
        try:
            res = rpc_call("tools/call", {"name": name, "arguments": args})
            content = res.get("result", {}).get("content", [])
            txt = content[0].get("text", "") if content else ""
            parsed = json.loads(txt) if txt.startswith("{") or txt.startswith("[") else txt
            print(f"[RESULT {name}]:\n{json.dumps(parsed, indent=2)[:300]}...")
        except Exception as e:
            print(f"[FAIL {name}]: {e}")

if __name__ == "__main__":
    main()
