#!/usr/bin/env python3
"""TASK-VOI-001 — Voice-loop preflight: verify everything BEFORE the owner test.

Run this on the machine that hosts the FRIDAY-Voice worker (Server 1) or on the
owner's laptop with the same .env loaded. It never prints secret values — only
their presence and derived facts (e.g. "LIVEKIT_API_KEY: present, 16 chars").

Checks (each PASS/FAIL/SKIP with evidence):
  1. env    — LIVEKIT_URL / LIVEKIT_API_KEY / LIVEKIT_API_SECRET present
  2. gemini — GOOGLE_API_KEY or GEMINI_API_KEY present for Gemini Live
  3. sdk    — livekit SDK importable
  4. token  — a real AccessToken JWT can be minted for a test room (10-min TTL)
  5. server — LIVEKIT_URL host resolves and accepts TCP (wss port 443/7880)
  6. frapi  — optional: the FRIDAY /api/livekit/token endpoint mints (needs URL)
  7. worker — the livekit_worker module imports cleanly (no runtime start)

Exit code 0 = every check PASS (SKIPs allowed); 1 = at least one FAIL.
Evidence lines are prefixed [PASS]/[FAIL]/[SKIP] for the runbook.
"""
from __future__ import annotations

import os
import socket
import sys
from datetime import timedelta
from pathlib import Path
from urllib.parse import urlsplit

FRIDAY_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(FRIDAY_ROOT / "src"))

RESULTS: list[tuple[str, str, str]] = []


def record(name: str, status: str, evidence: str) -> None:
    RESULTS.append((name, status, evidence))
    print(f"[{status}] {name}: {evidence}")


def check_env() -> bool:
    ok = True
    for var in ("LIVEKIT_URL", "LIVEKIT_API_KEY", "LIVEKIT_API_SECRET"):
        value = os.getenv(var, "").strip()
        if value:
            shown = value if var == "LIVEKIT_URL" else f"present, {len(value)} chars"
            record(f"env.{var}", "PASS", shown)
        else:
            record(f"env.{var}", "FAIL", "missing — set it in the FRIDAY .env")
            ok = False
    return ok


def check_gemini() -> bool:
    for var in ("GOOGLE_API_KEY", "GEMINI_API_KEY", "GOOGLE_GENAI_API_KEY"):
        if os.getenv(var, "").strip():
            record("gemini.key", "PASS", f"{var} present")
            return True
    record("gemini.key", "FAIL", "no GOOGLE/GEMINI API key found — Gemini Live cannot run")
    return False


def check_sdk() -> bool:
    try:
        from livekit import api  # noqa: F401
        import livekit.agents  # noqa: F401
        record("sdk.import", "PASS", "livekit + livekit.agents import cleanly")
        return True
    except Exception as exc:  # noqa: BLE001
        record("sdk.import", "FAIL", f"{type(exc).__name__}: {exc}")
        return False


def check_token() -> bool:
    key = os.getenv("LIVEKIT_API_KEY", "").strip()
    secret = os.getenv("LIVEKIT_API_SECRET", "").strip()
    if not key or not secret:
        record("token.mint", "SKIP", "no credentials to mint with")
        return True
    try:
        from livekit import api

        token = (
            api.AccessToken(key, secret)
            .with_identity("preflight-probe")
            .with_grants(api.VideoGrants(room_join=True, room="preflight-room"))
            .with_ttl(timedelta(minutes=10))
            .to_jwt()
        )
        if isinstance(token, bytes):
            token = token.decode()
        parts = token.split(".")
        record("token.mint", "PASS" if len(parts) == 3 else "FAIL",
               f"JWT minted: 3 segments, {len(token)} chars, header alg present: {parts[0][:8] != ''}")
        return len(parts) == 3
    except Exception as exc:  # noqa: BLE001
        record("token.mint", "FAIL", f"{type(exc).__name__}: {exc}")
        return False


def check_server() -> bool:
    url = os.getenv("LIVEKIT_URL", "").strip()
    if not url:
        record("server.reachable", "SKIP", "LIVEKIT_URL missing")
        return True
    try:
        parsed = urlsplit(url)
        host = parsed.hostname or ""
        port = parsed.port or (443 if parsed.scheme == "wss" else 80)
        ip = socket.gethostbyname(host)
        with socket.create_connection((ip, port), timeout=10):
            record("server.reachable", "PASS",
                   f"{host} resolves to {ip} and accepts TCP on {port} ({parsed.scheme})")
            return True
    except Exception as exc:  # noqa: BLE001
        record("server.reachable", "FAIL", f"{type(exc).__name__}: {exc}")
        return False


def check_friday_api() -> bool:
    """Optional: probe the local FRIDAY token endpoint (Server 1 hosts both)."""
    base = os.getenv("FRIDAY_API_BASE", "http://127.0.0.1:10000")
    url = f"{base}/api/livekit/token?room=preflight-room&identity=preflight-probe"
    try:
        import urllib.error
        import urllib.request

        req = urllib.request.Request(url, headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            body = resp.read()
            record("friday.token_endpoint", "PASS",
                   f"HTTP {resp.status}, {len(body)} bytes — dashboard voice can mint")
            return True
    except urllib.error.HTTPError as exc:
        # 401/403 = endpoint healthy and correctly key-gated (keyless preflight).
        if exc.code in (401, 403):
            record("friday.token_endpoint", "PASS",
                   f"HTTP {exc.code} — endpoint live and correctly requires the owner key")
            return True
        record("friday.token_endpoint", "FAIL", f"HTTP {exc.code}")
        return False
    except Exception as exc:  # noqa: BLE001
        record("friday.token_endpoint", "FAIL", f"{type(exc).__name__}: {exc}")
        return False


def check_worker_import() -> bool:
    """Import the worker module WITHOUT starting it (module-level preload only)."""
    try:
        import importlib.util

        spec = importlib.util.spec_from_file_location(
            "friday_voice_worker_probe",
            FRIDAY_ROOT / "src" / "friday" / "voice" / "livekit_worker.py",
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        model = module._voice_model()
        voice = module._voice_name()
        record("worker.import", "PASS",
               f"livekit_worker imports cleanly; model={model}, voice={voice}")
        return True
    except Exception as exc:  # noqa: BLE001
        record("worker.import", "FAIL", f"{type(exc).__name__}: {exc}")
        return False


def main() -> int:
    print("=" * 66)
    print("FRIDAY VOICE PREFLIGHT — TASK-VOI-001 (no secrets are printed)")
    print("=" * 66)
    ok = all([
        check_env(),
        check_gemini(),
        check_sdk(),
        check_token(),
        check_server(),
        check_friday_api(),
        check_worker_import(),
    ])
    fails = [name for name, status, _ in RESULTS if status == "FAIL"]
    print("-" * 66)
    print(f"{len(RESULTS) - len(fails)}/{len(RESULTS)} checks passed"
          + (f"; FAILED: {', '.join(fails)}" if fails else " — voice loop is READY for the owner test"))
    return 0 if not fails else 1


if __name__ == "__main__":
    sys.exit(main())
