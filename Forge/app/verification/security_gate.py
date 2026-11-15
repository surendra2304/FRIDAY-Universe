"""
Output Security Gate for Project FORGE (TASK-FRG-008).

Why this exists
---------------
Forge already ships a capable AST scanner, ``OutputSecurityScanner``
(``app/verification/security_scanner.py``): hardcoded secrets, eval/exec,
os.system, subprocess with ``shell=True``, pickle and unsafe yaml.load,
SQL-injection patterns and a dependency CVE table. But before this task it
was only invoked on *opt-in* paths — the delegate endpoint's
``require_sentinel`` flag and the delivery packager's
``require_sentinel_gate`` flag. The default verification battery (the one
whose ``all_passed`` verdict decides whether a build is declared SUCCESS in
``app/api/delegate.py``) never ran it. The battery's own security checkers
cover secrets plus substring checks for eval/exec/os.system only.

This module closes that gap in two parts:

1. ``scan_extended_risks`` — AST rules for the classes neither the battery
   checkers nor ``OutputSecurityScanner`` covered:
   - command injection: ``os.popen``, the ``os.exec*``/``os.spawn*`` family,
     and subprocess calls whose ``shell=`` flag is a runtime-computed
     expression (unverifiable — generated code must not need one);
   - unsafe deserialization beyond pickle/yaml: ``marshal``, ``dill``,
     ``shelve`` (pickle-backed), ``jsonpickle.decode``, ``torch.load``
     without ``weights_only=True``, ``numpy.load`` with
     ``allow_pickle=True``;
   - path traversal: file sinks (``open``, ``send_file``, ``FileResponse``,
     ``os``/``shutil`` path mutators) whose path argument is *constructed*
     from variables (concatenation, f-string, ``%``/``.format``), literal
     ``..`` path segments, and ``os.path.join`` with dynamic trailing
     components (an absolute or ``..`` component silently discards the
     intended base directory).

2. ``OutputSecurityGateChecker`` — a battery checker that runs the full
   scan (``OutputSecurityScanner`` + extended rules) over the task's
   generated project and FAILS the battery when any CRITICAL or HIGH
   finding exists. It fails closed: a missing workspace or a scanner
   exception is a failed check, never a pass. Because delegate SUCCESS
   requires ``manifest.all_passed``, registering this checker in
   ``VerificationEngine`` makes the scan a hard gate on every build.

Findings never embed source text for secret matches (the underlying
scanner redacts them); extended-rule findings carry no source snippets at
all, only rule names and line numbers.
"""

from __future__ import annotations

import ast
import time
from pathlib import Path
from typing import Any

from app.core.logging import get_logger
from app.execution.engine import ExecutionEngine
from app.verification.checkers import BaseChecker
from app.verification.evidence import CheckCategory, VerificationEvidence
from app.verification.security_scanner import (
    OutputSecurityScanner,
    SecurityFinding,
    SecuritySeverity,
)

logger = get_logger("verification.security_gate")

_BLOCKING_SEVERITIES = {SecuritySeverity.CRITICAL, SecuritySeverity.HIGH}
_MAX_ISSUES_IN_EVIDENCE = 200

_SUBPROCESS_FUNCS = {"run", "call", "check_call", "check_output", "Popen", "getoutput", "getstatusoutput"}
_FILE_SINK_NAMES = {"open", "io.open", "send_file", "FileResponse", "send_from_directory"}
_PATH_MUTATOR_ATTRS = {
    "open", "remove", "rename", "replace", "unlink", "rmdir",
    "mkdir", "makedirs", "copy", "copy2", "move",
}
_SKIPPED_PARTS = {".git", "node_modules", "__pycache__"}


def _dotted_name(func: ast.expr) -> str:
    parts: list[str] = []
    cur: ast.expr = func
    while isinstance(cur, ast.Attribute):
        parts.append(cur.attr)
        cur = cur.value
    if isinstance(cur, ast.Name):
        parts.append(cur.id)
    return ".".join(reversed(parts))


def _is_dynamic_path_expr(node: ast.expr) -> bool:
    """True when a path argument is built from runtime values."""
    if isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Add, ast.Mod)):
        return True
    if isinstance(node, ast.JoinedStr):
        return any(isinstance(v, ast.FormattedValue) for v in node.values)
    if (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "format"
    ):
        return True
    return False


def _finding(
    check_name: str,
    severity: SecuritySeverity,
    rel_path: str,
    line: int,
    description: str,
    fix: str,
) -> SecurityFinding:
    return SecurityFinding(
        check_name=check_name,
        severity=severity,
        file_path=rel_path,
        line_number=line,
        snippet=f"{check_name} at line {line}",
        description=description,
        fix_suggestion=fix,
    )


