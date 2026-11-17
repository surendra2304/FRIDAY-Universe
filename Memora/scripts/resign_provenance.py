#!/usr/bin/env python3
"""Memora provenance re-signing operator CLI (TASK-MEM-010).

Re-signs every memory record whose HMAC provenance signature was made
under the previous master key so the store survives a master-key
rotation. Both read paths discard records whose signature fails
verification, so a rotation without this step silently empties recall —
the MEM-005 env pass (2026-11-17) had to do it with a one-off script
because no tool existed; this is the durable version.

This is a CLI, not an API endpoint, on purpose: a store-wide master-key
primitive does not belong on the network surface. Running it requires
host access plus Memora's environment — the break-glass boundary.

Safety gates, mirroring scripts/memory_hygiene.py:

* Dry-run is the default and performs no writes; it reports the counts
  (already current / would re-sign / unverifiable / unsigned) so a
  rotation is rehearsed before it is executed.
* Applying requires BOTH: --apply and MEMORA_RESIGN_APPLY=1.
* The NEW signing key is never an input: it must be the MEMORA_MASTER_KEY
  currently in force in Memora's environment (the tool refuses to run if
  the master is unset or is not the key settings resolve).
* The OLD key is read only from MEMORA_OLD_MASTER_KEY (environment, never
  argv, so it cannot land in shell history or a process list).
* Records whose signature verifies under NEITHER key — including
  content-tampered records — are never force-signed; they are reported
  by id and left untouched. Unsigned records are likewise reported and
  never signed.

Usage (from the Memora directory, with the service venv; Memora stopped
or quiesced, exactly as for the MEM-005 one-off):

    MEMORA_OLD_MASTER_KEY=<previous master> python scripts/resign_provenance.py
    MEMORA_OLD_MASTER_KEY=<previous master> MEMORA_RESIGN_APPLY=1 \
        python scripts/resign_provenance.py --apply

Exit codes: 0 = clean (nothing refused), 2 = completed but unverifiable
or unsigned records were found and left untouched, 1 = refused to run.
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.security.resign import (  # noqa: E402
    APPLY_ENV,
    OLD_KEY_ENV,
    TASK_ID,
    ResignRefused,
    resign_records,
    resolve_rotation_keys,
)
from storage.relational.session import SessionLocal  # noqa: E402


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Memora provenance re-signing pass for master-key rotation"
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help=f"apply the re-signing (requires {APPLY_ENV}=1)",
    )
    parser.add_argument("--tenant", default=None, help="restrict to one tenant_id")
    parser.add_argument(
        "--batch-size", type=int, default=100, help="records per commit batch"
    )
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        stream=sys.stderr,
    )

    armed = os.environ.get(APPLY_ENV) == "1"
    applying = bool(args.apply and armed)
    if args.apply and not armed:
        print(
            f"REFUSING TO APPLY: --apply given but {APPLY_ENV}=1 is not set; "
            "running as dry-run instead.",
            file=sys.stderr,
        )

    try:
        old_secret, new_secret = resolve_rotation_keys(os.environ.get(OLD_KEY_ENV))
    except ResignRefused as exc:
        print(f"REFUSING TO RUN: {exc}", file=sys.stderr)
        return 1

    db = SessionLocal()
    try:
        report = resign_records(
            db,
            old_secret,
            new_secret,
            dry_run=not applying,
            batch_size=args.batch_size,
            tenant_id=args.tenant,
        )
    except ResignRefused as exc:
        print(f"ABORTED: {exc}", file=sys.stderr)
        return 1
    finally:
        db.close()

    output = {
        "task": TASK_ID,
        "mode": "apply" if applying else "dry-run",
        **report.counts(),
        "unverifiable_ids": report.unverifiable_ids,
        "unsigned_ids": report.unsigned_ids,
    }
    print(json.dumps(output, indent=1, default=str))
    if report.unverifiable or report.unsigned:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
