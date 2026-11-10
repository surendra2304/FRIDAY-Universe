#!/usr/bin/env python3
"""TASK-VAL-001 — Live fleet validation against the public gateway.

Probes every agent through https://friday-universe.duckdns.org exactly the way
the owner reaches them, captures timestamped evidence per agent, and writes a
machine-readable JSON report plus a markdown summary.

Design rules (docs/MASTER_PLAN.md §8):
- Read-only: nothing here mutates agent state. The single FRIDAY greeting probe
  is the same friend-chat the owner performs and is marked in the report.
- Honest: every failure is recorded verbatim; a non-200 is evidence, not noise.
- Repeatable: run locally, from any sandbox, or via the
  "Fleet Live Validation" workflow_dispatch (which adds server-side
  systemctl evidence with the same layout).

Usage:
    python scripts/validate_fleet_live.py [--base-url URL] [--out DIR] [--json-only]
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import ssl
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

GATEWAY_DEFAULT = "https://friday-universe.duckdns.org"

# (agent, gateway prefix) — mirrors deploy/Caddyfile routing.
AGENTS = [
    ("FRIDAY", "friday"),
    ("Inference", "inference"),
    ("Memora", "memora"),
    ("Stratex", "stratex"),
    ("Futuris", "futuris"),
    ("IntelX", "intelx"),
    ("Forge", "forge"),
    ("Sentinel", "sentinel"),
    ("Cortex", "cortex"),
    ("VyralX", "vyralx"),
]

# Per-agent read-only functional probes (beyond /health). Each entry:
# label -> (method, path, payload-or-None, validator)
# Validators must never raise; return (ok: bool, evidence: str).
FUNCTIONAL_PROBES: dict[str, list[dict]] = {
    "FRIDAY": [
        {
            "label": "fleet_status",
            "method": "GET",
            "path": "/friday/api/agents/status",
            "payload": None,
            "validate": lambda body, code: (
                code == 200 and isinstance(body, dict),
                "agents dict present" if isinstance(body, dict) else str(body)[:120],
            ),
        },
        {
            "label": "friend_persona_greeting",
            "method": "POST",
            "path": "/friday/api/chat",
            "payload": {"message": "hello FRIDAY"},
            "expect_failure": True,
            "validate": lambda body, code: (
                code in (401, 403, 503),
                f"remote chat without owner key blocked with HTTP {code} (D-023 gate live); persona E2E needs the owner key",
            ),
        },
        {
            "label": "control_session_requires_key",
            "method": "GET",
            "path": "/friday/api/control/session",
            "payload": None,
            "expect_failure": True,
            "validate": lambda body, code: (
                code in (401, 403, 503),
                f"unauthenticated remote mint blocked with HTTP {code} (TASK-SEC-005 live)",
            ),
        },
    ],
    "Memora": [
        {
            "label": "health_detail",
            "method": "GET",
            "path": "/memora/health",
            "payload": None,
            "validate": lambda body, code: (
                code == 200 and isinstance(body, dict),
                json.dumps(body)[:160],
            ),
        }
    ],
}


def utcnow() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _http(url: str, method: str = "GET", payload: dict | None = None, timeout: float = 20.0):
    """Return (status_code, parsed_body_or-raw-text, elapsed_seconds, error)."""
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Accept", "application/json")
    if data is not None:
        req.add_header("Content-Type", "application/json")
        req.add_header("Origin", "https://friday-universe.duckdns.org")
    start = time.monotonic()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", "replace")
            code = resp.status
            err = None
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", "replace") if exc.fp else ""
        code = exc.code
        err = f"HTTPError {exc.code}"
    except Exception as exc:  # noqa: BLE001 — evidence collector must not crash
        return None, None, time.monotonic() - start, f"{type(exc).__name__}: {exc}"
    elapsed = time.monotonic() - start
    try:
        body = json.loads(raw) if raw.strip() else ""
    except json.JSONDecodeError:
        body = raw[:400]
    return code, body, elapsed, err


def probe_health(base: str, prefix: str) -> dict:
    code, body, elapsed, err = _http(f"{base}/{prefix}/health")
    healthy = code == 200 and not err
    detail = ""
    if isinstance(body, dict):
        detail = json.dumps({k: body.get(k) for k in ("status", "service", "healthy", "version", "agent") if k in body})[:200]
    elif body:
        detail = str(body)[:200]
    return {
        "endpoint": f"/{prefix}/health",
        "http_status": code,
        "healthy": healthy,
        "latency_s": round(elapsed, 3),
        "detail": detail,
        "error": err,
        "probed_at": utcnow(),
    }


def run_functional(base: str, agent: str) -> list[dict]:
    results = []
    for probe in FUNCTIONAL_PROBES.get(agent, []):
        code, body, elapsed, err = _http(
            f"{base}{probe['path']}", probe["method"], probe.get("payload")
        )
        if probe.get("expect_failure"):
            ok, evidence = probe["validate"](body, code)
        else:
            ok, evidence = probe["validate"](body, code) if not err else (False, err)
        results.append(
            {
                "label": probe["label"],
                "endpoint": probe["path"],
                "http_status": code,
                "ok": bool(ok),
                "latency_s": round(elapsed, 3),
                "evidence": str(evidence)[:400],
                "probed_at": utcnow(),
            }
        )
    return results


def probe_bridge(base: str) -> dict:
    """MCP streamable-HTTP initialize handshake (owner-accepted public bridge, D-014)."""
    url = f"{base}/bridge/mcp"
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "2025-03-26",
            "capabilities": {},
            "clientInfo": {"name": "fleet-live-validator", "version": "1.0"},
        },
    }
    req = urllib.request.Request(url, data=json.dumps(payload).encode(), method="POST")
    req.add_header("Content-Type", "application/json")
    req.add_header("Accept", "application/json, text/event-stream")
    start = time.monotonic()
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            raw = resp.read().decode("utf-8", "replace")
            code = resp.status
            err = None
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", "replace") if exc.fp else ""
        code = exc.code
        err = f"HTTPError {exc.code}"
    except Exception as exc:  # noqa: BLE001
        return {
            "endpoint": "/bridge/mcp",
            "http_status": None,
            "ok": False,
            "error": f"{type(exc).__name__}: {exc}",
            "probed_at": utcnow(),
        }
    ok = code == 200
    server_info = ""
    for line in raw.splitlines():
        if line.startswith("data:"):
            try:
                data = json.loads(line[5:].strip())
                server_info = json.dumps(data.get("result", {}).get("serverInfo", {}))[:200]
            except json.JSONDecodeError:
                server_info = line[:200]
            break
    if not server_info and raw.strip().startswith("{"):
        try:
            server_info = json.dumps(json.loads(raw).get("result", {}).get("serverInfo", {}))[:200]
        except json.JSONDecodeError:
            server_info = raw[:200]
    return {
        "endpoint": "/bridge/mcp",
        "http_status": code,
        "ok": ok,
        "latency_s": round(time.monotonic() - start, 3),
        "server_info": server_info,
        "error": err,
        "probed_at": utcnow(),
    }


def probe_tls(hostname: str) -> dict:
    """TLS certificate + protocol evidence for the ingress review."""
    try:
        ctx = ssl.create_default_context()
        with socket.create_connection((hostname, 443), timeout=15) as sock:
            with ctx.wrap_socket(sock, server_hostname=hostname) as tls:
                cert = tls.getpeercert()
                proto = tls.version()
        not_after = cert.get("notAfter", "")
        return {
            "ok": True,
            "protocol": proto,
            "issuer": dict(x[0] for x in cert.get("issuer", ())) .get("organizationName", ""),
            "not_after": not_after,
            "subject_alt_names": [v for k, v in cert.get("subjectAltName", ())][:5],
        }
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": f"{type(exc).__name__}: {exc}"}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default=GATEWAY_DEFAULT)
    parser.add_argument("--out", default="docs/validation")
    parser.add_argument("--json-only", action="store_true")
    args = parser.parse_args()

    base = args.base_url.rstrip("/")
    report: dict = {
        "task": "TASK-VAL-001",
        "gateway": base,
        "started_at": utcnow(),
        "agents": {},
    }

    for agent, prefix in AGENTS:
        entry = {"gateway_prefix": prefix, "health": probe_health(base, prefix)}
        entry["functional"] = run_functional(base, agent)
        report["agents"][agent] = entry
        h = entry["health"]
        status = "OK" if h["healthy"] else f"FAIL({h['http_status'] or h['error']})"
        print(f"[{agent:<10}] /{prefix}/health -> {status} ({h['latency_s']}s) {h['detail'][:80]}")
        for fp in entry["functional"]:
            mark = "PASS" if fp["ok"] else "FAIL"
            print(f"    - {fp['label']}: {mark} (HTTP {fp['http_status']}) {str(fp['evidence'])[:100]}")

    report["bridge"] = probe_bridge(base)
    b = report["bridge"]
    print(f"[BRIDGE     ] initialize -> HTTP {b['http_status']} {b.get('server_info','')[:80]}")

    report["tls"] = probe_tls(urllib.parse.urlsplit(base).hostname or base)
    report["finished_at"] = utcnow()

    healthy = sum(1 for a in report["agents"].values() if a["health"]["healthy"])
    report["summary"] = {
        "agents_healthy": healthy,
        "agents_total": len(AGENTS),
        "bridge_ok": report["bridge"]["ok"],
        "all_functional_ok": all(
            fp["ok"] for a in report["agents"].values() for fp in a["functional"]
        ),
    }
    print(
        f"\nSUMMARY: {healthy}/{len(AGENTS)} agents healthy; bridge "
        f"{'OK' if report['bridge']['ok'] else 'FAIL'}; all functional probes "
        f"{'PASS' if report['summary']['all_functional_ok'] else 'SEE REPORT'}"
    )

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / f"fleet_live_validation_{report['started_at'][:10]}.json"
    json_path.write_text(json.dumps(report, indent=2) + "\n")

    if not args.json_only:
        md_lines = [
            f"# Live Fleet Validation — {report['started_at'][:10]} (TASK-VAL-001)",
            "",
            f"Gateway: `{base}` — probed {report['started_at']} to {report['finished_at']} UTC from a remote network (the owner's path).",
            "",
            "| Agent | Health | HTTP | Latency | Detail |",
            "|---|---|---|---|---|",
        ]
        for agent, entry in report["agents"].items():
            h = entry["health"]
            md_lines.append(
                f"| {agent} | {'OK' if h['healthy'] else 'FAIL'} | {h['http_status']} "
                f"| {h['latency_s']}s | {h['detail'] or h['error'] or ''} |"
            )
        md_lines += ["", "## Functional probes", ""]
        for agent, entry in report["agents"].items():
            for fp in entry["functional"]:
                md_lines.append(
                    f"- **{agent} / {fp['label']}**: {'PASS' if fp['ok'] else 'FAIL'} "
                    f"(HTTP {fp['http_status']}, {fp['latency_s']}s) — {fp['evidence']}"
                )
        br = report["bridge"]
        md_lines += [
            "",
            "## Engineering bridge (MCP initialize, D-014 public)",
            f"- HTTP {br['http_status']} — {br.get('server_info') or br.get('error')}",
            "",
            "## TLS",
            f"- {json.dumps(report['tls'])}",
            "",
            f"**Summary:** {healthy}/{len(AGENTS)} agents healthy; "
            f"bridge {'OK' if br['ok'] else 'FAIL'}; functional probes "
            f"{'all PASS' if report['summary']['all_functional_ok'] else 'see failures above'}.",
            "",
        ]
        md_path = out_dir / f"FLEET_LIVE_VALIDATION_{report['started_at'][:10]}.md"
        md_path.write_text("\n".join(md_lines))
        print(f"Wrote {json_path} and {md_path}")

    return 0 if healthy == len(AGENTS) else 1


if __name__ == "__main__":
    sys.exit(main())
