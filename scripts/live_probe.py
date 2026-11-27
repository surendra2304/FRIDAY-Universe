#!/usr/bin/env python3
"""TASK-REL-104 — live_probe.py: one command per agent, output filed as evidence.

Probes the live Inference gateway (Server 1, port 8001) once per agent:

  leg A (health, genuinely per-agent): ``POST /v1/mesh/ping/{agent_id}``
      — the gateway pings that peer's ``/health`` with a 2.0 s deadline and
      returns ``reachable`` / ``status_code`` / ``latency_ms``
      (``Inference/app/api/mesh_routes.py``, ``ping_mesh_peer``). Inference
      itself is not a mesh peer, so its health leg is ``GET /v1/health``.
  leg B (one real request per agent): ``POST /v1/task/execute`` with a small
      read-only ``TaskEnvelope`` per ``target_agent`` (action ``reason``,
      prompt "Reply with the single word OK."). The receipt is the content
      proof — not a bare 200: the result carries model/provider, latency and
      the gateway's ``verification_evidence``.

CODE-READ CAVEAT (checkpoint 2, verified first-hand on main): leg B reasons
IN-GATEWAY. ``execute_task`` (``Inference/app/api/universal_task_routes.py``)
never forwards to the peer: it detects specialist requirements from
``source_agent`` / ``action`` and runs the LLM call in Inference, and the
receipt always names ``target: "inference"``. So leg B proves the gateway's
real-request path per ``target_agent`` label; leg A is the proof the request
path actually reaches each peer. Do not read leg B as peer execution.

Auth: mesh and task routes require the Inference API key
(``require_inference_api_key``: ``X-Inference-API-Key`` / ``X-API-Key`` /
``X-Friday-API-Key`` / ``Authorization: Bearer``). The key comes from the
environment (default ``INFERENCE_API_KEY``) — never a CLI argument, never
pasted into output. ``GET /v1/health`` needs no key.

Usage:
    INFERENCE_API_KEY=<key> python scripts/live_probe.py
    INFERENCE_API_KEY=<key> python scripts/live_probe.py --gateway https://friday-universe.duckdns.org/inference
    INFERENCE_API_KEY=<key> python scripts/live_probe.py --agents friday,memora --output /tmp/probe.json
    python scripts/live_probe.py --health-only        # no LLM calls, key still needed for ping

Exit code: 0 when every probed agent passes both legs, 1 when any agent
fails a leg, 2 when the gateway itself is unreachable or misconfigured.
No daemon, no timer, no new service; output is one JSON evidence record.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
import uuid
from datetime import datetime, timezone

# The 10 FRIDAY Universe agents (checkpoint 1, §2; prod VCN URLs from
# Inference/app/core/config.py get_peer_config). Order is mesh order.
AGENTS = [
    "friday",
    "inference",
    "memora",
    "stratex",
    "futuris",
    "intelx",
    "forge",
    "sentinel",
    "cortex",
    "vyralx",
]

# Mesh peers: the 9 agents in PEER_METADATA (Inference/app/api/mesh_routes.py).
# Inference is the gateway itself, not a peer.
PEERS = [a for a in AGENTS if a != "inference"]

DEFAULT_GATEWAY = "http://10.0.0.121:8001"
PUBLIC_GATEWAY = "https://friday-universe.duckdns.org/inference"
DEFAULT_KEY_ENV = "INFERENCE_API_KEY"

# Tiny, read-only probe prompt. Kept minimal on purpose: the gateway bills
# max(100, len(payload)//4) estimated tokens per execute call, and the
# server-side max_tokens is 2048 — a one-word answer costs ~100 tokens.
PROBE_PROMPT = "Reply with the single word OK."


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _request(
    method: str,
    url: str,
    api_key: str | None,
    payload: dict | None,
    timeout: float,
) -> tuple[int | None, dict | str | None, float]:
    """One HTTP call. Returns (status, parsed body or error text, latency_ms).

    A transport failure returns status None and the exception text as body.
    """
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Accept", "application/json")
    if data is not None:
        req.add_header("Content-Type", "application/json")
    if api_key:
        req.add_header("X-Inference-API-Key", api_key)
    t0 = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8", "replace")
            latency_ms = round((time.perf_counter() - t0) * 1000.0, 2)
            try:
                return resp.status, json.loads(body), latency_ms
            except json.JSONDecodeError:
                return resp.status, body, latency_ms
    except urllib.error.HTTPError as exc:
        latency_ms = round((time.perf_counter() - t0) * 1000.0, 2)
        try:
            detail = exc.read().decode("utf-8", "replace")
        except Exception:
            detail = ""
        return exc.code, detail or f"HTTP {exc.code}", latency_ms
    except Exception as exc:  # unreachable gateway, DNS, timeout, ...
        latency_ms = round((time.perf_counter() - t0) * 1000.0, 2)
        return None, f"{type(exc).__name__}: {exc}", latency_ms


def probe_agent(
    agent: str,
    gateway: str,
    api_key: str | None,
    timeout: float,
    health_only: bool,
    started_at: str,
) -> dict:
    """Probe one agent: health leg + (unless --health-only) execute leg."""
    record: dict = {
        "agent": agent,
        "started_at": started_at,
        "health": None,
        "execute": None,
        "pass": False,
        "notes": [],
    }

    # --- Leg A: health -------------------------------------------------
    if agent == "inference":
        status, body, latency_ms = _request(
            "GET", f"{gateway}/v1/health", None, None, timeout
        )
        healthy = (
            status == 200
            and isinstance(body, dict)
            and body.get("status") == "healthy"
        )
        record["health"] = {
            "via": "GET /v1/health",
            "status_code": status,
            "latency_ms": latency_ms,
            "reachable": healthy,
            "detail": body if not healthy else body.get("service"),
        }
    else:
        status, body, latency_ms = _request(
            "POST", f"{gateway}/v1/mesh/ping/{agent}", api_key, {}, timeout
        )
        if status is None:
            record["health"] = {
                "via": f"POST /v1/mesh/ping/{agent}",
                "status_code": None,
                "latency_ms": latency_ms,
                "reachable": False,
                "detail": body,
            }
        elif status == 401:
            record["health"] = {
                "via": f"POST /v1/mesh/ping/{agent}",
                "status_code": 401,
                "latency_ms": latency_ms,
                "reachable": False,
                "detail": "unauthorized — check INFERENCE_API_KEY",
            }
        elif isinstance(body, dict):
            record["health"] = {
                "via": f"POST /v1/mesh/ping/{agent}",
                "status_code": status,
                "latency_ms": body.get("latency_ms", latency_ms),
                "reachable": bool(body.get("reachable")),
                "target_url": body.get("target_url"),
                "peer_status_code": body.get("status_code"),
            }
        else:
            record["health"] = {
                "via": f"POST /v1/mesh/ping/{agent}",
                "status_code": status,
                "latency_ms": latency_ms,
                "reachable": False,
                "detail": body if isinstance(body, str) else str(body),
            }
    health_ok = bool(record["health"]["reachable"])

    # --- Leg B: one real request ---------------------------------------
    if health_only:
        record["notes"].append("execute leg skipped (--health-only)")
        record["pass"] = health_ok
        return record
    if not api_key:
        record["execute"] = {
            "via": "POST /v1/task/execute",
            "status_code": None,
            "latency_ms": None,
            "result_status": "SKIPPED",
            "detail": f"no API key in ${DEFAULT_KEY_ENV} — set it to run leg B",
        }
        record["notes"].append("execute leg skipped: no API key")
        record["pass"] = False
        return record

    envelope = {
        "task_id": f"liveprobe-{agent}-{uuid.uuid4().hex[:8]}",
        "source_agent": "live_probe",
        "target_agent": agent,
        "action": "reason",
        "payload": {
            "prompt": PROBE_PROMPT,
            "probe": "live_probe",
            "target_agent": agent,
        },
        "priority": "low",
    }
    status, body, latency_ms = _request(
        "POST", f"{gateway}/v1/task/execute", api_key, envelope, timeout
    )
    if status is None or not isinstance(body, dict):
        record["execute"] = {
            "via": "POST /v1/task/execute",
            "status_code": status,
            "latency_ms": latency_ms,
            "result_status": "TRANSPORT_ERROR",
            "detail": body if isinstance(body, str) else str(body),
        }
    else:
        receipt = body.get("receipt") or {}
        evidence = receipt.get("verification_evidence") or {}
        result = body.get("result") or {}
        response_text = result.get("response", "")
        record["execute"] = {
            "via": "POST /v1/task/execute",
            "status_code": status,
            "latency_ms": body.get("execution_time_ms", latency_ms),
            "result_status": body.get("status"),
            "task_id": body.get("task_id"),
            # The receipt always names target "inference" (code-read fact):
            # leg B is in-gateway reasoning, not peer execution.
            "receipt_target": receipt.get("target"),
            "receipt_source": evidence.get("source"),
            "model_used": result.get("model_used"),
            "provider_used": result.get("provider_used"),
            "summary": (body.get("summary") or "")[:200],
            # Content receipt, not a bare 200.
            "content_receipt": response_text[:120] if response_text else "",
            "error": body.get("error"),
        }
    execute_ok = (
        record["execute"]["status_code"] == 200
        and record["execute"]["result_status"] == "SUCCESS"
        and bool(record["execute"].get("receipt_target"))
    )
    record["pass"] = health_ok and execute_ok
    return record


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Probe the live Inference gateway once per agent: "
        "gateway health + one real request, output filed as evidence."
    )
    parser.add_argument(
        "--gateway",
        default=os.environ.get("LIVE_PROBE_GATEWAY", DEFAULT_GATEWAY),
        help=f"Gateway base URL (default {DEFAULT_GATEWAY}; "
        f"public ingress {PUBLIC_GATEWAY}).",
    )
    parser.add_argument(
        "--agents",
        default=",".join(AGENTS),
        help="Comma-separated agent subset (default: all 10).",
    )
    parser.add_argument(
        "--api-key-env",
        default=DEFAULT_KEY_ENV,
        help=f"Env var holding the Inference API key (default {DEFAULT_KEY_ENV}).",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=120.0,
        help="Per-request timeout in seconds (default 120; the gateway "
        "bounds each peer ping to 2 s server-side).",
    )
    parser.add_argument(
        "--health-only",
        action="store_true",
        help="Run only the health leg (no LLM calls).",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Write the JSON evidence record to this file as well as stdout.",
    )
    args = parser.parse_args(argv)

    agents = [a.strip().lower() for a in args.agents.split(",") if a.strip()]
    unknown = [a for a in agents if a not in AGENTS]
    if unknown:
        print(f"unknown agent(s): {', '.join(unknown)}", file=sys.stderr)
        return 2
    gateway = args.gateway.rstrip("/")
    api_key = os.environ.get(args.api_key_env)
    if not api_key:
        print(
            f"warning: no API key in ${args.api_key_env} — "
            "mesh ping / task execute legs will fail or skip",
            file=sys.stderr,
        )

    started_at = _iso_now()
    gateway_health: dict = {"via": "GET /v1/health"}
    status, body, latency_ms = _request(
        "GET", f"{gateway}/v1/health", None, None, args.timeout
    )
    gateway_health.update(
        {
            "status_code": status,
            "latency_ms": latency_ms,
            "reachable": status == 200
            and isinstance(body, dict)
            and body.get("status") == "healthy",
            "detail": body if status != 200 or not isinstance(body, dict) else body.get("service"),
        }
    )
    if not gateway_health["reachable"]:
        evidence = {
            "tool": "live_probe.py",
            "task": "TASK-REL-104",
            "gateway": gateway,
            "started_at": started_at,
            "finished_at": _iso_now(),
            "gateway_health": gateway_health,
            "agents": [],
            "passed": 0,
            "failed": len(agents),
            "ok": False,
            "error": "gateway /v1/health unreachable or unhealthy — no per-agent probes run",
        }
        print(json.dumps(evidence, indent=2))
        if args.output:
            with open(args.output, "w", encoding="utf-8") as fh:
                json.dump(evidence, fh, indent=2)
        return 2

    records = [
        probe_agent(a, gateway, api_key, args.timeout, args.health_only, started_at)
        for a in agents
    ]
    passed = sum(1 for r in records if r["pass"])
    evidence = {
        "tool": "live_probe.py",
        "task": "TASK-REL-104",
        "gateway": gateway,
        "started_at": started_at,
        "finished_at": _iso_now(),
        "gateway_health": gateway_health,
        "agents": records,
        "passed": passed,
        "failed": len(records) - passed,
        "ok": passed == len(records),
        "caveat": (
            "Leg B (/v1/task/execute) reasons in-gateway; its receipt always "
            "names target 'inference'. Leg A (mesh ping) is the per-agent "
            "reach proof. See the script docstring."
        ),
    }
    text = json.dumps(evidence, indent=2)
    print(text)
    if args.output:
        with open(args.output, "w", encoding="utf-8") as fh:
            fh.write(text + "\n")
    return 0 if evidence["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
