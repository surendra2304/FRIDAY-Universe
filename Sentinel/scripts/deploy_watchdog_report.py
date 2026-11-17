#!/usr/bin/env python3
"""Per-server deploy-watchdog reporter (TASK-OBS-004).

Run this on a fleet server Sentinel does NOT run on (today: Server 1),
from a systemd timer or cron. It reads the server's own deployed HEAD
and tracked-tree cleanliness from its repo checkout and posts them to
Sentinel's deploy-watchdog ingress; Sentinel compares them against
origin/main in its single state store and alerts through the
operations alert path when divergence persists beyond the threshold.
The reporter is deliberately dumb: no state, no decisions — all logic
lives in ``sentinel.modules.operations.deploy_watchdog``.

Stdlib only, so it runs under the fleet's shared venv or any python3.

Example (Server 1, every 10 minutes):
    python3 deploy_watchdog_report.py \
        --sentinel-url http://10.0.0.120:8008 \
        --server server-1 \
        --checkout /opt/friday_universe

Exit codes: 0 = report accepted (any watchdog status), 1 = could not
read the local HEAD, 2 = report could not be delivered.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import urllib.request


def read_checkout_head(checkout: str) -> str | None:
    try:
        out = subprocess.run(
            ["git", "-C", checkout, "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    sha = (out.stdout or "").strip()
    return sha if out.returncode == 0 and len(sha) >= 7 else None


def read_checkout_branch(checkout: str) -> str | None:
    """Branch the checkout is on (TASK-OBS-005); None if detached/unreadable."""
    try:
        out = subprocess.run(
            ["git", "-C", checkout, "branch", "--show-current"],
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    name = (out.stdout or "").strip()
    return name if out.returncode == 0 and name else None


def read_checkout_tree_clean(checkout: str) -> bool | None:
    """Tracked-tree cleanliness (untracked runtime files don't count)."""
    try:
        out = subprocess.run(
            ["git", "-C", checkout, "status", "--porcelain"],
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if out.returncode != 0:
        return None
    for line in (out.stdout or "").splitlines():
        if line and not line.startswith("??"):
            return False
    return True


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sentinel-url", required=True, help="Base URL of the Sentinel API")
    parser.add_argument("--server", required=True, help="This server's watchdog name, e.g. server-1")
    parser.add_argument("--checkout", default="/opt/friday_universe", help="Repo checkout path")
    parser.add_argument("--timeout", type=float, default=30.0)
    args = parser.parse_args(argv)

    head = read_checkout_head(args.checkout)
    if not head:
        print(f"deploy-watchdog-report: cannot read HEAD of {args.checkout}", file=sys.stderr)
        return 1

    tree_clean = read_checkout_tree_clean(args.checkout)
    branch = read_checkout_branch(args.checkout)
    url = args.sentinel_url.rstrip("/") + "/operations/deploy-watchdog/report"
    payload = json.dumps(
        {
            "server": args.server,
            "deployed_head": head,
            "tree_clean": tree_clean,
            "branch": branch,
        }
    ).encode("utf-8")
    request = urllib.request.Request(
        url, data=payload, headers={"Content-Type": "application/json"}, method="POST"
    )
    try:
        with urllib.request.urlopen(request, timeout=args.timeout) as response:
            body = json.loads(response.read().decode("utf-8"))
    except Exception as e:  # delivery failure must be visible to the timer
        print(f"deploy-watchdog-report: POST {url} failed: {e}", file=sys.stderr)
        return 2
    print(
        f"deploy-watchdog-report: {args.server} head={head[:8]} "
        f"status={body.get('status')} main={str(body.get('main_head'))[:8]} "
        f"branch={branch}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
