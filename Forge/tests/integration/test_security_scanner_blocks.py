"""
Integration Test: Security Scanner Blocks Insecure Deliverables and Formats Re-Generation Feedback.
"""

import tempfile
from pathlib import Path

import pytest

from app.verification.security_scanner import (
    OutputSecurityScanner,
)


@pytest.fixture
def insecure_workspace():
    """Create a temporary workspace containing critical security vulnerabilities."""
    with tempfile.TemporaryDirectory() as tmpdir:
        ws = Path(tmpdir)

        # 1. Insecure Python file with hardcoded AWS secret and eval()
        py_code = """
import os

AWS_SECRET_KEY = "AKIA1234567890ABCDEF"

def execute_user_script(payload: str):
    # Critical RCE
    return eval(payload)
"""
        (ws / "main.py").write_text(py_code, encoding="utf-8")

        # 2. Insecure database file with SQL injection
        db_code = """
import sqlite3

def find_user(conn, uid: str):
    cursor = conn.cursor()
    # Critical SQL injection
    cursor.execute(f"SELECT * FROM users WHERE id = '{uid}'")
    return cursor.fetchall()
"""
        (ws / "db.py").write_text(db_code, encoding="utf-8")

        # 3. Vulnerable package in requirements.txt
        (ws / "requirements.txt").write_text("pillow==8.1.1\n", encoding="utf-8")

        yield ws


def test_security_scanner_blocks_insecure_deliverable(insecure_workspace: Path):
    """Verify that OutputSecurityScanner flags critical vulnerabilities and blocks delivery."""
    scanner = OutputSecurityScanner(insecure_workspace)
    report = scanner.scan_all()

    # 1. Must block delivery
    assert report.blocks_delivery is True
    assert report.passed is False
    assert report.critical_count >= 3  # Secret + eval + SQL injection + pillow CVE

    # 2. Check findings
    findings = {f.check_name: f for f in report.findings}
    assert any("Secret" in name for name in findings)
    assert any("eval" in name for name in findings)
    assert any("SQL Injection" in name for name in findings)

    # 3. Check feedback generation for AI-Universe re-synthesis
    feedback = scanner.format_feedback_for_regeneration(report)
    assert "SECURITY VULNERABILITIES DETECTED — RE-SYNTHESIS MANDATORY:" in feedback
    assert "main.py" in feedback
    assert "db.py" in feedback
