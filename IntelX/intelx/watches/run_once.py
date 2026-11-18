"""Run one standing-watch poll on demand (proofs and operations).

Usage:
    python -m intelx.watches.run_once [--watch ai_model_releases]
        [--state PATH] [--outbox PATH]
        [--max-alerts-per-poll N] [--baseline-max-age-hours H]
    python -m intelx.watches.run_once --domain platforms_policy
        [--state PATH] [--outbox PATH]

Prints the PollResult as JSON (a list of them with --domain, which polls
every watch declared in that domain — TASK-INT-013). State and outbox
default to ``./data/watches/`` (or INTELX_WATCH_STATE_PATH /
INTELX_WATCH_OUTBOX_PATH). TASK-INT-007.
"""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path

from intelx.watches.domains import DOMAINS, watches_in_domain
from intelx.watches.engine import WATCHES, WatchService, with_overrides


async def _main(args: argparse.Namespace) -> int:
    overrides: dict[str, object] = {}
    if args.max_alerts_per_poll is not None:
        overrides["max_alerts_per_poll"] = args.max_alerts_per_poll
    if args.baseline_max_age_hours is not None:
        overrides["baseline_max_age_hours"] = args.baseline_max_age_hours
    service = WatchService(
        state_path=Path(args.state) if args.state else None,
        outbox_path=Path(args.outbox) if args.outbox else None,
    )
    if args.domain is not None:
        results = []
        for watch in watches_in_domain(args.domain, WATCHES):
            if overrides:
                watch = with_overrides(watch, **overrides)
            results.append((await service.poll_once(watch)).to_dict())
        print(json.dumps(results, indent=2, ensure_ascii=False))
        return 0
    watch = WATCHES[args.watch]
    if overrides:
        watch = with_overrides(watch, **overrides)
    result = await service.poll_once(watch)
    print(json.dumps(result.to_dict(), indent=2, ensure_ascii=False))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Poll one IntelX standing watch once.")
    parser.add_argument("--watch", default="ai_model_releases", choices=sorted(WATCHES))
    parser.add_argument("--domain", default=None, choices=sorted(DOMAINS))
    parser.add_argument("--state", default=None)
    parser.add_argument("--outbox", default=None)
    parser.add_argument("--max-alerts-per-poll", type=int, default=None)
    parser.add_argument("--baseline-max-age-hours", type=int, default=None)
    return asyncio.run(_main(parser.parse_args()))


if __name__ == "__main__":
    raise SystemExit(main())
