"""TASK-IG-FRG-02: specialised build-agent roster + skill registry.

Corpus source: Dc_iv4YKCAh — an open-source release pitched as "63 AI
agents with 249 skills" that do engineering work, including agents that
red-team their own fleet's code. The transferable pattern is not the
headline numbers; it is the *structure*: a library of small, named,
composable skills, and a roster of specialised agents defined by which
skills they carry. A role stops being one giant prompt and becomes an
auditable composition — you can see exactly which capabilities a
reviewer was given, and which it was not.

This module is that structure for Forge, at fleet-honest scale: a
declarative registry (pure data + validation + lookup, no behaviour
change to the existing roles in ``roles.py``). Consumers can ask:

* ``skills_for_role("security_reviewer")`` — what a role can do;
* ``skills_for_file("app/api/users.py")`` — what applies to a file;
* ``prompt_fragments([...])`` — the exact instruction text a role
  assembled from its skills would carry;
* ``specialist("red-teamer")`` — a roster entry composing skills.

The registry is deliberately data, not code paths: growing it toward
the corpus's scale is adding entries, and ``validate_registry`` keeps
the library honest (unique ids, known roles, resolvable references,
non-empty fragments). Nothing here fabricates coverage: a skill exists
only if its fragment is written out below.
"""
from __future__ import annotations

import fnmatch
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

# Role keys mirror the role families already in app/agents/roles.py
# (Architect / Developer / Tester / SecurityReviewer) plus the review
# roles TASK-IG-FRG-01 introduced (cross-model auditor, red team).
ROLES: Tuple[str, ...] = (
    "architect",
    "developer",
    "tester",
    "reviewer",
    "security_reviewer",
    "red_teamer",
    "docs",
    "devops",
    "performance",
)


@dataclass(frozen=True)
class Skill:
    """One named, composable capability."""

    id: str
    title: str
    roles: Tuple[str, ...]
    languages: Tuple[str, ...] = ()  # empty = language-agnostic
    file_globs: Tuple[str, ...] = ()  # empty = not file-scoped
    prompt_fragment: str = ""
    review_focus: Tuple[str, ...] = ()  # defect classes this skill hunts

    def applies_to_file(self, path: str, language: Optional[str] = None) -> bool:
        if self.file_globs and not any(
            fnmatch.fnmatch(path, glob) for glob in self.file_globs
        ):
            return False
        if language and self.languages and language not in self.languages:
            return False
        return bool(self.file_globs or self.languages)


@dataclass(frozen=True)
class Specialist:
    """A roster entry: a specialised build agent = a role + its skills."""

    name: str
    role: str
    purpose: str
    skill_ids: Tuple[str, ...]


def _skill(
    id: str,
    title: str,
    roles: Sequence[str],
    fragment: str,
    languages: Sequence[str] = (),
    file_globs: Sequence[str] = (),
    review_focus: Sequence[str] = (),
) -> Skill:
    return Skill(
        id=id,
        title=title,
        roles=tuple(roles),
        languages=tuple(languages),
        file_globs=tuple(file_globs),
        prompt_fragment=fragment,
        review_focus=tuple(review_focus),
    )


# ---------------------------------------------------------------------------
# The library. Every fragment below is the actual instruction a role
# carrying the skill would receive — written out, not promised.
# ---------------------------------------------------------------------------

