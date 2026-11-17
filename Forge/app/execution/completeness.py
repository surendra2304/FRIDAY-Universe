"""
Module Completeness Gate for Project FORGE (TASK-FRG-010).

The gate answers one question at the moment it matters -- after synthesis,
before the tester gate runs: does every module the goal or the architect's
manifest names exist as a real file in the project?

TASK-FRG-003's battery proved the hole this closes. The Developer role
iterates the manifest and tries hard per file (Inference channel, offline
synthesis, local fallback), but nothing ever compares the manifest with
the disk afterwards, and two of its success tests actively mask an
omission:

* the deterministic-synthesis "delivered" test accepts ANY produced .py
  file as satisfying the requested manifest entry, so a one-file
  synthesis silently "delivers" a four-module project (R3's store.py /
  pricing.py, R2's and R4's two-module goals collapsing to main.py);
* the fallback path records whatever the extractor happened to write,
  never whether the requested file is among it.

The build then reached the tester gate with modules missing. Before
TASK-FRG-003 that surfaced as fabricated sys.modules stand-ins and a
manifest claiming all_passed for code that did not exist; after it, as
honest test-collection errors -- better, but still a failed build that a
completeness check could have healed or failed fast, by name.

This gate runs in OrchestratorCore.step_task when the tester gate node
becomes ready, and once more in run_task before the verification battery
(the backstop for plans whose DAG carries no tester gate). For each
missing module it invokes the recovery ladder's create route
(RecoveryEngine.create_missing_module: same Inference channel, same 0.70
confidence bar, same compile gate, same guarded write). A module that
still cannot be produced ends the build in a FAILED state whose error
names the missing modules -- never a silent proceed to a battery that
would judge an incomplete file set.

Only importable source modules are gated. Test files belong to the
Tester role, README/docs to the Release role and the architect; demanding
them before the tester gate would manufacture failures, not catch them.
(TASK-FRG-013: the run_task backstop -- which runs after the Tester
role has finished -- opts into declared test files via
``include_test_files``; the in-DAG gate keeps the default.)

The expected set is the manifest union the modules the goal and its
requirements state, read with ``min_paths=1`` (see expected_modules):
FRG-004's extraction returns nothing below three stated paths -- the
right rule for the architect's manifest-or-template choice, but as the
gate's only goal-side source it left one- and two-module goals with an
empty expected set whenever the plan produced no manifest, and the gate
never engaged. The 2026-11-16 production acceptance battery's
two-module case completed over an empty project directory, judged
vacuously by the verification battery; it is pinned in
tests/test_frg010_completeness_gate.py.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable

from app.core.logging import get_logger

logger = get_logger("execution.completeness")

# The recovery subsystem's role: it holds the FS read/write permissions the
# create route and its guarded writes already run under.
_GATE_ROLE = "debugger"

_CODE_SUFFIXES = {
    ".py",
    ".js",
    ".jsx",
    ".ts",
    ".tsx",
    ".go",
    ".rs",
    ".java",
    ".c",
    ".h",
    ".cpp",
    ".hpp",
    ".cc",
    ".sh",
    ".rb",
    ".php",
    ".swift",
    ".kt",
}

_EXCLUDED_NAMES = {
    "readme.md",
    "file_manifest.json",
    "architecture_spec.md",
    "conftest.py",
}

CreateModuleFn = Callable[[str, str], Awaitable[tuple[bool, str]]]


def _normalize(path: Any) -> str:
    p = str(path).strip().replace("\\", "/")
    while p.startswith("./"):
        p = p[2:]
    return p.lstrip("/")


def _is_expected_module(path: str, include_test_files: bool = False) -> bool:
    """True for an importable source module the gate is responsible for.

    Test files are excluded by default: mid-build they belong to the
    Tester role, and demanding them before the tester gate would
    manufacture failures. TASK-FRG-013: the run_task backstop passes
    ``include_test_files=True`` -- by then the Tester role has run, so
    a goal/manifest-declared test file that still does not exist is a
    layout miss like any other (G5 shipped without tests/test_api.py).
    """
    if not path or path.endswith("/"):
        return False
    if path.startswith("docs/"):
        return False
    parts = path.split("/")
    name = parts[-1]
    lower = name.lower()
    if lower in _EXCLUDED_NAMES:
        return False
    is_test_file = (
        "tests" in parts[:-1]
        or lower.startswith("test_")
        or lower.endswith("_test.py")
        or lower.endswith((".test.js", ".test.ts", ".spec.js", ".spec.ts"))
    )
    if is_test_file and not include_test_files:
        return False
    if "." not in name:
        return False
    suffix = "." + lower.rsplit(".", 1)[-1]
    return suffix in _CODE_SUFFIXES


def expected_modules(
    goal: str,
    requirements: list[str] | None,
    manifest_files: list[str] | None,
    include_test_files: bool = False,
) -> list[str]:
    """Modules that must exist: manifest-declared union goal-named.

    The manifest is the architect's declared layout; the goal text is the
    caller's. TASK-FRG-004 made the architect honour the goal's explicit
    layout when no model manifest exists, but a model-produced manifest
    can still drop a goal-named module, so the gate checks the union --
    in manifest order, goal-stated extras appended in stated order.

    The goal is read with ``min_paths=1``, not the architect-side
    default of three: that threshold decides whether a stated layout
    replaces the architect's keyword templates, while the gate's
    question is which modules the build owes. A goal stating two
    modules owes both, however few they are; with the default, such a
    goal (and no manifest) computed an empty expected set here and the
    gate never engaged -- the 2026-11-16 production acceptance battery
    watched a two-module build complete over an empty directory. Only
    paths the goal or requirements state verbatim are returned, and
    ``_is_expected_module`` still restricts the set to importable source
    modules, so nothing is invented: when nothing is stated and no
    manifest exists, the expected set is empty and the gate stays
    silent, exactly as before.
    """
    from app.agents.roles import explicit_layout_from_goal

    ordered: list[str] = []
    candidates = [str(x) for x in (manifest_files or [])]
    candidates += explicit_layout_from_goal(
        goal or "", list(requirements or []), min_paths=1
    )
    for raw in candidates:
        path = _normalize(raw)
        if path and _is_expected_module(path, include_test_files) and path not in ordered:
            ordered.append(path)
    return ordered


def read_manifest_files(fs, task_id: str) -> list[str]:
    """The architect's docs/FILE_MANIFEST.json, parsed like the roles do."""
    try:
        raw = fs.read_file(task_id, "docs/FILE_MANIFEST.json", role=_GATE_ROLE)
    except Exception:
        return []
    try:
        parsed = json.loads(raw)
    except Exception:
        return []
    if isinstance(parsed, list):
        return [str(x) for x in parsed if x]
    if isinstance(parsed, dict) and "files" in parsed:
        return [str(x) for x in parsed["files"] if x]
    return []


