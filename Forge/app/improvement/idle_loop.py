"""
Forge Idle Experiment Loop (TASK-FRG-017) — Self-Upgrade Programme, slice 1.

When Forge has no assigned work, it runs small, pre-declared experiments
on its own build behaviour and banks the lessons in Memora. Design:
~/workspace/self-upgrade/DESIGN.md (the shared self-upgrade mechanism).

The cycle:

  observe     -> Forge's own recent task outcomes (its StateStore)
  hypothesise -> closed catalogue: the dominant failure cluster in those
                 outcomes picks the golden build spec whose starting
                 manifest strategy is put to the test
  experiment  -> champion vs challenger manifest over that golden spec,
                 built by the deterministic synthesizer
                 (app.agents.synthesis) in a throwaway sandbox directory
                 and scored by the generated project's own test suite
  measure     -> composite score declared in advance (below); the
                 challenger is promoted only if it beats the champion by
                 PROMOTION_MARGIN and does not regress the generated-test
                 pass rate. Win or lose, the result is recorded.
  lesson      -> a procedural-type memory written through
                 mesh.memory_fabric: PROMOTE lessons go to Forge's
                 private section (AGENT_PRIVATE); DISCARD lessons — the
                 failed experiments — are written privately AND copied
                 to the universal section (UNIVERSE_GLOBAL), the owner's
                 standing rule R, so one agent's mistake teaches all ten.
                 Lessons are mirrored in a durable local ledger first;
                 a failed fabric delivery stays "pending" there and is
                 retried by flush_pending_lessons() on later cycles.

Bounds (DESIGN section 5): idle-only (any active task stops the cycle),
one cycle at a time, a daily cap, a per-arm time box, and the
FORGE_IDLE_EXPERIMENTS=off kill switch. Nothing here touches production
services, production data, another agent, or any risk parameter. The
champion registry this loop maintains is its own record — production
build roles do NOT read it yet; adopting a champion into the build path
is a change that travels the Universe's change path (Forge builds it,
Sentinel gates it, Cortex schedules it, fleet CD deploys it).

Slice 2 (the lifespan-wiring follow-up) adds the two review conditions
that blocked wiring, and the wiring itself:

  C2 — host-load gate. A cycle starts only when the host is calm: the
  1-minute load average must be below LOAD_GATE_FRACTION of the CPU
  count (the same fraction Stratex's self-experiment loop adopted from
  this review) AND at least MIN_MEM_AVAILABLE_FRACTION of memory must
  be available. A refusal is logged with the measured values. The gate
  fails closed: an unreadable load or memory reading refuses the cycle.
  The fleet hosts have ~956 MB of RAM for seven agents; an experiment
  battery that spawns pytest subprocesses must never compete with
  production work for that memory.

  C3 — Memora-confirmed lesson delivery. Slice 1 counted a lesson as
  delivered when fabric.record() returned without raising — but the
  fabric records locally and discards the cloud dispatch result, so
  "delivered" meant fabric-accepted, not Memora-accepted. The writer
  now delivers through the fabric's record_and_confirm_cloud() and
  counts a lesson delivered ONLY when Memora itself answered the
  dispatch (HTTP 200/201). Unconfirmed deliveries are retried with
  exponential backoff inside deliver(), and still stay "pending" in
  the lessons ledger for flush_pending_lessons() afterwards.

  Wiring — app.main's lifespan starts run_forever() ONLY through
  start_if_enabled(): the loop is wired behind FORGE_IDLE_EXPERIMENTS
  and starts solely when that flag is explicitly "on". Unset, "off",
  or any other value leaves the loop unstarted — the default is OFF,
  and setting the flag is a coordinator activation step, never part of
  a code change. (A directly constructed loop driven by hand keeps
  slice 1's experiments_enabled() kill-switch semantics: the "off"
  family of values vetoes every cycle.)
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import subprocess
import sys
import tempfile
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable

from app.agents.pattern_library import match_pattern
from app.agents.synthesis import synthesize_files_for_goal, synthesize_project
from app.core.logging import get_logger
from app.memory.models import TaskState

if TYPE_CHECKING:  # pragma: no cover - typing only, avoids an import cycle
    from app.memory.state_store import StateStore

UTC = timezone.utc

logger = get_logger("improvement.idle_loop")

# ---------------------------------------------------------------------------
# Declared constants — the experiment's rules, fixed in advance (DESIGN s.2)
# ---------------------------------------------------------------------------

#: Task states that mean Forge is NOT idle: assigned work always wins.
ACTIVE_STATES = frozenset(
    {
        TaskState.PENDING,
        TaskState.READY,
        TaskState.RUNNING,
        TaskState.VERIFYING,
        TaskState.BLOCKED,
    }
)

#: A challenger must beat the champion's composite by at least this much.
PROMOTION_MARGIN = 2.0

#: Score weights (composite = 100 * weighted sum of the three fractions).
WEIGHT_TESTS = 0.5
WEIGHT_MANIFEST = 0.3
WEIGHT_COMPILE = 0.2

DEFAULT_DAILY_CAP = 6
DEFAULT_ARM_TIMEOUT_S = 120.0
DEFAULT_POLL_SECONDS = 300.0

#: C2 host-load gate (slice 2): a cycle may start only while the
#: 1-minute load average is below this fraction of the CPU count.
#: Mirrors Stratex self-experiments' LOAD_GATE_FRACTION, which adopted
#: the value from this task's review condition.
LOAD_GATE_FRACTION = 0.7

#: C2 host-load gate (slice 2): a cycle may start only while at least
#: this fraction of total memory is available (MemAvailable / MemTotal
#: from /proc/meminfo). On a ~956 MB fleet host this reserves ~143 MB
#: of headroom the experiment battery may not consume.
MIN_MEM_AVAILABLE_FRACTION = 0.15

#: FRG-019 staleness bound for the idle gate: an ACTIVE task whose last
#: update is older than this is a dead row, not live work. Forge's own
#: record (2026-11-23, Oracle StateStore) holds 6 ACTIVE rows — 4 READY
#: + 2 RUNNING — untouched for 206+ hours across a service restart, so
#: the pre-fix check (`any ACTIVE`) was False forever and the loop could
#: never start. 24 h is far above any genuine Forge build (minutes),
#: and the check only gates the loop — it never mutates a row.
STALE_ACTIVE_AFTER_HOURS = 24.0

#: C3 delivery retry (slice 2): attempts per deliver() call before the
#: lesson is left pending in the ledger, and the first backoff delay —
#: each subsequent delay doubles (1 s, 2 s with the defaults).
DELIVERY_MAX_ATTEMPTS = 3
DELIVERY_BACKOFF_SECONDS = 1.0

#: Failure-cluster taxonomy — deliberately mirrors
#: app.improvement.self_improve so idle-loop hypotheses and the existing
#: improvement proposals speak the same language.
_CLUSTER_RULES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("missing_dependencies", ("dependency", "modulenotfound", "importerror")),
    ("syntax_errors", ("syntax", "syntaxerror", "indentationerror")),
    ("verification_failures", ("verification", "check", "assert")),
    ("fallback_stub_issues", ("fallback", "stub")),
    ("security_violations", ("security",)),
)


def cluster_of(error_message: str | None) -> str:
    """Classify one failed task's error into the shared cluster taxonomy."""
    err = (error_message or "").lower()
    for cluster, needles in _CLUSTER_RULES:
        if any(n in err for n in needles):
            return cluster
    return "runtime_failures"


