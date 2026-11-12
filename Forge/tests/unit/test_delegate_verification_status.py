"""Saved real-workspace evidence, not the orchestrator's completion label, controls status."""
import json
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from app.api import delegate
from app.memory.models import TaskState


@pytest.mark.asyncio
@pytest.mark.parametrize("manifest,expected", [
    (None, "DEGRADED"),
    ({"all_passed": False, "partial_failure": True, "failed_stages": 3,
      "failure_summary": "syntax and missing tools", "stages": {"build": {"passed": False, "exit_code": 1}}}, "PARTIAL_FAILURE"),
    ({"all_passed": True, "failed_stages": 0, "stages": {}}, "FAILED"),
    ({"all_passed": True, "failed_stages": 0, "stages": {"test": {"passed": True, "exit_code": 1}}}, "FAILED"),
    ({"all_passed": True, "failed_stages": 0, "stages": {"test": {"passed": True, "exit_code": 0}}}, "DEGRADED"),
])
async def test_completed_state_does_not_override_saved_verification(tmp_path, monkeypatch, manifest, expected):
    if manifest is not None:
        (tmp_path / "verification_manifest.json").write_text(json.dumps(manifest))
    monkeypatch.setattr(delegate.workspace_manager, "get_workspace_paths", lambda _: SimpleNamespace(artifacts=tmp_path))
    task = SimpleNamespace(state=TaskState.COMPLETED, goal="Build converter", progress_percentage=100,
                           created_at=datetime.now(timezone.utc), error_message=None)
    result = await delegate.get_task_status("fixture-completed-task", store=SimpleNamespace(get_task=AsyncMock(return_value=task)))
    assert result.status == expected
    assert result.verification_manifest == manifest
    if expected != "SUCCESS":
        assert result.error
        assert "verification status " + expected in result.summary
