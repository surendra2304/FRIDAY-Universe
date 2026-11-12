"""Real TesterRole/parser ingestion; provider and subprocess boundaries are explicit fixtures."""
import ast
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.agents.roles import TesterRole
from app.providers.base import ProviderResponse


@pytest.mark.asyncio
async def test_provider_prose_cannot_be_written_as_test_python(monkeypatch):
    from app.integrations import ai_universe_client
    provider = SimpleNamespace(generate_tests=AsyncMock(return_value={"test_code": "Here is an exhaustive, professional test suite."}))
    monkeypatch.setattr(ai_universe_client, "get_ai_universe_client", lambda: provider)
    role = TesterRole()
    role.prompt_model = AsyncMock(return_value=ProviderResponse(content="```python\ndef test_main():\n    assert 1 == 1\n```", model="explicit-fixture"))
    fs = MagicMock()
    fs.search_files.return_value = []
    fs.read_file.return_value = "def main():\n    return 1\n"
    fs.create_file.side_effect = lambda **kw: kw["relative_path"]
    terminal = SimpleNamespace(run_command=AsyncMock(return_value=SimpleNamespace(exit_code=0, stdout="fixture result", stderr="")))
    result = await role.execute_step("fixture-task", "test converter", {"goal": "Build a converter"}, SimpleNamespace(fs=fs, terminal=terminal))
    role.prompt_model.assert_awaited_once()
    assert fs.create_file.call_count == 1
    code = fs.create_file.call_args.kwargs["content"]
    ast.parse(code)
    assert code.startswith("def test_main")
    assert "Here is" not in code
    assert result["exit_code"] == 0
