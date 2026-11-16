"""TASK-IG2-FRG-08: the Claudex Loop — build/audit role-swap until agreement.

Corpus source: DdRxjWhlrNC (package G-13) — route work across models
so one model plans/builds and a DIFFERENT model audits; then the
roles swap and the loop continues until both agree the work is clean.
The point of the pattern is killing self-grading: no model ever signs
off its own output.

What Forge already had (TASK-IG-FRG-01, ``review_passes.py``): the
single cross-model audit pass, with the independence rule enforced —
``cross_model_audit`` refuses (UNAVAILABLE) when reviewer == author.
What it did not have is the LOOP: the iteration, the swap, the
findings fed back into the next build, and an honest terminal state.
This module is that loop, composed over the existing audit — it does
not re-implement the audit, and it inherits the audit's honesty rules:

* ``AGREED`` is reported only when an audit actually ran and returned
  PASS. Nothing else is ever called agreement.
* An audit that could not run (``UNAVAILABLE`` — same model, missing
  provider, unparseable verdict) STOPS the loop immediately with
  status ``UNAVAILABLE``. Looping past an audit that never happened
  would manufacture agreement out of absence of evidence.
* Reaching the round cap with findings still open is ``EXHAUSTED`` —
  a real outcome, reported as itself, never dressed up as AGREED.
* A build that raises, replies unparseably, or returns an empty file
  set is ``BUILD_FAILED`` — distinct from exhaustion: the loop never
  got an auditable artefact that round.

Shape: like ``review_passes``, this module performs no network I/O of
its own. The deployment injects ``build_fn`` (a model callable wired
to Inference via ``app.providers``) and either an ``audit_fn`` or a
``review_fn`` for the default audit (``cross_model_audit``). Tests
inject fakes. The builder receives the goal, the current file set,
and the previous round's findings as data, and must reply with the
COMPLETE new file set as strict JSON — ``{"files": {"path": "…"}}``
or a bare ``{"path": "…"}`` object (see :func:`build_loop_prompt`
for the prompt a deployment sends).
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Awaitable, Callable, Dict, List, Optional

from app.verification.review_passes import PassResult, ReviewStatus, cross_model_audit

# (goal, current_files, previous_findings_as_dicts) -> raw reply text.
BuildFn = Callable[[str, Dict[str, str], List[dict]], Awaitable[str]]
# (files, author_model, auditor_model) -> the audit's PassResult.
AuditFn = Callable[[Dict[str, str], str, str], Awaitable[PassResult]]
# Prompt-in / text-out model callable for the default audit path.
ReviewFn = Callable[[str], Awaitable[str]]

DEFAULT_MAX_ROUNDS = 3


class LoopStatus(str, Enum):
    AGREED = "AGREED"  # an audit ran and passed — the two models agree
    EXHAUSTED = "EXHAUSTED"  # round cap reached with findings still open
    UNAVAILABLE = "UNAVAILABLE"  # an audit could not run; loop stopped
    BUILD_FAILED = "BUILD_FAILED"  # a build produced nothing auditable


@dataclass
class LoopRound:
    round_number: int
    builder_model: str
    auditor_model: str
    audit_status: str  # ReviewStatus value of the audit that round
    issues: List[dict] = field(default_factory=list)
    detail: str = ""

    def to_dict(self) -> dict:
        return {
            "round_number": self.round_number,
            "builder_model": self.builder_model,
            "auditor_model": self.auditor_model,
            "audit_status": self.audit_status,
            "issues": self.issues,
            "detail": self.detail,
        }


@dataclass
class ClaudexLoopResult:
    status: LoopStatus
    rounds: List[LoopRound] = field(default_factory=list)
    files: Dict[str, str] = field(default_factory=dict)  # last built file set
    detail: str = ""

    def to_dict(self) -> dict:
        return {
            "status": self.status.value,
            "rounds": [r.to_dict() for r in self.rounds],
            "files": sorted(self.files),
            "detail": self.detail,
        }


# ---------------------------------------------------------------------------
# Builder prompt + reply parsing
# ---------------------------------------------------------------------------

_BUILD_INSTRUCTION = (
    "Reply with ONLY a JSON object, no prose, in exactly this shape:\n"
    '{"files": {"<path>": "<complete file content>", ...}}\n'
    "Return the COMPLETE file set for the project, not a diff: files "
    "you omit are deleted."
)


def build_loop_prompt(
    goal: str,
    files: Dict[str, str],
    findings: List[dict],
    builder_model: str,
    auditor_model: str,
) -> str:
    """The prompt a deployment's build_fn sends the builder model.
    Pure function. States the loop's terms up front: a different model
    audits this build, and next round the roles swap — the builder
    knows its work is not self-graded."""
    parts = [
        f"You are the BUILDER model ({builder_model}) in a two-model "
        f"build/audit loop. A different model ({auditor_model}) will "
        "audit your output; next round the roles swap and you audit "
        "theirs. Build the goal below as a complete file set.",
        "",
        f"GOAL: {goal}",
    ]
    if files:
        parts += ["", "Current file set (your starting point):"]
        for path in sorted(files):
            parts.append(f"===== FILE: {path} =====\n{files[path]}")
    if findings:
        parts += [
            "",
            "The auditor's findings on the previous build — fix every "
            "one of these; do not reintroduce them:",
        ]
        for finding in findings:
            parts.append(
                f"- [{finding.get('severity', 'MEDIUM')}] "
                f"{finding.get('file_path', '<unknown>')}: "
                f"{finding.get('description', '')}"
            )
    parts += ["", _BUILD_INSTRUCTION]
    return "\n".join(parts)


def parse_build_reply(text: Optional[str]) -> Optional[Dict[str, str]]:
    """Strict parsing of a builder reply into a file set. Returns the
    ``{path: content}`` dict, or ``None`` when the reply is not a
    usable file set — the caller must treat that as BUILD_FAILED,
    never as an empty-but-valid build."""
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
    files = payload.get("files", payload)
    if not isinstance(files, dict) or not files:
        return None
    for path, content in files.items():
        if not isinstance(path, str) or not path or not isinstance(content, str):
            return None
    return dict(files)


# ---------------------------------------------------------------------------
# The loop
# ---------------------------------------------------------------------------


async def run_claudex_loop(
    goal: str,
    model_a: str,
    model_b: str,
    build_fn: BuildFn,
    audit_fn: Optional[AuditFn] = None,
    review_fn: Optional[ReviewFn] = None,
    max_rounds: int = DEFAULT_MAX_ROUNDS,
    initial_files: Optional[Dict[str, str]] = None,
) -> ClaudexLoopResult:
    """Run build -> cross-model audit -> swap, until agreement.

    Round 1: ``model_a`` builds, ``model_b`` audits. Round 2 swaps,
    and so on. The auditor's findings are fed to the next builder as
    data. Terminal states are exactly the four :class:`LoopStatus`
    values — see the module docstring for what each one guarantees.

    Raises ValueError on programmer error (same model twice, unnamed
    model, max_rounds < 1): a loop configured to self-grade is a
    defect in the caller, refused loudly rather than reported as a
    loop outcome.
    """
    if not model_a or not model_b:
        raise ValueError("both models must be named; an unnamed model cannot be audited")
    if model_a.strip() == model_b.strip():
        raise ValueError(
            f"builder and auditor are the same model ({model_a}); "
            "the Claudex Loop exists to prevent self-grading"
        )
    if max_rounds < 1:
        raise ValueError("max_rounds must be >= 1")

    if audit_fn is None:

        async def _default_audit(
            files: Dict[str, str], author: str, auditor: str
        ) -> PassResult:
            return await cross_model_audit(files, author, auditor, review_fn)

        audit_fn = _default_audit

    files: Dict[str, str] = dict(initial_files or {})
    findings: List[dict] = []
    rounds: List[LoopRound] = []

    for round_number in range(1, max_rounds + 1):
        builder, auditor = (
            (model_a, model_b) if round_number % 2 == 1 else (model_b, model_a)
        )
        try:
            raw = await build_fn(goal, dict(files), list(findings))
        except Exception as exc:  # the build did not happen — say so
            return ClaudexLoopResult(
                status=LoopStatus.BUILD_FAILED,
                rounds=rounds,
                files=files,
                detail=f"round {round_number}: builder {builder} raised: {exc!r}",
            )
        built = parse_build_reply(raw)
        if built is None:
            return ClaudexLoopResult(
                status=LoopStatus.BUILD_FAILED,
                rounds=rounds,
                files=files,
                detail=(
                    f"round {round_number}: builder {builder} returned no usable "
                    "file set (unparseable or empty reply)"
                ),
            )
        files = built
        audit = await audit_fn(files, builder, auditor)
        rounds.append(
            LoopRound(
                round_number=round_number,
                builder_model=builder,
                auditor_model=auditor,
                audit_status=audit.status.value,
                issues=[i.to_dict() for i in audit.issues],
                detail=audit.detail,
            )
        )
        if audit.status is ReviewStatus.PASS:
            return ClaudexLoopResult(
                status=LoopStatus.AGREED,
                rounds=rounds,
                files=files,
                detail=(
                    f"agreement in round {round_number}: {auditor} audited "
                    f"{builder}'s build and found nothing"
                ),
            )
        if audit.status is ReviewStatus.UNAVAILABLE:
            return ClaudexLoopResult(
                status=LoopStatus.UNAVAILABLE,
                rounds=rounds,
                files=files,
                detail=(
                    f"round {round_number}: audit did not run ({audit.detail}); "
                    "loop stopped — an audit that never happened cannot be "
                    "looped past or counted as agreement"
                ),
            )
        findings = [i.to_dict() for i in audit.issues]

    return ClaudexLoopResult(
        status=LoopStatus.EXHAUSTED,
        rounds=rounds,
        files=files,
        detail=(
            f"no agreement after {max_rounds} round(s); "
            f"{len(findings)} finding(s) still open — reported as exhausted, "
            "not as agreed"
        ),
    )
