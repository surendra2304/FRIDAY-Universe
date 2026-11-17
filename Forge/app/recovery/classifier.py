"""
Failure Classifier for Project FORGE Recovery Subsystem.
Analyzes failed verification evidence, stack traces, and test output to classify root causes.
"""

import re
from enum import Enum

from pydantic import BaseModel

from app.verification.evidence import VerificationEvidence

# The phrasings with which this fleet actually reports a missing project
# module (TASK-REL-028): the interpreter's own "No module named 'x'", the
# runtime smoke checker's "Failed to import the required module 'x'", and
# the wrappers generated code raises ("Failed to import module 'x'" /
# "Failed to import 'name' from 'x'"). Only a bare top-level module name is
# captured; group 1 covers the first three shapes, group 2 the last.
_MISSING_MODULE_RE = re.compile(
    r"(?:No module named|Failed to import the required module|Failed to import module)"
    r" '([A-Za-z_][A-Za-z0-9_]*)'"
    r"|Failed to import '[^']+' from '([A-Za-z_][A-Za-z0-9_]*)'"
)

# Python's own phrasing when a from-import names something the target module
# does not define (TASK-FRG-005): "ImportError: cannot import name 'x' from
# 'y'". The repair target for this shape is neither x nor y -- it is the file
# doing the importing, which the traceback frames name.
_CANNOT_IMPORT_RE = re.compile(
    r"cannot import name '([A-Za-z_][A-Za-z0-9_]*)' from '([A-Za-z_][A-Za-z0-9_.]*)'"
)

# Traceback frames, in both spellings the fleet's checkers emit:
#   File "/path/to/main.py", line 1, in <module>      (interpreter)
#   main.py:1: in <module>                            (pytest short summary)
_FRAME_RE = re.compile(
    r'File "([^"]+\.py)", line \d+|([A-Za-z0-9_\-./\\]+\.py):\d+: in '
)


def _importing_file(text: str) -> str | None:
    """The project file whose import raised, from the traceback frames.

    The last frame before the error line is where the failing import
    statement lives. Test files are deprioritised (a test importing the
    project is the messenger, not the fix site) but used when nothing else
    is on the stack. Paths are normalised the way the recovery engine
    expects: forward slashes, relative to the project root when the
    workspace layout is visible in the path.
    """
    frames = []
    for m in _FRAME_RE.finditer(text):
        frames.append(m.group(1) or m.group(2))
    if not frames:
        return None

    def is_test(path: str) -> bool:
        base = path.replace("\\", "/").rsplit("/", 1)[-1]
        return base.startswith("test_") or base.endswith("_test.py") or "/tests/" in path.replace("\\", "/")

    chosen = None
    for frame in frames:
        if not is_test(frame):
            chosen = frame
    if chosen is None:
        chosen = frames[-1]
    chosen = chosen.replace("\\", "/")
    if "project/" in chosen:
        chosen = chosen.split("project/")[-1]
    elif chosen.startswith("/"):
        chosen = chosen.rsplit("/", 1)[-1]
    return chosen


class FailureClass(str, Enum):
    SYNTAX_ERROR = "syntax_error"
    DEPENDENCY_MISSING = "dependency_missing"
    LOGIC_BUG = "logic_bug"
    # TASK-FRG-013: the failure is in the generated TEST, not the code --
    # a golden value the test author invented from recall, disproven by
    # executing the implementation (see app/verification/golden_values).
    TEST_DEFECT = "test_defect"
    INTEGRATION_ERROR = "integration_error"
    TIMEOUT = "timeout"
    PERMISSION_DENIED = "permission_denied"
    ENVIRONMENT_ERROR = "environment_error"
    UNKNOWN = "unknown"


class FailureDiagnosis(BaseModel):
    failure_class: FailureClass
    failing_file: str | None = None
    failing_line: int | None = None
    #: The project file whose import statement raised (TASK-FRG-005). For a
    #: missing module the repair target stays the missing module's file (the
    #: create route consumes it); this names the fallback fix site for the
    #: routes that patch existing files when that target does not exist.
    importing_file: str | None = None
    error_message: str
    stack_trace: str | None = None
    suggested_strategy: str
    raw_evidence_summary: str = ""