# ---------------------------------------------------------------------------
# C2 — host-load gate (slice 2)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class HostLoadSnapshot:
    """One reading of the host's load and memory pressure."""

    load1: float
    cpu_count: int
    mem_available_fraction: float | None  # None = memory reading unavailable

    @property
    def load_fraction(self) -> float:
        return self.load1 / max(1, self.cpu_count)

    def refusal_reason(
        self,
        max_load_fraction: float = LOAD_GATE_FRACTION,
        min_mem_available_fraction: float = MIN_MEM_AVAILABLE_FRACTION,
    ) -> str | None:
        """Why this snapshot refuses a cycle, or None when it is calm."""
        if self.load_fraction >= max_load_fraction:
            return (
                f"load1 {self.load1:.2f} is {self.load_fraction:.2f} of "
                f"{self.cpu_count} cpu(s), at/above the "
                f"{max_load_fraction:.2f} gate"
            )
        if self.mem_available_fraction is None:
            return "memory availability unreadable (/proc/meminfo)"
        if self.mem_available_fraction < min_mem_available_fraction:
            return (
                f"memory available fraction "
                f"{self.mem_available_fraction:.3f} is below the "
                f"{min_mem_available_fraction:.3f} gate"
            )
        return None


def mem_available_fraction(meminfo_text: str) -> float | None:
    """MemAvailable / MemTotal from /proc/meminfo text, or None."""
    total = available = None
    for line in meminfo_text.splitlines():
        parts = line.split()
        if len(parts) >= 2 and parts[0] == "MemTotal:":
            try:
                total = float(parts[1])
            except ValueError:
                return None
        elif len(parts) >= 2 and parts[0] == "MemAvailable:":
            try:
                available = float(parts[1])
            except ValueError:
                return None
    if not total or available is None:
        return None
    return available / total


def read_host_load(meminfo_path: str = "/proc/meminfo") -> HostLoadSnapshot | None:
    """Read the current host load + memory pressure.

    Returns None when the load average itself is unreadable — the gate
    treats an unreadable host as a loaded host (fail closed). A missing
    or unparseable meminfo leaves mem_available_fraction None, which
    the gate also treats as a refusal.
    """
    try:
        load1 = os.getloadavg()[0]
    except (OSError, AttributeError):
        return None
    mem_fraction: float | None = None
    try:
        mem_fraction = mem_available_fraction(
            Path(meminfo_path).read_text(encoding="utf-8")
        )
    except OSError:
        mem_fraction = None
    return HostLoadSnapshot(
        load1=load1,
        cpu_count=os.cpu_count() or 1,
        mem_available_fraction=mem_fraction,
    )


