"""Karpathy-derived coding principles for Forge (TASK-IG2-FRG-01).

Adopts the four principles from ``Forge/AGENT_GUIDELINES.md`` in machine
readable form so Forge can (a) render them into every task prompt and
(b) mechanically preflight a planned task and scope-check a finished
diff against them. The principles are guidance, not a verification
substitute: a clean preflight never marks a task done on its own.

Attribution: distilled by Forrest Chang from Andrej Karpathy's Jan 2026
observations on LLM coding pitfalls (multica-ai/andrej-karpathy-skills;
declared MIT in its README/manifests, no LICENSE file shipped — see
AGENT_GUIDELINES.md for the full caveat).
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class Principle:
    id: str
    title: str
    guidance: str


PRINCIPLES: tuple[Principle, ...] = (
    Principle(
        id="think-before-coding",
        title="Think Before Coding",
        guidance=(
            "State assumptions explicitly. If multiple interpretations "
            "exist, surface them and the trade-off instead of silently "
            "picking one. If a wrong guess would be expensive, stop and "
            "name what is missing."
        ),
    ),
    Principle(
        id="simplicity-first",
        title="Simplicity First",
        guidance=(
            "Minimum code that solves the stated problem. No speculative "
            "abstractions, unrequested configurability, or handling for "
            "cases that cannot occur."
        ),
    ),
    Principle(
        id="surgical-changes",
        title="Surgical Changes",
        guidance=(
            "Touch only what the task requires. No drive-by refactors, "
            "renames or reformatting; every changed line traces back to "
            "the task."
        ),
    ),
    Principle(
        id="goal-driven-execution",
        title="Goal-Driven Execution",
        guidance=(
            "Turn the task into verifiable success criteria first, then "
            "loop until they are actually verified with evidence. Code "
            "existing is not the same as the task being done."
        ),
    ),
)


def guidance_block() -> str:
    """Render the four principles as a prompt-ready guidance block."""
    lines = ["Coding principles (Karpathy-derived, see AGENT_GUIDELINES.md):"]
    for i, principle in enumerate(PRINCIPLES, 1):
        lines.append(f"{i}. {principle.title} — {principle.guidance}")
    return "\n".join(lines)


@dataclass(slots=True)
class PreflightReport:
    ok: bool
    missing: list[str] = field(default_factory=list)

    def summary(self) -> str:
        if self.ok:
            return "preflight OK: assumptions and success criteria stated"
        return "preflight incomplete: " + "; ".join(self.missing)


def preflight(
    task: str,
    assumptions: list[str] | tuple[str, ...] = (),
    success_criteria: list[str] | tuple[str, ...] = (),
) -> PreflightReport:
    """Check a planned task against principles 1 and 4.

    A task may start only when its assumptions are stated (Think Before
    Coding) and it carries at least one verifiable success criterion
    (Goal-Driven Execution). This checks presence, not quality — the
    human/agent still has to write honest criteria.
    """
    missing: list[str] = []
    if not task or not task.strip():
        missing.append("task description is empty")
    if not assumptions:
        missing.append("no assumptions stated (Think Before Coding)")
    if not success_criteria:
        missing.append("no verifiable success criteria (Goal-Driven Execution)")
    return PreflightReport(ok=not missing, missing=missing)


@dataclass(slots=True)
class ScopeReport:
    ok: bool
    out_of_scope: list[str] = field(default_factory=list)

    def summary(self) -> str:
        if self.ok:
            return "scope OK: every changed file is in the declared scope"
        return "out-of-scope changes: " + ", ".join(self.out_of_scope)


def scope_check(
    changed_files: list[str] | tuple[str, ...],
    allowed_prefixes: list[str] | tuple[str, ...],
) -> ScopeReport:
    """Check a finished diff against principle 3 (Surgical Changes).

    ``allowed_prefixes`` are repo-relative path prefixes the task
    declared it would touch; any changed file outside them is flagged
    as a drive-by change to revert or explicitly justify.
    """
    prefixes = tuple(p.rstrip("/") + "/" for p in allowed_prefixes)
    plain = tuple(p.rstrip("/") for p in allowed_prefixes)
    out = [
        f
        for f in changed_files
        if not any(f == p or f.startswith(pre) for p, pre in zip(plain, prefixes))
    ]
    return ScopeReport(ok=not out, out_of_scope=sorted(out))
