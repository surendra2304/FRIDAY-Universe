"""
Unit tests for DeveloperRole using AI Universe as the primary code generation reasoning engine.
"""

from pathlib import Path
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from app.agents.roles import DeveloperRole
from app.core.config import Settings
from app.core.workspace import WorkspaceManager
from app.execution.engine import ExecutionEngine
from app.integrations.ai_universe_client import AIUniverseResponse


@pytest.fixture
def temp_engine(tmp_path: Path):
    settings = Settings()
    settings.workspaces_dir = tmp_path / "workspaces"
    wm = WorkspaceManager(settings=settings)
    engine = ExecutionEngine(wm=wm)
    return engine, wm


@pytest.mark.asyncio
async def test_developer_role_calls_ai_universe_ask_and_writes_raw_code(temp_engine):
    """
    Validates that DeveloperRole calls AIUniverseClient.ask() as its primary code generator
    and writes raw code response directly into workspace main.py.
    """
    engine, wm = temp_engine
    task_id = str(uuid4())
    wm.create_workspace(task_id)

    developer = DeveloperRole()

    mock_ai_response = AIUniverseResponse(
        answer="""def calculate_total(prices):\n    return sum(prices)\n\ndef main():\n    print('Total:', calculate_total([10, 20, 30]))\n\nif __name__ == '__main__':\n    main()\n""",
        confidence=0.95,
        unresolved_disagreements=[],
        key_evidence=["Optimized linear summation"],
        run_id="run_ai_universe_coder_001",
    )

    with patch(
        "app.integrations.ai_universe_client.AIUniverseClient.ask", new_callable=AsyncMock
    ) as mock_ask:
        mock_ask.return_value = mock_ai_response

        context = {"goal": "Build an expense calculator utility"}
        result = await developer.execute_step(
            task_id=task_id,
            node_title="Implement Core Calculation Engine",
            context=context,
            engine=engine,
        )

        assert result["status"] == "success"
        assert "main.py" in result["files_written"]
        assert result["ai_universe_run_id"] == "run_ai_universe_coder_001"

        # Verify mock call prompt
        mock_ask.assert_called_once()
        call_prompt = mock_ask.call_args[1]["question"]
        assert (
            "Write the complete code for main.py based on the overall architecture" in call_prompt
        )
        assert "Build an expense calculator utility" in call_prompt

        # Verify file content on disk
        written_content = engine.fs.read_file(task_id, "main.py", role="developer")
        assert "def calculate_total(prices):" in written_content
        assert "return sum(prices)" in written_content


@pytest.mark.asyncio
async def test_developer_role_parses_markdown_headers_from_ai_universe(temp_engine):
    """
    Validates that DeveloperRole extracts structured file blocks from AI Universe response.
    """
    engine, wm = temp_engine
    task_id = str(uuid4())
    wm.create_workspace(task_id)

    developer = DeveloperRole()

    mock_ai_response = AIUniverseResponse(
        answer="""### File: app/calculator.py
```python
def add(a, b):
    return a + b
```

### File: app/utils.py
```python
def format_currency(val):
    return f"${val:.2f}"
```
""",
        confidence=0.88,
        run_id="run_ai_universe_multi_file_002",
    )

    with patch(
        "app.integrations.ai_universe_client.AIUniverseClient.ask", new_callable=AsyncMock
    ) as mock_ask:
        mock_ask.return_value = mock_ai_response

        context = {"goal": "Build modular calculator"}
        result = await developer.execute_step(
            task_id=task_id,
            node_title="Implement Calculator Modules",
            context=context,
            engine=engine,
        )

        assert result["status"] == "success"
        assert "app/calculator.py" in result["files_written"]
        assert "app/utils.py" in result["files_written"]
        assert result["ai_universe_run_id"] == "run_ai_universe_multi_file_002"

        calc_content = engine.fs.read_file(task_id, "app/calculator.py", role="developer")
        assert "def add(a, b):" in calc_content


@pytest.mark.asyncio
async def test_developer_role_fallback_on_low_confidence(temp_engine):
    """
    Validates that when AI Universe returns confidence < 0.70, DeveloperRole falls back
    to local model reasoning.
    """
    engine, wm = temp_engine
    task_id = str(uuid4())
    wm.create_workspace(task_id)

    developer = DeveloperRole()

    mock_ai_response = AIUniverseResponse(
        answer="Incomplete or disputed snippet",
        confidence=0.45,
        run_id="run_low_conf",
    )

    with patch(
        "app.integrations.ai_universe_client.AIUniverseClient.ask", new_callable=AsyncMock
    ) as mock_ask:
        mock_ask.return_value = mock_ai_response

        context = {"goal": "Build fallback task"}
        result = await developer.execute_step(
            task_id=task_id,
            node_title="Implement Fallback Logic",
            context=context,
            engine=engine,
        )

        assert result["status"] == "success"
        # Should not have ai_universe_run_id because it fell back
        assert "ai_universe_run_id" not in result
        mock_ask.assert_called_once()


@pytest.mark.asyncio
async def test_developer_role_fallback_on_ai_universe_error(temp_engine):
    """
    Validates that when AI Universe raises network/connection error, DeveloperRole falls back
    gracefully to local model without crashing.
    """
    engine, wm = temp_engine
    task_id = str(uuid4())
    wm.create_workspace(task_id)

    developer = DeveloperRole()

    with patch(
        "app.integrations.ai_universe_client.AIUniverseClient.ask",
        side_effect=RuntimeError("AI Universe offline"),
    ):
        context = {"goal": "Build offline resilience test"}
        result = await developer.execute_step(
            task_id=task_id,
            node_title="Implement Offline Resilience",
            context=context,
            engine=engine,
        )

        assert result["status"] == "success"
        assert "ai_universe_run_id" not in result