# ---------------------------------------------------------------------------
# Golden specs — fixed build shapes the battery measures against
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class GoldenSpec:
    """One golden build shape: a goal whose outcome Forge can score."""

    id: str
    goal: str
    requirements: tuple[str, ...] = ()


GOLDEN_SPECS: tuple[GoldenSpec, ...] = (
    GoldenSpec(
        id="cli_todo",
        goal="Create a robust Python CLI Todo application with JSON persistence",
        requirements=(
            "Support adding, listing, completing, and deleting todos",
            "Include unit tests with 100% assertion coverage",
            "Provide CLI argument parsing via argparse",
        ),
    ),
    GoldenSpec(
        id="api_items",
        goal="Build a REST API for managing inventory items with CRUD endpoints",
        requirements=(
            "Support creating, listing, updating, and deleting items",
            "Include unit tests for every endpoint",
        ),
    ),
    GoldenSpec(
        id="library_roman",
        goal=(
            "Write a Python library module roman.py providing functions "
            "to convert roman numerals to integers and back"
        ),
        requirements=("Include unit tests for the conversion functions",),
    ),
    GoldenSpec(
        id="script_textstats",
        goal=(
            "Write a Python script that reads a text file and reports "
            "word frequency statistics"
        ),
        requirements=("Include unit tests for the statistics functions",),
    ),
)

SPECS_BY_ID = {s.id: s for s in GOLDEN_SPECS}

#: Which golden spec puts each failure cluster's shape to the test.
CLUSTER_TO_SPEC = {
    "verification_failures": "cli_todo",
    "missing_dependencies": "api_items",
    "security_violations": "api_items",
    "syntax_errors": "library_roman",
    "fallback_stub_issues": "script_textstats",
    "runtime_failures": "cli_todo",
}


# ---------------------------------------------------------------------------
# Scores and records
# ---------------------------------------------------------------------------


@dataclass
class ArmScore:
    """One battery arm: one manifest over one golden spec, measured."""

    manifest: list[str]
    mutation: str
    files_written: int = 0
    manifest_fraction: float = 0.0
    compile_fraction: float = 0.0
    test_fraction: float = 0.0
    tests_passed: int = 0
    tests_failed: int = 0
    wall_seconds: float = 0.0
    error: str = ""

    @property
    def composite(self) -> float:
        return round(
            100.0
            * (
                WEIGHT_TESTS * self.test_fraction
                + WEIGHT_MANIFEST * self.manifest_fraction
                + WEIGHT_COMPILE * self.compile_fraction
            ),
            2,
        )

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["composite"] = self.composite
        return d


@dataclass
class CycleReport:
    """The outcome of one attempted cycle (ran or skipped, and why)."""

    status: str  # "ran" | "skipped"
    reason: str = ""
    experiment_id: str = ""
    spec_id: str = ""
    verdict: str = ""  # "PROMOTE" | "DISCARD" when status == "ran"
    champion_composite: float | None = None
    challenger_composite: float | None = None


# ---------------------------------------------------------------------------
# The battery — deterministic synthesis + the generated project's own tests
# ---------------------------------------------------------------------------

_PASSED_RE = re.compile(r"(\d+) passed")
_FAILED_RE = re.compile(r"(\d+) failed")
_ERROR_RE = re.compile(r"(\d+) errors?")