def _scan_python_extended(rel_path: str, source: str) -> list[SecurityFinding]:
    findings: list[SecurityFinding] = []
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return findings

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        name = _dotted_name(node.func)
        base = name.split(".")[-1]
        root = name.split(".")[0]
        line = getattr(node, "lineno", 0)

        # --- command injection: os.popen / os.exec* / os.spawn* -----------
        if name == "os.popen":
            findings.append(_finding(
                "Command Injection (os.popen)", SecuritySeverity.HIGH, rel_path, line,
                "os.popen() executes a shell command string and is susceptible to command injection.",
                "Use subprocess.run([...], shell=False) with an explicit argument list.",
            ))
        elif root == "os" and (base.startswith("exec") or base.startswith("spawn")):
            findings.append(_finding(
                "Command Injection (os.exec/spawn family)", SecuritySeverity.HIGH, rel_path, line,
                f"os.{base}() replaces or spawns processes from generated code paths.",
                "Invoke subprocess.run([...], shell=False) instead of the os.exec/os.spawn family.",
            ))
        # --- command injection: unverifiable shell= flag -------------------
        elif root in ("subprocess", "commands") and base in _SUBPROCESS_FUNCS:
            for kw in node.keywords:
                if kw.arg == "shell" and not isinstance(kw.value, ast.Constant):
                    findings.append(_finding(
                        "Command Injection (unverifiable shell flag)", SecuritySeverity.HIGH,
                        rel_path, line,
                        "subprocess called with a runtime-computed shell= flag; the gate cannot verify it is False.",
                        "Pass shell=False literally and supply the command as an argument list.",
                    ))

        # --- unsafe deserialization (beyond pickle / yaml) -----------------
        if name in ("marshal.load", "marshal.loads"):
            findings.append(_finding(
                "Insecure Deserialization (marshal)", SecuritySeverity.HIGH, rel_path, line,
                "marshal deserialization of untrusted data is unsafe and must never process external input.",
                "Use JSON or another data-only format for untrusted payloads.",
            ))
        elif name in ("dill.load", "dill.loads"):
            findings.append(_finding(
                "Insecure Deserialization (dill)", SecuritySeverity.HIGH, rel_path, line,
                "dill deserialization executes arbitrary code during object reconstruction (pickle family).",
                "Use JSON or another data-only format for untrusted payloads.",
            ))
        elif name == "shelve.open":
            findings.append(_finding(
                "Insecure Deserialization (shelve)", SecuritySeverity.HIGH, rel_path, line,
                "shelve databases are pickle-backed; opening an untrusted shelf executes arbitrary code.",
                "Store data in JSON or SQLite instead of shelve.",
            ))
        elif name == "jsonpickle.decode":
            findings.append(_finding(
                "Insecure Deserialization (jsonpickle)", SecuritySeverity.HIGH, rel_path, line,
                "jsonpickle.decode() can instantiate arbitrary Python classes from encoded data.",
                "Use json.loads() with explicit schema validation.",
            ))
        elif name == "torch.load":
            has_weights_only = any(
                kw.arg == "weights_only"
                and isinstance(kw.value, ast.Constant)
                and kw.value.value is True
                for kw in node.keywords
            )
            if not has_weights_only:
                findings.append(_finding(
                    "Insecure Deserialization (torch.load)", SecuritySeverity.HIGH, rel_path, line,
                    "torch.load() without weights_only=True unpickles arbitrary code from the checkpoint file.",
                    "Pass weights_only=True or load state dicts from trusted sources only.",
                ))
        elif name in ("numpy.load", "np.load"):
            allow_pickle = any(
                kw.arg == "allow_pickle"
                and isinstance(kw.value, ast.Constant)
                and kw.value.value is True
                for kw in node.keywords
            )
            if allow_pickle:
                findings.append(_finding(
                    "Insecure Deserialization (numpy allow_pickle)", SecuritySeverity.HIGH,
                    rel_path, line,
                    "numpy.load(..., allow_pickle=True) unpickles embedded objects from the .npy file.",
                    "Load arrays with allow_pickle=False (the default) for untrusted files.",
                ))

        # --- path traversal --------------------------------------------------
        is_sink = (
            name in _FILE_SINK_NAMES
            or (base in _PATH_MUTATOR_ATTRS and root in ("os", "shutil", "pathlib"))
        )
        if is_sink and node.args:
            arg = node.args[0]
            if _is_dynamic_path_expr(arg):
                findings.append(_finding(
                    "Path Traversal (dynamic path construction)", SecuritySeverity.HIGH,
                    rel_path, line,
                    "A filesystem path is constructed from runtime values and passed to a file sink without containment validation.",
                    "Resolve the path against a fixed base directory and verify the result stays inside it before use.",
                ))
            elif (
                isinstance(arg, ast.Constant)
                and isinstance(arg.value, str)
                and ".." in arg.value.split("/")
            ):
                findings.append(_finding(
                    "Path Traversal (parent-directory literal)", SecuritySeverity.MEDIUM,
                    rel_path, line,
                    "A literal path containing '..' segments is passed to a file sink.",
                    "Address files inside the project tree without parent-directory segments.",
                ))
        if name == "os.path.join" and len(node.args) >= 2:
            if any(isinstance(a, (ast.Name, ast.Call, ast.Subscript)) for a in node.args[1:]):
                findings.append(_finding(
                    "Path Traversal (dynamic join component)", SecuritySeverity.MEDIUM,
                    rel_path, line,
                    "os.path.join() with a dynamic trailing component: an absolute or '..' component discards the base directory.",
                    "Validate the joined, resolved path remains inside the intended base directory.",
                ))
    return findings


