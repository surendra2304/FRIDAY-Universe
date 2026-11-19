"""TASK-FRG-017 slice 2: lifespan wiring + review conditions C2 and C3.

The contract pinned here:

  * C2 — a cycle never starts on a loaded host: the 1-minute load
    average must be below LOAD_GATE_FRACTION of the CPU count AND at
    least MIN_MEM_AVAILABLE_FRACTION of memory must be available.
    Refusals are logged, return reason "host_load_gate", and fail
    closed (an unreadable load or memory reading refuses too). The
    gate is checked after the kill switch and before the idle gate —
    the order Stratex's self-experiment loop shipped.
  * C3 — a lesson counts as delivered ONLY when Memora confirmed
    acceptance: the writer delivers through the fabric's
    record_and_confirm_cloud(), retries unconfirmed attempts with
    exponential backoff, and leaves the lesson pending otherwise.
    Local fabric acceptance (record() returning, a SQLite row) never
    counts; a fabric with no confirmation path can never confirm.
  * Wiring — the FastAPI lifespan starts the loop only through
    start_if_enabled(): FORGE_IDLE_EXPERIMENTS must be explicitly
    "on". Unset/off/anything else = not started (default OFF); the
    flag itself is set nowhere in code — activation is a coordinator
    step.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

import pytest
from app.improvement.idle_loop import (
    LOAD_GATE_FRACTION,
    MIN_MEM_AVAILABLE_FRACTION,
    ArmScore,
    FabricLessonWriter,
    GoldenSpec,
    HostLoadSnapshot,
    IdleExperimentLoop,
    mem_available_fraction,
    read_host_load,
)
from app.memory.models import TaskEntity, TaskState

# ---------------------------------------------------------------------------
# Test doubles
# ---------------------------------------------------------------------------


class FakeStore:
    """Minimal StateStore stand-in: the loop only calls list_tasks."""

    def __init__(self, tasks: list[TaskEntity]):
        self._tasks = tasks

    async def list_tasks(self, state=None, limit: int = 50, since_timestamp=None):
        return self._tasks[:limit]


class FakeBattery:
    def __init__(self, champion=(0.5, 1.0, 1.0), challenger=(1.0, 1.0, 1.0)):
        self._champion = champion
        self._challenger = challenger
        self.calls: list[str] = []

    def run_arm(self, spec: GoldenSpec, manifest: list[str], mutation: str) -> ArmScore:
        self.calls.append(mutation)
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
        self.calls.append({"content": content, "metadata": metadata, "universal": universal})
        return self.ok


def make_task(state: TaskState, error: str | None = None) -> TaskEntity:
    return TaskEntity(
        goal="build something",
        workspace_path="/tmp/forge-idle-wiring-test",
        state=state,
        error_message=error,
    )


def calm_snapshot() -> HostLoadSnapshot:
    return HostLoadSnapshot(load1=0.2, cpu_count=4, mem_available_fraction=0.9)


def make_loop(tmp_path: Path, tasks, battery, writer, **kwargs) -> IdleExperimentLoop:
    kwargs.setdefault("load_probe", calm_snapshot)
    return IdleExperimentLoop(
        store=FakeStore(tasks),
        data_dir=tmp_path / "idle",
        battery=battery,
        lesson_writer=writer,
        **kwargs,
    )


def read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


# ---------------------------------------------------------------------------
# C2 — host-load gate
# ---------------------------------------------------------------------------


async def test_load_gate_refuses_high_load_and_logs_it(tmp_path, caplog):
    loop = make_loop(
        tmp_path,
        [],
        FakeBattery(),
        FakeWriter(),
        load_probe=lambda: HostLoadSnapshot(
            load1=3.9, cpu_count=4, mem_available_fraction=0.9
        ),
    )
    with caplog.at_level(logging.WARNING, logger="forge.improvement.idle_loop"):
        report = await loop.run_one_cycle()
    assert report.status == "skipped"
    assert report.reason == "host_load_gate"
    assert loop.battery.calls == []  # no experiment arm ever ran
    assert read_jsonl(tmp_path / "idle" / "experiments.jsonl") == []
    assert "host-load gate" in caplog.text
    assert "3.90" in caplog.text  # the measured load is in the refusal log


async def test_load_gate_refuses_low_available_memory(tmp_path):
    loop = make_loop(
        tmp_path,
        [],
        FakeBattery(),
        FakeWriter(),
        load_probe=lambda: HostLoadSnapshot(
            load1=0.2, cpu_count=4, mem_available_fraction=0.05
        ),
    )
    report = await loop.run_one_cycle()
    assert report.status == "skipped"
    assert report.reason == "host_load_gate"
    assert loop.battery.calls == []


async def test_load_gate_fails_closed_when_load_unreadable(tmp_path):
    loop = make_loop(
        tmp_path, [], FakeBattery(), FakeWriter(), load_probe=lambda: None
    )
    report = await loop.run_one_cycle()
    assert report.status == "skipped"
    assert report.reason == "host_load_gate"


async def test_load_gate_fails_closed_when_probe_raises(tmp_path):
    def exploding_probe():
        raise OSError("no /proc")

    loop = make_loop(
        tmp_path, [], FakeBattery(), FakeWriter(), load_probe=exploding_probe
    )
    report = await loop.run_one_cycle()
    assert report.status == "skipped"
    assert report.reason == "host_load_gate"


async def test_load_gate_fails_closed_when_memory_unreadable(tmp_path):
    loop = make_loop(
        tmp_path,
        [],
        FakeBattery(),
        FakeWriter(),
        load_probe=lambda: HostLoadSnapshot(
            load1=0.2, cpu_count=4, mem_available_fraction=None
        ),
    )
    report = await loop.run_one_cycle()
    assert report.status == "skipped"
    assert report.reason == "host_load_gate"


async def test_calm_host_lets_the_cycle_run(tmp_path):
    loop = make_loop(
        tmp_path,
        [make_task(TaskState.COMPLETED)],
        FakeBattery(),
        FakeWriter(),
    )
    report = await loop.run_one_cycle()
    assert report.status == "ran"
    assert report.verdict == "PROMOTE"


async def test_load_gate_is_checked_before_the_idle_gate(tmp_path):
    # Busy Forge on a loaded host: the load refusal wins (the gate
    # order Stratex's loop shipped — kill switch, load, work probe).
    loop = make_loop(
        tmp_path,
        [make_task(TaskState.RUNNING)],
        FakeBattery(),
        FakeWriter(),
        load_probe=lambda: HostLoadSnapshot(
            load1=3.9, cpu_count=4, mem_available_fraction=0.9
        ),
    )
    report = await loop.run_one_cycle()
    assert report.reason == "host_load_gate"


async def test_kill_switch_still_beats_the_load_gate(tmp_path, monkeypatch):
    monkeypatch.setenv("FORGE_IDLE_EXPERIMENTS", "off")
    loop = make_loop(
        tmp_path,
        [],
        FakeBattery(),
        FakeWriter(),
        load_probe=lambda: HostLoadSnapshot(
            load1=3.9, cpu_count=4, mem_available_fraction=0.9
        ),
    )
    report = await loop.run_one_cycle()
    assert report.reason == "kill_switch_off"


def test_snapshot_refusal_boundaries():
    at_load_gate = HostLoadSnapshot(
        load1=LOAD_GATE_FRACTION * 4, cpu_count=4, mem_available_fraction=0.9
    )
    assert at_load_gate.refusal_reason() is not None  # at the gate = refused
    just_below = HostLoadSnapshot(
        load1=LOAD_GATE_FRACTION * 4 - 0.01, cpu_count=4, mem_available_fraction=0.9
    )
    assert just_below.refusal_reason() is None
    at_mem_gate = HostLoadSnapshot(
        load1=0.1, cpu_count=4, mem_available_fraction=MIN_MEM_AVAILABLE_FRACTION
    )
    assert at_mem_gate.refusal_reason() is None  # at the floor = allowed
    below_mem_gate = HostLoadSnapshot(
        load1=0.1,
        cpu_count=4,
        mem_available_fraction=MIN_MEM_AVAILABLE_FRACTION - 0.01,
    )
    assert below_mem_gate.refusal_reason() is not None


def test_mem_available_fraction_parsing():
    text = (
        "MemTotal:        1000000 kB\n"
        "MemFree:          100000 kB\n"
        "MemAvailable:     250000 kB\n"
        "Buffers:           10000 kB\n"
    )
    assert mem_available_fraction(text) == 0.25
    assert mem_available_fraction("MemTotal:        1000000 kB\n") is None
    assert mem_available_fraction("MemAvailable:     250000 kB\n") is None
    assert mem_available_fraction("MemTotal:  bogus kB\nMemAvailable: 1 kB\n") is None
    assert mem_available_fraction("") is None


def test_read_host_load_returns_a_real_snapshot():
    if not Path("/proc/meminfo").exists():
        pytest.skip("no /proc/meminfo on this platform")
    snapshot = read_host_load()
    assert snapshot is not None
    assert snapshot.cpu_count >= 1
    assert snapshot.load1 >= 0.0
    assert snapshot.mem_available_fraction is not None
    assert 0.0 <= snapshot.mem_available_fraction <= 1.0


# ---------------------------------------------------------------------------
# C3 — Memora-confirmed lesson delivery
# ---------------------------------------------------------------------------


class ConfirmingFabric:
    """Fabric double whose Memora confirmation follows a script."""

    def __init__(self, script: list):
        self.script = list(script)
        self.calls: list[dict] = []

    def record_and_confirm_cloud(self, **kwargs):
        self.calls.append(kwargs)
        outcome = self.script.pop(0) if self.script else True
        if isinstance(outcome, Exception):
            raise outcome
        return object(), outcome


def make_writer(fabric, sleeps: list[float]) -> FabricLessonWriter:
    return FabricLessonWriter(
        fabric=fabric,
        max_attempts=3,
        backoff_seconds=1.0,
        sleeper=sleeps.append,
    )


def test_delivery_counts_only_memora_confirmation_with_backoff():
    sleeps: list[float] = []
    fabric = ConfirmingFabric([False, False, True])
    writer = make_writer(fabric, sleeps)
    assert writer.deliver("a lesson", {}, universal=False) is True
    assert len(fabric.calls) == 3
    assert sleeps == [1.0, 2.0]  # exponential backoff between attempts


def test_unconfirmed_delivery_returns_false_after_max_attempts():
    sleeps: list[float] = []
    fabric = ConfirmingFabric([False, False, False, True])
    writer = make_writer(fabric, sleeps)
    assert writer.deliver("a lesson", {}, universal=False) is False
    assert len(fabric.calls) == 3  # the 4th scripted answer is never reached
    assert sleeps == [1.0, 2.0]


def test_record_only_fabric_can_never_confirm_delivery():
    class RecordOnlyFabric:
        def __init__(self):
            self.record_calls = 0

        def record(self, **kwargs):
            self.record_calls += 1
            return object()

    fabric = RecordOnlyFabric()
    writer = make_writer(fabric, [])
    assert writer.deliver("a lesson", {}, universal=False) is False
    # Local acceptance is not even attempted as a delivery path: the
    # writer refuses to call record() and call it delivered (C3).
    assert fabric.record_calls == 0


def test_delivery_recovers_from_a_raising_attempt():
    sleeps: list[float] = []
    fabric = ConfirmingFabric([RuntimeError("memora unreachable"), True])
    writer = make_writer(fabric, sleeps)
    assert writer.deliver("a lesson", {}, universal=False) is True
    assert len(fabric.calls) == 2
    assert sleeps == [1.0]


def test_real_fabric_reports_the_dispatch_verdict():
    pytest.importorskip("mesh.memory_fabric")
    from mesh.memory_fabric import MemoryScope, UniversalMemoryFabric

    fabric = UniversalMemoryFabric(local_db_path=":memory:")
    fabric.record_context = lambda *a, **k: None  # isolate dispatch semantics

    fabric._dispatch_to_cloud = lambda entry: False
    entry, confirmed = fabric.record_and_confirm_cloud(
        owner_agent="FORGE",
        content_text="a lesson",
        scope=MemoryScope.AGENT,
        memory_type="procedural",
        source="forge_idle_experiment",
        importance=0.8,
        confidence=1.0,
        metadata={"experiment_id": "exp_x"},
    )
    assert confirmed is False  # Memora did not accept it
    assert entry.owner_agent == "FORGE"
    assert entry.namespace == "memora://forge/private"

    # record() keeps its historical contract: entry returned either way.
    assert fabric.record(owner_agent="FORGE", content_text="x") is not None

    fabric._dispatch_to_cloud = lambda entry: True
    _entry, confirmed = fabric.record_and_confirm_cloud(
        owner_agent="FORGE", content_text="a lesson", scope=MemoryScope.AGENT
    )
    assert confirmed is True


async def test_unconfirmed_lesson_stays_pending_then_flushes_on_confirmation(tmp_path):
    fabric = ConfirmingFabric([False])
    writer = FabricLessonWriter(
        fabric=fabric, max_attempts=1, backoff_seconds=0, sleeper=lambda s: None
    )
    loop = make_loop(
        tmp_path,
        [make_task(TaskState.COMPLETED)],
        FakeBattery(),
        writer,
    )
    report = await loop.run_one_cycle()
    assert report.status == "ran"
    lessons = read_jsonl(tmp_path / "idle" / "lessons.jsonl")
    assert lessons[0]["deliveries"]["private"] is False  # pending, not delivered

    fabric.script = [True]  # Memora confirms on the retry
    assert loop.flush_pending_lessons() == 1
    lessons = read_jsonl(tmp_path / "idle" / "lessons.jsonl")
    assert lessons[0]["deliveries"]["private"] is True


# ---------------------------------------------------------------------------
# Wiring — lifespan gate, default OFF
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "value,expected",
    [
        (None, False),  # unset: default OFF
        ("off", False),
        ("0", False),
        ("false", False),
        ("yes", False),  # only the explicit "on" arms the wiring
        ("on", True),
        ("ON", True),
        (" on ", True),
    ],
)
def test_lifespan_enabled_requires_explicit_on(monkeypatch, value, expected):
    if value is None:
        monkeypatch.delenv("FORGE_IDLE_EXPERIMENTS", raising=False)
    else:
        monkeypatch.setenv("FORGE_IDLE_EXPERIMENTS", value)
    assert IdleExperimentLoop.lifespan_enabled() is expected


def test_start_if_enabled_returns_none_by_default(monkeypatch, tmp_path):
    monkeypatch.delenv("FORGE_IDLE_EXPERIMENTS", raising=False)
    loop = IdleExperimentLoop.start_if_enabled(
        FakeStore([]), data_dir=tmp_path / "idle"
    )
    assert loop is None


def test_start_if_enabled_builds_a_loop_only_when_on(monkeypatch, tmp_path):
    monkeypatch.setenv("FORGE_IDLE_EXPERIMENTS", "on")
    loop = IdleExperimentLoop.start_if_enabled(
        FakeStore([]),
        data_dir=tmp_path / "idle",
        battery=FakeBattery(),
        lesson_writer=FakeWriter(),
        load_probe=calm_snapshot,
    )
    assert isinstance(loop, IdleExperimentLoop)
    assert loop.data_dir == tmp_path / "idle"


def test_main_lifespan_wires_the_loop_through_start_if_enabled():
    main_py = Path(__file__).resolve().parents[1] / "app" / "main.py"
    source = main_py.read_text(encoding="utf-8")
    assert "IdleExperimentLoop.start_if_enabled" in source
    assert "idle_loop_task = asyncio.create_task(idle_loop.run_forever())" in source
    assert "idle_loop_task.cancel()" in source
    # The flag is read, never set, by the wiring: activation stays a
    # coordinator step (no env assignment anywhere in the module).
    assert 'os.environ["FORGE_IDLE_EXPERIMENTS"]' not in source
    assert 'setenv("FORGE_IDLE_EXPERIMENTS"' not in source