class GoldenBattery:
    """Scores a starting-manifest strategy against the golden specs.

    An arm synthesizes the spec's project restricted to the given
    manifest (Forge's deterministic offline builder — the same code
    path Forge falls back to in production), writes it into a throwaway
    directory, compile-checks every Python file, and runs the generated
    project's own pytest suite. Nothing outside the temp directory is
    touched.
    """

    def __init__(self, timeout_s: float = DEFAULT_ARM_TIMEOUT_S):
        self.timeout_s = timeout_s

    def run_arm(self, spec: GoldenSpec, manifest: list[str], mutation: str) -> ArmScore:
        started = time.monotonic()
        score = ArmScore(manifest=list(manifest), mutation=mutation)
        try:
            files = synthesize_files_for_goal(
                spec.goal, list(manifest), list(spec.requirements)
            )
        except Exception as exc:  # synthesis declining is a measured zero
            score.error = f"synthesis_failed: {exc}"
            score.wall_seconds = round(time.monotonic() - started, 2)
            return score

        if manifest:
            present = sum(1 for name in manifest if name in files)
            score.manifest_fraction = present / len(manifest)
        else:
            score.manifest_fraction = 1.0 if files else 0.0

        with tempfile.TemporaryDirectory(prefix="forge_idle_exp_") as td:
            root = Path(td)
            written = self._write_files(root, files)
            score.files_written = written
            py_files = sorted(p for p in root.rglob("*.py") if p.is_file())
            if py_files:
                compiled = sum(1 for p in py_files if self._compiles(p))
                score.compile_fraction = compiled / len(py_files)
            passed, failed = self._run_generated_tests(root)
            score.tests_passed = passed
            score.tests_failed = failed
            if passed + failed > 0:
                score.test_fraction = passed / (passed + failed)
        score.wall_seconds = round(time.monotonic() - started, 2)
        return score

    @staticmethod
    def _write_files(root: Path, files: dict[str, str]) -> int:
        written = 0
        for name, content in files.items():
            rel = Path(name)
            if rel.is_absolute() or ".." in rel.parts:
                continue  # never write outside the sandbox directory
            dest = root / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(content, encoding="utf-8")
            written += 1
        return written

    @staticmethod
    def _compiles(path: Path) -> bool:
        import py_compile

        try:
            py_compile.compile(str(path), doraise=True)
            return True
        except Exception:
            return False

    def _run_generated_tests(self, root: Path) -> tuple[int, int]:
        try:
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "pytest",
                    "-q",
                    "-p",
                    "no:cacheprovider",
                    "--no-header",
                ],
                cwd=str(root),
                capture_output=True,
                text=True,
                timeout=self.timeout_s,
            )
        except subprocess.TimeoutExpired:
            return 0, 1  # a hung generated suite is a failing suite
        out = (proc.stdout or "") + (proc.stderr or "")
        passed_m = _PASSED_RE.search(out)
        failed_m = _FAILED_RE.search(out)
        error_m = _ERROR_RE.search(out)
        passed = int(passed_m.group(1)) if passed_m else 0
        failed = int(failed_m.group(1)) if failed_m else 0
        if error_m:
            failed += int(error_m.group(1))
        return passed, failed


# ---------------------------------------------------------------------------
# Lesson delivery — Memora via the shared memory fabric
# ---------------------------------------------------------------------------


class FabricLessonWriter:
    """Delivers lessons to Memora through mesh.memory_fabric.

    The fabric write is the fleet's sanctioned path (the agent's own
    key, graceful local degrade inside the fabric).

    C3 (slice 2): a delivery counts as made ONLY when Memora itself
    confirmed acceptance — the fabric's record_and_confirm_cloud()
    reports True only when Memora answered the cloud dispatch with
    HTTP 200/201. Slice 1 counted record() returning without raising,
    but the fabric records locally (in-memory / SQLite) and discards
    the dispatch result, so "delivered" meant fabric-accepted, never
    Memora-accepted. A fabric that offers no confirmation path can
    therefore never confirm a delivery here. Unconfirmed attempts are
    retried with exponential backoff (DELIVERY_MAX_ATTEMPTS attempts,
    DELIVERY_BACKOFF_SECONDS doubling); a lesson that still is not
    confirmed returns False and stays "pending" in the loop's local
    ledger for flush_pending_lessons() on later cycles. Retrying is
    safe against double-banking: Memora's POST /v1/memories suppresses
    duplicate content server-side.
    """

    def __init__(
        self,
        fabric: Any | None = None,
        max_attempts: int = DELIVERY_MAX_ATTEMPTS,
        backoff_seconds: float = DELIVERY_BACKOFF_SECONDS,
        sleeper: Callable[[float], None] = time.sleep,
    ):
        self._fabric = fabric
        self.max_attempts = max(1, max_attempts)
        self.backoff_seconds = backoff_seconds
        self._sleeper = sleeper

    def _get_fabric(self) -> Any:
        if self._fabric is None:
            from mesh.memory_fabric import UniversalMemoryFabric

            self._fabric = UniversalMemoryFabric()
        return self._fabric

    def deliver(self, content: str, metadata: dict[str, Any], *, universal: bool) -> bool:
        try:
            from mesh.memory_fabric import MemoryScope

            fabric = self._get_fabric()
        except Exception as exc:
            logger.warning(f"idle-loop lesson delivery failed: {exc}")
            return False
        confirm = getattr(fabric, "record_and_confirm_cloud", None)
        if not callable(confirm):
            logger.warning(
                "idle-loop lesson NOT delivered: the memory fabric offers "
                "no cloud-confirmation path (record_and_confirm_cloud), so "
                "Memora acceptance cannot be verified; lesson stays pending"
            )
            return False
        scope = MemoryScope.UNIVERSAL if universal else MemoryScope.AGENT
        delay = self.backoff_seconds
        for attempt in range(1, self.max_attempts + 1):
            try:
                _entry, confirmed = confirm(
                    owner_agent="FORGE",
                    content_text=content,
                    scope=scope,
                    memory_type="procedural",
                    source="forge_idle_experiment",
                    importance=0.8,
                    confidence=1.0,
                    metadata=metadata,
                )
            except Exception as exc:
                logger.warning(
                    f"idle-loop lesson delivery attempt {attempt}/"
                    f"{self.max_attempts} failed: {exc}"
                )
                confirmed = False
            if confirmed:
                return True
            logger.warning(
                f"idle-loop lesson not confirmed by Memora (attempt "
                f"{attempt}/{self.max_attempts}, scope={scope.value}); "
                "local fabric acceptance does not count as delivery"
            )
            if attempt < self.max_attempts:
                self._sleeper(delay)
                delay *= 2
        return False