class FailureClassifier:
    """Classifies verification errors into actionable failure classes and extracts stack frames."""

    def classify(self, evidence: VerificationEvidence) -> FailureDiagnosis:
        text = f"{evidence.stderr}\n{evidence.stdout}"

        # 0. TASK-FRG-013: the golden-value checker's failure is a TEST
        # defect by construction -- it only fails on golden values it
        # executed and proved fabricated, with the implementation
        # corroborated. It must never fall through to the LOGIC_BUG
        # reading below (its stderr names assertion-shaped text), which
        # would aim the repair ladder at correct code.
        if evidence.check_name == "Golden Value Verification":
            first_file = None
            for issue in evidence.issues or []:
                if isinstance(issue, dict) and issue.get("file"):
                    first_file = str(issue["file"])
                    break
            return FailureDiagnosis(
                failure_class=FailureClass.TEST_DEFECT,
                failing_file=first_file,
                error_message=(
                    "Generated test carries golden value(s) disproven by "
                    "executing the implementation; the test is the defect."
                ),
                stack_trace=text,
                suggested_strategy=(
                    "Replace each fabricated expected literal with the "
                    "value computed by executing the implementation "
                    "(deterministic golden correction route)."
                ),
                raw_evidence_summary=text[:300],
            )

        # 1. Syntax Error check (AST checker or Python runtime/linter)
        is_syntax = (
            "syntaxerror" in text.lower()
            or "indentationerror" in text.lower()
            or "taberror" in text.lower()
            or "invalid syntax" in text.lower()
            or "syntax error" in text.lower()
            or evidence.check_name == "Python AST Build & Syntax Check"
        )
        if is_syntax:
            file_match = re.search(
                r'(?:File "|[\'"]file[\'"]:\s*[\'"]|([a-zA-Z0-9_\-./\\]+\.py)[,\s]+line\s+)(\d+)?',
                text,
            )
            # Try structured dictionary match from AST checker: [{'file': 'main.py', 'line': 12
            dict_match = re.search(
                r"['\"]file['\"]:\s*['\"]([^'\"]+)['\"],\s*['\"]line['\"]:\s*(\d+)", text
            )
            file_path_match = re.search(r'File "([^"]+)", line (\d+)', text)
            paren_match = re.search(r"invalid syntax \(([^,]+),\s*line\s*(\d+)\)", text)

            failing_f = None
            failing_l = None

            if dict_match:
                failing_f = dict_match.group(1)
                failing_l = int(dict_match.group(2))
            elif file_path_match:
                failing_f = file_path_match.group(1)
                failing_l = int(file_path_match.group(2))
            elif paren_match:
                failing_f = paren_match.group(1)
                failing_l = int(paren_match.group(2))

            msg_match = re.search(
                r"(SyntaxError|IndentationError|TabError|invalid syntax)[\s:]*(.*)",
                text,
                re.IGNORECASE,
            )
            return FailureDiagnosis(
                failure_class=FailureClass.SYNTAX_ERROR,
                failing_file=failing_f,
                failing_line=failing_l,
                error_message=msg_match.group(0) if msg_match else "Syntax error detected",
                stack_trace=text,
                suggested_strategy="Inspect syntax error line and fix grammar, indentation, or unclosed delimiters.",
                raw_evidence_summary=text[:300],
            )

        # 2. Dependency Missing / Import Error
        module_match = _MISSING_MODULE_RE.search(text)
        cannot_import = _CANNOT_IMPORT_RE.search(text)
        if (
            "ModuleNotFoundError:" in text
            or "ImportError:" in text
            or "No module named" in text
            or module_match
        ):
            msg_match = re.search(r"(ModuleNotFoundError|ImportError): (.*)", text)
            missing_module = (
                (module_match.group(1) or module_match.group(2)) if module_match else None
            )
            importing = _importing_file(text)
            if cannot_import and importing:
                # "cannot import name 'x' from 'y'": y exists, x does not.
                # Nothing is missing on disk, so there is nothing to create;
                # the fix site is the importing file (correct the import or
                # the name it asks for). TASK-FRG-005: this shape used to
                # produce failing_file=None and every repair route aimed at
                # an arbitrary first project file -- or at nothing.
                return FailureDiagnosis(
                    failure_class=FailureClass.DEPENDENCY_MISSING,
                    failing_file=importing,
                    importing_file=importing,
                    error_message=(
                        msg_match.group(0)
                        if msg_match
                        else cannot_import.group(0)
                    ),
                    stack_trace=text,
                    suggested_strategy="Correct the imported name in the importing file, or define the name in the module it is imported from.",
                    raw_evidence_summary=text[:300],
                )
            return FailureDiagnosis(
                failure_class=FailureClass.DEPENDENCY_MISSING,
                # Name the missing module's file: it is the repair target
                # (TASK-REL-028's create route consumes exactly this).
                failing_file=f"{missing_module}.py" if missing_module else None,
                importing_file=importing,
                error_message=(
                    msg_match.group(0)
                    if msg_match
                    else module_match.group(0)
                    if module_match
                    else "Missing dependency or module"
                ),
                stack_trace=text,
                suggested_strategy="Add missing module or correct import path in project source.",
                raw_evidence_summary=text[:300],
            )

        # 3. Timeout Error
        if evidence.duration_ms > 30000 or "timed out" in text.lower() or "TimeoutError" in text:
            return FailureDiagnosis(
                failure_class=FailureClass.TIMEOUT,
                error_message="Execution timed out",
                stack_trace=text,
                suggested_strategy="Optimize slow loop or increase timeout boundary.",
                raw_evidence_summary=text[:300],
            )

        # 4. Permission Error
        if "PermissionError:" in text or "Access is denied" in text or "Security Violation" in text:
            return FailureDiagnosis(
                failure_class=FailureClass.PERMISSION_DENIED,
                error_message="Permission denied or sandbox violation",
                stack_trace=text,
                suggested_strategy="Verify file permissions and sandbox path constraints.",
                raw_evidence_summary=text[:300],
            )

        # 5. Logic Bug / Test Failure
        if (
            "AssertionError" in text
            or "FAILED (" in text
            or "FAILED tests" in text
            or "FAILED" in text
        ):
            file_match = re.search(r"([\w/\\._-]+\.py):(\d+): in ", text)
            return FailureDiagnosis(
                failure_class=FailureClass.LOGIC_BUG,
                failing_file=file_match.group(1) if file_match else None,
                failing_line=int(file_match.group(2)) if file_match else None,
                error_message="Assertion or logic check failure in test run",
                stack_trace=text,
                suggested_strategy="Adjust logic to satisfy expected assertion or fix boundary condition.",
                raw_evidence_summary=text[:300],
            )

        # Default fallback
        return FailureDiagnosis(
            failure_class=FailureClass.UNKNOWN,
            error_message=text[:120] if text.strip() else "Unknown verification failure",
            stack_trace=text,
            suggested_strategy="Perform deep diagnostic inspection using Debugger agent.",
            raw_evidence_summary=text[:300],
        )


failure_classifier = FailureClassifier()