def project_files(fs, task_id: str) -> set[str] | None:
    """Every file in the project, or None when the listing itself failed.

    None matters: a workspace that cannot be listed must not be reported
    as "everything is missing" -- the gate would fail a sound build on an
    infrastructure error. Callers treat None as indeterminate and let the
    build proceed ungated, exactly as it did before this gate existed.
    """
    try:
        return {_normalize(p) for p in fs.search_files(task_id, pattern="*", role=_GATE_ROLE)}
    except Exception:
        return None


@dataclass
class CompletenessReport:
    expected: list[str] = field(default_factory=list)
    healed: list[str] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)
    indeterminate: bool = False

    @property
    def complete(self) -> bool:
        return not self.missing

    def failure_message(self) -> str:
        names = ", ".join(self.missing)
        return (
            "Module completeness gate (TASK-FRG-010): "
            f"{len(self.missing)} module(s) named by the goal/manifest are "
            f"missing and could not be created: {names}. The build fails "
            "here instead of proceeding to the tester gate, which would "
            "otherwise judge an incomplete file set."
        )


class ModuleCompletenessGate:
    """Compare goal/manifest modules with the disk; heal or report."""

    def __init__(
        self,
        engine,
        store=None,
        create_module: CreateModuleFn | None = None,
    ):
        self.engine = engine
        self.store = store
        self._create_module = create_module

    async def _create_via_recovery(self, task_id: str, target_file: str) -> tuple[bool, str]:
        from app.recovery.engine import RecoveryEngine

        recovery = RecoveryEngine(exec_engine=self.engine, store=self.store)
        return await recovery.create_missing_module(task_id, target_file)

    async def ensure_complete(
        self,
        task_id: str,
        goal: str,
        requirements: list[str] | None = None,
        include_test_files: bool = False,
    ) -> CompletenessReport:
        fs = self.engine.fs
        expected = expected_modules(
            goal,
            requirements,
            read_manifest_files(fs, task_id),
            include_test_files=include_test_files,
        )
        if not expected:
            return CompletenessReport()

        present = project_files(fs, task_id)
        if present is None:
            logger.error(
                f"[Task {task_id}] Module completeness gate could not list the "
                "project files; proceeding ungated rather than failing a "
                "build on a listing error"
            )
            return CompletenessReport(expected=expected, indeterminate=True)

        missing = [m for m in expected if m not in present]
        healed: list[str] = []
        if missing:
            create = self._create_module or self._create_via_recovery
            for target in missing:
                try:
                    ok, message = await create(task_id, target)
                except Exception as exc:  # a broken route must not crash the build
                    ok, message = False, f"{type(exc).__name__}: {exc}"
                if ok:
                    healed.append(target)
                    logger.info(
                        f"[Task {task_id}] Module completeness gate created "
                        f"missing module '{target}' via the create route"
                    )
                else:
                    logger.warning(
                        f"[Task {task_id}] Module completeness gate could not "
                        f"create '{target}': {message}"
                    )
            # Trust the disk, not the route's claim: a creation that
            # reported success but left no file has not healed anything.
            present_after = project_files(fs, task_id)
            if present_after is not None:
                missing = [m for m in expected if m not in present_after]
                healed = [h for h in healed if h not in missing]
            else:
                missing = [m for m in missing if m not in healed]

        report = CompletenessReport(expected=expected, healed=healed, missing=missing)
        await self._record(task_id, report)
        return report

    async def _record(self, task_id: str, report: CompletenessReport) -> None:
        if not self.store:
            return
        try:
            if report.healed:
                await self.store.record_event(
                    task_id=task_id,
                    event_type="module_completeness.healed",
                    payload={"healed": report.healed, "expected": report.expected},
                )
            if report.missing:
                await self.store.record_event(
                    task_id=task_id,
                    event_type="module_completeness.failed",
                    payload={"missing": report.missing, "expected": report.expected},
                )
        except Exception:
            pass
