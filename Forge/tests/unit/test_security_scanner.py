"""
Unit Tests for Output Security Scanner and Security-First Verification in Project FORGE.
"""

import tempfile
from pathlib import Path

import pytest

from app.verification.security_scanner import (
    OutputSecurityScanner,
)


@pytest.fixture
def temp_workspace():
    """Create a temporary workspace directory for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


def test_secrets_scanning_and_redaction(temp_workspace: Path):
    """Test detection of hardcoded AWS keys, OpenAI keys, and DB URIs with redaction."""
    bad_code = """
# Insecure configuration file
AWS_KEY = "AKIA1234567890ABCDEF"
OPENAI_TOKEN = "sk-abcdefghijklmnopqrstuvwxyz1234567890"
DB_URI = "postgresql://admin:supersecretpassword123@localhost:5432/production_db"
"""
    (temp_workspace / "config.py").write_text(bad_code, encoding="utf-8")

    scanner = OutputSecurityScanner(temp_workspace)
    report = scanner.scan_all()

    assert report.blocks_delivery is True
    assert report.critical_count >= 2

    # Check redaction
    for f in report.findings:
        if "Secret" in f.check_name:
            assert "***REDACTED***" in f.snippet
            assert "supersecretpassword123" not in f.snippet
            assert "AKIA1234567890ABCDEF" not in f.snippet


def test_dangerous_ast_functions_detection(temp_workspace: Path):
    """Test AST detection of eval, exec, os.system, and subprocess shell=True."""
    dangerous_code = """
import os
import subprocess
import pickle

def run_untrusted(user_input):
    eval(user_input)
    exec("print('executing dynamic statement')")
    os.system(f"echo {user_input}")
    subprocess.run(f"ls {user_input}", shell=True)
    pickle.loads(user_input)
"""
    (temp_workspace / "runner.py").write_text(dangerous_code, encoding="utf-8")

    scanner = OutputSecurityScanner(temp_workspace)
    report = scanner.scan_all()

    assert report.blocks_delivery is True
    assert report.critical_count >= 2  # eval, exec, subprocess shell=True
    assert report.high_count >= 2  # os.system, pickle

    findings_checks = [f.check_name for f in report.findings]
    assert any("eval" in c for c in findings_checks)
    assert any("exec" in c for c in findings_checks)
    assert any("os.system" in c for c in findings_checks)
    assert any("subprocess shell=True" in c for c in findings_checks)
    assert any("pickle" in c for c in findings_checks)


def test_sql_injection_and_xss_detection(temp_workspace: Path):
    """Test SQL string concatenation and DOM innerHTML XSS detection."""
    sql_code = """
import sqlite3

def query_user(username):
    conn = sqlite3.connect("db.sqlite")
    cursor = conn.cursor()
    # Insecure f-string SQL
    cursor.execute(f"SELECT * FROM users WHERE username = '{username}'")
    # Insecure concatenation
    cursor.execute("SELECT * FROM items WHERE id = " + username)
"""
    (temp_workspace / "db_ops.py").write_text(sql_code, encoding="utf-8")

    js_code = """
function displayUser(data) {
    const box = document.getElementById("profile");
    // Insecure innerHTML
    box.innerHTML = data.bio;
}
"""
    (temp_workspace / "app.js").write_text(js_code, encoding="utf-8")

    scanner = OutputSecurityScanner(temp_workspace)
    report = scanner.scan_all()

    assert report.blocks_delivery is True
    assert report.critical_count >= 2  # SQL injections
    assert report.high_count >= 1  # DOM XSS

    finding_checks = [f.check_name for f in report.findings]
    assert any("SQL Injection" in c for c in finding_checks)
    assert any("XSS" in c for c in finding_checks)


def test_cve_dependency_scanning_and_remediation(temp_workspace: Path):
    """Test detection of vulnerable packages and automated upgrade remediation."""
    # Write vulnerable requirements.txt
    reqs_content = "urllib3==1.26.4\npillow==8.1.1\nfastapi>=0.110.0\n"
    (temp_workspace / "requirements.txt").write_text(reqs_content, encoding="utf-8")

    scanner = OutputSecurityScanner(temp_workspace)
    report = scanner.scan_all()

    assert report.blocks_delivery is True
    cve_findings = [f for f in report.findings if f.cve_id is not None]
    assert len(cve_findings) >= 2
    assert any("CVE-2021-33503" == f.cve_id for f in cve_findings)
    assert any("CVE-2021-27921" == f.cve_id for f in cve_findings)

    # Perform automated remediation
    remediated = scanner.remediate_vulnerable_dependencies()
    assert len(remediated) >= 2
    assert any("urllib3" in r for r in remediated)
    assert any("pillow" in r for r in remediated)

    # Check updated requirements.txt and requirements.lock
    updated_reqs = (temp_workspace / "requirements.txt").read_text(encoding="utf-8")
    assert "urllib3>=1.26.18" in updated_reqs
    assert "pillow>=10.2.0" in updated_reqs

    lock_file = temp_workspace / "requirements.lock"
    assert lock_file.exists()

    # Re-scan after remediation
    rescan_report = scanner.scan_all()
    assert rescan_report.blocks_delivery is False
    assert len(rescan_report.findings) == 0


def test_clean_workspace_passes_security_scanner(temp_workspace: Path):
    """Test that secure parameterized code passes with zero blocking findings."""
    clean_python = """
import os
from pydantic import BaseModel, Field

class UserModel(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)

def fetch_user(cursor, username: str):
    # Secure parameterized query
    cursor.execute("SELECT id, username FROM users WHERE username = ?", (username,))
    return cursor.fetchone()
"""
    (temp_workspace / "secure_service.py").write_text(clean_python, encoding="utf-8")

    clean_js = """
document.addEventListener("DOMContentLoaded", () => {
    const el = document.getElementById("title");
    if (el) {
        el.textContent = "Welcome to FORGE";
    }
});
"""
    (temp_workspace / "app.js").write_text(clean_js, encoding="utf-8")

    scanner = OutputSecurityScanner(temp_workspace)
    report = scanner.scan_all()

    assert report.passed is True
    assert report.blocks_delivery is False
    assert report.critical_count == 0
    assert report.high_count == 0


def test_regeneration_feedback_formatting(temp_workspace: Path):
    """Test constructing formatted feedback for AI-Universe re-synthesis."""
    bad_code = """
def run_cmd(arg):
    eval(arg)
"""
    (temp_workspace / "bad.py").write_text(bad_code, encoding="utf-8")

    scanner = OutputSecurityScanner(temp_workspace)
    report = scanner.scan_all()
    feedback = scanner.format_feedback_for_regeneration(report)

    assert "SECURITY VULNERABILITIES DETECTED — RE-SYNTHESIS MANDATORY:" in feedback
    assert "Dangerous Function (eval)" in feedback
    assert "bad.py" in feedback