def scan_extended_risks(project_dir: Path) -> list[SecurityFinding]:
    """Run the extended AST rules over every Python file in a project tree."""
    findings: list[SecurityFinding] = []
    for path in sorted(project_dir.rglob("*.py")):
        if any(part in _SKIPPED_PARTS for part in path.parts):
            continue
        try:
            source = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        rel_path = str(path.relative_to(project_dir))
        findings.extend(_scan_python_extended(rel_path, source))
    return findings


class OutputSecurityGateChecker(BaseChecker):
    """
    Verification-battery gate: scans generated code with the full output
    security scanner (plus the extended rules above) and fails the battery
    on any CRITICAL or HIGH finding. Fails closed on missing workspaces
    and scanner errors.
    """

    def __init__(self):
        super().__init__(name="Output Security Gate", category=CheckCategory.SECURITY)

    async def run_check(self, task_id: str, engine: ExecutionEngine) -> VerificationEvidence:
        start_time = time.perf_counter()

        def _evidence(**kw: Any) -> VerificationEvidence:
            kw.setdefault("duration_ms", round((time.perf_counter() - start_time) * 1000.0, 2))
            return VerificationEvidence(check_name=self.name, category=self.category, **kw)

        paths = engine.wm.get_workspace_paths(task_id)
        if not paths or not paths.project or not paths.project.exists():
            # Fail closed, mirroring BuildChecker's missing-workspace precedent:
            # no generated code to scan is not evidence of safe code.
            return _evidence(
                exit_code=2,
                passed=False,
                stderr="Cannot run output security gate: no workspace project was produced to scan.",
            )

        try:
            report = OutputSecurityScanner(paths.project).scan_all()
            findings = list(report.findings) + scan_extended_risks(paths.project)
        except Exception as e:
            logger.error(f"Output security gate scan failed for task '{task_id}': {e}")
            return _evidence(
                exit_code=1,
                passed=False,
                stderr=f"Output security scan failed to execute ({type(e).__name__}); failing closed.",
            )

        counts = {sev: 0 for sev in SecuritySeverity}
        for f in findings:
            counts[f.severity] = counts.get(f.severity, 0) + 1
        blocking = [f for f in findings if f.severity in _BLOCKING_SEVERITIES]
        passed = len(blocking) == 0

        issues = [
            {
                "file": f.file_path,
                "line": f.line_number,
                "rule": f.check_name,
                "severity": f.severity.value,
            }
            for f in findings[:_MAX_ISSUES_IN_EVIDENCE]
        ]
        artifacts = sorted({f.file_path for f in findings})

        stdout = (
            f"Scanned {report.scanned_files_count} files: "
            f"{counts[SecuritySeverity.CRITICAL]} critical, {counts[SecuritySeverity.HIGH]} high, "
            f"{counts[SecuritySeverity.MEDIUM]} medium, {counts[SecuritySeverity.LOW]} low findings."
        )
        if len(findings) > _MAX_ISSUES_IN_EVIDENCE:
            stdout += f" Issues list truncated at {_MAX_ISSUES_IN_EVIDENCE} of {len(findings)}."

        return _evidence(
            command="output_security_gate(OutputSecurityScanner.scan_all + extended_rules)",
            exit_code=0 if passed else 1,
            passed=passed,
            stdout=stdout,
            stderr=(
                ""
                if passed
                else f"Output security gate blocked: {len(blocking)} critical/high findings in generated code."
            ),
            artifacts_inspected=artifacts,
            issues=issues,
        )
