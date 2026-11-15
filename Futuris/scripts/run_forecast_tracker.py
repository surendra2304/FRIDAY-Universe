#!/usr/bin/env python3
"""TASK-FUT-006 live forecast-vs-actual tracker CLI.

Runs one scoring pass and/or prints the rolling calibration report from
the live ``forecast_scores`` store. Uses the production storage
configuration (``DATABASE_URL``), exactly like the Futuris service.

Usage (from ``Futuris/``):

    python3 scripts/run_forecast_tracker.py                 # report only
    python3 scripts/run_forecast_tracker.py --score         # score, then report
    python3 scripts/run_forecast_tracker.py --report-only --target trading:BTCUSDT:price_variance_24h
    python3 scripts/run_forecast_tracker.py --evidence-class live

The report is honest by construction: below the minimum sample it prints
``insufficient_data`` with null metrics rather than a verdict the data
cannot support (see ``futuris.services.forecast_tracker``).
"""

from __future__ import annotations

import argparse
import asyncio
import json

from futuris.services.forecast_tracker import ForecastTracker
from futuris.storage.db import async_session_factory


async def _main(args: argparse.Namespace) -> dict:
    async with async_session_factory() as session:
        tracker = ForecastTracker(session)
        out: dict = {}
        if args.score:
            out["scoring"] = await tracker.score_resolved()
        if args.score or not args.report_only:
            out["report"] = await tracker.calibration_report(
                target=args.target, evidence_class=args.evidence_class
            )
        return out


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--score",
        action="store_true",
        help="run one scoring pass over newly resolved forecasts first",
    )
    parser.add_argument(
        "--report-only",
        action="store_true",
        help="print the calibration report without scoring (report is the default)",
    )
    parser.add_argument("--target", default=None, help="restrict the report to one target")
    parser.add_argument(
        "--evidence-class",
        default=None,
        help="restrict the report to one evidence class (e.g. live)",
    )
    args = parser.parse_args()
    result = asyncio.run(_main(args))
    print(json.dumps(result, indent=2, default=str))


if __name__ == "__main__":
    main()