DEFAULT_SKILLS: Tuple[Skill, ...] = (
    # --- architecture -------------------------------------------------
    _skill(
        "arch.module-boundaries",
        "Module boundary design",
        ("architect",),
        "Design module boundaries before writing code: each module owns one "
        "concern, dependencies point inward toward pure logic, and no module "
        "reaches into another's internals. Name the boundary in the plan.",
    ),
    _skill(
        "arch.api-contracts",
        "API contract design",
        ("architect", "developer"),
        "Define the API contract (paths, request/response shapes, error "
        "shape) before implementing it; handlers must match the contract "
        "exactly, including error cases.",
        file_globs=("*/api/*.py", "*/routers/*.py", "*/routes.py"),
    ),
    _skill(
        "arch.data-modelling",
        "Data modelling",
        ("architect", "developer"),
        "Model the data before the code: entities, invariants, and which "
        "writes must be transactional. Never let a handler invent a schema "
        "the model layer does not know.",
    ),
    # --- development --------------------------------------------------
    _skill(
        "dev.python-services",
        "Python service implementation",
        ("developer",),
        "Implement Python services with explicit error handling: no bare "
        "except, no swallowed errors, no silent fallbacks that fabricate "
        "results. Functions return real data or raise — never plausible "
        "placeholder values.",
        languages=("python",),
        file_globs=("*.py",),
    ),
    _skill(
        "dev.python-310-compat",
        "Python 3.10 compatibility",
        ("developer", "reviewer"),
        "Target Python 3.10: never use datetime.UTC, enum.StrEnum, "
        "asyncio.timeout, or other 3.11+ stdlib idioms. Use "
        "timezone.utc and (str, Enum) instead.",
        languages=("python",),
        file_globs=("*.py",),
        review_focus=("py311-idiom",),
    ),
    _skill(
        "dev.web-frontend",
        "Web frontend implementation",
        ("developer",),
        "Build frontends that work without a framework CDN at runtime "
        "where the project requires it; escape every interpolated value "
        "by default and treat innerHTML as a code smell that needs a "
        "written justification.",
        languages=("javascript", "typescript", "html"),
        file_globs=("*.js", "*.ts", "*.jsx", "*.tsx", "*.html"),
    ),
    _skill(
        "dev.sql-safety",
        "Safe SQL construction",
        ("developer", "security_reviewer"),
        "Build SQL only with bound parameters. String formatting, "
        "f-strings and concatenation into a query are defects, not style "
        "choices — including in tests and admin scripts.",
        file_globs=("*.py", "*.js", "*.ts"),
        review_focus=("sql-injection",),
    ),
    _skill(
        "dev.input-validation",
        "Input validation at boundaries",
        ("developer", "security_reviewer"),
        "Validate every value that crosses a trust boundary (HTTP input, "
        "file content, another agent's reply) at the boundary: type, "
        "range, and shape. Reject with a named error, never coerce "
        "silently.",
        review_focus=("missing-validation", "trust-boundary"),
    ),
    # --- testing ------------------------------------------------------
    _skill(
        "test.behaviour-tests",
        "Behaviour tests from the goal",
        ("tester",),
        "Derive tests from the goal's own words: every behaviour the goal "
        "states gets a test that would fail if the behaviour were absent. "
        "Never assert exact error strings or internals the goal does not "
        "specify.",
    ),
    _skill(
        "test.fail-on-main",
        "Fail-on-main discipline",
        ("tester", "reviewer"),
        "A regression test must fail on the unfixed code and pass on the "
        "fixed code. If it passes on both, it proves nothing — say so "
        "instead of counting it.",
        review_focus=("vacuous-test",),
    ),
    _skill(
        "test.edge-cases",
        "Edge-case coverage",
        ("tester",),
        "For each function under test, cover: empty input, missing file, "
        "malformed input, and the boundary value on each side of every "
        "threshold the code checks.",
    ),
    # --- review -------------------------------------------------------
    _skill(
        "review.correctness",
        "Correctness review",
        ("reviewer",),
        "Review for correctness against the stated goal: does the code do "
        "what the goal says, for the inputs the goal names? Flag any place "
        "where the code's behaviour and its own comments/docstrings "
        "disagree.",
        review_focus=("goal-mismatch", "doc-code-divergence"),
    ),
    _skill(
        "review.honesty",
        "Honesty / fabrication review",
        ("reviewer", "red_teamer"),
        "Hunt fabrication: fallback values presented as real results, "
        "success reported for work that did not run, metrics computed "
        "from constants, errors swallowed so a failure looks like a "
        "pass. Any instance is a blocking finding.",
        review_focus=("fabricated-result", "swallowed-error", "fake-success"),
    ),
    _skill(
        "review.error-handling",
        "Error-handling review",
        ("reviewer",),
        "Check that failures surface: exceptions are either handled with "
        "a real recovery or propagate with context. A caught exception "
        "that returns a default value is a finding unless the default is "
        "the documented contract.",
        review_focus=("swallowed-error",),
    ),
    # --- security review ----------------------------------------------
    _skill(
        "sec.sql-injection",
        "SQL injection review",
        ("security_reviewer", "red_teamer"),
        "Trace every SQL statement to its inputs. Any query whose text "
        "contains an interpolated value — f-string, %, format, concat, "
        "or a builder that splices raw strings — is a HIGH finding with "
        "the concrete payload that would exploit it.",
        file_globs=("*.py", "*.js", "*.ts"),
        review_focus=("sql-injection",),
    ),
    _skill(
        "sec.xss",
        "XSS review",
        ("security_reviewer", "red_teamer"),
        "Trace every value rendered into HTML/JS to its source. "
        "innerHTML/dangerouslySetInnerHTML/v-html with a non-literal, "
        "Jinja |safe, disabled autoescape, and document.write are "
        "findings; name the user-controlled input that reaches the sink.",
        file_globs=("*.js", "*.ts", "*.jsx", "*.tsx", "*.html"),
        review_focus=("xss",),
    ),
    _skill(
        "sec.command-injection",
        "Command injection review",
        ("security_reviewer", "red_teamer"),
        "Find every subprocess/os.system/eval/exec call. shell=True with "
        "any interpolated argument, and any command built from external "
        "input, is a CRITICAL finding.",
        review_focus=("command-injection",),
    ),
    _skill(
        "sec.auth-boundaries",
        "Auth boundary review",
        ("security_reviewer",),
        "For each route/handler, name the identity it requires and the "
        "check that enforces it. A handler that acts on a caller-supplied "
        "identity without verification is a HIGH finding.",
        review_focus=("auth-bypass", "missing-auth"),
    ),
    _skill(
        "sec.secrets",
        "Secrets handling review",
        ("security_reviewer",),
        "No credential may appear in generated code, logs, or error "
        "messages. Flag hardcoded keys, tokens in URLs, and log lines "
        "that print environment or headers wholesale.",
        review_focus=("secret-leak", "hardcoded-secret"),
    ),
    _skill(
        "sec.path-traversal",
        "Path traversal review",
        ("security_reviewer", "red_teamer"),
        "Any filesystem path built from external input must be proven to "
        "stay inside its root (resolve + prefix check). An unproven path "
        "join is a HIGH finding.",
        review_focus=("path-traversal",),
    ),
    # --- red team -------------------------------------------------------
    _skill(
        "redteam.trust-boundaries",
        "Trust-boundary attack",
        ("red_teamer",),
        "Enumerate the code's trust boundaries, then attack each one: "
        "oversized input, wrong types, replayed messages, a peer that "
        "lies. Report the boundary that breaks first, with the exact "
        "input.",
        review_focus=("trust-boundary",),
    ),
    _skill(
        "redteam.privilege-escalation",
        "Privilege escalation attack",
        ("red_teamer",),
        "Look for the path from the least-privileged input to the most "
        "dangerous capability in the code (shell, file write, other "
        "users' data). If a path exists without a check, it is a "
        "CRITICAL finding.",
        review_focus=("privilege-escalation",),
    ),
    # --- docs / devops / performance ------------------------------------
    _skill(
        "docs.readme-accuracy",
        "README accuracy",
        ("docs", "reviewer"),
        "Documentation must describe the code as it is, including its "
        "limits. A README that claims a capability the code lacks is a "
        "defect of the same severity as a code bug.",
        review_focus=("doc-code-divergence",),
    ),
    _skill(
        "devops.systemd-units",
        "systemd unit hygiene",
        ("devops",),
        "Service units must name their memory limits, restart policy and "
        "working directory explicitly, sized for a ~1GB host: if the "
        "unit does not state its budget, the budget does not exist.",
        file_globs=("*.service",),
    ),
    _skill(
        "perf.memory-budget",
        "Memory-budget awareness",
        ("performance", "developer"),
        "The fleet runs on ~1GB hosts. Flag imports and data structures "
        "whose resident cost is unbounded or disproportionate to the "
        "task, and eager loading of machinery a code path may never use.",
        review_focus=("unbounded-memory",),
    ),
)


