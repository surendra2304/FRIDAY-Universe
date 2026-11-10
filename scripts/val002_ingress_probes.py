#!/usr/bin/env python3
"""TASK-VAL-002 — Read-only security probes of the public ingress surface.

Every probe here is read-only or an auth-REJECTION check (expecting 401/403/405).
No valid credentials are presented anywhere; no state-changing request succeeds.

Evidence feeds docs/security/INGRESS_BRIDGE_REVIEW_<date>.md.
"""
from __future__ import annotations

import datetime as dt
import json
import ssl
import socket
import time
import urllib.error
import urllib.request

BASE = "https://friday-universe.duckdns.org"
HOST = "friday-universe.duckdns.org"


def utcnow() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def http(url: str, method: str = "GET", payload: dict | None = None, headers: dict | None = None, timeout: float = 20.0):
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Accept", "application/json")
    if data is not None:
        req.add_header("Content-Type", "application/json")
    for k, v in (headers or {}).items():
        req.add_header(k, v)
    start = time.monotonic()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, dict(resp.headers), resp.read().decode("utf-8", "replace")[:600], round(time.monotonic() - start, 3), None
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", "replace")[:600] if exc.fp else ""
        return exc.code, dict(exc.headers or {}), body, round(time.monotonic() - start, 3), None
    except Exception as exc:  # noqa: BLE001
        return None, {}, "", round(time.monotonic() - start, 3), f"{type(exc).__name__}: {exc}"


def main() -> None:
    results = []

    def record(label: str, url: str, method: str, expect: str, got_code, detail: str):
        ok = expect in str(got_code) if isinstance(got_code, int) else False
        results.append({"t": utcnow(), "label": label, "request": f"{method} {url}", "expected": expect, "got": got_code, "pass": ok, "detail": detail[:300]})
        print(f"[{'PASS' if ok else 'INFO'}] {label}: expected {expect}, got HTTP {got_code} — {detail[:120]}")

    # --- 1. TLS ---
    ctx = ssl.create_default_context()
    with socket.create_connection((HOST, 443), timeout=15) as sock:
        with ctx.wrap_socket(sock, server_hostname=HOST) as tls:
            cert = tls.getpeercert()
            proto = tls.version()
            cipher = tls.cipher()
    print(f"[PASS] TLS: {proto}, cipher {cipher[0]}, issuer {dict(x[0] for x in cert.get('issuer', ())).get('organizationName','')}, expires {cert.get('notAfter')}")
    results.append({"t": utcnow(), "label": "tls", "pass": True, "detail": f"{proto}; {cipher[0]}; expires {cert.get('notAfter')}"})

    # --- 2. Ingress security headers ---
    code, headers, body, _, err = http(f"{BASE}/friday/")
    interesting = {k: v for k, v in headers.items() if k.lower() in (
        "x-content-type-options", "x-frame-options", "referrer-policy",
        "strict-transport-security", "content-security-policy", "server", "x-powered-by")}
    print(f"[INFO] Gateway headers: {json.dumps(interesting)}")
    results.append({"t": utcnow(), "label": "ingress_headers", "pass": None, "detail": interesting})

    # --- 3. FRIDAY control surface (TASK-SEC-005 must be live) ---
    code, _, body, _, _ = http(f"{BASE}/friday/api/control/session")
    record("control_session_no_key", f"{BASE}/friday/api/control/session", "GET", "401", code, body)

    code, _, body, _, _ = http(f"{BASE}/friday/api/control/session", headers={"Origin": "https://evil.example.com"})
    record("control_session_forged_origin", f"{BASE}/friday/api/control/session", "GET", "403", code, body)

    code, _, body, _, _ = http(f"{BASE}/friday/api/control/session", headers={"Origin": BASE, "x-friday-api-key": "wrong-key-abc"})
    record("control_session_wrong_key", f"{BASE}/friday/api/control/session", "GET", "401", code, body)

    code, _, body, _, _ = http(f"{BASE}/friday/api/chat", method="POST", payload={"message": "hi"})
    record("chat_no_key", f"{BASE}/friday/api/chat", "POST", "401", code, body)

    code, _, body, _, _ = http(f"{BASE}/friday/api/v1/dispatch/records/report")
    record("dispatch_records_report_public", f"{BASE}/friday/api/v1/dispatch/records/report", "GET", "200/401", code, body[:200])

    # --- 4. Engineering bridge (owner-accepted public, D-014) ---
    init = {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2025-03-26", "capabilities": {}, "clientInfo": {"name": "val2-probe", "version": "1.0"}}}
    req = urllib.request.Request(f"{BASE}/bridge/mcp", data=json.dumps(init).encode(), method="POST")
    req.add_header("Content-Type", "application/json")
    req.add_header("Accept", "application/json, text/event-stream")
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            bridge_code, bridge_body = resp.status, resp.read().decode("utf-8", "replace")[:300]
    except urllib.error.HTTPError as exc:
        bridge_code, bridge_body = exc.code, (exc.read().decode("utf-8", "replace")[:300] if exc.fp else "")
    record("bridge_initialize_no_auth", f"{BASE}/bridge/mcp", "POST", "200 (D-014 accepted)", bridge_code, bridge_body)

    # tools/list — inventory what a remote anonymous caller can see (D-014 risk documentation)
    req = urllib.request.Request(f"{BASE}/bridge/mcp", data=json.dumps({"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}}).encode(), method="POST")
    req.add_header("Content-Type", "application/json")
    req.add_header("Accept", "application/json, text/event-stream")
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
            print(f"[INFO] Anonymous bridge tools visible: {tools}")
            results.append({"t": utcnow(), "label": "bridge_tools_anonymous", "pass": None, "detail": tools})
    except Exception as exc:  # noqa: BLE001
        print(f"[INFO] bridge tools/list failed: {exc}")

    # --- 5. Agent state-changing endpoints must reject anonymous callers ---
    code, _, body, _, _ = http(f"{BASE}/forge/api/v1/task/execute", method="POST", payload={"task": "probe"})
    record("forge_task_execute_no_key", f"{BASE}/forge/api/v1/task/execute", "POST", "401", code, body)

    code, _, body, _, _ = http(f"{BASE}/stratex/api/v1/trading/engines/autohedge/consensus", method="POST", payload={})
    record("stratex_trading_no_key", f"{BASE}/stratex/api/v1/trading/engines/autohedge/consensus", "POST", "401", code, body)

    code, _, body, _, _ = http(f"{BASE}/sentinel/api/v1/security/scan", method="POST", payload={})
    record("sentinel_scan_no_key", f"{BASE}/sentinel/api/v1/security/scan", "POST", "401/404/405", code, body[:200])

    code, _, body, _, _ = http(f"{BASE}/inference/api/v1/chat/completions", method="POST", payload={"messages": []})
    record("inference_completions_no_key", f"{BASE}/inference/api/v1/chat/completions", "POST", "401", code, body)

    # --- 6. Origin gate on a non-FRIDAY state-changing surface (CORS drive-by class) ---
    code, _, body, _, _ = http(f"{BASE}/friday/api/voice/speak", method="POST", payload={"text": "test"}, headers={"Origin": "https://evil.example.com"})
    record("friday_voice_speak_forged_origin", f"{BASE}/friday/api/voice/speak", "POST", "403", code, body)

    out = {"probed_at": utcnow(), "results": results}
    Path_out = "/tmp/val002_probes.json"
    with open(Path_out, "w") as fh:
        json.dump(out, fh, indent=2)
    print(f"\nWrote {Path_out}")


if __name__ == "__main__":
    main()
