#!/usr/bin/env python3
"""TASK-FUT-011 — mark self-graded BacktestEngine outcomes. Never rewrite them.

Background
----------
TASK-FUT-010 proved that Futuris's legacy ``BacktestEngine`` substituted the
forecast AS the actual observation whenever the real observation was missing
at a forecast's expiry, and persisted the fabricated value as a real
``Outcome`` row under ``resolution_rule_version="backtest:v1.0"`` (the engine
fix is PR #362: a missing actual now leaves the origin UNSCORED and persists
nothing). This script is the remediation for any rows the pre-fix engine
already wrote.

Coordinator decision (TASK-FUT-011, RD-010 precedent): the rows are MARKED,
never deleted and never silently rewritten. ``observed_value`` is evidence —
including evidence of the fabrication — and stays exactly as written.

The mark
--------
The outcomes schema has exactly one non-destructive annotation field:
``ambiguity_note`` (Text, nullable, surfaced verbatim in API responses).
Marking appends a fixed marker to that note (preserving any existing text);
it never touches ``observed_value``, ``event_occurred``, or any other column.

The signature
-------------
The pre-fix write path persisted ``observed_value = round(actual, 2)`` where
a missing observation made ``actual := forecast.prediction``. A row is
self-graded iff::

    resolution_rule_version == "backtest:v1.0"
    AND observed_value IS NOT NULL
    AND observed_value == round(forecast.prediction, 2)   (exact float equality)

Safety contract
---------------
* Dry-run is the default: it performs SELECTs only and prints the exact set
  it would mark. ``--apply`` is required for any write.
* The row set is ALWAYS re-derived live from the signature at run time; no
  stale id list is ever trusted. The verified census is baked in below only
  as a comparison baseline — drift between the baseline and the live set is
  printed loudly, and ``--expected-count N`` makes the script abort on drift.
* Idempotent: rows already carrying the marker are skipped, in Python and in
  the UPDATE's WHERE clause.
* Post-apply verification re-reads every marked row and asserts the marker is
  present AND ``observed_value`` is byte-identical to the pre-apply snapshot.

Verified census baseline (2026-11-15, production, direct SELECT via the
deployed app's own session factory): total outcomes = 0, backtest:v1.0
rows = 0, self-graded rows = 0. The production outcomes table is empty —
the nightly job currently dies on the missing statsforecast dependency
before it can persist anything (journal, 2026-11-15 02:01:27 IST) — so
today this script is a standing guard for the window between a
statsforecast provisioning and the PR #362 deploy, not a cleanup of
existing rows.

Usage (on Server 1, from the Futuris checkout):
    PYTHONPATH=/opt/friday_universe/Futuris \
      /opt/friday_universe/venv/bin/python \
      Futuris/scripts/annotate_self_graded_outcomes.py [--apply] [--expected-count N]
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from typing import Any, Iterable, Mapping

MARKER = (
    "TAINT[TASK-FUT-011]: ground_truth=fabricated_self_grade — this outcome's "
    "observed_value is the forecast's own prediction, persisted by the pre-fix "
    "BacktestEngine when no observation existed at expiry (TASK-FUT-010). "
    "Marked, not altered: exclude this row from calibration/accuracy figures."
)
SIGNATURE_VERSION = "backtest:v1.0"

# Verified production census, 2026-11-15 (TASK-FUT-011): the outcomes table
# was EMPTY. Baseline for drift reporting only — never used as the row set.
VERIFIED_CENSUS_DATE = "2026-11-15"
VERIFIED_CENSUS_TAINTED_IDS: tuple[str, ...] = ()


# ---------------------------------------------------------------------------
# Pure classification / marking logic (unit-tested, no DB required)
# ---------------------------------------------------------------------------

def is_self_graded(observed_value: Any, prediction: Any, version: Any) -> bool:
    """True iff a row carries the exact pre-fix substitution signature."""
    if version != SIGNATURE_VERSION:
        return False
    if observed_value is None or prediction is None:
        return False
    try:
        return float(observed_value) == round(float(prediction), 2)
    except (TypeError, ValueError):
        return False


def select_tainted(rows: Iterable[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
    """Filter joined (outcome, forecast) row dicts down to the self-graded set."""
    return [
        r
        for r in rows
        if is_self_graded(r.get("observed_value"), r.get("prediction"),
                          r.get("resolution_rule_version"))
    ]


def apply_marker(existing_note: str | None, marker: str = MARKER) -> str:
    """Append the taint marker to an ambiguity_note, idempotently.

    Any existing note text is preserved verbatim; a row already carrying the
    marker is returned unchanged.
    """
    if existing_note and marker in existing_note:
        return existing_note
    if existing_note:
        return existing_note.rstrip() + " | " + marker
    return marker


# ---------------------------------------------------------------------------
# Database pass (imports are local so the pure logic above stays importable
# without the futuris package or a database configuration)
# ---------------------------------------------------------------------------

async def _fetch_joined_rows(session: Any) -> list[dict[str, Any]]:
    from sqlalchemy import text

    rows = (
        await session.execute(
            text(
                "SELECT o.outcome_id, o.observed_value, o.ambiguity_note, "
                "o.resolution_rule_version, f.prediction "
                "FROM outcomes o JOIN forecasts f "
                "ON f.forecast_id = o.forecast_id "
                "WHERE o.resolution_rule_version = :version "
                "ORDER BY o.resolved_at ASC"
            ),
            {"version": SIGNATURE_VERSION},
        )
    ).mappings().all()
    return [dict(r) for r in rows]


async def run(apply: bool, expected_count: int | None) -> int:
    from sqlalchemy import text

    from futuris.storage.db import async_session_factory

    async with async_session_factory() as session:
        joined = await _fetch_joined_rows(session)
        tainted = select_tainted(joined)
        tainted_ids = [str(r["outcome_id"]) for r in tainted]

        print(f"backtest rows under signature version {SIGNATURE_VERSION}: {len(joined)}")
        print(f"self-graded rows (live signature): {len(tainted)}")
        print(
            f"verified census baseline ({VERIFIED_CENSUS_DATE}): "
            f"{len(VERIFIED_CENSUS_TAINTED_IDS)} rows"
        )
        if set(tainted_ids) != set(VERIFIED_CENSUS_TAINTED_IDS):
            print(
                "DRIFT: live self-graded set differs from the verified census "
                "baseline — the rows below are the live set and are the ones "
                "this run would mark.",
                file=sys.stderr,
            )
        for r in tainted:
            print(f"  outcome_id={r['outcome_id']} observed_value={r['observed_value']}")

        if expected_count is not None and len(tainted) != expected_count:
            print(
                f"ABORT: --expected-count {expected_count} != live count "
                f"{len(tainted)}; nothing written.",
                file=sys.stderr,
            )
            await session.rollback()
            return 2

        if not apply:
            print("DRY-RUN: no writes performed. Re-run with --apply to mark.")
            await session.rollback()
            return 0

        if not tainted:
            print("APPLY: nothing to mark; no writes performed.")
            await session.rollback()
            return 0

        before = {str(r["outcome_id"]): r["observed_value"] for r in tainted}
        marked = 0
        for r in tainted:
            new_note = apply_marker(r.get("ambiguity_note"))
            if new_note == r.get("ambiguity_note"):
                continue  # already marked — idempotent skip
            result = await session.execute(
                text(
                    "UPDATE outcomes SET ambiguity_note = :note "
                    "WHERE outcome_id = :oid AND (ambiguity_note IS NULL "
                    "OR ambiguity_note NOT LIKE '%TAINT[TASK-FUT-011]%')"
                ),
                {"note": new_note, "oid": r["outcome_id"]},
            )
            marked += result.rowcount or 0
        await session.commit()
        print(f"APPLY: marked {marked} row(s).")

        # Post-apply verification: marker present, observed_value untouched.
        joined_after = await _fetch_joined_rows(session)
        after = {str(r["outcome_id"]): r for r in joined_after}
        failures = []
        for oid, obs_before in before.items():
            row = after.get(oid)
            if row is None:
                failures.append(f"{oid}: row missing after apply")
            elif MARKER not in (row.get("ambiguity_note") or ""):
                failures.append(f"{oid}: marker absent after apply")
            elif float(row["observed_value"]) != float(obs_before):
                failures.append(f"{oid}: observed_value CHANGED — must never happen")
        if failures:
            for f in failures:
                print(f"VERIFY-FAIL: {f}", file=sys.stderr)
            return 3
        print(f"VERIFY: {len(before)} row(s) marked, observed_value unchanged on all.")
        return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--apply",
        action="store_true",
        help="actually write the markers (default is a read-only dry-run)",
    )
    parser.add_argument(
        "--expected-count",
        type=int,
        default=None,
        help="abort if the live self-graded count differs from this number",
    )
    args = parser.parse_args(argv)
    return asyncio.run(run(apply=args.apply, expected_count=args.expected_count))


if __name__ == "__main__":
    raise SystemExit(main())
