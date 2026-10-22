"""
Failure Classifier for Project FORGE Recovery Subsystem.
Analyzes failed verification evidence, stack traces, and test output to classify root causes.
"""

import re
from enum import Enum

from pydantic import BaseModel

from app.verification.evidence import VerificationEvidence


class FailureClass(str, Enum):
    SYNTAX_ERROR = "syntax_error"
    DEPENDENCY_MISSING = "dependency_missing"
    LOGIC_BUG = "logic_bug"
    INTEGRATION_ERROR = "integration_error"
    TIMEOUT = "timeout"
    PERMISSION_DENIED = "permission_denied"
    ENVIRONMENT_ERROR = "environment_error"
    UNKNOWN = "unknown"


class FailureDiagnosis(BaseModel):
    failure_class: FailureClass
    failing_file: str | None = None
    failing_line: int | None = None
    error_message: str
    stack_trace: str | None = None
    suggested_strategy: str
    raw_evidence_summary: str = ""


class FailureClassifier:
    """Classifies verification errors into actionable failure classes and extracts stack frames."""

    def classify(self, evidence: VerificationEvidence) -> FailureDiagnosis:
        text = f"{evidence.stderr}\n{evidence.stdout}"

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
        if "ModuleNotFoundError:" in text or "ImportError:" in text or "No module named" in text:
            msg_match = re.search(r"(ModuleNotFoundError|ImportError): (.*)", text)
            return FailureDiagnosis(
                failure_class=FailureClass.DEPENDENCY_MISSING,
                error_message=msg_match.group(0) if msg_match else "Missing dependency or module",
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