# ---------------------------------------------------------------------------
# Hypothesis formation — closed catalogue over Forge's own outcomes
# ---------------------------------------------------------------------------


@dataclass
class Hypothesis:
    spec_id: str
    cluster: str | None
    statement: str


def form_hypothesis(tasks: list[Any], prior_spec_counts: dict[str, int]) -> Hypothesis:
    """Pick the next experiment from Forge's recent task outcomes.

    The dominant failure cluster in the recent record chooses the
    golden spec (CLUSTER_TO_SPEC). With no failures on record, the
    least-recently-tested spec is probed instead — the loop measures
    its champions even when nothing is visibly wrong.
    """
    failures = [t for t in tasks if t.state == TaskState.FAILED]
    if failures:
        counts: dict[str, int] = {}
        for t in failures:
            counts[cluster_of(t.error_message)] = counts.get(cluster_of(t.error_message), 0) + 1
        cluster = max(sorted(counts), key=lambda c: counts[c])
        spec_id = CLUSTER_TO_SPEC[cluster]
        statement = (
            f"Forge's recent failures cluster on '{cluster}' "
            f"({counts[cluster]} of {len(failures)} failed tasks). A different "
            f"starting-manifest shape for {spec_id}-shaped builds will score "
            f"higher on the golden battery than the current champion."
        )
        return Hypothesis(spec_id=spec_id, cluster=cluster, statement=statement)
    spec_id = min(
        (s.id for s in GOLDEN_SPECS),
        key=lambda sid: prior_spec_counts.get(sid, 0),
    )
    return Hypothesis(
        spec_id=spec_id,
        cluster=None,
        statement=(
            f"No failures in Forge's recent record; probing the "
            f"least-recently-tested golden shape ({spec_id}) to re-measure "
            f"its champion manifest."
        ),
    )


def champion_manifest(spec: GoldenSpec) -> list[str]:
    """The current default starting manifest for a spec.

    The pattern library's matched manifest when a pattern recognises
    the goal; otherwise the deterministic builder's own full file set —
    i.e. exactly what Forge would start from today.
    """
    match = match_pattern(spec.goal, list(spec.requirements))
    if match is not None:
        return list(match.manifest)
    produced = synthesize_project(spec.goal, list(spec.requirements))
    return sorted(produced.keys())


def challenger_mutations(spec: GoldenSpec, base: list[str]) -> list[tuple[str, list[str]]]:
    """The closed catalogue of challenger shapes for a champion manifest.

    Each mutation is a real, declared starting-shape change. Mutations
    that would not change the manifest are omitted.
    """
    out: list[tuple[str, list[str]]] = []
    match = match_pattern(spec.goal, list(spec.requirements))
    if match is not None and match.pattern.library_manifest:
        lib = match.pattern.manifest_for(match.module_name, wants_main=False)
        if lib and lib != base:
            out.append(("library_shape", list(lib)))
    no_readme = [m for m in base if Path(m).name != "README.md"]
    if no_readme and no_readme != base:
        out.append(("drop_readme", no_readme))
    py_only = [m for m in base if m.endswith(".py")]
    if py_only and py_only != base:
        out.append(("py_only", py_only))
    return out


def _is_stale(last: datetime, now: datetime) -> bool:
    """True when `last` is older than STALE_ACTIVE_AFTER_HOURS.

    Naive timestamps are read as UTC (the store writes UTC).
    """
    if last.tzinfo is None:
        last = last.replace(tzinfo=UTC)
    if now.tzinfo is None:
        now = now.replace(tzinfo=UTC)
    return (now - last).total_seconds() > STALE_ACTIVE_AFTER_HOURS * 3600


# ---------------------------------------------------------------------------
# The loop
# ---------------------------------------------------------------------------


