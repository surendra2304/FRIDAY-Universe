#!/usr/bin/env python3
"""Read-only on-host deployment evidence; prints JSON, never writes a report.

Run on each VM with --server 1 or 2 and an optional trusted --expected-revision
(full commit SHA from GitHub). Does not fetch, checkout, read env/logs, or restart.
A cached origin/main comparison is explicitly NOT proof of current GitHub state.
HTTP health is evidence of reported health, not functional/integration verification.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import subprocess
import urllib.error
import urllib.request
from pathlib import Path

# Canonical deployment placement, not additional agents for daemons/voice/bridge.
PLACEMENT = {
    1: {"FRIDAY": 10000, "Inference": 8001, "Memora": 8002, "Stratex": 8003,
        "Futuris": 8004, "IntelX": 8005, "Forge": 8006},
    2: {"Cortex": 8009, "Sentinel": 8008, "VyralX": 8010},
}
SHA = re.compile(r"[0-9a-f]{40}\Z")
PROPERTIES = ("LoadState", "ActiveState", "SubState", "NRestarts", "MemoryCurrent", "MemoryMax")


def command(args: list[str], cwd: Path) -> str | None:
    """Do not emit subprocess output on failure: stderr may contain credentials."""
    try:
        result = subprocess.run(args, cwd=cwd, capture_output=True, text=True,
                                timeout=10, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return result.stdout.strip() if result.returncode == 0 else None


def git_snapshot(repo: Path, expected: str | None) -> dict:
    def git(*args):
        # Optional locks disabled: even index refresh should not write to shared work.
        return command(["git", "--no-optional-locks", *args], repo)

    head = git("rev-parse", "--verify", "HEAD^{commit}")
    cached = git("rev-parse", "--verify", "refs/remotes/origin/main^{commit}")
    status = git("status", "--porcelain=v1", "-z", "--untracked-files=normal")
    # -z avoids quoted/multiline filenames. Rename records carry a second path.
    counts = {"tracked_changes": 0, "untracked_entries": 0}
    if status is not None:
        entries = iter(status.split("\0"))
        for entry in entries:
            if len(entry) < 3:
                continue
            if entry[:2] == "??":
                counts["untracked_entries"] += 1
            else:
                counts["tracked_changes"] += 1
            if "R" in entry[:2] or "C" in entry[:2]:
                next(entries, None)
    return {
        "head": head if head and SHA.fullmatch(head) else None,
        "cached_origin_main": cached if cached and SHA.fullmatch(cached) else None,
        "cached_ref_is_remote_verification": False,
        "expected_revision": expected,
        "matches_expected": head == expected if head and expected else None,
        "matches_cached_origin_main": head == cached if head and cached else None,
        "worktree_observed": status is not None,
        "protected_local_work": any(counts.values()) if status is not None else None,
        **counts,
    }


def service_snapshot(name: str, repo: Path) -> dict:
    raw = command(["systemctl", "show", name + ".service",
                   "--property=" + ",".join(PROPERTIES)], repo)
    if raw is None:
        return {"observed": False, "active": None}
    fields = dict(line.split("=", 1) for line in raw.splitlines() if "=" in line)
    fields = {k: v for k, v in fields.items() if k in PROPERTIES}
    return {"observed": bool(fields),
            "active": fields.get("ActiveState") == "active" if fields else None,
            **fields}


def classify_health(code: int | None, body: object) -> dict:
    """A 200/HTML response or explicit degraded payload must not become healthy."""
    transport = code == 200
    reported = "unknown"
    if isinstance(body, dict):
        state = str(body.get("status", "")).strip().lower()
        if body.get("healthy") is False or body.get("ready") is False or state in {
            "degraded", "unhealthy", "error", "failed", "not_ready", "not_initialized", "down"}:
            reported = "unhealthy"
        elif state in {"ok", "healthy", "ready", "up", "operational", "running"} or body.get("healthy") is True:
            reported = "healthy"
    return {"http_status": code, "http_ok": transport, "reported_health": reported,
            "health_ok": transport and reported == "healthy",
            "functional_verified": False}


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None  # fixed loopback probes must never follow an external redirect


def health_snapshot(port: int) -> dict:
    code, body, error = None, None, None
    try:
        # Ignore ambient HTTP_PROXY: local evidence must come from this host.
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
        with opener.open(f"http://127.0.0.1:{port}/health", timeout=5) as response:
            code = response.status
            raw = response.read(65537)
        if len(raw) <= 65536:
            try:
                body = json.loads(raw)
            except (ValueError, UnicodeError):
                error = "invalid_json"
        else:
            error = "response_too_large"
    except urllib.error.HTTPError as exc:
        code, error = exc.code, "http_error"
    except Exception as exc:
        # No URL, response body, headers or raw exception text in audit artifacts.
        error = type(exc).__name__
    return {**classify_health(code, body), "error": error}


def audit(server: int, repo: Path, expected: str | None) -> dict:
    agents = {name: {"unit": service_snapshot(name, repo), "health": health_snapshot(port)}
              for name, port in PLACEMENT[server].items()}
    git = git_snapshot(repo, expected)
    runtime_ok = all(a["unit"]["active"] is True and a["health"]["health_ok"] for a in agents.values())
    return {"observed_at": dt.datetime.now(dt.timezone.utc).isoformat(), "server": server,
            "git": git, "agents": agents, "runtime_ok": runtime_ok,
            "checkout_revision_verified": git["matches_expected"] is True,
            "running_process_revision": "not_assessed",
            "production_ready": "not_assessed"}


def full_sha(value: str) -> str:
    if not SHA.fullmatch(value):
        raise argparse.ArgumentTypeError("expected a full lowercase 40-character commit SHA")
    return value


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--server", required=True, type=int, choices=(1, 2))
    parser.add_argument("--repo", type=Path, default=Path("/opt/friday_universe"))
    parser.add_argument("--expected-revision", type=full_sha)
    args = parser.parse_args(argv)
    report = audit(args.server, args.repo, args.expected_revision)
    print(json.dumps(report, indent=2))
    # Incomplete evidence is not success. Protected local work is informational,
    # not an invitation to clean it or a reason to call running services unhealthy.
    return 0 if report["runtime_ok"] and report["checkout_revision_verified"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
