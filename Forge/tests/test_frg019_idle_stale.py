"""TASK-FRG-019: Forge idle gate ignores stale ACTIVE rows.

Forge's own record (2026-11-23, live Oracle StateStore) holds 6 ACTIVE
rows — 4 READY + 2 RUNNING — untouched for 206+ hours across a service
restart, while no new work has arrived since Nov 17. The pre-fix idle
gate (`any ACTIVE`) was therefore False forever and the idle experiment
loop could never start. The fix: an ACTIVE row counts as live work
only while it was updated within STALE_ACTIVE_AFTER_HOURS (24 h); older
rows are dead rows from a crashed or restarted worker. The gate only
decides whether Forge is idle — it never mutates a row — and a row with
no usable timestamp fails closed (counts as live work).
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from app.improvement.idle_loop import (
    STALE_ACTIVE_AFTER_HOURS,
    ArmScore,
    GoldenSpec,
    HostLoadSnapshot,
    IdleExperimentLoop,
)
from app.memory.models import TaskEntity, TaskState

UTC = timezone.utc
NOW = datetime(2026, 11, 23, 10, 32, tzinfo=UTC)


class FakeStore:
    """Minimal StateStore stand-in: the loop only calls list_tasks."""

    def __init__(self, tasks: list[TaskEntity]):
        self._tasks = tasks

    async def list_tasks(self, state=None, limit: int = 50, since_timestamp=None):
        return self._tasks[:limit]


class FakeBattery:
    """Scripted battery: champion fractions for the incumbent mutation,
    challenger fractions for everything else."""

    def __init__(self, champion: tuple[float, float, float], challenger: tuple[float, float, float]):
        self._champion = champion  # (test, manifest, compile) fractions
        self._challenger = challenger

    def run_arm(self, spec: GoldenSpec, manifest: list[str], mutation: str) -> ArmScore:
        tf, mf, cf = self._champion if mutation == "forge_default" else self._challenger
        return ArmScore(
            manifest=list(manifest),
            mutation=mutation,
            files_written=3,
            manifest_fraction=mf,
            compile_fraction=cf,
            test_fraction=tf,
            tests_passed=int(tf * 10),
            tests_failed=int((1 - tf) * 10),
        )


class FakeWriter:
    def __init__(self, ok: bool = True):
        self.ok = ok
        self.calls: list[dict] = []

    def deliver(self, content: str, metadata: dict, *, universal: bool) -> bool:
        self.calls.append(
            {"content": content, "metadata": metadata, "universal": universal}
        )
        return self.ok


def make_task(
    state: TaskState,
    age_hours: float = 0.0,
    error: str | None = None,
    goal: str = "build something",
) -> TaskEntity:
    ts = NOW - timedelta(hours=age_hours)
    return TaskEntity(
        goal=goal,
        workspace_path="/tmp/forge-idle-test",
        state=state,
        error_message=error,
        created_at=ts,
        updated_at=ts,
    )


def live_record_tasks() -> list[TaskEntity]:
    """The 6 stale ACTIVE rows from Forge's live record, 2026-11-23."""
    return [
        make_task(TaskState.READY, 212.6, goal="REL019 probe: plan a function that checks palindromes"),
        make_task(TaskState.READY, 212.5, goal="REL019 probe: plan a CSV parser"),
        make_task(TaskState.READY, 212.4, goal="REL019 probe: plan a rate limiter (via FRIDAY fleet client)"),
        make_task(TaskState.READY, 212.1, goal="REL019 recheck: plan a token bucket rate limiter"),
        make_task(TaskState.RUNNING, 206.1, goal="incident TEST_FAILURE"),
        make_task(TaskState.RUNNING, 206.0, goal="incident TEST_FAILURE"),
    ]


def make_loop(tmp_path: Path, tasks, battery=None, writer=None, **kwargs) -> IdleExperimentLoop:
    kwargs.setdefault(
        "load_probe",
        lambda: HostLoadSnapshot(
            load1=0.2, cpu_count=4, mem_available_fraction=0.9
        ),
    )
    return IdleExperimentLoop(
        store=FakeStore(tasks),
        data_dir=tmp_path / "idle",
        battery=battery,
        lesson_writer=writer,
        **kwargs,
    )


