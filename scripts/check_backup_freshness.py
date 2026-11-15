#!/usr/bin/env python3
"""TASK-SEN-009 — fleet backup freshness check (the "maintain a backup" tripwire).

Reads the backup root on a server and answers one question: *when did the
last COMPLETE backup land, and is that fresh enough?* Built to be consumed
by machines, not just humans:

* the ``backup-watchdog`` GitHub workflow runs it over SSH on a schedule
  offset from the backup itself and opens/updates the [BACKUP-ALERT]
  issue when it exits non-zero (a backup schedule that silently stops
  firing cannot alert on itself — this watchdog has its own schedule);
* Sentinel (or any poller) can run it on Server 1 and consume the
  one-line JSON: ``status``, ``age_hours``, ``last_success_at``,
  ``latest_attempt_at``, ``latest_attempt_complete``.

Exit codes: 0 = fresh, 1 = stale (a complete backup exists but is too
old), 2 = no complete backup exists at all.

A backup counts as complete when its manifest says so (``complete``
flag, TASK-SEN-009) or, for pre-SEN-009 manifests, when it recorded no
failed agents and a clean verify. This mirrors
``backup_completeness`` in backup_fleet_databases.py — keep the two in
sync.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path

DEFAULT_ROOT = "/var/backups/friday-universe"
DEFAULT_MAX_AGE_HOURS = 120.0  # two slots/week (Sun+Wed) -> alert after ~5 days


def manifest_completeness(manifest: dict) -> bool:
    if "complete" in manifest:
        return bool(manifest["complete"])
    verify = manifest.get("verify") or {}
    return not manifest.get("failed_agents") and verify.get("failed", 1) == 0


def _parse_ts(value: str | None) -> dt.datetime | None:
    if not value:
        return None
    try:
        return dt.datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(
            tzinfo=dt.timezone.utc)
    except ValueError:
        return None


def assess(root: Path, *, now: dt.datetime | None = None,
           max_age_hours: float = DEFAULT_MAX_AGE_HOURS) -> dict:
    """Build the freshness report for a backup root (pure, testable)."""
    now = now or dt.datetime.now(dt.timezone.utc)
    report: dict = {
        "root": str(root),
        "checked_at": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "status": "never",
        "last_success_at": None,
        "age_hours": None,
        "latest_attempt_at": None,
        "latest_attempt_complete": None,
        "complete_backups": 0,
    }
    if not root.is_dir():
        return report
    dirs = sorted([d for d in root.iterdir() if d.is_dir()], reverse=True)
    successes: list[dt.datetime] = []
    for d in dirs:
        manifest_path = d / "manifest.json"
        if not manifest_path.is_file():
            continue
        try:
            manifest = json.loads(manifest_path.read_text())
        except Exception:  # noqa: BLE001 — unreadable manifest: not evidence
            continue
        created = _parse_ts(manifest.get("created_at"))
        complete = manifest_completeness(manifest)
        if report["latest_attempt_at"] is None and created is not None:
            report["latest_attempt_at"] = manifest["created_at"]
            report["latest_attempt_complete"] = complete
        if complete and created is not None:
            successes.append(created)
    report["complete_backups"] = len(successes)
    if successes:
        last = max(successes)
        report["last_success_at"] = last.strftime("%Y-%m-%dT%H:%M:%SZ")
        report["age_hours"] = round((now - last).total_seconds() / 3600.0, 2)
        report["status"] = "stale" if report["age_hours"] > max_age_hours else "ok"
    report["max_age_hours"] = max_age_hours
    return report


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--root", default=DEFAULT_ROOT, help="backup root directory")
    ap.add_argument("--max-age-hours", type=float, default=DEFAULT_MAX_AGE_HOURS,
                    help="alert when the last complete backup is older than this")
    ap.add_argument("--json", action="store_true", help="print the JSON report only")
    args = ap.parse_args()

    report = assess(Path(args.root), max_age_hours=args.max_age_hours)
    exit_code = {"ok": 0, "stale": 1, "never": 2}[report["status"]]

    if args.json:
        print(json.dumps(report))
    else:
        print(f"[BACKUP-FRESHNESS] status={report['status']} "
              f"last_success={report['last_success_at']} age_hours={report['age_hours']} "
              f"latest_attempt={report['latest_attempt_at']} "
              f"latest_attempt_complete={report['latest_attempt_complete']} "
              f"complete_backups={report['complete_backups']} root={report['root']}")
        print(json.dumps(report))
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
