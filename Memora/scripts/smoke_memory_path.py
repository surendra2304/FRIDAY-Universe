#!/usr/bin/env python3
"""Post-deploy memory-path smoke probe for Memora (TASK-MEM-009).

``/health`` does not exercise the ``memory_records`` ORM, so on
2026-11-17 the fleet deployed happily on top of a schema the code
could not query: every memory path failed for ~1.5h while health
stayed green. This probe is the gate that cannot be fooled that way —
it performs the real round-trip an agent performs:

1. ``POST /v1/capture/events`` — one event carrying a unique marker,
   as the authenticated ``memora`` identity. The capture contract
   answers HTTP 200 even for a refusal (``{"stored": false, "reason":
   "pipeline_refused: DatabaseError"}`` is the schema-behind shape),
   so the probe requires ``stored is True`` and a record id, not just
   a 200.
2. ``GET /v1/memories/search?q=<marker>`` — the hybrid search (the
   read path FRIDAY's recall uses) must return the marker. A bounded
   retry covers read-back lag only; an HTTP error — the schema-behind
   500 — fails immediately.
3. Cleanup — the probe record is hard-deleted and a follow-up GET
   must answer 404, so repeated deploys never accumulate probe rows
   in shared memory. A cleanup failure fails the probe too: the
   delete path is part of the ORM surface this gate exists to prove.

Fleet CD (``.github/workflows/deploy-monorepo.yml``, Server-1 job)
runs this after the health gate whenever the run restarted Memora;
the probe's exit code is the deploy's verdict: 0 = the memory path
serves, 1 = fail the deploy loudly.

Keys are read from server-side env files into process memory only and
are never printed (the MEM-005-era re-probe discipline). No third-party
dependencies — urllib only, so it runs in the bare fleet venv.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path
from typing import Callable, List, Optional, Tuple

MEMORA_ROOT = Path(__file__).resolve().parent.parent
REPO_ROOT = MEMORA_ROOT.parent

DEFAULT_BASE_URL = "http://127.0.0.1:8002"
DEFAULT_AGENT = "memora"
DEFAULT_KEY_VAR = "MEMORA_API_KEY"
DEFAULT_ENV_FILES = (MEMORA_ROOT / ".env", REPO_ROOT / ".env")

Transport = Callable[[str, str, dict, Optional[dict], float], Tuple[int, object]]


def load_key(var: str, env_files) -> Tuple[Optional[str], Optional[str]]:
    """Return (value, source_file) for an env var; never prints the value."""
    for path in env_files:
        try:
            with open(path) as handle:
                for line in handle:
                    line = line.strip()
                    if line.startswith(var + "="):
                        value = line.split("=", 1)[1].strip().strip('"').strip("'")
                        return (value or None), str(path)
        except OSError:
            continue
    return None, None


def urllib_transport(method: str, url: str, headers: dict, body: Optional[dict], timeout: float):
    data = json.dumps(body).encode() if body is not None else None
    request = urllib.request.Request(url, data=data, method=method)
    for name, value in headers.items():
        request.add_header(name, value)
    if data:
        request.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read().decode()
            return response.status, (json.loads(raw) if raw else None)
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode()
        try:
            parsed = json.loads(raw) if raw else None
        except json.JSONDecodeError:
            parsed = raw[:300]
        return exc.code, parsed


def run_smoke(
    base_url: str,
    agent: str,
    api_key: str,
    transport: Transport = urllib_transport,
    marker: Optional[str] = None,
    timeout: float = 60.0,
    search_attempts: int = 5,
    search_delay: float = 2.0,
    log=print,
) -> bool:
    """Capture -> search round-trip. Returns True only if every step passes."""
    # A single alphanumeric token: lexical tokenisers split on dashes,
    # and the read-back must match the marker as one content token.
    marker = marker or f"ZXQSMOKE{uuid.uuid4().hex[:12]}"
    session_id = f"smoke-{marker}"
    headers = {"X-Agent-Name": agent, "X-Api-Key": api_key}
    base = base_url.rstrip("/")
    ok = True

    def step(name: str, passed: bool, detail: str = "") -> None:
        nonlocal ok
        ok = ok and passed
        log(f"MEMORA-SMOKE {name}: {'PASS' if passed else 'FAIL'}{(' - ' + detail) if detail else ''}")

    # 1. Capture one event carrying the marker.
    status, body = transport(
        "POST",
        f"{base}/v1/capture/events",
        headers,
        {
            "session_id": session_id,
            "kind": "observation",
            "content": f"MEMORA SMOKE marker {marker}: post-deploy memory-path probe.",
        },
        timeout,
    )
    record_id = body.get("id") if isinstance(body, dict) else None
    stored = isinstance(body, dict) and body.get("stored") is True
    step(
        "capture",
        status == 200 and stored and bool(record_id),
        f"status={status} stored={body.get('stored') if isinstance(body, dict) else None}"
        + (f" reason={body.get('reason')}" if isinstance(body, dict) and body.get("reason") else "")
        + (f" id={record_id}" if record_id else ""),
    )

    # 2. The hybrid-search read-back must find the marker. The bounded
    # retry covers read-back lag only: an HTTP error (the schema-behind
    # 500) fails immediately, never retries.
    search_ok = False
    search_detail = "not attempted"
    for attempt in range(1, max(1, search_attempts) + 1):
        status, body = transport(
            "GET",
            f"{base}/v1/memories/search?q={marker}&limit=10",
            headers,
            None,
            timeout,
        )
        if status != 200:
            search_detail = f"status={status} attempt={attempt} (HTTP error - no retry)"
            break
        results = body if isinstance(body, list) else []
        found = marker in json.dumps(results, default=str)
        search_detail = f"status=200 results={len(results)} marker_found={found} attempt={attempt}"
        if found:
            search_ok = True
            break
        if attempt < search_attempts:
            time.sleep(search_delay)
    step("search", search_ok, search_detail)

    # 3. Cleanup: hard-delete the probe record; a GET after must 404.
    if record_id:
        status, _ = transport("DELETE", f"{base}/v1/memories/{record_id}?hard=true", headers, None, timeout)
        step("cleanup_delete", status == 200, f"status={status}")
        status, _ = transport("GET", f"{base}/v1/memories/{record_id}", headers, None, timeout)
        step("cleanup_get_after", status == 404, f"status={status}")
    else:
        step("cleanup", False, "no record id from capture - nothing to clean, probe already failed")

    log(f"MEMORA-SMOKE RESULT: {'PASS' if ok else 'FAIL'} marker={marker}")
    return ok


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Memora post-deploy memory-path smoke probe")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--agent", default=DEFAULT_AGENT)
    parser.add_argument("--key-var", default=DEFAULT_KEY_VAR)
    parser.add_argument("--env-file", action="append", type=Path, default=None,
                        help="env file to read the API key from (repeatable)")
    parser.add_argument("--timeout", type=float, default=60.0)
    parser.add_argument("--search-attempts", type=int, default=5)
    parser.add_argument("--search-delay", type=float, default=2.0)
    args = parser.parse_args(argv)

    env_files = args.env_file if args.env_file else list(DEFAULT_ENV_FILES)
    api_key, source = load_key(args.key_var, env_files)
    print(f"MEMORA-SMOKE keyload: var={args.key_var} found={bool(api_key)} source={source}")
    if not api_key:
        print("MEMORA-SMOKE RESULT: FAIL - no API key available for the probe identity")
        return 1
    try:
        passed = run_smoke(
            args.base_url,
            args.agent,
            api_key,
            timeout=args.timeout,
            search_attempts=args.search_attempts,
            search_delay=args.search_delay,
        )
    except Exception as exc:  # noqa: BLE001 - the exit code is the contract
        print(f"MEMORA-SMOKE RESULT: FAIL - probe error: {type(exc).__name__}: {exc}")
        return 1
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