DEFAULT_ROSTER: Tuple[Specialist, ...] = (
    Specialist(
        "architect",
        "architect",
        "Designs the build: boundaries, contracts, data model.",
        ("arch.module-boundaries", "arch.api-contracts", "arch.data-modelling"),
    ),
    Specialist(
        "python-developer",
        "developer",
        "Implements Python services and APIs.",
        (
            "dev.python-services",
            "dev.python-310-compat",
            "dev.sql-safety",
            "dev.input-validation",
            "arch.api-contracts",
        ),
    ),
    Specialist(
        "web-developer",
        "developer",
        "Implements web frontends and templates.",
        ("dev.web-frontend", "dev.input-validation"),
    ),
    Specialist(
        "test-engineer",
        "tester",
        "Writes behaviour tests that can actually fail.",
        ("test.behaviour-tests", "test.fail-on-main", "test.edge-cases"),
    ),
    Specialist(
        "code-reviewer",
        "reviewer",
        "Independent correctness + honesty review of generated code.",
        (
            "review.correctness",
            "review.honesty",
            "review.error-handling",
            "dev.python-310-compat",
            "test.fail-on-main",
        ),
    ),
    Specialist(
        "security-reviewer",
        "security_reviewer",
        "Dedicated security review pass (injection, XSS, auth, secrets).",
        (
            "sec.sql-injection",
            "sec.xss",
            "sec.command-injection",
            "sec.auth-boundaries",
            "sec.secrets",
            "sec.path-traversal",
            "dev.sql-safety",
            "dev.input-validation",
        ),
    ),
    Specialist(
        "red-teamer",
        "red_teamer",
        "Adversarial reviewer: assumes the code is exploitable, proves where.",
        (
            "redteam.trust-boundaries",
            "redteam.privilege-escalation",
            "sec.sql-injection",
            "sec.xss",
            "sec.command-injection",
            "sec.path-traversal",
            "review.honesty",
        ),
    ),
    Specialist(
        "docs-writer",
        "docs",
        "Writes documentation that matches the code, limits included.",
        ("docs.readme-accuracy",),
    ),
    Specialist(
        "devops-engineer",
        "devops",
        "Ships units and deploy config sized for the fleet's hosts.",
        ("devops.systemd-units", "perf.memory-budget"),
    ),
    Specialist(
        "performance-reviewer",
        "performance",
        "Reviews resident cost and eager-loading on small hosts.",
        ("perf.memory-budget",),
    ),
)


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------


