"""TASK-FRG-017: Forge idle experiment loop.

The loop's contract, pinned here:

  * it never runs while Forge has assigned work (idle gate) and never
    runs with the kill switch off;
  * hypotheses come from Forge's own failure clusters, in the same
    taxonomy as app.improvement.self_improve;
  * a challenger is promoted only by the pre-declared bar (composite
    margin AND no generated-test regression) — never by a prettier
    story;
  * every ran cycle lands in the experiment ledger with its scores,
    and its lesson is delivered as a procedural-type memory: PROMOTE
    lessons to Forge's private section only, DISCARD (failed
    experiment) lessons privately AND to the universal section
    (owner's standing rule R);
  * a failed Memora delivery stays pending in the local lessons ledger
    and is retried, never silently dropped;
  * the real golden battery, run on the real deterministic builder,
    produces a complete, passing build for the CLI golden shape.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.improvement.idle_loop import (
    SPECS_BY_ID,
    ArmScore,
    FabricLessonWriter,
    GoldenBattery,
    GoldenSpec,
    IdleExperimentLoop,
    challenger_mutations,
    champion_manifest,
    cluster_of,
    form_hypothesis,
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
    """Scripted battery: champion fractions for the incumbent mutation,
    challenger fractions for everything else."""

    def __init__(self, champion: tuple[float, float, float], challenger: tuple[float, float, float]):
        self._champion = champion  # (test, manifest, compile) fractions
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
        self.calls.append(
            {"content": content, "metadata": metadata, "universal": universal}
        )
        return self.ok


def make_task(state: TaskState, error: str | None = None, goal: str = "build something") -> TaskEntity:
    return TaskEntity(
        goal=goal,
        workspace_path="/tmp/forge-idle-test",
        state=state,
        error_message=error,
    )


def read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def make_loop(tmp_path: Path, tasks, battery, writer, **kwargs) -> IdleExperimentLoop:
    return IdleExperimentLoop(
        store=FakeStore(tasks),
        data_dir=tmp_path / "idle",
        battery=battery,
        lesson_writer=writer,
        **kwargs,
    )


# ---------------------------------------------------------------------------
# Gates
# ---------------------------------------------------------------------------


async def test_kill_switch_skips_cycle(tmp_path, monkeypatch):
    monkeypatch.setenv("FORGE_IDLE_EXPERIMENTS", "off")
    loop = make_loop(tmp_path, [], FakeBattery((1, 1, 1), (1, 1, 1)), FakeWriter())
    report = await loop.run_one_cycle()
    assert report.status == "skipped"
    assert report.reason == "kill_switch_off"
    assert read_jsonl(tmp_path / "idle" / "experiments.jsonl") == []


async def test_busy_forge_skips_cycle(tmp_path):
    tasks = [make_task(TaskState.RUNNING)]
    loop = make_loop(tmp_path, tasks, FakeBattery((1, 1, 1), (1, 1, 1)), FakeWriter())
    report = await loop.run_one_cycle()
    assert report.status == "skipped"
    assert report.reason == "forge_busy"


async def test_daily_cap_stops_second_cycle(tmp_path):
    tasks = [make_task(TaskState.COMPLETED)]
    loop = make_loop(
        tmp_path,
        tasks,
        FakeBattery((0.5, 1.0, 1.0), (1.0, 1.0, 1.0)),
        FakeWriter(),
        daily_cap=1,
    )
    first = await loop.run_one_cycle()
    assert first.status == "ran"
    second = await loop.run_one_cycle()
    assert second.status == "skipped"
    assert second.reason == "daily_cap_reached"


# ---------------------------------------------------------------------------
# Hypothesis formation
# ---------------------------------------------------------------------------


def test_cluster_taxonomy_matches_self_improve():
    assert cluster_of("ModuleNotFoundError: no module named x") == "missing_dependencies"
    assert cluster_of("SyntaxError: invalid syntax") == "syntax_errors"
    assert cluster_of("Verification failed: assert 1 == 2") == "verification_failures"
    assert cluster_of("fallback stub written") == "fallback_stub_issues"
    assert cluster_of("security scan blocked the build") == "security_violations"
    assert cluster_of("something else entirely") == "runtime_failures"
    assert cluster_of(None) == "runtime_failures"


def test_hypothesis_comes_from_dominant_failure_cluster():
    tasks = [
        make_task(TaskState.FAILED, "Verification failed: assert x"),
        make_task(TaskState.FAILED, "verification battery: check failed"),
        make_task(TaskState.FAILED, "SyntaxError somewhere"),
        make_task(TaskState.COMPLETED),
    ]
    hyp = form_hypothesis(tasks, {})
    assert hyp.cluster == "verification_failures"
    assert hyp.spec_id == "cli_todo"
    assert "verification_failures" in hyp.statement


def test_hypothesis_without_failures_probes_least_tested_spec():
    tasks = [make_task(TaskState.COMPLETED)]
    hyp = form_hypothesis(tasks, {"cli_todo": 3, "api_items": 1})
    assert hyp.cluster is None
    assert hyp.spec_id in {"library_roman", "script_textstats"}


def test_no_challenger_when_manifest_has_no_mutable_difference():
    spec = GoldenSpec(id="nonsense", goal="Zqx wobble frobnicate the gizmo")
    assert challenger_mutations(spec, ["main.py"]) == []


# ---------------------------------------------------------------------------
# Verdicts, champion registry, lessons
# ---------------------------------------------------------------------------


async def test_promote_updates_champion_and_lesson_stays_private(tmp_path):
    tasks = [make_task(TaskState.COMPLETED)]
    writer = FakeWriter()
    loop = make_loop(
        tmp_path, tasks, FakeBattery((0.5, 1.0, 1.0), (1.0, 1.0, 1.0)), writer
    )
    report = await loop.run_one_cycle()
    assert report.status == "ran"
    assert report.verdict == "PROMOTE"
    assert report.champion_composite == 75.0
    assert report.challenger_composite == 100.0

    champions = json.loads((tmp_path / "idle" / "champions.json").read_text())
    entry = champions[report.spec_id]
    assert entry["mutation"] != "forge_default"
    assert entry["composite"] == 100.0
    assert entry["experiment_id"] == report.experiment_id

    ledger = read_jsonl(tmp_path / "idle" / "experiments.jsonl")
    assert len(ledger) == 1
    assert ledger[0]["verdict"] == "PROMOTE"
    assert ledger[0]["hypothesis"]["bar"]  # the bar was declared in advance
    assert ledger[0]["champion"]["composite"] == 75.0
    assert ledger[0]["challenger"]["composite"] == 100.0

    # PROMOTE lesson: private section only, no universal copy.
    assert len(writer.calls) == 1
    assert writer.calls[0]["universal"] is False
    assert "PROMOTE" in writer.calls[0]["content"]
    lessons = read_jsonl(tmp_path / "idle" / "lessons.jsonl")
    assert lessons[0]["deliveries"] == {"private": True, "universal": None}


async def test_discard_keeps_champion_and_lesson_goes_universal(tmp_path):
    tasks = [make_task(TaskState.COMPLETED)]
    writer = FakeWriter()
    loop = make_loop(
        tmp_path, tasks, FakeBattery((0.5, 1.0, 1.0), (0.4, 1.0, 1.0)), writer
    )
    report = await loop.run_one_cycle()
    assert report.status == "ran"
    assert report.verdict == "DISCARD"
    assert not (tmp_path / "idle" / "champions.json").exists()

    # Failed experiment: private lesson AND a universal copy (rule R).
    assert len(writer.calls) == 2
    assert writer.calls[0]["universal"] is False
    assert writer.calls[1]["universal"] is True
    assert "DISCARD" in writer.calls[0]["content"]
    lessons = read_jsonl(tmp_path / "idle" / "lessons.jsonl")
    assert lessons[0]["deliveries"] == {"private": True, "universal": True}


async def test_test_regression_blocks_promotion_despite_higher_composite(tmp_path):
    tasks = [make_task(TaskState.COMPLETED)]
    loop = make_loop(
        tmp_path,
        tasks,
        # champion: tests perfect, manifest empty -> 70.0
        # challenger: composite 95.0 but generated tests regressed
        FakeBattery((1.0, 0.0, 1.0), (0.9, 1.0, 1.0)),
        FakeWriter(),
    )
    report = await loop.run_one_cycle()
    assert report.verdict == "DISCARD"
    assert "regressed" in report.reason
    assert not (tmp_path / "idle" / "champions.json").exists()


async def test_failed_delivery_stays_pending_and_is_retried(tmp_path):
    tasks = [make_task(TaskState.COMPLETED)]
    writer = FakeWriter(ok=False)
    loop = make_loop(
        tmp_path, tasks, FakeBattery((0.5, 1.0, 1.0), (1.0, 1.0, 1.0)), writer
    )
    report = await loop.run_one_cycle()
    assert report.status == "ran"
    lessons = read_jsonl(tmp_path / "idle" / "lessons.jsonl")
    assert lessons[0]["deliveries"]["private"] is False

    writer.ok = True
    assert loop.flush_pending_lessons() == 1
    lessons = read_jsonl(tmp_path / "idle" / "lessons.jsonl")
    assert lessons[0]["deliveries"]["private"] is True


# ---------------------------------------------------------------------------
# Lesson writer — the real fabric call shape
# ---------------------------------------------------------------------------


def test_fabric_writer_writes_procedural_type_to_the_right_sections():
    pytest.importorskip("mesh.memory_fabric")
    from mesh.memory_fabric import MemoryScope

    captured: list[dict] = []

    class FakeFabric:
        def record(self, **kwargs):
            captured.append(kwargs)

    writer = FabricLessonWriter(fabric=FakeFabric())
    assert writer.deliver("a lesson", {"experiment_id": "exp_x"}, universal=False) is True
    assert writer.deliver("a lesson", {"experiment_id": "exp_x"}, universal=True) is True

    private_call, universal_call = captured
    assert private_call["owner_agent"] == "FORGE"
    assert private_call["memory_type"] == "procedural"
    assert private_call["scope"] == MemoryScope.AGENT  # Forge's private section
    assert universal_call["scope"] == MemoryScope.UNIVERSAL  # every agent's section
    assert universal_call["memory_type"] == "procedural"


def test_fabric_writer_failure_is_a_pending_not_an_exception():
    class ExplodingFabric:
        def record(self, **kwargs):
            raise RuntimeError("memora unreachable")

    writer = FabricLessonWriter(fabric=ExplodingFabric())
    assert writer.deliver("a lesson", {}, universal=False) is False


# ---------------------------------------------------------------------------
# The real battery against the real deterministic builder
# ---------------------------------------------------------------------------


def test_real_battery_scores_the_cli_golden_shape():
    spec = SPECS_BY_ID["cli_todo"]
    manifest = champion_manifest(spec)
    assert manifest  # Forge has a starting shape for its own golden goal
    battery = GoldenBattery(timeout_s=120)
    score = battery.run_arm(spec, manifest, "forge_default")
    assert score.error == ""
    assert score.files_written > 0
    assert score.manifest_fraction == 1.0
    assert score.compile_fraction == 1.0
    assert score.test_fraction > 0.9
    assert score.composite > 80.0
