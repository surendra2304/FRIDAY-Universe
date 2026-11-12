"""Role/client boundaries are explicit provider fixtures, not successful live builds."""
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
import pytest
from app.agents.roles import TesterRole
from app.core.context import ContextManager
from app.integrations.ai_universe_client import AIUniverseClient


@pytest.mark.asyncio
async def test_owner_objective_requirements_and_framework_reach_test_provider(monkeypatch):
    from app.integrations import ai_universe_client
    tests = "import unittest\nclass TestCSV(unittest.TestCase):\n    def test_empty(self):\n        self.assertEqual([], [])\n"
    provider = SimpleNamespace(generate_tests=AsyncMock(return_value={"test_code": "Here are the tests.\n```python\n" + tests + "```"}))
    monkeypatch.setattr(ai_universe_client, "get_ai_universe_client", lambda: provider)
    fs = MagicMock()
    fs.search_files.return_value = []
    fs.read_file.return_value = "# source padding\n" * 400 + "def convert():\n    return []\n"
    fs.create_file.side_effect = lambda **kw: kw["relative_path"]
    terminal = SimpleNamespace(run_command=AsyncMock(return_value=SimpleNamespace(exit_code=0, stdout="", stderr="Ran 1 test: explicit fixture")))
    role = TesterRole()
    role.prompt_model = AsyncMock(side_effect=AssertionError("unexpected fallback"))
    goal = "Build CSV to JSON. Include unittest tests for quoted commas and empty input."
    result = await role.execute_step("fixture", "test", {"goal": goal, "requirements": ["standard library only"]}, SimpleNamespace(fs=fs, terminal=terminal))
    kwargs = provider.generate_tests.call_args.kwargs
    assert kwargs["test_framework"] == "unittest"
    assert kwargs["project_goal"] == goal
    assert kwargs["requirements"] == ["standard library only"]
    assert "def convert" in kwargs["code"]
    assert fs.create_file.call_args.kwargs["content"].startswith("import unittest")
    assert "-m unittest discover" in terminal.run_command.call_args.kwargs["command"]
    assert result["exit_code"] == 0


def test_context_budget_does_not_discard_explicit_requirements():
    context = ContextManager()
    engine = SimpleNamespace(fs=SimpleNamespace(search_files=lambda **kw: []))
    result = context.build_agent_context("fixture", "developer", "implement",
        {"goal": "CSV to JSON", "requirements": ["quoted commas", "empty input"]}, engine)
    assert result["requirements"] == ["quoted commas", "empty input"]


@pytest.mark.asyncio
async def test_inference_client_transmits_owner_goal_and_framework(monkeypatch):
    http = SimpleNamespace(post=AsyncMock(return_value=SimpleNamespace(raise_for_status=lambda: None, json=lambda: {"test_code": ""})))
    class Client:
        async def __aenter__(self):
            return http
        async def __aexit__(self, *_):
            return False
    monkeypatch.setattr("app.integrations.ai_universe_client.httpx.AsyncClient", lambda **kw: Client())
    await AIUniverseClient(base_url="https://fixture.invalid").generate_tests("complete source", test_framework="unittest", project_goal="CSV to JSON", requirements=["quoted commas"])
    payload = http.post.call_args.kwargs["json"]
    assert payload["project_goal"] == "CSV to JSON"
    assert payload["requirements"] == ["quoted commas"]
    assert payload["test_framework"] == "unittest"