@dataclass
class SkillRegistry:
    skills: Tuple[Skill, ...] = DEFAULT_SKILLS
    roster: Tuple[Specialist, ...] = DEFAULT_ROSTER

    def _by_id(self) -> Dict[str, Skill]:
        return {s.id: s for s in self.skills}

    def get_skill(self, skill_id: str) -> Skill:
        by_id = self._by_id()
        if skill_id not in by_id:
            raise KeyError(f"unknown skill: {skill_id}")
        return by_id[skill_id]

    def specialist(self, name: str) -> Specialist:
        for entry in self.roster:
            if entry.name == name:
                return entry
        raise KeyError(f"unknown specialist: {name}")

    def specialist_skills(self, name: str) -> List[Skill]:
        entry = self.specialist(name)
        return [self.get_skill(sid) for sid in entry.skill_ids]

    def skills_for_role(self, role: str) -> List[Skill]:
        if role not in ROLES:
            raise KeyError(f"unknown role: {role}")
        return [s for s in self.skills if role in s.roles]

    def skills_for_file(
        self, path: str, language: Optional[str] = None
    ) -> List[Skill]:
        return [s for s in self.skills if s.applies_to_file(path, language)]

    def skills_for_review_focus(self, focus: str) -> List[Skill]:
        return [s for s in self.skills if focus in s.review_focus]

    def prompt_fragments(self, skill_ids: Iterable[str]) -> str:
        """The exact instruction text for a set of skills, in registry
        order (not request order) so a role's prompt is deterministic."""
        wanted = set(skill_ids)
        parts = [
            f"[{s.id}] {s.prompt_fragment}" for s in self.skills if s.id in wanted
        ]
        missing = wanted - {s.id for s in self.skills}
        if missing:
            raise KeyError(f"unknown skill(s): {sorted(missing)}")
        return "\n".join(parts)

    def validate(self) -> List[str]:
        """Structural honesty checks. Returns a list of problems; an
        empty list means the registry is internally consistent."""
        problems: List[str] = []
        seen = set()
        for skill in self.skills:
            if skill.id in seen:
                problems.append(f"duplicate skill id: {skill.id}")
            seen.add(skill.id)
            if not skill.prompt_fragment.strip():
                problems.append(f"skill {skill.id} has an empty prompt fragment")
            if not skill.roles:
                problems.append(f"skill {skill.id} has no roles")
            for role in skill.roles:
                if role not in ROLES:
                    problems.append(f"skill {skill.id} names unknown role {role}")
        names = set()
        for entry in self.roster:
            if entry.name in names:
                problems.append(f"duplicate specialist name: {entry.name}")
            names.add(entry.name)
            if entry.role not in ROLES:
                problems.append(
                    f"specialist {entry.name} has unknown role {entry.role}"
                )
            if not entry.skill_ids:
                problems.append(f"specialist {entry.name} carries no skills")
            for sid in entry.skill_ids:
                if sid not in seen:
                    problems.append(
                        f"specialist {entry.name} references unknown skill {sid}"
                    )
        return problems


DEFAULT_REGISTRY = SkillRegistry()
