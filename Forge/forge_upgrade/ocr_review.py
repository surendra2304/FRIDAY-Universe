"""Open Code Review (``ocr``) supplement for Forge (TASK-IG2-FRG-03).

Wires Alibaba's open-code-review CLI (alibaba/open-code-review,
Apache-2.0) into Forge's PR-review tooling as a *supplement*:

* Delegation Mode is the default — the host coding agent supplies the
  model, OCR supplies deterministic file selection and its ruleset;
  no separate API key and no added cost.
* OCR's recall is deliberately low (vendor's own design; its headline
  benchmark is Alibaba's own AACR-Bench, not independently replicated),
  so its result NEVER gates a merge and NEVER replaces or upgrades
  Forge's existing review verdict. It can only add findings.
* If the ``ocr`` binary is absent, the pass reports UNAVAILABLE —
  the existing review proceeds exactly as before.

CLI shape (TASK-FRG-028, verified live 2026-11-25 against ocr
v1.14.3): delegation is a *subcommand*, not a flag — ``ocr delegate
preview`` lists the reviewable files and ``ocr delegate rule <files>``
prints the resolved ruleset, both with no LLM and no provider
configured. ``ocr review`` takes ``--from`` (not ``--base``), takes no
``--file`` and no ``--delegate`` flag, and needs a configured LLM
provider; it is therefore opt-in only (``provider_review=True``) and
never runs by default. The wave-2 command builder (``ocr review
--base main --format json --delegate --file ...``) matched no shipped
CLI flag and would have failed on every invocation; it is replaced
here.
"""
from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

# Files deterministic selection never sends to a judgement pass:
# binaries, lockfiles, generated output and vendored trees cannot be
# line-reviewed meaningfully and only burn tokens.
SKIP_SUFFIXES = {
    ".lock", ".png", ".jpg", ".jpeg", ".gif", ".ico", ".pdf", ".zip",
    ".whl", ".pyc", ".min.js", ".min.css", ".map",
}
SKIP_PARTS = {"node_modules", ".git", "__pycache__", "dist", "build", "vendor"}
SKIP_NAMES = {"package-lock.json", "yarn.lock", "poetry.lock", "uv.lock"}


@dataclass(frozen=True, slots=True)
class OcrFinding:
    file: str
    line: int
    severity: str
    rule: str
    message: str


@dataclass(slots=True)
class OcrResult:
    status: str  # "completed" | "unavailable" | "failed"
    detail: str
    findings: list[OcrFinding] = field(default_factory=list)


def ocr_status() -> tuple[bool, str]:
    exe = shutil.which("ocr")
    if exe:
        return True, f"ocr CLI at {exe}"
    return (
        False,
        "ocr CLI not installed; install with "
        "`npm install -g @alibaba-group/open-code-review` (on-demand tool)",
    )


def select_review_files(changed_files: list[str]) -> list[str]:
    """Deterministically select which changed files the pass reviews.

    Mirrors OCR's core idea — engineering, not the model, decides the
    review set — so no changed source file is silently skipped, while
    binaries/lockfiles/generated files are excluded by rule.
    """
    selected = []
    for name in changed_files:
        path = Path(name)
        if path.name in SKIP_NAMES:
            continue
        if any(part in SKIP_PARTS for part in path.parts):
            continue
        if path.suffix.lower() in SKIP_SUFFIXES:
            continue
        if ".generated." in path.name:
            continue
        selected.append(name)
    return sorted(selected)


def build_delegate_preview_command(base: str | None = None) -> list[str]:
    """Build the ``ocr delegate preview`` invocation.

    No LLM, no provider: lists the files OCR would review. With ``base``
    the preview covers that ref range (``--from``); without it the
    workspace changes are previewed.
    """
    cmd = ["ocr", "delegate", "preview"]
    if base:
        cmd.extend(["--from", base])
    return cmd


def build_delegate_rule_command(files: list[str]) -> list[str]:
    """Build the ``ocr delegate rule <files>`` invocation.

    No LLM, no provider: prints the resolved review ruleset for the
    given files, grouped by content. This is the deterministic half of
    Delegation Mode — the rules the host agent judges against.
    """
    return ["ocr", "delegate", "rule", *files]


