"""TASK-IG-FRG-01: independent review passes over generated code.

Corpus sources: Dc_iv4YKCAh (self-red-team), DdRxjWhlrNC (cross-model
audit — a different model reviews than wrote), DeihJQuCpdp (dedicated
security review pass, SQL injection / XSS focus).

The properties pinned here are the honesty properties:

* a same-model "audit" is self-grading -> UNAVAILABLE, never PASS;
* a missing/failing reviewer or an unparseable verdict -> UNAVAILABLE;
* the aggregate can only be PASS when every pass actually ran clean;
* the deterministic security pass really flags SQL injection / XSS.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.verification.review_passes import (
    ReviewStatus,
    build_audit_prompt,
    build_redteam_prompt,
    collect_review_files,
    cross_model_audit,
    red_team_review,
    run_review_passes,
    security_review_pass,
)


def _write(root: Path, rel: str, content: str) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


SQLI_CODE = '''
import sqlite3

def find_user(conn, name):
    query = f"SELECT * FROM users WHERE name = '{name}'"
    return conn.execute(query).fetchall()
'''

CLEAN_CODE = '''
import sqlite3

def find_user(conn, name):
    return conn.execute(
        "SELECT * FROM users WHERE name = ?", (name,)
    ).fetchall()
'''


# ---------------------------------------------------------------------------
# Deterministic security pass
# ---------------------------------------------------------------------------


def test_security_pass_flags_sql_injection(tmp_path):
    _write(tmp_path, "app.py", SQLI_CODE)
    result = security_review_pass(tmp_path)
    assert result.status is ReviewStatus.FINDINGS
    assert any("SQL Injection" in i.description for i in result.issues)


def test_security_pass_clean_code_passes(tmp_path):
    _write(tmp_path, "app.py", CLEAN_CODE)
    result = security_review_pass(tmp_path)
    assert result.status is ReviewStatus.PASS
    assert result.issues == []


def test_security_pass_flags_jinja_safe_filter(tmp_path):
    _write(tmp_path, "templates/page.html", "<div>{{ user_bio | safe }}</div>")
    result = security_review_pass(tmp_path)
    assert result.status is ReviewStatus.FINDINGS
    assert any("safe" in i.description for i in result.issues)


def test_security_pass_flags_innerhtml_in_template(tmp_path):
    _write(
        tmp_path,
        "templates/page.html",
        "<script>el.innerHTML = location.hash;</script>",
    )
    result = security_review_pass(tmp_path)
    assert result.status is ReviewStatus.FINDINGS


def test_security_pass_missing_workspace_is_unavailable(tmp_path):
    result = security_review_pass(tmp_path / "does-not-exist")
    assert result.status is ReviewStatus.UNAVAILABLE


# ---------------------------------------------------------------------------
# Cross-model audit: independence is enforced, failures fail closed
# ---------------------------------------------------------------------------


async def _ok_fn(prompt: str) -> str:
    return json.dumps({"verdict": "pass", "issues": []})


async def _findings_fn(prompt: str) -> str:
    return json.dumps(
        {
            "verdict": "findings",
            "issues": [
                {
                    "file": "app.py",
                    "line": 4,
                    "severity": "HIGH",
                    "description": "SQL built by f-string",
                }
            ],
        }
    )


async def _garbage_fn(prompt: str) -> str:
    return "Looks fine to me, ship it!"


async def _boom_fn(prompt: str) -> str:
    raise RuntimeError("provider down")


@pytest.mark.asyncio
async def test_cross_model_audit_pass():
    files = {"app.py": CLEAN_CODE}
    result = await cross_model_audit(files, "model-a", "model-b", _ok_fn)
    assert result.status is ReviewStatus.PASS
    assert result.reviewer_model == "model-b"


@pytest.mark.asyncio
async def test_cross_model_audit_findings():
    files = {"app.py": SQLI_CODE}
    result = await cross_model_audit(files, "model-a", "model-b", _findings_fn)
    assert result.status is ReviewStatus.FINDINGS
    assert result.issues[0].severity == "HIGH"
    assert result.issues[0].line_number == 4


@pytest.mark.asyncio
async def test_cross_model_audit_same_model_is_unavailable():
    files = {"app.py": CLEAN_CODE}
    result = await cross_model_audit(files, "model-a", "model-a", _ok_fn)
    assert result.status is ReviewStatus.UNAVAILABLE
    assert "self-grading" in result.detail


@pytest.mark.asyncio
async def test_cross_model_audit_unknown_author_is_unavailable():
    files = {"app.py": CLEAN_CODE}
    result = await cross_model_audit(files, None, "model-b", _ok_fn)
    assert result.status is ReviewStatus.UNAVAILABLE


@pytest.mark.asyncio
async def test_cross_model_audit_no_provider_is_unavailable():
    files = {"app.py": CLEAN_CODE}
    result = await cross_model_audit(files, "model-a", "model-b", None)
    assert result.status is ReviewStatus.UNAVAILABLE


@pytest.mark.asyncio
async def test_cross_model_audit_provider_error_is_unavailable():
    files = {"app.py": CLEAN_CODE}
    result = await cross_model_audit(files, "model-a", "model-b", _boom_fn)
    assert result.status is ReviewStatus.UNAVAILABLE


@pytest.mark.asyncio
async def test_cross_model_audit_unparseable_verdict_is_unavailable():
    files = {"app.py": CLEAN_CODE}
    result = await cross_model_audit(files, "model-a", "model-b", _garbage_fn)
    assert result.status is ReviewStatus.UNAVAILABLE


@pytest.mark.asyncio
async def test_cross_model_audit_no_files_is_unavailable():
    result = await cross_model_audit({}, "model-a", "model-b", _ok_fn)
    assert result.status is ReviewStatus.UNAVAILABLE


def test_audit_prompt_names_author_and_demands_json():
    prompt = build_audit_prompt({"app.py": CLEAN_CODE}, "model-a")
    assert "model-a" in prompt
    assert '"verdict"' in prompt


# ---------------------------------------------------------------------------
# Red-team pass
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_red_team_findings():
    files = {"app.py": SQLI_CODE}
    result = await red_team_review(files, "model-b", _findings_fn, "model-a")
    assert result.status is ReviewStatus.FINDINGS


@pytest.mark.asyncio
async def test_red_team_same_model_allowed_but_disclosed():
    files = {"app.py": CLEAN_CODE}
    result = await red_team_review(files, "model-a", _ok_fn, "model-a")
    assert result.status is ReviewStatus.PASS
    assert "same-model" in result.detail


def test_redteam_prompt_is_adversarial():
    prompt = build_redteam_prompt({"app.py": SQLI_CODE})
    assert "Assume" in prompt and "exploitable" in prompt


# ---------------------------------------------------------------------------
# Aggregate runner: agreement, not inflation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_aggregate_without_provider_is_never_pass(tmp_path):
    _write(tmp_path, "app.py", CLEAN_CODE)
    report = await run_review_passes(tmp_path, "model-a", "model-b", None)
    assert report.overall_status is ReviewStatus.UNAVAILABLE


@pytest.mark.asyncio
async def test_aggregate_all_clean_is_pass(tmp_path):
    _write(tmp_path, "app.py", CLEAN_CODE)
    report = await run_review_passes(tmp_path, "model-a", "model-b", _ok_fn)
    assert report.overall_status is ReviewStatus.PASS


@pytest.mark.asyncio
async def test_aggregate_security_findings_dominate(tmp_path):
    _write(tmp_path, "app.py", SQLI_CODE)
    report = await run_review_passes(tmp_path, "model-a", "model-b", _ok_fn)
    assert report.overall_status is ReviewStatus.FINDINGS
    assert report.all_issues


@pytest.mark.asyncio
async def test_aggregate_same_model_audit_blocks_pass(tmp_path):
    _write(tmp_path, "app.py", CLEAN_CODE)
    report = await run_review_passes(tmp_path, "model-a", "model-a", _ok_fn)
    assert report.overall_status is ReviewStatus.UNAVAILABLE


# ---------------------------------------------------------------------------
# File collection bounds
# ---------------------------------------------------------------------------


def test_collect_review_files_bounds_and_skips(tmp_path):
    _write(tmp_path, "b.py", "x = 1\n")
    _write(tmp_path, "a.py", "y = 2\n")
    _write(tmp_path, "node_modules/pkg/index.js", "z = 3\n")
    _write(tmp_path, "notes.txt", "not reviewable\n")
    files = collect_review_files(tmp_path)
    assert list(files) == ["a.py", "b.py"]


def test_collect_review_files_truncation_is_marked(tmp_path):
    _write(tmp_path, "big.py", "x = 1\n" * 5000)
    files = collect_review_files(tmp_path, max_bytes_per_file=100)
    assert "truncated" in files["big.py"]
