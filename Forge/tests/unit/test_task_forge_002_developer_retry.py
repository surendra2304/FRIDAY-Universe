"""TASK-FORGE-002 (GAP 1) regressions: sub-threshold code answers are retried with evidence.

Before the fix, DeveloperRole accepted Inference output only at confidence >= 0.70
with no retry -- one sub-threshold answer sent the build to deterministic synthesis
or the local stub -- and repair_with_inference rejected a low-confidence reply with
no second attempt. Both now retry once, feeding the rejection evidence back into
the prompt. Provider calls are labelled test doubles; no real endpoint is hit.
"""

from pathlib import Path
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from app.agents.repair import repair_with_inference
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
async def test_low_confidence_answer_is_retried_with_qa_verdict(temp_engine):
    """A sub-threshold first attempt must be resent once, carrying the QA verdict
    Inference reported, and the accepted second answer must be the one used."""
    engine, wm = temp_engine
    task_id = str(uuid4())
    wm.create_workspace(task_id)

    developer = DeveloperRole()
    first = AIUniverseResponse(
        answer="def broken(:\n    pass",
        confidence=0.55,
        run_id="run_low_conf_1",
        error="model output did not parse as python: SyntaxError at line 1",
    )
    second = AIUniverseResponse(
        answer="def main():\n    print('ok')\n",
        confidence=0.92,
        run_id="run_accepted_2",
    )

    with patch(
        "app.integrations.ai_universe_client.AIUniverseClient.generate_code",
        new_callable=AsyncMock,
    ) as mock_gen:
        mock_gen.side_effect = [first, second]
        result = await developer.execute_step(
            task_id=task_id,
            node_title="Implement Retry Target",
            context={"goal": "Build a tiny retry probe"},
            engine=engine,
        )

        assert mock_gen.await_count == 2
        assert result["status"] == "success"
        assert result["ai_universe_run_id"] == "run_accepted_2"
        assert result["fallback_stub"] is False

        retry_kwargs = mock_gen.call_args_list[1].kwargs
        retry_requirements = " ".join(retry_kwargs["requirements"])
        assert "Previous attempt was rejected" in retry_requirements
        assert "quality verdict" in retry_requirements
        assert "SyntaxError" in retry_requirements
        assert "Previous attempt was rejected" in retry_kwargs["context"]["prompt"]

        written = engine.fs.read_file(task_id, "main.py", role="developer")
        assert "def main():" in written


@pytest.mark.asyncio
async def test_two_rejected_attempts_still_fall_back_to_local_model(temp_engine):
    """The retry must not loop forever: after the second rejection the existing
    deterministic-synthesis fallback runs, exactly as before the fix."""
    engine, wm = temp_engine
    task_id = str(uuid4())
    wm.create_workspace(task_id)

    developer = DeveloperRole()
    low = AIUniverseResponse(
        answer="disputed snippet",
        confidence=0.45,
        run_id="run_low_conf",
    )

    with patch(
        "app.integrations.ai_universe_client.AIUniverseClient.generate_code",
        new_callable=AsyncMock,
    ) as mock_gen:
        mock_gen.return_value = low
        result = await developer.execute_step(
            task_id=task_id,
            node_title="Implement Fallback Logic",
            context={"goal": "Build fallback task"},
            engine=engine,
        )

        assert mock_gen.await_count == 2
        assert result["status"] == "success"
        assert "ai_universe_run_id" not in result


@pytest.mark.asyncio
async def test_accepted_first_attempt_is_not_retried(temp_engine):
    """A confidence >= 0.70 answer must keep the single-call behavior."""
    engine, wm = temp_engine
    task_id = str(uuid4())
    wm.create_workspace(task_id)

    developer = DeveloperRole()
    good = AIUniverseResponse(
        answer="def calculate_total(prices):\n    return sum(prices)\n",
        confidence=0.95,
        run_id="run_good_once",
    )

    with patch(
        "app.integrations.ai_universe_client.AIUniverseClient.generate_code",
        new_callable=AsyncMock,
    ) as mock_gen:
        mock_gen.return_value = good
        result = await developer.execute_step(
            task_id=task_id,
            node_title="Implement Calculator",
            context={"goal": "Build an expense calculator utility"},
            engine=engine,
        )

        assert mock_gen.await_count == 1
        assert result["ai_universe_run_id"] == "run_good_once"


@pytest.mark.asyncio
async def test_repair_with_inference_retries_after_low_confidence(tmp_path, monkeypatch):
    """repair.py: a low-confidence reply must be retried once with the rejection
    reason as evidence, and the accepted repair written to the workspace."""
    from app.integrations import ai_universe_client

    settings = Settings(workspaces_dir=tmp_path / "workspaces")
    wm = WorkspaceManager(settings=settings)
    wm.write_project_file("fixture", "calc.py", "def add(a, b):\n    return a - b\n")
    engine = ExecutionEngine(wm=wm)

    first = AIUniverseResponse(answer="not usable", confidence=0.40, run_id="r1")
    second = AIUniverseResponse(
        answer="### File: calc.py\n```python\ndef add(a, b):\n    return a + b\n```",
        confidence=0.92,
        run_id="r2",
    )
    calls = []

    class FakeRepairClient:
        async def generate_code(self, **kwargs):
            calls.append(kwargs)
            return first if len(calls) == 1 else second

    monkeypatch.setattr(
        ai_universe_client, "get_ai_universe_client", lambda: FakeRepairClient()
    )

    result = await repair_with_inference(
        "fixture",
        {"goal": "calculator adds numbers", "requirements": [],
         "error": "assert add(1, 1) == 2", "project_files": ["calc.py"]},
        engine,
    )

    assert result["status"] == "success"
    assert result["fixed_files"] == ["calc.py"]
    assert result["verification_required"] is True
    assert len(calls) == 2
    retry_requirements = " ".join(calls[1]["requirements"])
    assert "Previous attempt was rejected (unavailable_or_low_confidence)" in retry_requirements
    assert "unavailable_or_low_confidence" not in " ".join(result["rejections"])
    repaired = engine.fs.read_file("fixture", "calc.py", role="debugger")
    assert "def add(a, b):\n    return a + b" in repaired
    assert "a - b" not in repaired


@pytest.mark.asyncio
async def test_repair_with_inference_reports_rejection_after_second_attempt(tmp_path, monkeypatch):
    """Two rejected attempts end the repair honestly; the file stays untouched."""
    from app.integrations import ai_universe_client

    settings = Settings(workspaces_dir=tmp_path / "workspaces")
    wm = WorkspaceManager(settings=settings)
    original = "def add(a, b):\n    return a - b\n"
    wm.write_project_file("fixture", "calc.py", original)
    engine = ExecutionEngine(wm=wm)

    low = AIUniverseResponse(answer="still not usable", confidence=0.50, run_id="r")
    calls = []

    class AlwaysLowClient:
        async def generate_code(self, **kwargs):
            calls.append(kwargs)
            return low

    monkeypatch.setattr(
        ai_universe_client, "get_ai_universe_client", lambda: AlwaysLowClient()
    )

    result = await repair_with_inference(
        "fixture",
        {"goal": "calculator adds numbers", "requirements": [],
         "error": "assert add(1, 1) == 2", "project_files": ["calc.py"]},
        engine,
    )

    assert result["status"] == "failed"
    assert result["fixed_files"] == []
    assert "unavailable_or_low_confidence:calc.py" in result["rejections"]
    assert len(calls) == 2
    assert engine.fs.read_file("fixture", "calc.py", role="debugger") == original
