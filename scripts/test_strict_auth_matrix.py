import os
import secrets
import sys
import urllib.request
import json
import ssl

ctx = ssl.create_default_context()
BASE_URL = os.getenv("FRIDAY_MCP_URL", "https://friday-universe.duckdns.org/mcp")

# Never commit tokens. Export FRIDAY_MCP_TOKEN before running this verifier.
NEW_TOKEN = os.getenv("FRIDAY_MCP_TOKEN", "").strip()
if not NEW_TOKEN:
    raise SystemExit("FRIDAY_MCP_TOKEN is not set; refusing to probe the gateway.")

# A random 24-byte value is guaranteed not to be a live credential.
OLD_EXPIRED_TOKEN = secrets.token_hex(24)

def rpc_call(url, method, params=None, headers=None):
    payload = {"jsonrpc": "2.0", "id": 1, "method": method}
    if params:
        payload["params"] = params
    hdrs = {"Content-Type": "application/json"}
    if headers:
        hdrs.update(headers)
    req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers=hdrs)
    try:
        with urllib.request.urlopen(req, context=ctx, timeout=10) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8")
        try:
            return e.code, json.loads(body)
        except Exception:
            return e.code, body

print("="*65)
print("TEST 1: Unauthenticated 'initialize' (Protocol Discovery)")
code, res = rpc_call(BASE_URL, "initialize")
print(f"Status: {code}, Server: {res.get('result', {}).get('serverInfo', {}).get('name')}")
assert code == 200

print("="*65)
print("TEST 2: Unauthenticated 'tools/list' (Tool Discovery)")
code, res = rpc_call(BASE_URL, "tools/list")
tools = res.get('result', {}).get('tools', [])
print(f"Status: {code}, Tools Count: {len(tools)}")
assert code == 200
assert len(tools) >= 15

print("="*65)
print("TEST 3: Unauthenticated 'laptop_read_file' -> MUST BE BLOCKED")
code, res = rpc_call(BASE_URL, "tools/call", {"name": "laptop_read_file", "arguments": {"relative_path": "FRIDAY/README.md"}})
print(f"Status: {code}, Response: {res}")
assert code == 401

print("="*65)
print("TEST 4: Unauthenticated 'laptop_list_workspace' -> MUST BE BLOCKED")
code, res = rpc_call(BASE_URL, "tools/call", {"name": "laptop_list_workspace", "arguments": {}})
print(f"Status: {code}, Response: {res}")
assert code == 401

print("="*65)
print("TEST 5: Unauthenticated 'get_cloud_vm_status' -> MUST BE BLOCKED")
code, res = rpc_call(BASE_URL, "tools/call", {"name": "get_cloud_vm_status", "arguments": {}})
print(f"Status: {code}, Response: {res}")
assert code == 401

print("="*65)
print("TEST 6: Call with OLD EXPIRED TOKEN -> MUST BE BLOCKED (401)")
code, res = rpc_call(BASE_URL, "tools/call", {"name": "get_cloud_vm_status", "arguments": {}}, headers={"Authorization": f"Bearer {OLD_EXPIRED_TOKEN}"})
print(f"Status: {code}, Response: {res}")
assert code == 401

print("="*65)
print("TEST 7: Call with NEW TOKEN via 'Authorization: Bearer <TOKEN>' -> MUST SUCCEED (200)")
code, res = rpc_call(BASE_URL, "tools/call", {"name": "get_cloud_vm_status", "arguments": {}}, headers={"Authorization": f"Bearer {NEW_TOKEN}"})
print(f"Status: {code}, Result status: {json.loads(res['result']['content'][0]['text'])['status']}")
assert code == 200

print("="*65)
print("TEST 8: Call laptop tool with NEW TOKEN -> MUST SUCCEED (200)")
code, res = rpc_call(BASE_URL, "tools/call", {"name": "laptop_system_info", "arguments": {}}, headers={"Authorization": f"Bearer {NEW_TOKEN}"})
print(f"Status: {code}, Output: {res['result']['content'][0]['text'].splitlines()[0]}")
assert code == 200
assert "Laptop System Info" in res['result']['content'][0]['text']

print("="*65)
print("TEST 9: Call Dokploy with NEW TOKEN -> MUST SUCCEED (200)")
code, res = rpc_call(BASE_URL, "tools/call", {"name": "dokploy_check_health", "arguments": {}}, headers={"Authorization": f"Bearer {NEW_TOKEN}"})
print(f"Status: {code}, Dokploy health: {json.loads(res['result']['content'][0]['text'])['status']}")
assert code == 200

print("="*65)
print("TEST 10: Call 'dokploy_deploy_app' without confirmation -> SAFETY GUARD ACTIVATED")
code, res = rpc_call(BASE_URL, "tools/call", {"name": "dokploy_deploy_app", "arguments": {"app_id": "app_friday"}}, headers={"Authorization": f"Bearer {NEW_TOKEN}"})
print(f"Status: {code}, Safety Guard text: {res['result']['content'][0]['text']}")
assert "Safety Guard" in res['result']['content'][0]['text']

print("="*65)
print("TEST 11: Call 'laptop_read_file' with NEW TOKEN -> MUST SUCCEED (200)")
code, res = rpc_call(BASE_URL, "tools/call", {"name": "laptop_read_file", "arguments": {"relative_path": "README.md"}}, headers={"Authorization": f"Bearer {NEW_TOKEN}"})
print(f"Status: {code}, File content preview: {res['result']['content'][0]['text'].splitlines()[0]}")
assert code == 200
assert "=== File:" in res['result']['content'][0]['text']

print("="*65)
print("ALL 11 STRICT SECURITY & INTEGRATION TESTS PASSED PERFECTLY!")