def build_ocr_review_command(base: str = "main") -> list[str]:
    """Build the provider-backed ``ocr review`` invocation.

    Only valid when an LLM provider is configured; never used by the
    default pass. ``--from`` is the real flag (``--base`` does not
    exist in ocr v1.14.3) and there is no ``--file`` / ``--delegate``
    flag on this subcommand.
    """
    return ["ocr", "review", "--from", base, "--format", "json"]


def parse_ocr_json(output: str) -> list[OcrFinding]:
    """Parse ``ocr --format json`` output into findings.

    Accepts either a bare list or an object with a ``comments`` /
    ``findings`` list. Unparseable output raises ValueError — callers
    must surface that as a failed pass, never as "no findings".
    """
    data = json.loads(output)
    items = data if isinstance(data, list) else data.get("comments", data.get("findings", []))
    findings = []
    for item in items:
        findings.append(
            OcrFinding(
                file=str(item.get("file", item.get("path", ""))),
                line=int(item.get("line", 0) or 0),
                severity=str(item.get("severity", "info")),
                rule=str(item.get("rule", item.get("rule_id", ""))),
                message=str(item.get("message", item.get("comment", ""))),
            )
        )
    return findings


def _count_rule_groups(output: str) -> int:
    """Count ``### Rule Group N:`` headings in delegate-rule output."""
    return sum(
        1 for line in output.splitlines()
        if line.startswith("### Rule Group ")
    )


def run_ocr_review(
    changed_files: list[str],
    base: str = "main",
    workdir: str | Path | None = None,
    provider_review: bool = False,
    runner=subprocess.run,
) -> OcrResult:
    """Run the ocr pass over the selected files, if the CLI exists.

    Default (Delegation Mode, no LLM): ``ocr delegate rule`` over the
    selected files. A completed delegate pass carries no findings —
    findings only come from an LLM judgement — so the result reports
    the ruleset fetched and leaves findings empty; callers must not
    read that as "the code is clean". With ``provider_review=True``
    the pass additionally runs provider-backed ``ocr review`` and
    parses its JSON findings; that path needs a configured provider
    and is never taken by default.
    """
    available, detail = ocr_status()
    if not available:
        return OcrResult("unavailable", detail)
    files = select_review_files(changed_files)
    if not files:
        return OcrResult("completed", "no reviewable files in the change set")
    if not provider_review:
        proc = runner(
            build_delegate_rule_command(files),
            capture_output=True,
            text=True,
            timeout=600,
            cwd=str(workdir) if workdir is not None else None,
        )
        if proc.returncode != 0:
            return OcrResult("failed", (proc.stderr or proc.stdout or "")[-500:])
        groups = _count_rule_groups(proc.stdout or "")
        return OcrResult(
            "completed",
            f"delegate pass: rules fetched for {len(files)} files "
            f"({groups} rule groups); no LLM judgement run, no findings",
        )
    proc = runner(
        build_ocr_review_command(base=base),
        capture_output=True,
        text=True,
        timeout=1200,
        cwd=str(workdir) if workdir is not None else None,
    )
    if proc.returncode != 0:
        return OcrResult("failed", (proc.stderr or proc.stdout or "")[-500:])
    try:
        findings = parse_ocr_json(proc.stdout)
    except (ValueError, TypeError) as exc:
        return OcrResult("failed", f"unparseable ocr output: {exc}")
    return OcrResult(
        "completed", f"ocr reviewed {len(files)} files", findings=findings
    )


@dataclass(slots=True)
class SupplementedReview:
    """Existing verdict, unchanged, plus whatever OCR added."""

    gate_verdict: str  # exactly the existing review's verdict
    gate_changed_by_ocr: bool  # always False — pinned by tests
    ocr_status: str
    ocr_findings: list[OcrFinding] = field(default_factory=list)
    note: str = ""


def supplement_review(existing_verdict: str, ocr: OcrResult) -> SupplementedReview:
    """Attach an OCR result to an existing review verdict.

    The gate verdict is returned byte-for-byte unchanged regardless of
    what OCR found or whether it ran at all: OCR supplements the
    existing independent review, it is never a replacement gate.
    """
    note = (
        "OCR is a supplement with deliberately low recall; "
        "the existing review verdict stands."
    )
    if ocr.status != "completed":
        note = f"OCR pass {ocr.status} ({ocr.detail}); existing review stands."
    return SupplementedReview(
        gate_verdict=existing_verdict,
        gate_changed_by_ocr=False,
        ocr_status=ocr.status,
        ocr_findings=list(ocr.findings),
        note=note,
    )
