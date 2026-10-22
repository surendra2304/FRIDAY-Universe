"""
Unit tests for BrowserChecker and Web UI Verification.
"""

from pathlib import Path

import pytest

from app.core.config import Settings
from app.core.workspace import WorkspaceManager
from app.execution.engine import ExecutionEngine
from app.verification.checkers import BrowserChecker


@pytest.fixture
def browser_context(temp_dir: Path):
    settings = Settings()
    settings.workspaces_dir = temp_dir / "workspaces"
    wm = WorkspaceManager(settings=settings)
    engine = ExecutionEngine(wm=wm)
    return {"wm": wm, "engine": engine, "task_id": "test_browser_task"}


@pytest.mark.asyncio
async def test_browser_checker_skips_when_no_html(browser_context):
    wm: WorkspaceManager = browser_context["wm"]
    engine: ExecutionEngine = browser_context["engine"]
    task_id = "test_no_html"

    # Only python file, no web assets
    wm.write_project_file(task_id, "main.py", "print('hello')\n")

    checker = BrowserChecker()
    evidence = await checker.run_check(task_id, engine)

    assert evidence.passed is True
    assert evidence.exit_code == 0
    assert "Browser check skipped" in evidence.stdout


@pytest.mark.asyncio
async def test_browser_checker_verifies_web_page_and_captures_screenshot(browser_context):
    wm: WorkspaceManager = browser_context["wm"]
    engine: ExecutionEngine = browser_context["engine"]
    task_id = "test_web_page"

    html_content = """<!DOCTYPE html>
<html>
<head><title>FORGE Web Test</title></head>
<body>
    <h1>Todo Application</h1>
    <button id="add-btn">Add Todo</button>
</body>
</html>
"""
    wm.write_project_file(task_id, "index.html", html_content)

    checker = BrowserChecker()
    evidence = await checker.run_check(task_id, engine)

    assert evidence.passed is True
    assert evidence.exit_code == 0
    assert "Browser verification completed" in evidence.stdout

    # Evidence must be real. The checker used to write a hardcoded 1x1 PNG and
    # call it a screenshot, so this assertion has been corrected (not weakened)
    # to demand the honest contract: the fetched HTML is persisted as evidence
    # and the metadata explicitly records that no screenshot was captured.
    artifacts_dir = wm.get_task_workspace_dir(task_id) / "artifacts"
    evidence_files = list(artifacts_dir.glob("browser_evidence_*.html"))
    assert len(evidence_files) >= 1, "no real evidence artifact was written"
    assert evidence_files[0].stat().st_size > 0
    assert "Todo Application" in evidence_files[0].read_text(encoding="utf-8")

    meta_files = list(artifacts_dir.glob("browser_evidence_*.meta.json"))
    assert len(meta_files) >= 1
    import json

    meta = json.loads(meta_files[0].read_text(encoding="utf-8"))
    assert meta["screenshot"] is False
    assert "playwright" in meta["note"].lower()

    # The fabricated 1x1 PNG must be gone.
    assert not list(artifacts_dir.glob("screenshot_*.png")), (
        "BrowserChecker still fabricates a 1x1 PNG as screenshot evidence"
    )


@pytest.mark.asyncio
async def test_browser_checker_detects_missing_assets(browser_context):
    wm: WorkspaceManager = browser_context["wm"]
    engine: ExecutionEngine = browser_context["engine"]
    task_id = "test_broken_assets"

    # HTML with non-existent stylesheet and image
    broken_html = """<!DOCTYPE html>
<html>
<head><link rel="stylesheet" href="non_existent_styles.css"></head>
<body>
    <img src="missing_logo.png" alt="logo" />
</body>
</html>
"""
    wm.write_project_file(task_id, "index.html", broken_html)

    checker = BrowserChecker()
    evidence = await checker.run_check(task_id, engine)

    assert evidence.passed is False
    assert evidence.exit_code == 1
    assert len(evidence.issues) >= 1
