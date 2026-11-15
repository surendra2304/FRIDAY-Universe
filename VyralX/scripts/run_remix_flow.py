"""VyralX remix flow driver (TASK-VYR-004).

Builds shorts out of other people's videos — but only Creative Commons /
public-domain / owner-owned material, with a provenance record for every
source, an original commentary script, and a render that waits in the
review queue. This script never uploads anything.

    # see what reusable sources exist for a topic (provenance recorded)
    python scripts/run_remix_flow.py discover --query "stock market"

    # produce one remix from the first matching candidate in the registry
    python scripts/run_remix_flow.py produce --record-id <id> \
        --script-file scripts/remix_scripts/leverage.txt \
        --title "Money in 40 Seconds: Leverage" --lane finance_explainer

    # inspect the review queue
    python scripts/run_remix_flow.py queue

Policy: VyralX/docs/REMIX_POLICY.md. Lanes: finance_explainer (priority 1),
space_science (priority 2). Anime/gameplay compilations are excluded.
"""
from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path

from app.services.remix_flow import (
    discover_candidates,
    list_review_queue,
    load_provenance,
    produce_remix_short,
)

log = logging.getLogger("vyralx.run_remix_flow")


def _print(payload: object) -> None:
    print(json.dumps(payload, indent=2, ensure_ascii=False, default=str))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    discover = sub.add_parser("discover", help="find reusable sources for a topic")
    discover.add_argument("--query", required=True)
    discover.add_argument("--limit", type=int, default=5)
    discover.add_argument(
        "--sources",
        default="wikimedia_commons,internet_archive,nasa",
        help="comma-separated subset of wikimedia_commons,internet_archive,nasa",
    )

    produce = sub.add_parser("produce", help="remix one recorded candidate")
    produce.add_argument("--record-id", required=True)
    produce.add_argument("--script-file", type=Path, required=True)
    produce.add_argument("--title", required=True)
    produce.add_argument("--hook", default="")
    produce.add_argument("--lane", default="finance_explainer")
    produce.add_argument("--category", default="VIRAL")
    produce.add_argument(
        "--with-db",
        action="store_true",
        help="also persist rights/render rows + a pending_approval publish job",
    )

    sub.add_parser("queue", help="list the review queue")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")

    if args.command == "discover":
        candidates = discover_candidates(
            args.query,
            limit_per_source=args.limit,
            sources=[s.strip() for s in args.sources.split(",") if s.strip()],
        )
        _print([c.to_dict() for c in candidates])
        return 0

    if args.command == "queue":
        _print(list_review_queue())
        return 0

    if args.command == "produce":
        record = next(
            (r for r in load_provenance() if r.record_id == args.record_id), None
        )
        if record is None:
            parser.error(f"no provenance record {args.record_id!r} in the registry")
        script = args.script_file.read_text(encoding="utf-8").strip()
        db = None
        if args.with_db:
            from app.database import SessionLocal

            db = SessionLocal()
        try:
            result = produce_remix_short(
                record,
                script,
                title=args.title,
                hook=args.hook,
                lane=args.lane,
                category=args.category,
                db=db,
            )
        finally:
            if db is not None:
                db.close()
        _print(result)
        return 0 if result.get("status") in {"PENDING_REVIEW", "SKIPPED"} else 1

    return 2


if __name__ == "__main__":
    raise SystemExit(main())
