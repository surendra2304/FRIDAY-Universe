"""
Unit tests for Baseline Capture and Regression Guard Awareness in VerificationEngine.
"""

from pathlib import Path
from uuid import uuid4

import pytest

from app.core.config import Settings
from app.core.workspace import WorkspaceManager
from app.execution.engine import ExecutionEngine
from app.verification.engine import VerificationEngine


@pytest.mark.asyncio
async def test_baseline_capture_and_regression_detection(temp_dir: Path):
    settings = Settings()
    settings.workspaces_dir = temp_dir / "workspaces"
    wm = WorkspaceManager(settings=settings)
    engine = ExecutionEngine(wm=wm)
    verifier = VerificationEngine(engine=engine, wm=wm)

    task_id = str(uuid4())
    wm.create_workspace(task_id)

    # 1. Scaffold initial working code + tests
    initial_main = "def add(a: int, b: int) -> int:\n    return a + b\n"
    initial_test = "from main import add\ndef test_add():\n    assert add(2, 3) == 5\n"

    wm.write_project_file(task_id, "main.py", initial_main)
    wm.write_project_file(task_id, "test_main.py", initial_test)

    # 2. Capture baseline: all tests passing
    baseline = await verifier.capture_baseline(task_id)
    assert baseline.all_passed is True
    assert (wm.get_task_workspace_dir(task_id) / "artifacts" / "baseline_report.json").exists()

    # 3. Introduce a regression: modify main.py to break existing test
    broken_main = "def add(a: int, b: int) -> int:\n    return a - b\n"  # Bug!
    wm.write_project_file(task_id, "main.py", broken_main)

    # 4. Verify post-modification: VerificationEngine must detect regression
    post_report = await verifier.verify_task(task_id)
    assert post_report.all_passed is False
    assert post_report.baseline_comparison is not None
    assert post_report.baseline_comparison["regression_detected"] is True

    # 5. Fix regression: modify main.py back to correct logic
    wm.write_project_file(task_id, "main.py", initial_main)
    fixed_report = await verifier.verify_task(task_id)
    assert fixed_report.all_passed is True
    assert fixed_report.baseline_comparison["regression_detected"] is False
