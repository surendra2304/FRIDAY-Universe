"""
Regression test for the "verification-ordering" bug found by live, real-usage
testing of FORGE (not just running the existing test suite).

`DeliveryPackager.package_delivery()` is invoked by `ReleaseEngineerRole` as
part of the Release DAG stage, which runs *before*
`OrchestratorCore.run_task`'s post-DAG `_verify_and_repair()` step ever calls
`VerificationEngine.verify_task()` for the first time. The old implementation
only *read* `artifacts/verification_report.json` if it happened to already
exist on disk, and otherwise silently defaulted to
`{"all_passed": True, "total_checks": 0, ...}`.

Live reproduction (2026-10-07, task5107102026091432, goal "Build a CLI todo
app"): `completion_report.json` was written claiming `all_passed: true` with
zero checks run, ~300ms *before* `verification_report.json` was written
showing the real result: `all_passed: false, 8/10 passed`. Any caller relying
on the completion report -- the artifact this project's own README calls out
as "Evidence Over Model Confidence" -- was told a broken build had fully
passed.

This test packages delivery for a workspace that has never been verified and
whose code is deliberately broken (a syntax error), with NO
verification_report.json present beforehand, and asserts the completion
report tells the truth.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.core.config import Settings
from app.core.workspace import WorkspaceManager
from app.execution.delivery import DeliveryPackager
from app.execution.engine import ExecutionEngine


@pytest.mark.asyncio
async def test_package_delivery_runs_fresh_verification_when_none_exists(temp_dir: Path):
    settings = Settings()
    settings.workspaces_dir = temp_dir / "workspaces"
    wm = WorkspaceManager(settings=settings)
    engine = ExecutionEngine(wm=wm)

    task_id = "task_delivery_ordering_regress"
    wm.create_workspace(task_id)

    # Deliberately broken code: a syntax error, guaranteed to fail the Build
    # & Syntax Check (and therefore the overall verification battery).
    wm.write_project_file(task_id, "main.py", "def broken(:\n    pass\n")

    paths = wm.get_workspace_paths(task_id)
    verification_report_path = paths.artifacts / "verification_report.json"
    assert not verification_report_path.exists(), (
        "test setup invariant violated: verification must not have run yet"
    )

    packager = DeliveryPackager(engine=engine, wm=wm)
    delivery = await packager.package_delivery(
        task_id=task_id,
        goal="Build something that is deliberately broken",
        requirements=[],
    )

    # The core assertion: an unverified, broken build must NEVER be reported
    # as having passed. This is the exact opposite of the old default.
    assert delivery.test_build_status["all_passed"] is False
    assert delivery.test_build_status["total_checks"] > 0, (
        "package_delivery must actually run verification instead of "
        "defaulting to zero checks"
    )

    # A real verification report must now exist and agree with what was
    # reported in the completion report -- no more "predates verification"
    # ordering bug.
    assert verification_report_path.exists()
    real_report = json.loads(verification_report_path.read_text(encoding="utf-8"))
    assert real_report["all_passed"] == delivery.test_build_status["all_passed"]
    assert real_report["total_checks"] == delivery.test_build_status["total_checks"]

    completion_report_path = paths.artifacts / "completion_report.json"
    assert completion_report_path.exists()
    completion_data = json.loads(completion_report_path.read_text(encoding="utf-8"))
    assert completion_data["test_build_status"]["all_passed"] is False
