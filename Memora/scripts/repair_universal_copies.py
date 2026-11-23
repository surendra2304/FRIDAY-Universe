#!/usr/bin/env python3
"""Memora UNIVERSAL dual-copy repair CLI (TASK-MEM-021).

Re-signs UNIVERSAL dual copies whose HMAC provenance signature was
inherited from their original (pre-fix ``_make_universal_copy`` copied
the original's provenance verbatim, including a signature computed over
the original's id). Such copies fail verification, so search's Safety
Invariant 2 leg discards them for every actor — the MEM-019 lesson was
invisible to search while direct GET returned it. The repair re-signs
each stale copy under its own id and upserts its embedding, so it
becomes searchable without re-promotion. New copies are fixed at
creation time by the promotion code itself; this tool exists for the
already-created stale ones.

This is a CLI, not an API endpoint, on purpose: a store-wide repair
primitive does not belong on the network surface. Running it requires
host access plus Memora's environment — the break-glass boundary.

Safety gates, mirroring scripts/resign_provenance.py (TASK-MEM-010):

* Dry-run is the default and performs no writes; it reports the counts
  (already current / would re-sign / unverifiable / unsigned) so a
  repair is rehearsed before it is executed.
* Applying requires BOTH: --apply and MEMORA_REPAIR_UNIVERSAL_APPLY=1.
* The signing key is never an input: it must be the MEMORA_MASTER_KEY
  currently in force in Memora's environment (the tool refuses to run
  if the master is unset).
* Records whose content hash no longer matches their text (tampered)
  and records with no signature at all (unsigned) are never
  force-signed; they are reported by id and left untouched.

Usage (from the Memora directory, with the service venv; Memora stopped
or quiesced, exactly as for the MEM-010 one-off):

    python scripts/repair_universal_copies.py
    MEMORA_REPAIR_UNIVERSAL_APPLY=1 python scripts/repair_universal_copies.py --apply

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

from core.config import settings  # noqa: E402
from core.memory.promotion import MemoryPromotionService  # noqa: E402
from storage.relational.session import SessionLocal  # noqa: E402

TASK_ID = "TASK-MEM-021"
APPLY_ENV = "MEMORA_REPAIR_UNIVERSAL_APPLY"


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Memora UNIVERSAL dual-copy repair pass (TASK-MEM-021)"
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help=f"apply the repair (requires {APPLY_ENV}=1)",
    )
    parser.add_argument("--tenant", default=None, help="restrict to one tenant_id")
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
        master = settings.MEMORA_MASTER_KEY
        if not master:
            raise ValueError(
                "MEMORA_MASTER_KEY is not set in Memora's environment; refusing "
                "to re-sign — the current master key (break-glass) is the only "
                "authorized signing key."
            )
        if settings.get_memora_api_key() != master:
            raise ValueError(
                "settings.get_memora_api_key() does not resolve to "
                "MEMORA_MASTER_KEY; refusing to re-sign to a key that is not "
                "the master in force."
            )
    except Exception as exc:
        print(f"REFUSING TO RUN: {exc}", file=sys.stderr)
        return 1

    db = SessionLocal()
    try:
        report = MemoryPromotionService.repair_universal_copies(
            db,
            dry_run=not applying,
            tenant_id=args.tenant,
        )
        if applying:
            db.commit()
        else:
            db.rollback()
    finally:
        db.close()

    output = {
        "task": TASK_ID,
        "mode": "apply" if applying else "dry-run",
        **report,
    }
    print(json.dumps(output, indent=1, default=str))
    if report["unverifiable_ids"] or report["unsigned_ids"]:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
