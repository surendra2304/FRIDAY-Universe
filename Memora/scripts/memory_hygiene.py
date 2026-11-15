#!/usr/bin/env python3
"""Memora memory-hygiene operator CLI (TASK-MEM-004).

Scans the live memory store for exact duplicates, near duplicates and direct
contradictions, prints a JSON report, and — only when explicitly armed —
applies the reconciliation plan (losers are SUPERSEDED, never deleted;
provenance is preserved and annotated; every action is audit-logged).

Dry-run is the default and performs no writes. Applying requires BOTH:

    MEMORA_HYGIENE_APPLY=1  and  --apply

Near-duplicate actions additionally require --include-near.

Usage (from the Memora directory, with the service venv):

    python scripts/memory_hygiene.py                 # dry-run report
    python scripts/memory_hygiene.py --tenant default
    MEMORA_HYGIENE_APPLY=1 python scripts/memory_hygiene.py --apply
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.memory.hygiene import (  # noqa: E402
    TASK_ID,
    analyze,
    apply_actions,
    load_live_records,
)
from storage.relational.session import SessionLocal  # noqa: E402

APPLY_ENV = "MEMORA_HYGIENE_APPLY"


def main() -> int:
    parser = argparse.ArgumentParser(description="Memora dedup/contradiction hygiene pass")
    parser.add_argument("--apply", action="store_true", help="apply the plan (requires the env gate)")
    parser.add_argument("--include-near", action="store_true", help="also apply near-duplicate actions")
    parser.add_argument("--tenant", default=None, help="restrict to one tenant_id")
    parser.add_argument("--namespace", default=None, help="restrict to one namespace_id")
    parser.add_argument("--max-actions", type=int, default=None, help="cap applied actions")
    parser.add_argument("--task-id", default=TASK_ID, help="task tag written into provenance/audit")
    args = parser.parse_args()

    armed = os.environ.get(APPLY_ENV) == "1"
    applying = bool(args.apply and armed)
    if args.apply and not armed:
        print(
            f"REFUSING TO APPLY: --apply given but {APPLY_ENV}=1 is not set; "
            "running as dry-run instead.",
            file=sys.stderr,
        )

    db = SessionLocal()
    try:
        records = load_live_records(db, tenant_id=args.tenant, namespace_id=args.namespace)
        report = analyze(records)
        output = {"mode": "apply" if applying else "dry-run", **report.counts()}
        output["actions"] = [a.as_dict() for a in report.actions]
        if applying:
            actor_id = None
            try:
                from core.identity.service import IdentityService

                actor = IdentityService.get_agent_by_name(db, "memora", tenant_id=args.tenant or "default")
                actor_id = actor.id if actor else None
            except Exception:
                actor_id = None
            result = apply_actions(
                db,
                report.actions,
                actor_id=actor_id,
                task_id=args.task_id,
                include_near=args.include_near,
                max_actions=args.max_actions,
            )
            output["apply_result"] = {
                "applied": len(result["applied"]),
                "skipped": result["skipped"],
                "failed": result["failed"],
                "applied_actions": result["applied"],
            }
        print(json.dumps(output, indent=1, default=str))
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
