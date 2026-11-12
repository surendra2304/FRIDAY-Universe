"""No-provider/no-test boundaries cannot fabricate tested deliverables."""
from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx
import pytest
from app.core.config import Settings
from app.core.workspace import WorkspaceManager
from app.execution.engine import ExecutionEngine
from app.integrations.ai_universe_client import AIUniverseClient
from app.verification.checkers import TestChecker


@pytest.mark.asyncio
async def test_python_without_tests_is_failed_evidence(temp_dir):
    settings = Settings(workspaces_dir=temp_dir / "workspaces")
    wm = WorkspaceManager(settings=settings)
    engine = ExecutionEngine(wm=wm)
    wm.write_project_file("missing-tests", "main.py", "print('generic program')\n")
    evidence = await TestChecker().run_check("missing-tests", engine)
    assert evidence.passed is False
    assert evidence.exit_code != 0
    assert "no tests were executed" in evidence.stderr
    assert evidence.artifacts_inspected == ["main.py"]


@pytest.mark.asyncio
async def test_missing_workspace_cannot_pass_tests():
    engine = SimpleNamespace(wm=SimpleNamespace(get_workspace_paths=lambda _: None))
    evidence = await TestChecker().run_check("no-workspace", engine)
    assert not evidence.passed
    assert evidence.exit_code != 0


@pytest.mark.asyncio
async def test_provider_outage_does_not_create_assert_true_test(monkeypatch):
    http = SimpleNamespace(post=AsyncMock(side_effect=httpx.ReadTimeout("explicit fixture")))
    class Client:
        async def __aenter__(self):
            return http
        async def __aexit__(self, *_):
            return False
    monkeypatch.setattr("app.integrations.ai_universe_client.httpx.AsyncClient", lambda **_: Client())
    result = await AIUniverseClient(base_url="https://explicit-fixture.invalid").generate_tests("def convert(): pass")
    assert result["test_code"] == ""
    assert result["confidence"] == 0
    assert "no tests generated" in result["error"]