class IdleExperimentLoop:
    """Forge's idle-time experiment cycle (see module docstring)."""

    def __init__(
        self,
        store: "StateStore",
        data_dir: Path,
        battery: GoldenBattery | None = None,
        lesson_writer: FabricLessonWriter | None = None,
        daily_cap: int = DEFAULT_DAILY_CAP,
        load_probe: Callable[[], HostLoadSnapshot | None] | None = None,
        max_load_fraction: float = LOAD_GATE_FRACTION,
        min_mem_available_fraction: float = MIN_MEM_AVAILABLE_FRACTION,
    ):
        self.store = store
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.battery = battery or GoldenBattery()
        self.lesson_writer = lesson_writer or FabricLessonWriter()
        self.daily_cap = daily_cap
        self._load_probe = load_probe or read_host_load
        self.max_load_fraction = max_load_fraction
        self.min_mem_available_fraction = min_mem_available_fraction

    @classmethod
    def from_settings(cls, store: "StateStore", **kwargs: Any) -> "IdleExperimentLoop":
        from app.core.config import get_settings

        return cls(
            store=store,
            data_dir=Path(get_settings().data_dir) / "idle_experiments",
            **kwargs,
        )

    # -- gates ------------------------------------------------------------

    @staticmethod
    def experiments_enabled() -> bool:
        return os.getenv("FORGE_IDLE_EXPERIMENTS", "on").strip().lower() not in {
            "off",
            "0",
            "false",
            "no",
        }

    @staticmethod
    def lifespan_enabled() -> bool:
        """The lifespan-wiring gate: True ONLY for an explicit "on".

        Stricter than experiments_enabled() on purpose. The kill
        switch's historical default (unset = cycles allowed) was safe
        while nothing started the loop; wiring run_forever() into the
        FastAPI lifespan inverts that risk, so the wiring arms only on
        an explicit FORGE_IDLE_EXPERIMENTS=on. Unset, "off", or any
        other value leaves the loop unstarted — default OFF. Setting
        the flag is the coordinator's activation step.
        """
        return os.getenv("FORGE_IDLE_EXPERIMENTS", "").strip().lower() == "on"

    @classmethod
    def start_if_enabled(
        cls,
        store: "StateStore",
        data_dir: Path | None = None,
        **kwargs: Any,
    ) -> "IdleExperimentLoop | None":
        """The lifespan wiring point: a loop when explicitly enabled.

        Returns None (and logs why) unless lifespan_enabled() — the
        caller in app.main's lifespan treats None as "not started" and
        never creates the driver task. Mirrors the start_if_enabled
        activation point Stratex's self-experiment loop shipped.
        """
        if not cls.lifespan_enabled():
            logger.info(
                "idle experiment loop not started: FORGE_IDLE_EXPERIMENTS "
                "is not explicitly 'on' (default off; activation is a "
                "coordinator step)"
            )
            return None
        if data_dir is not None:
            return cls(store=store, data_dir=Path(data_dir), **kwargs)
        return cls.from_settings(store, **kwargs)

    def host_load_refusal(self) -> str | None:
        """C2: why the host-load gate refuses a cycle now, or None.

        Reads load average + memory pressure through the loop's load
        probe. Fails closed: an unreadable host refuses the cycle,
        exactly as an overloaded one does.
        """
        try:
            snapshot = self._load_probe()
        except Exception as exc:
            return f"host load probe failed: {exc}"
        if snapshot is None:
            return "host load average unreadable (getloadavg)"
        return snapshot.refusal_reason(
            max_load_fraction=self.max_load_fraction,
            min_mem_available_fraction=self.min_mem_available_fraction,
        )

    async def is_idle(self, now: datetime | None = None) -> bool:
        """True when Forge has no live work.

        FRG-019: an ACTIVE row counts as live work only while it was
        updated recently. Forge's own record (2026-11-23) holds 6 ACTIVE
        rows untouched for 206+ hours across a service restart, so the
        pre-fix check (`any ACTIVE`) was False forever and the loop
        could never start. A row whose last update is older than
        STALE_ACTIVE_AFTER_HOURS is a dead row from a crashed or
        restarted worker, not assigned work; it is skipped here (and
        logged) but never mutated — the loop only decides whether Forge
        is idle. A row with no usable timestamp fails closed: it counts
        as live work.
        """
        tasks = await self.store.list_tasks(limit=200)
        now = now or datetime.now(UTC)
        live: list[str] = []
        stale: list[str] = []
        for task in tasks:
            if task.state not in ACTIVE_STATES:
                continue
            last = task.updated_at or task.created_at
            if last is not None and _is_stale(last, now):
                stale.append(task.id)
            else:
                live.append(task.id)
        if stale:
            logger.info(
                "idle gate: ignoring %d stale ACTIVE task(s) "
                "(no update for > %.0f h): %s",
                len(stale),
                STALE_ACTIVE_AFTER_HOURS,
                ", ".join(stale),
            )
        return not live

    # -- durable local records ---------------------------------------------

    @property
    def _ledger_path(self) -> Path:
        return self.data_dir / "experiments.jsonl"

    @property
    def _lessons_path(self) -> Path:
        return self.data_dir / "lessons.jsonl"

    @property
    def _champions_path(self) -> Path:
        return self.data_dir / "champions.json"

    def _read_jsonl(self, path: Path) -> list[dict[str, Any]]:
        if not path.exists():
            return []
        rows = []
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line:
                try:
                    rows.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
        return rows

    def _append_jsonl(self, path: Path, row: dict[str, Any]) -> None:
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, default=str) + "\n")

    def _load_champions(self) -> dict[str, Any]:
        if not self._champions_path.exists():
            return {}
        try:
            return json.loads(self._champions_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {}

    def _save_champions(self, champions: dict[str, Any]) -> None:
        tmp = self._champions_path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(champions, indent=2), encoding="utf-8")
        os.replace(tmp, self._champions_path)

    def _cycles_today(self, ledger: list[dict[str, Any]]) -> int:
        today = datetime.now(UTC).date().isoformat()
        return sum(
            1
            for row in ledger
            if row.get("status") == "ran" and str(row.get("ts", "")).startswith(today)
        )

    # -- one cycle -----------------------------------------------------------

    async def run_one_cycle(self, now: datetime | None = None) -> CycleReport:
        """Run one idle experiment cycle.

        `now` is the frozen clock for tests (threaded into the
        idle gate); omitted it means the wall clock, as in
        production.
        """
        if not self.experiments_enabled():
            return CycleReport(status="skipped", reason="kill_switch_off")
        load_refusal = self.host_load_refusal()
        if load_refusal is not None:
            logger.warning(
                f"idle experiment cycle refused by host-load gate: {load_refusal}"
            )
            return CycleReport(status="skipped", reason="host_load_gate")
        if not await self.is_idle(now=now):
            return CycleReport(status="skipped", reason="forge_busy")
        ledger = self._read_jsonl(self._ledger_path)
        if self._cycles_today(ledger) >= self.daily_cap:
            return CycleReport(status="skipped", reason="daily_cap_reached")
        self.flush_pending_lessons()

        tasks = await self.store.list_tasks(limit=200)
        prior_counts: dict[str, int] = {}
        for row in ledger:
            sid = row.get("spec_id")
            if sid:
                prior_counts[sid] = prior_counts.get(sid, 0) + 1
        hypothesis = form_hypothesis(tasks, prior_counts)
        spec = SPECS_BY_ID[hypothesis.spec_id]

        champions = self._load_champions()
        champion_entry = champions.get(spec.id)
        if champion_entry:
            champ_manifest = list(champion_entry["manifest"])
            champ_mutation = str(champion_entry.get("mutation", "forge_default"))
        else:
            champ_manifest = champion_manifest(spec)
            champ_mutation = "forge_default"

        mutations = challenger_mutations(spec, champ_manifest)
        if not mutations:
            self._append_jsonl(
                self._ledger_path,
                {
                    "ts": datetime.now(UTC).isoformat(),
                    "status": "skipped",
                    "reason": "no_challenger_differs",
                    "spec_id": spec.id,
                },
            )
            return CycleReport(
                status="skipped", reason="no_challenger_differs", spec_id=spec.id
            )
        rotation = prior_counts.get(spec.id, 0) % len(mutations)
        mutation_name, chall_manifest = mutations[rotation]

        experiment_id = f"exp_{datetime.now(UTC).strftime('%Y%m%d%H%M%S')}_{spec.id}"
        champion_score, challenger_score = await asyncio.to_thread(
            self._run_arms, spec, champ_manifest, champ_mutation, chall_manifest, mutation_name
        )

        verdict, reason = self._judge(champion_score, challenger_score)
        if verdict == "PROMOTE":
            champions[spec.id] = {
                "manifest": chall_manifest,
                "mutation": mutation_name,
                "composite": challenger_score.composite,
                "experiment_id": experiment_id,
                "updated_at": datetime.now(UTC).isoformat(),
            }
            self._save_champions(champions)

        record = {
            "ts": datetime.now(UTC).isoformat(),
            "status": "ran",
            "experiment_id": experiment_id,
            "spec_id": spec.id,
            "hypothesis": {
                "cluster": hypothesis.cluster,
                "statement": hypothesis.statement,
                "metric": "golden battery composite (0.5 tests + 0.3 manifest + 0.2 compile)",
                "bar": f"promote if challenger >= champion + {PROMOTION_MARGIN} and test fraction does not regress",
            },
            "champion": champion_score.to_dict(),
            "challenger": challenger_score.to_dict(),
            "verdict": verdict,
            "reason": reason,
        }
        self._append_jsonl(self._ledger_path, record)

        lesson = self._compose_lesson(record, hypothesis)
        metadata = {
            "experiment_id": experiment_id,
            "spec_id": spec.id,
            "verdict": verdict,
            "champion_composite": champion_score.composite,
            "challenger_composite": challenger_score.composite,
            "cluster": hypothesis.cluster,
        }
        deliveries = {
            "private": self.lesson_writer.deliver(lesson, metadata, universal=False),
            "universal": None,
        }
        if verdict == "DISCARD":
            # Standing rule R: a failed experiment's lesson also goes to
            # the universal section, so every agent learns from it.
            deliveries["universal"] = self.lesson_writer.deliver(
                lesson, metadata, universal=True
            )
        self._append_jsonl(
            self._lessons_path,
            {
                "ts": datetime.now(UTC).isoformat(),
                "experiment_id": experiment_id,
                "verdict": verdict,
                "content": lesson,
                "metadata": metadata,
                "deliveries": deliveries,
            },
        )
        logger.info(
            f"idle experiment {experiment_id}: {spec.id} {verdict} "
            f"(champion {champion_score.composite} vs challenger {challenger_score.composite})"
        )
        return CycleReport(
            status="ran",
            reason=reason,
            experiment_id=experiment_id,
            spec_id=spec.id,
            verdict=verdict,
            champion_composite=champion_score.composite,
            challenger_composite=challenger_score.composite,
        )

    def _run_arms(
        self,
        spec: GoldenSpec,
        champ_manifest: list[str],
        champ_mutation: str,
        chall_manifest: list[str],
        mutation_name: str,
    ) -> tuple[ArmScore, ArmScore]:
        champion = self.battery.run_arm(spec, champ_manifest, champ_mutation)
        challenger = self.battery.run_arm(spec, chall_manifest, mutation_name)
        return champion, challenger

    @staticmethod
    def _judge(champion: ArmScore, challenger: ArmScore) -> tuple[str, str]:
        if challenger.test_fraction < champion.test_fraction:
            return (
                "DISCARD",
                "challenger regressed the generated-test pass rate "
                f"({champion.test_fraction:.2f} -> {challenger.test_fraction:.2f})",
            )
        if challenger.composite >= champion.composite + PROMOTION_MARGIN:
            return (
                "PROMOTE",
                f"challenger beat the champion by "
                f"{challenger.composite - champion.composite:.2f} points "
                f"(bar: {PROMOTION_MARGIN})",
            )
        return (
            "DISCARD",
            f"challenger did not clear the promotion bar "
            f"({challenger.composite:.2f} vs champion {champion.composite:.2f} + {PROMOTION_MARGIN})",
        )

    @staticmethod
    def _compose_lesson(record: dict[str, Any], hypothesis: Hypothesis) -> str:
        champ = record["champion"]
        chall = record["challenger"]
        if record["verdict"] == "PROMOTE":
            action = (
                f"the challenger shape '{chall['mutation']}' is the new "
                f"champion for {record['spec_id']}-shaped builds — start "
                f"from manifest {chall['manifest']} for this shape"
            )
        else:
            action = (
                f"the champion shape '{champ['mutation']}' stands — do not "
                f"retry the '{chall['mutation']}' shape for "
                f"{record['spec_id']} until the underlying failure mix changes"
            )
        return (
            f"Idle experiment {record['experiment_id']} on golden shape "
            f"{record['spec_id']}: {hypothesis.statement} Champion "
            f"({champ['mutation']}) scored {champ['composite']} "
            f"(tests {champ['test_fraction']:.2f}, manifest "
            f"{champ['manifest_fraction']:.2f}, compile "
            f"{champ['compile_fraction']:.2f}); challenger "
            f"({chall['mutation']}) scored {chall['composite']} "
            f"(tests {chall['test_fraction']:.2f}, manifest "
            f"{chall['manifest_fraction']:.2f}, compile "
            f"{chall['compile_fraction']:.2f}). Verdict: "
            f"{record['verdict']} — {record['reason']}. Lesson: {action}."
        )

    # -- pending lesson retry -------------------------------------------------

    def flush_pending_lessons(self) -> int:
        """Retry Memora delivery for lessons still marked pending.

        Returns how many lessons became fully delivered. The lessons
        ledger is rewritten in place; delivery flags only ever move
        from False to True.
        """
        rows = self._read_jsonl(self._lessons_path)
        if not rows:
            return 0
        delivered_now = 0
        changed = False
        for row in rows:
            deliveries = row.get("deliveries") or {}
            needs_universal = row.get("verdict") == "DISCARD"
            pending = (deliveries.get("private") is not True) or (
                needs_universal and deliveries.get("universal") is not True
            )
            if not pending:
                continue
            if deliveries.get("private") is not True:
                ok = self.lesson_writer.deliver(
                    row["content"], row.get("metadata") or {}, universal=False
                )
                deliveries["private"] = ok
                changed = True
            if needs_universal and deliveries.get("universal") is not True:
                ok = self.lesson_writer.deliver(
                    row["content"], row.get("metadata") or {}, universal=True
                )
                deliveries["universal"] = ok
                changed = True
            row["deliveries"] = deliveries
            if deliveries.get("private") is True and (
                not needs_universal or deliveries.get("universal") is True
            ):
                delivered_now += 1
        if changed:
            tmp = self._lessons_path.with_suffix(".jsonl.tmp")
            with tmp.open("w", encoding="utf-8") as fh:
                for row in rows:
                    fh.write(json.dumps(row, default=str) + "\n")
            os.replace(tmp, self._lessons_path)
        return delivered_now

    # -- driver ----------------------------------------------------------------

    async def run_forever(
        self,
        poll_seconds: float = DEFAULT_POLL_SECONDS,
        stop_event: asyncio.Event | None = None,
    ) -> None:
        """Poll for idle windows and run one cycle per window.

        Wired into the FastAPI lifespan in slice 2 through
        start_if_enabled() — the driver task exists only when
        FORGE_IDLE_EXPERIMENTS is explicitly "on" (default off).
        A failing cycle is logged and never kills the loop.
        """
        stop = stop_event or asyncio.Event()
        while not stop.is_set():
            try:
                await self.run_one_cycle()
            except Exception as exc:
                logger.warning(f"idle experiment cycle failed: {exc}")
            try:
                await asyncio.wait_for(stop.wait(), timeout=poll_seconds)
            except asyncio.TimeoutError:
                continue
