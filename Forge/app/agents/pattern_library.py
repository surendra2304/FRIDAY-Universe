"""
Forge Pattern Library (TASK-FRG-006).

Mined from Forge's *verified* successful builds, this library gives a new
build a proven starting shape -- manifest, flat test layout, and the layout
rules that the successful runs obeyed -- instead of a blank page that the
Architect has to re-derive from scratch on every task.

Mining discipline: a pattern is only admitted here with provenance naming
the run(s) or generators that verified the shape. Patterns are starting
points, not substitutes for the build: the Architect may still extend the
manifest, and the verification battery remains the only judge of a build.

Sources mined for the initial library:

- TASK-REL-028 acceptance run 6 (task19414112026204733, production delegate
  path): Forge's first end-to-end successful build. SUCCESS / COMPLETED,
  first verification battery 11/11, 69 pytest passed from the generated
  suite. The winning run consolidated the library function into ``main.py``
  under a ``[main.py, README.md]`` manifest with a flat, root-level test
  file. The five runs before it failed on structural seams -- a module the
  manifest never named (recovery create route, PR #210), a missing-module
  classifier that never fired (PR #211), generated tests reaching for
  ``parent.parent`` path surgery (PR #213), and a module embedded as a
  string inside ``main.py`` and materialised at run time (the root cause
  repaired by PR #209).
- The deterministic generators in ``app.agents.synthesis`` (``_cli_main`` /
  ``_cli_tests`` / ``_api_main`` / ``_api_tests``): every emitted Python
  file is compile-checked before it is returned and the synthesis campaign
  harness runs each generated project's own test suite. These are the
  shapes Forge already falls back to when no provider can author code, so
  they are verified by construction and by campaign.
- TASK-FRG-003 run 1's goal shape (a named module ``roman.py`` plus a
  ``main.py`` demonstrating it) as the canonical two-module brief. FRG-003
  was still in flight when this library was mined, so no FRG-003 outcome
  is claimed as provenance; the two-module pattern's verification rests on
  the REL-028 fix wave that made the shape buildable at all.

Web goals are deliberately out of scope: ForgeWebStudio owns web shapes.
The matcher returns ``None`` for web goals and for anything it does not
recognise, and every caller keeps its previous behaviour on ``None``.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.core.logging import get_logger

logger = get_logger("agents.pattern_library")


@dataclass(frozen=True)
class BuildPattern:
    """A reusable, verified starting shape for one class of build."""

    id: str
    name: str
    summary: str
    provenance: str
    #: Manifest entries; ``{module}`` is substituted with the goal's module.
    manifest: tuple[str, ...]
    #: Manifest used when the goal names a module but asks for no main.py.
    library_manifest: tuple[str, ...] = ()
    layout_rules: tuple[str, ...] = ()
    test_layout: str = ""

    def manifest_for(self, module_name: str | None, wants_main: bool = True) -> list[str]:
        entries = self.manifest if wants_main or not self.library_manifest else self.library_manifest
        out: list[str] = []
        for entry in entries:
            name = entry.replace("{module}", module_name or "module")
            if name not in out:
                out.append(name)
        return out


@dataclass(frozen=True)
class PatternMatch:
    """A matched pattern plus everything a caller needs to start from it."""

    pattern: BuildPattern
    module_name: str | None = None
    wants_main: bool = True

    @property
    def manifest(self) -> list[str]:
        return self.pattern.manifest_for(self.module_name, self.wants_main)

    @property
    def guidance(self) -> str:
        """Prompt-ready block: the proven starting shape for this build."""
        lines = [
            f"Proven build pattern: {self.pattern.name} ({self.pattern.id}).",
            f"Start from this manifest shape: {self.manifest}.",
        ]
        lines.extend(f"- {rule}" for rule in self.pattern.layout_rules)
        if self.pattern.test_layout:
            lines.append(f"- Test layout: {self.pattern.test_layout}")
        lines.append(
            "The pattern is a starting point verified on earlier builds; "
            "extend it only where the goal genuinely requires more."
        )
        return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# The mined patterns
# ---------------------------------------------------------------------------

PY_SINGLE_MODULE = BuildPattern(
    id="python-single-module",
    name="Python single-module utility",
    summary=(
        "One algorithm/utility living in main.py with a flat generated test "
        "suite beside it."
    ),
    provenance=(
        "TASK-REL-028 acceptance run 6 (task19414112026204733), production "
        "delegate path: SUCCESS/COMPLETED, first battery 11/11, 69 pytest "
        "passed. The run's Architect manifested [main.py, README.md] and "
        "consolidated the library function into main.py."
    ),
    manifest=("main.py", "test_main.py", "README.md"),
    layout_rules=(
        "Keep every file flat at the project root; no package directory and no __init__.py for a single-module build.",
        "Implement the requested function(s) directly in main.py; do not split a second module the goal did not name.",
        "Never embed a module's source as a string inside main.py to be written out at run time (the REL-028 root-cause defect).",
    ),
    test_layout=(
        "test_main.py at the project root importing by bare module name "
        "(``from main import ...``); never sys.path or parent.parent path surgery."
    ),
)

PY_TWO_MODULE = BuildPattern(
    id="python-two-module",
    name="Python named-module plus entry point",
    summary=(
        "A goal-named library module with a main.py that demonstrates or "
        "drives it, tests flat at the root."
    ),
    provenance=(
        "Shape of the TASK-REL-028 palindrome goal's intended layout and of "
        "TASK-FRG-003 run 1 (roman.py + main.py). REL-028 runs 1-5 failed on "
        "this shape until the fix wave landed: recovery create route for "
        "manifest-missing modules (PR #210), missing-module classifier "
        "(PR #211), flat test-path write boundary (PR #213)."
    ),
    manifest=("{module}.py", "main.py", "test_main.py", "README.md"),
    library_manifest=("{module}.py", "test_{module}.py", "README.md"),
    layout_rules=(
        "The module file must be named exactly as the goal names it and must appear in the manifest; a module the manifest omits is the REL-028 manifest-missing-module failure.",
        "The module is a real file written directly, never embedded as a string inside main.py and materialised at run time.",
        "main.py imports the module by its bare name (``import {module}``); every file stays flat at the project root.",
    ),
    test_layout=(
        "Tests flat at the project root importing the module directly "
        "(``import {module}``); never parent.parent path surgery (PR #213)."
    ),
)

PY_CLI_CRUD = BuildPattern(
    id="python-cli-crud",
    name="Python CLI with JSON record store",
    summary=(
        "argparse subcommand CLI in main.py over a JSON-file store class, "
        "with tmp_path-isolated tests."
    ),
    provenance=(
        "Deterministic generators app/agents/synthesis.py _cli_main / "
        "_cli_tests: every emitted file compile-checked via compile_checked "
        "and each generated project's own suite run by the synthesis "
        "campaign harness."
    ),
    manifest=("main.py", "test_main.py", "requirements.txt", "README.md"),
    layout_rules=(
        "One main.py holding the store class, the argparse parser and the subcommand handlers; no extra modules.",
        "The store persists to a JSON file and tolerates a missing or corrupt file by starting empty.",
        "Every subcommand the goal names gets a handler and a help entry; exit code 0 on success, 1 on a handled error.",
    ),
    test_layout=(
        "test_main.py at the root; store tests isolate persistence with "
        "pytest tmp_path so no test touches a real data file."
    ),
)

PY_FASTAPI_CRUD = BuildPattern(
    id="fastapi-crud",
    name="FastAPI CRUD service",
    summary=(
        "FastAPI app in main.py with pydantic models, an in-memory store "
        "and a health endpoint, tested through TestClient."
    ),
    provenance=(
        "Deterministic generators app/agents/synthesis.py _api_main / "
        "_api_tests: compile-checked on emission and suite-verified by the "
        "synthesis campaign harness."
    ),
    manifest=("main.py", "test_main.py", "requirements.txt", "README.md"),
    layout_rules=(
        "The FastAPI app, pydantic models and store all live in main.py; expose GET /health before the resource routes.",
        "Create/list/get/update/delete routes for the goal's resource with 404 on a missing id, mirroring the mined generator's route order.",
        "requirements.txt carries the fastapi/uvicorn/pydantic/pytest/httpx floors the mined generator emits.",
    ),
    test_layout=(
        "test_main.py at the root driving the app through "
        "fastapi.testclient.TestClient; no live server or network."
    ),
)

PATTERNS: tuple[BuildPattern, ...] = (
    PY_TWO_MODULE,
    PY_FASTAPI_CRUD,
    PY_CLI_CRUD,
    PY_SINGLE_MODULE,
)

PATTERNS_BY_ID: dict[str, BuildPattern] = {p.id: p for p in PATTERNS}


# ---------------------------------------------------------------------------
# Matching
# ---------------------------------------------------------------------------

#: Web goals belong to ForgeWebStudio; the library stays out of their way.
_WEB_SIGNALS = (
    "website",
    "web site",
    "web page",
    "webpage",
    "web app",
    "web application",
    "landing page",
    "html",
    "css",
    "frontend",
    "front-end",
    "three.js",
    "webgl",
    "react",
    "next.js",
    "nextjs",
)

_MODULE_RES = (
    re.compile(r"module\s+(?:named\s+|called\s+)?[`\"']?([a-z][a-z0-9_]*)(?:\.py)?[`\"']?"),
    re.compile(r"[`\"']?([a-z][a-z0-9_]*)\.py[`\"']?\s+(?:module\s+)?(?:with|containing|that\s+provides|providing|implementing)"),
    re.compile(r"separate\s+(?:python\s+)?module\s+(?:named\s+|called\s+)?[`\"']?([a-z][a-z0-9_]*)"),
)

#: Names that are entry points or test files, never the mined module.
_NOT_MODULES = {"main", "test", "app", "index", "init", "setup", "run"}


def extract_module_name(goal: str) -> str | None:
    """The module a goal explicitly names (``a module roman.py ...``), if any."""
    text = goal.lower()
    for rx in _MODULE_RES:
        m = rx.search(text)
        if not m:
            continue
        name = m.group(1)
        if name in _NOT_MODULES:
            continue
        try:
            from app.agents.synthesis import _safe_module_name

            safe = _safe_module_name(name)
        except Exception:
            safe = name
        if safe and safe not in _NOT_MODULES:
            return safe
    return None


def match_pattern(goal: str, requirements: list[str] | None = None) -> PatternMatch | None:
    """Match a goal to a mined pattern, or ``None`` to keep prior behaviour.

    Conservative by design: a wrong starting shape is worse than none, so
    ambiguous goals fall through to the callers' existing logic.
    """
    if not goal or not goal.strip():
        return None
    text = goal.lower()
    joined = " ".join([goal, *(requirements or [])]).lower()

    if any(sig in text for sig in _WEB_SIGNALS):
        return None

    # A goal that names its module gets the two-module shape; whether an
    # entry point joins it depends on the goal asking for one.
    module_name = extract_module_name(goal)
    if module_name:
        wants_main = "main.py" in text or "main program" in text or "demonstrat" in text
        return PatternMatch(pattern=PY_TWO_MODULE, module_name=module_name, wants_main=wants_main)

    # Reuse the deterministic synthesizer's own goal reading for kind, so
    # the library and the offline builder never disagree about what a goal
    # is asking for.
    kind = None
    commands: list[str] = []
    try:
        from app.agents.synthesis import ProjectKind, parse_goal

        spec = parse_goal(goal, requirements)
        kind = spec.kind
        commands = list(spec.commands or [])
        if kind is ProjectKind.API:
            return PatternMatch(pattern=PY_FASTAPI_CRUD)
        if kind is ProjectKind.CLI and len(commands) >= 2:
            return PatternMatch(pattern=PY_CLI_CRUD)
        if kind in (ProjectKind.SCRIPT, ProjectKind.LIBRARY):
            return PatternMatch(pattern=PY_SINGLE_MODULE)
    except Exception as exc:  # pragma: no cover - matcher must never break a build
        logger.debug(f"Pattern matcher goal parse failed: {exc}")

    if any(k in joined for k in ("fastapi", "rest api")):
        return PatternMatch(pattern=PY_FASTAPI_CRUD)
    if "python" in joined and ("function" in joined or "main.py" in joined):
        return PatternMatch(pattern=PY_SINGLE_MODULE)
    return None
