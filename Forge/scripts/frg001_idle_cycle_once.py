#!/usr/bin/env python3
"""TASK-FRG-001: run ONE Forge idle-experiment cycle, then exit.

The caged one-shot driver for the FRG-017 idle loop. The loop itself
lives in the Forge FastAPI lifespan (started only when
FORGE_IDLE_EXPERIMENTS is explicitly "on"); this driver runs exactly
one cycle through the same entry point
(``IdleExperimentLoop.start_if_enabled``) and prints the cycle report
as JSON, so a cycle's timestamps land in the experiment ledger and in
the operator's hands without keeping a second long-lived process.

Usage (live, on Server 1, under the cage unit — see
``Forge/app/deployment/forge-idle-loop-cage.service``)::

    FORGE_IDLE_EXPERIMENTS=on python scripts/frg001_idle_cycle_once.py

Usage (sandbox, no production DB, no Memora delivery)::

    FORGE_IDLE_EXPERIMENTS=on python scripts/frg001_idle_cycle_once.py --sandbox

Exit codes: 0 = a cycle ran (verdict in the JSON report);
1 = skipped (kill switch off inside the loop, host-load gate, Forge
busy, or daily cap — reason in the JSON report); 2 = the driver was
not explicitly enabled (FORGE_IDLE_EXPERIMENTS is not "on") or the
arguments are unusable. Activation is a coordinator step, never part
of a code change: the cage unit sets the flag; a human running this
by hand without it gets a refusal, not a cycle.

In sandbox mode the lesson writer is stubbed to "not delivered"
(the lesson still lands in the local lessons ledger as pending, for
the live path's flush_pending_lessons() to retry) and the task store
is empty (idle by construction). The golden battery still runs for
real: the generated project's own pytest suite executes in a
throwaway sandbox directory.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

# The script lives in Forge/scripts/; the Forge tree root (parent of
# scripts/) must be on sys.path for the `app.*` imports to resolve,
# wherever the driver is invoked from.
_FORGE_ROOT = Path(__file__).resolve().parent.parent
if str(_FORGE_ROOT) not in sys.path:
    sys.path.insert(0, str(_FORGE_ROOT))

from app.improvement.idle_loop import IdleExperimentLoop  # noqa: E402

UTC = timezone.utc


class _SandboxStore:
    """Empty task store: no assigned work, so the idle gate passes."""

    async def list_tasks(self, state=None, limit: int = 50, since_timestamp=None):
        return []


class _SandboxLessonWriter:
    """Lesson delivery stubbed as NOT delivered.

    The lesson text still lands in the loop's local lessons ledger
    (marked pending), so a later live run retries the Memora delivery
    via flush_pending_lessons(). Nothing is claimed as delivered that
    was not.
    """

    def deliver(self, content: str, metadata: dict, *, universal: bool) -> bool:
        return False


def _report(report, *, data_dir: Path, mode: str) -> dict:
    return {
        "task": "TASK-FRG-001",
        "mode": mode,
        "ts": datetime.now(UTC).isoformat(),
        "status": report.status,
        "reason": report.reason,
        "experiment_id": report.experiment_id,
        "spec_id": report.spec_id,
        "verdict": report.verdict,
        "champion_composite": report.champion_composite,
        "challenger_composite": report.challenger_composite,
        "data_dir": str(data_dir),
        "ledger": str(Path(data_dir) / "experiments.jsonl"),
    }


async def _run_live(data_dir: Path | None) -> tuple[int, dict]:
    from app.memory.db import db_manager
    from app.memory.state_store import StateStore

    await db_manager.init_db()
    loop = IdleExperimentLoop.start_if_enabled(
        StateStore(db_manager),
        data_dir=data_dir,
    )
    if loop is None:  # start_if_enabled already logged why
        return 2, {"task": "TASK-FRG-001", "mode": "live",
                   "status": "refused", "reason": "not_enabled"}
    report = await loop.run_one_cycle()
    out = _report(report, data_dir=loop.data_dir, mode="live")
    return (0 if report.status == "ran" else 1), out


async def _run_sandbox(data_dir: Path | None) -> tuple[int, dict]:
    if data_dir is None:
        data_dir = Path(tempfile.mkdtemp(prefix="frg001-sandbox-"))
    loop = IdleExperimentLoop(
        store=_SandboxStore(),
        data_dir=data_dir,
        lesson_writer=_SandboxLessonWriter(),
    )
    report = await loop.run_one_cycle()
    out = _report(report, data_dir=data_dir, mode="sandbox")
    out["lesson_delivery"] = "stubbed-sandbox (pending in local ledger)"
    return (0 if report.status == "ran" else 1), out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run one Forge idle-experiment cycle (TASK-FRG-001)."
    )
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=None,
        help="Loop data dir (experiments.jsonl lives here). Live default: "
             "the Forge settings data dir + /idle_experiments.",
    )
    parser.add_argument(
        "--sandbox",
        action="store_true",
        help="Sandbox mode: empty task store, stubbed lesson delivery, "
             "temp data dir unless --data-dir is given. No production "
             "DB, no Memora call.",
    )
    args = parser.parse_args(argv)

    if not IdleExperimentLoop.lifespan_enabled():
        print(
            json.dumps({
                "task": "TASK-FRG-001",
                "status": "refused",
                "reason": "FORGE_IDLE_EXPERIMENTS is not explicitly 'on' "
                          "(default off; activation is a coordinator step)",
            }),
            file=sys.stderr,
        )
        return 2

    if args.sandbox:
        code, out = asyncio.run(_run_sandbox(args.data_dir))
    else:
        code, out = asyncio.run(_run_live(args.data_dir))
    print(json.dumps(out, indent=2, default=str))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