def make_idle_loop(tmp_path: Path, tasks) -> IdleExperimentLoop:
    """A loop for is_idle-only tests: no battery or writer needed."""
    return IdleExperimentLoop(
        store=FakeStore(tasks),
        data_dir=tmp_path / "idle",
    )


def read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


# ---------------------------------------------------------------------------
# The staleness bound itself
# ---------------------------------------------------------------------------


def test_stale_bound_is_24h():
    assert STALE_ACTIVE_AFTER_HOURS == 24.0


async def test_live_record_stale_rows_do_not_block_idle(tmp_path):
    loop = make_idle_loop(tmp_path, live_record_tasks())
    assert await loop.is_idle(now=NOW) is True


async def test_fresh_active_row_blocks_idle(tmp_path):
    loop = make_idle_loop(tmp_path, [make_task(TaskState.RUNNING, age_hours=1.0)])
    assert await loop.is_idle(now=NOW) is False


async def test_mixed_fresh_and_stale_row_blocks_idle(tmp_path):
    tasks = live_record_tasks() + [make_task(TaskState.READY, age_hours=0.5)]
    loop = make_idle_loop(tmp_path, tasks)
    assert await loop.is_idle(now=NOW) is False


async def test_boundary_around_24h(tmp_path):
    fresh = make_idle_loop(tmp_path, [make_task(TaskState.RUNNING, age_hours=23.0)])
    assert await fresh.is_idle(now=NOW) is False
    stale = make_idle_loop(tmp_path, [make_task(TaskState.RUNNING, age_hours=25.0)])
    assert await stale.is_idle(now=NOW) is True


async def test_updated_at_none_falls_back_to_created_at(tmp_path):
    old = make_task(TaskState.RUNNING, age_hours=30.0)
    old.updated_at = None
    loop = make_idle_loop(tmp_path, [old])
    assert await loop.is_idle(now=NOW) is True

    young = make_task(TaskState.RUNNING, age_hours=1.0)
    young.updated_at = None
    loop = make_idle_loop(tmp_path, [young])
    assert await loop.is_idle(now=NOW) is False


async def test_no_timestamp_fails_closed_as_live(tmp_path):
    task = make_task(TaskState.RUNNING, age_hours=30.0)
    task.updated_at = None
    task.created_at = None
    loop = make_idle_loop(tmp_path, [task])
    assert await loop.is_idle(now=NOW) is False


async def test_naive_timestamps_read_as_utc(tmp_path):
    task = make_task(TaskState.RUNNING, age_hours=30.0)
    task.updated_at = task.updated_at.replace(tzinfo=None)
    task.created_at = task.created_at.replace(tzinfo=None)
    loop = make_idle_loop(tmp_path, [task])
    assert await loop.is_idle(now=NOW) is True


async def test_terminal_states_never_block_idle(tmp_path):
    tasks = [
        make_task(TaskState.FAILED, age_hours=1.0, error="verification failed"),
        make_task(TaskState.COMPLETED, age_hours=1.0),
        make_task(TaskState.CANCELLED, age_hours=1.0),
    ]
    loop = make_idle_loop(tmp_path, tasks)
    assert await loop.is_idle(now=NOW) is True


# ---------------------------------------------------------------------------
# The loop actually starts past stale rows
# ---------------------------------------------------------------------------


async def test_cycle_runs_past_stale_rows(tmp_path):
    loop = make_loop(
        tmp_path,
        live_record_tasks(),
        FakeBattery((0.5, 1.0, 1.0), (1.0, 1.0, 1.0)),
        FakeWriter(),
    )
    report = await loop.run_one_cycle()
    assert report.status == "ran"
    assert report.verdict == "PROMOTE"
    assert report.spec_id == "cli_todo"  # no failures on record: least-tested spec
    ledger = read_jsonl(tmp_path / "idle" / "experiments.jsonl")
    assert len(ledger) == 1
    assert ledger[0]["verdict"] == "PROMOTE"


async def test_cycle_still_skips_on_fresh_active_row(tmp_path):
    loop = make_loop(
        tmp_path,
        [make_task(TaskState.RUNNING, age_hours=1.0)],
        FakeBattery((0.5, 1.0, 1.0), (1.0, 1.0, 1.0)),
        FakeWriter(),
    )
    report = await loop.run_one_cycle()
    assert report.status == "skipped"
    assert report.reason == "forge_busy"
    assert read_jsonl(tmp_path / "idle" / "experiments.jsonl") == []
