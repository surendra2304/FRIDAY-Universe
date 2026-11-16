"""TASK-IG-FRG-01: independent review passes over Forge-generated code.

Why this module exists
----------------------
Three items in the owner's Instagram reference corpus (2026-11-15)
describe the same discipline from three angles:

* Dc_iv4YKCAh — an open-source fleet of specialised agents whose code is
  red-teamed by a *separate* reviewer before delivery;
* DdRxjWhlrNC — "Claudex Loop": route work across models so one model
  writes the code and a *different* model audits it, fixing self-grading;
* DeihJQuCpdp — a dedicated security-focused code-review pass (SQL
  injection, XSS) over generated code before delivery.

Forge already has point-in-time gates (TesterRole / SecurityReviewerRole
in ``app/agents/roles.py``) and a final verification battery whose
security leg is ``OutputSecurityScanner``. What it did not have is a
review layer that is *independent of the author*: a deterministic
security review focused on injection/XSS, a cross-model audit that
refuses to run when reviewer == author, and an adversarial red-team
pass — all reporting through one honest aggregate.

Honesty rules (FRG-009 / FRG-011 discipline, binding here):

* A pass that could not run reports ``UNAVAILABLE`` — never ``PASS``.
  A missing review provider, a same-model "audit", a provider error,
  an empty reply, or an unparseable verdict are all ``UNAVAILABLE``.
* The aggregate is ``FINDINGS`` if any pass found issues, else
  ``UNAVAILABLE`` if any pass is unavailable, else ``PASS``. Agreement,
  not inflation: a green deterministic scan cannot launder an audit
  that never happened.
* The model-based passes take an injected async ``review_fn``; this
  module performs no network I/O of its own, so a deployment wires it
  to Inference (via ``app.providers``) explicitly, and tests wire fakes.

Integration point (wired by TASK-IG2-FRG-10): the verification
battery (``app/verification/engine.py``) runs :func:`run_review_passes`
over the settled workspace as its "Independent Review Passes" stage,
reachable from the production path (``app/api/delegate.py`` ->
``verification_engine.verify_task``). A FINDINGS aggregate becomes a
failed battery evidence — a named hard failure in the report's
failure_reasons; an UNAVAILABLE aggregate fails closed when a
reviewer was configured, and is recorded as a disclosed gate result
when none was. The full report is persisted as the
``review_passes_report.json`` task artifact.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Awaitable, Callable, Dict, List, Optional

from app.verification.security_scanner import OutputSecurityScanner

# A review provider: prompt in, raw reply text out. Injected so this
# module never performs network I/O itself.
ReviewFn = Callable[[str], Awaitable[str]]

# ---------------------------------------------------------------------------
# Data shapes
# ---------------------------------------------------------------------------


class ReviewStatus(str, Enum):
    PASS = "PASS"  # the pass ran and found nothing
    FINDINGS = "FINDINGS"  # the pass ran and found issues
    UNAVAILABLE = "UNAVAILABLE"  # the pass could not run — NOT a pass


@dataclass
class ReviewIssue:
    source: str  # which pass raised it
    severity: str  # CRITICAL / HIGH / MEDIUM / LOW (free text from models is normalised)
    file_path: str
    description: str
    line_number: Optional[int] = None
    fix_suggestion: str = ""

    def to_dict(self) -> dict:
        return {
            "source": self.source,
            "severity": self.severity,
            "file_path": self.file_path,
            "line_number": self.line_number,
            "description": self.description,
            "fix_suggestion": self.fix_suggestion,
        }


@dataclass
class PassResult:
    name: str
    status: ReviewStatus
    issues: List[ReviewIssue] = field(default_factory=list)
    detail: str = ""
    author_model: Optional[str] = None
    reviewer_model: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "status": self.status.value,
            "issues": [i.to_dict() for i in self.issues],
            "detail": self.detail,
            "author_model": self.author_model,
            "reviewer_model": self.reviewer_model,
        }


@dataclass
class ReviewReport:
    workspace_path: str
    passes: List[PassResult] = field(default_factory=list)

    @property
    def overall_status(self) -> ReviewStatus:
        """Agreement, not inflation: findings outrank unavailability,
        unavailability outranks pass. An empty report is UNAVAILABLE —
        no pass ran, so nothing may be called reviewed."""
        if any(p.status is ReviewStatus.FINDINGS for p in self.passes):
            return ReviewStatus.FINDINGS
        if not self.passes or any(
            p.status is ReviewStatus.UNAVAILABLE for p in self.passes
        ):
            return ReviewStatus.UNAVAILABLE
        return ReviewStatus.PASS

    @property
    def all_issues(self) -> List[ReviewIssue]:
        return [issue for p in self.passes for issue in p.issues]

    def to_dict(self) -> dict:
        return {
            "workspace_path": self.workspace_path,
            "overall_status": self.overall_status.value,
            "passes": [p.to_dict() for p in self.passes],
        }


# ---------------------------------------------------------------------------
# File collection for the model-based passes
# ---------------------------------------------------------------------------

REVIEWABLE_SUFFIXES = {".py", ".js", ".ts", ".jsx", ".tsx", ".html", ".htm"}
_EXCLUDED_DIRS = frozenset(
    {
        ".git",
        "__pycache__",
        ".pytest_cache",
        ".venv",
        "venv",
        "node_modules",
        "dist",
        "build",
    }
)


def collect_review_files(
    workspace: Path,
    max_files: int = 40,
    max_bytes_per_file: int = 20_000,
    max_total_bytes: int = 200_000,
) -> Dict[str, str]:
    """Bounded, deterministic snapshot of reviewable source files.

    Returns ``{relative_path: content}`` sorted by path. Files past the
    byte caps are truncated with an explicit marker — a reviewer must
    never be silently shown a partial file as if it were whole.
    """
    workspace = Path(workspace)
    collected: Dict[str, str] = {}
    total = 0
    if not workspace.is_dir():
        return collected
    candidates = []
    for path in workspace.rglob("*"):
        if not path.is_file() or path.is_symlink():
            continue
        if any(part in _EXCLUDED_DIRS for part in path.parts):
            continue
        if path.suffix.lower() not in REVIEWABLE_SUFFIXES:
            continue
        candidates.append(path)
    for path in sorted(candidates, key=lambda p: p.as_posix()):
        if len(collected) >= max_files or total >= max_total_bytes:
            break
        try:
            raw = path.read_bytes()
        except OSError:
            continue
        text = raw.decode("utf-8", errors="ignore")
        truncated = False
        if len(text) > max_bytes_per_file:
            text = text[:max_bytes_per_file]
            truncated = True
        if truncated:
            text += "\n[... file truncated by the review collector ...]\n"
        collected[path.relative_to(workspace).as_posix()] = text
        total += len(text)
    return collected


# ---------------------------------------------------------------------------
# Pass 1 — deterministic security review (SQL injection / XSS focus)
# ---------------------------------------------------------------------------

# The OutputSecurityScanner check names this pass treats as in-scope:
# injection and XSS findings. (The full battery judges the rest; this
# pass is the corpus's dedicated security review, so it stays focused.)
_INJECTION_CHECK_MARKERS = ("SQL Injection", "DOM XSS", "React XSS")

# Template/HTML XSS patterns the scanner does not cover: it scans .html
# files for secrets only, so Jinja autoescape escapes and inline-script
# sinks in templates are this pass's own deterministic checks.
_TEMPLATE_XSS_RULES = [
    (
        re.compile(r"\|\s*safe\b"),
        "HIGH",
        "Jinja '|safe' filter renders a value without escaping (XSS if the value is user-influenced).",
        "Remove '|safe' or escape/sanitise the value before rendering.",
    ),
    (
        re.compile(r"\{%-?\s*autoescape\s+false"),
        "HIGH",
        "Jinja autoescape disabled for a block (XSS risk for any interpolated value).",
        "Keep autoescape on; escape individual values explicitly where HTML is intended.",
    ),
    (
        re.compile(r"document\.write\s*\("),
        "MEDIUM",
        "document.write() in an inline script can inject unsanitised markup (XSS).",
        "Build DOM nodes with textContent / createElement instead.",
    ),
    (
        re.compile(r"\.innerHTML\s*=\s*(?!['\"`])"),
        "HIGH",
        "innerHTML assigned from a non-literal expression in an inline script (DOM XSS).",
        "Assign via textContent, or sanitise the value with a vetted sanitiser first.",
    ),
]


def _scan_template_xss(rel_path: str, content: str) -> List[ReviewIssue]:
    issues: List[ReviewIssue] = []
    for lineno, line in enumerate(content.splitlines(), start=1):
        for pattern, severity, description, fix in _TEMPLATE_XSS_RULES:
            if pattern.search(line):
                issues.append(
                    ReviewIssue(
                        source="security_review",
                        severity=severity,
                        file_path=rel_path,
                        line_number=lineno,
                        description=description,
                        fix_suggestion=fix,
                    )
                )
    return issues


def security_review_pass(workspace: Path) -> PassResult:
    """Deterministic security review of generated code.

    Composes with (does not duplicate) ``OutputSecurityScanner``: the
    scanner's injection/XSS findings are lifted into the review report,
    and template files get the additional HTML/Jinja XSS checks above.
    A scanner failure makes the pass UNAVAILABLE — fail closed, never a
    fabricated clean bill.
    """
    workspace = Path(workspace)
    name = "security_review"
    if not workspace.is_dir():
        return PassResult(
            name=name,
            status=ReviewStatus.UNAVAILABLE,
            detail=f"workspace not found: {workspace}",
        )
    try:
        report = OutputSecurityScanner(workspace).scan_all()
    except Exception as exc:  # scanner failure is absence of evidence
        return PassResult(
            name=name,
            status=ReviewStatus.UNAVAILABLE,
            detail=f"security scanner failed: {exc!r}",
        )
    issues: List[ReviewIssue] = []
    for finding in report.findings:
        if any(marker in finding.check_name for marker in _INJECTION_CHECK_MARKERS):
            issues.append(
                ReviewIssue(
                    source=name,
                    severity=finding.severity.value,
                    file_path=finding.file_path,
                    line_number=finding.line_number,
                    description=f"{finding.check_name}: {finding.description}",
                    fix_suggestion=finding.fix_suggestion,
                )
            )
    for path in sorted(workspace.rglob("*")):
        if not path.is_file() or path.is_symlink():
            continue
        if any(part in _EXCLUDED_DIRS for part in path.parts):
            continue
        if path.suffix.lower() not in {".html", ".htm", ".jinja", ".jinja2", ".j2"}:
            continue
        try:
            content = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        issues.extend(
            _scan_template_xss(path.relative_to(workspace).as_posix(), content)
        )
    status = ReviewStatus.FINDINGS if issues else ReviewStatus.PASS
    return PassResult(
        name=name,
        status=status,
        issues=issues,
        detail=(
            f"scanned {report.scanned_files_count} files; "
            f"{len(issues)} injection/XSS issue(s) in scope for this pass"
        ),
    )


# ---------------------------------------------------------------------------
# Passes 2 & 3 — cross-model audit and self-red-team (model-based)
# ---------------------------------------------------------------------------

_VERDICT_INSTRUCTION = (
    "Reply with ONLY a JSON object, no prose, in exactly this shape:\n"
    '{"verdict": "pass" or "findings", "issues": [{"file": "<path>", '
    '"line": <int or null>, "severity": "CRITICAL|HIGH|MEDIUM|LOW", '
    '"description": "<what is wrong and why>"}]}\n'
    'Use "pass" with an empty issues list only if you found nothing.'
)

_SEVERITIES = {"CRITICAL", "HIGH", "MEDIUM", "LOW"}


def _files_block(files: Dict[str, str]) -> str:
    parts = []
    for path in sorted(files):
        parts.append(f"===== FILE: {path} =====\n{files[path]}")
    return "\n\n".join(parts)


def build_audit_prompt(files: Dict[str, str], author_model: str) -> str:
    """Prompt for the cross-model audit: a *different* model reviews the
    author's code. Pure function — the same input always audits the same
    way."""
    return (
        "You are an independent code auditor. The code below was written "
        f"by a different AI model ({author_model}). You did not write it; "
        "your job is to find real defects in it: correctness bugs, "
        "security vulnerabilities (especially SQL injection and XSS), "
        "broken error handling, and places where the code claims to do "
        "something it does not. Do not praise it. Do not invent defects "
        "that are not in the code shown.\n\n" + _VERDICT_INSTRUCTION + "\n\n"
        + _files_block(files)
    )


def build_redteam_prompt(files: Dict[str, str]) -> str:
    """Prompt for the self-red-team pass: adversarial by construction.
    The reviewer is instructed to assume the code is exploitable and to
    prove it, which surfaces what a polite review misses."""
    return (
        "You are a red-team reviewer. Assume the code below IS "
        "exploitable and your job is to prove where. Attack it: "
        "injection (SQL, command, template), cross-site scripting, "
        "authentication/authorization bypass, path traversal, unsafe "
        "deserialization, secret leakage, and trust-boundary violations "
        "(data accepted without validation, errors swallowed silently, "
        "checks that can be bypassed). For each weakness, name the file "
        "and the concrete input or sequence that would exploit it. If a "
        "part genuinely resists attack, say nothing about it.\n\n"
        + _VERDICT_INSTRUCTION + "\n\n" + _files_block(files)
    )


def _parse_review_verdict(
    text: Optional[str], source: str
) -> Optional[List[ReviewIssue]]:
    """Strict verdict parsing. Returns the issue list on success
    (empty list = pass), or ``None`` when the reply is not a usable
    verdict — the caller must then mark the pass UNAVAILABLE. A model
    reply that cannot be parsed is never treated as a pass."""
    if not text or not text.strip():
        return None
    match = re.search(r"\{.*\}", text, flags=re.DOTALL)
    if not match:
        return None
    try:
        payload = json.loads(match.group(0))
    except (ValueError, TypeError):
        return None
    if not isinstance(payload, dict):
        return None
    verdict = str(payload.get("verdict", "")).strip().lower()
    if verdict not in {"pass", "findings"}:
        return None
    raw_issues = payload.get("issues")
    if verdict == "pass":
        return []
    if not isinstance(raw_issues, list) or not raw_issues:
        return None  # "findings" with no findings is not a usable verdict
    issues: List[ReviewIssue] = []
    for raw in raw_issues:
        if not isinstance(raw, dict):
            return None
        severity = str(raw.get("severity", "MEDIUM")).strip().upper()
        if severity not in _SEVERITIES:
            severity = "MEDIUM"
        line = raw.get("line")
        issues.append(
            ReviewIssue(
                source=source,
                severity=severity,
                file_path=str(raw.get("file", "<unknown>")),
                line_number=line if isinstance(line, int) else None,
                description=str(raw.get("description", "")).strip()
                or "reviewer reported an issue without a description",
            )
        )
    return issues


async def _run_model_pass(
    name: str,
    prompt: str,
    review_fn: Optional[ReviewFn],
    author_model: Optional[str],
    reviewer_model: Optional[str],
) -> PassResult:
    if review_fn is None:
        return PassResult(
            name=name,
            status=ReviewStatus.UNAVAILABLE,
            detail="no review provider configured for this pass",
            author_model=author_model,
            reviewer_model=reviewer_model,
        )
    if not reviewer_model:
        return PassResult(
            name=name,
            status=ReviewStatus.UNAVAILABLE,
            detail="no reviewer model named; an unnamed reviewer cannot be audited",
            author_model=author_model,
            reviewer_model=reviewer_model,
        )
    try:
        reply = await review_fn(prompt)
    except Exception as exc:  # provider failure is absence of evidence
        return PassResult(
            name=name,
            status=ReviewStatus.UNAVAILABLE,
            detail=f"review provider failed: {exc!r}",
            author_model=author_model,
            reviewer_model=reviewer_model,
        )
    issues = _parse_review_verdict(reply, source=name)
    if issues is None:
        return PassResult(
            name=name,
            status=ReviewStatus.UNAVAILABLE,
            detail="reviewer reply was not a parseable verdict; treated as no evidence, not as a pass",
            author_model=author_model,
            reviewer_model=reviewer_model,
        )
    return PassResult(
        name=name,
        status=ReviewStatus.FINDINGS if issues else ReviewStatus.PASS,
        issues=issues,
        detail=f"reviewed by {reviewer_model}; {len(issues)} issue(s)",
        author_model=author_model,
        reviewer_model=reviewer_model,
    )


async def cross_model_audit(
    files: Dict[str, str],
    author_model: Optional[str],
    reviewer_model: Optional[str],
    review_fn: Optional[ReviewFn],
) -> PassResult:
    """The Claudex-Loop rule, enforced: the auditor MUST be a different
    model from the author. Same model (or an unnamed author/reviewer)
    is self-grading, so the pass is UNAVAILABLE — it does not run and
    it does not pass."""
    name = "cross_model_audit"
    if not files:
        return PassResult(
            name=name,
            status=ReviewStatus.UNAVAILABLE,
            detail="no reviewable files were collected",
            author_model=author_model,
            reviewer_model=reviewer_model,
        )
    if not author_model:
        return PassResult(
            name=name,
            status=ReviewStatus.UNAVAILABLE,
            detail="author model unknown; independence of the audit cannot be established",
            author_model=author_model,
            reviewer_model=reviewer_model,
        )
    if reviewer_model and reviewer_model.strip() == author_model.strip():
        return PassResult(
            name=name,
            status=ReviewStatus.UNAVAILABLE,
            detail=(
                f"reviewer model equals author model ({author_model}); "
                "a model auditing its own output is self-grading, not an audit"
            ),
            author_model=author_model,
            reviewer_model=reviewer_model,
        )
    return await _run_model_pass(
        name,
        build_audit_prompt(files, author_model),
        review_fn,
        author_model,
        reviewer_model,
    )


async def red_team_review(
    files: Dict[str, str],
    reviewer_model: Optional[str],
    review_fn: Optional[ReviewFn],
    author_model: Optional[str] = None,
) -> PassResult:
    """Adversarial self-red-team pass. Independence is weaker by design
    (the point is the adversarial stance, not a second opinion), so a
    same-model red team is allowed but disclosed in the result detail —
    never hidden."""
    name = "red_team"
    if not files:
        return PassResult(
            name=name,
            status=ReviewStatus.UNAVAILABLE,
            detail="no reviewable files were collected",
            author_model=author_model,
            reviewer_model=reviewer_model,
        )
    result = await _run_model_pass(
        name, build_redteam_prompt(files), review_fn, author_model, reviewer_model
    )
    if (
        author_model
        and reviewer_model
        and reviewer_model.strip() == author_model.strip()
        and result.status is not ReviewStatus.UNAVAILABLE
    ):
        result.detail += (
            " (same-model red team: adversarial stance only, no model independence)"
        )
    return result


# ---------------------------------------------------------------------------
# Aggregate runner
# ---------------------------------------------------------------------------


async def run_review_passes(
    workspace: Path,
    author_model: Optional[str] = None,
    reviewer_model: Optional[str] = None,
    review_fn: Optional[ReviewFn] = None,
) -> ReviewReport:
    """Run all three passes over a workspace and aggregate honestly.

    ``review_fn`` is the deployment's model callable (e.g. backed by
    Inference). Without it, the model passes report UNAVAILABLE and the
    aggregate can never be PASS — by design.
    """
    workspace = Path(workspace)
    passes: List[PassResult] = [security_review_pass(workspace)]
    files = collect_review_files(workspace)
    passes.append(
        await cross_model_audit(files, author_model, reviewer_model, review_fn)
    )
    passes.append(
        await red_team_review(files, reviewer_model, review_fn, author_model)
    )
    return ReviewReport(workspace_path=str(workspace), passes=passes)
