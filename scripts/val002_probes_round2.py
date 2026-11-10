#!/usr/bin/env python3
"""TASK-VAL-002 round 2 — corrected paths + bridge MCP session protocol."""
from __future__ import annotations

import datetime as dt
import json
import urllib.error
import urllib.request

BASE = "https://friday-universe.duckdns.org"


def http(url: str, method: str = "GET", payload: dict | None = None, headers: dict | None = None, timeout: float = 20.0):
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Accept", "application/json")
    if data is not None:
        req.add_header("Content-Type", "application/json")
    for k, v in (headers or {}).items():
        req.add_header(k, v)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, resp.read().decode("utf-8", "replace")[:800], dict(resp.headers)
    except urllib.error.HTTPError as exc:
        return exc.code, (exc.read().decode("utf-8", "replace")[:800] if exc.fp else ""), dict(exc.headers or {})
    except Exception as exc:  # noqa: BLE001
        return None, f"{type(exc).__name__}: {exc}", {}


def now() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


print(f"--- probes at {now()} ---")

# 1. Inference chat completions, no key (route is key-gated by Depends)
code, body, _ = http(f"{BASE}/inference/v1/chat/completions", "POST", {"model": "gpt-oss-120b", "messages": [{"role": "user", "content": "hi"}]})
print(f"[{'PASS' if code in (401, 403) else 'FINDING'}] inference /v1/chat/completions no key -> HTTP {code}: {body[:160]}")

# 2. Stratex anonymous surface — read-only views into the live-execution engine state
code, body, _ = http(f"{BASE}/stratex/api/live/exchanges")
print(f"[{'INFO'}] stratex /api/live/exchanges anonymous -> HTTP {code}: {body[:200]}")
code, body, _ = http(f"{BASE}/stratex/api/live/account")
print(f"[{'INFO'}] stratex /api/live/account anonymous -> HTTP {code}: {body[:200]}")

# 3. Bridge MCP: initialize -> capture session id -> tools/list (documents D-014 anonymous exposure)
init = {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2025-03-26", "capabilities": {}, "clientInfo": {"name": "val2-probe", "version": "1.0"}}}
req = urllib.request.Request(f"{BASE}/bridge/mcp", data=json.dumps(init).encode(), method="POST")
req.add_header("Content-Type", "application/json")
req.add_header("Accept", "application/json, text/event-stream")
try:
    with urllib.request.urlopen(req, timeout=20) as resp:
        raw = resp.read().decode("utf-8", "replace")
        sid = resp.headers.get("mcp-session-id") or resp.headers.get("Mcp-Session-Id") or ""
        print(f"[INFO] bridge initialize 200; session-id header present: {bool(sid)}")
except urllib.error.HTTPError as exc:
    raw, sid = "", ""
    print(f"[INFO] bridge initialize HTTP {exc.code}")

if sid:
    req = urllib.request.Request(f"{BASE}/bridge/mcp", data=json.dumps({"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}}).encode(), method="POST")
    req.add_header("Content-Type", "application/json")
    req.add_header("Accept", "application/json, text/event-stream")
    req.add_header("mcp-session-id", sid)
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            raw = resp.read().decode("utf-8", "replace")
            tools = []
            for line in raw.splitlines():
                if line.startswith("data:"):
                    try:
                        data = json.loads(line[5:].strip())
                        tools = [t.get("name") for t in data.get("result", {}).get("tools", [])]
                    except json.JSONDecodeError:
                        pass
                    break
            print(f"[FINDING-D14] anonymous bridge tools visible: {tools}")
    except urllib.error.HTTPError as exc:
        print(f"[INFO] bridge tools/list with session -> HTTP {exc.code}")
else:
    print("[INFO] no session id header returned; streamable-http may be stateless here — retry tools/list without session")
    req = urllib.request.Request(f"{BASE}/bridge/mcp", data=json.dumps({"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}}).encode(), method="POST")
    req.add_header("Content-Type", "application/json")
    req.add_header("Accept", "application/json, text/event-stream")
    req.add_header("mcp-session-id", "probe-stateless")
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            raw = resp.read().decode("utf-8", "replace")
            for line in raw.splitlines():
                if line.startswith("data:"):
                    try:
                        data = json.loads(line[5:].strip())
                        print(f"[FINDING-D14] anonymous bridge tools: {[t.get('name') for t in data.get('result', {}).get('tools', [])]}")
                    except json.JSONDecodeError:
                        print(f"[INFO] tools/list data line (unparsed): {line[:200]}")
                    break
    except urllib.error.HTTPError as exc:
        print(f"[INFO] bridge tools/list retry -> HTTP {exc.code}")

# 4. Gateway-level: HEAD/GET on root (owner's dashboard) and nonexistent paths (info-leak check)
code, body, hdrs = http(f"{BASE}/definitely-not-a-route")
server_hdr = hdrs.get("Server", "")
print(f"[INFO] unknown route -> HTTP {code}; Server header: {server_hdr}")
