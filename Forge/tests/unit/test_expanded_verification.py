"""
Unit tests for Expanded Objective Verification Battery.
"""

from pathlib import Path

import pytest

from app.core.config import Settings
from app.core.workspace import WorkspaceManager
from app.execution.engine import ExecutionEngine
from app.verification.expanded_battery import (
    AccessibilityChecker,
    CodeQualityComplexityChecker,
    PerformanceSanityChecker,
    SecurityVulnerabilityChecker,
)


@pytest.mark.asyncio
async def test_security_vulnerability_checker(tmp_path: Path):
    settings = Settings()
    settings.workspaces_dir = tmp_path / "workspaces"
    wm = WorkspaceManager(settings=settings)
    engine = ExecutionEngine(wm=wm)
    task_id = "test_sec_task_01"
    wm.create_workspace(task_id)

    # 1. Clean code -> passes
    wm.write_project_file(task_id, "main.py", "def add(a, b):\n    return a + b\n")
    checker = SecurityVulnerabilityChecker()
    ev = await checker.run_check(task_id, engine)
    assert ev.passed is True
    assert len(ev.issues) == 0

    # 2. Insecure code with hardcoded key and eval
    insecure_code = 'API_KEY = "sk-123456789012345678901234567890"\nresult = eval("2 + 2")\n'
    wm.write_project_file(task_id, "insecure.py", insecure_code)
    ev_bad = await checker.run_check(task_id, engine)
    assert ev_bad.passed is False
    assert len(ev_bad.issues) >= 2


@pytest.mark.asyncio
async def test_performance_sanity_checker(tmp_path: Path):
    settings = Settings()
    settings.workspaces_dir = tmp_path / "workspaces"
    wm = WorkspaceManager(settings=settings)
    engine = ExecutionEngine(wm=wm)
    task_id = "test_perf_task_01"
    wm.create_workspace(task_id)

    wm.write_project_file(
        task_id,
        "index.html",
        "<html><head><title>App</title></head><body><h1>Hello</h1></body></html>",
    )
    checker = PerformanceSanityChecker()
    ev = await checker.run_check(task_id, engine)
    assert ev.passed is True


@pytest.mark.asyncio
async def test_code_quality_complexity_checker(tmp_path: Path):
    settings = Settings()
    settings.workspaces_dir = tmp_path / "workspaces"
    wm = WorkspaceManager(settings=settings)
    engine = ExecutionEngine(wm=wm)
    task_id = "test_quality_task_01"
    wm.create_workspace(task_id)

    # Simple function
    wm.write_project_file(task_id, "main.py", "def simple():\n    return 42\n")
    checker = CodeQualityComplexityChecker()
    ev = await checker.run_check(task_id, engine)
    assert ev.passed is True


@pytest.mark.asyncio
async def test_accessibility_checker(tmp_path: Path):
    settings = Settings()
    settings.workspaces_dir = tmp_path / "workspaces"
    wm = WorkspaceManager(settings=settings)
    engine = ExecutionEngine(wm=wm)
    task_id = "test_a11y_task_01"
    wm.create_workspace(task_id)

    # Valid accessible HTML
    valid_html = '<html lang="en"><head><title>Test</title></head><body><h1>Title</h1><img src="pic.png" alt="Profile picture"></body></html>'
    wm.write_project_file(task_id, "index.html", valid_html)
    checker = AccessibilityChecker()
    ev = await checker.run_check(task_id, engine)
    assert ev.passed is True

    # Inaccessible HTML (missing alt and missing h1)
    bad_html = '<html><head><title>Test</title></head><body><img src="pic.png"></body></html>'
    wm.write_project_file(task_id, "bad.html", bad_html)
    ev_bad = await checker.run_check(task_id, engine)
    assert ev_bad.passed is False
    assert len(ev_bad.issues) >= 1
