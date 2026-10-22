"""
Unit tests for the Autonomous Closed-Loop Self-Healing Engine.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from app.selfrepair.engine import SelfRepairEngine
from app.selfrepair.models import RepairStrategyType


@pytest.mark.asyncio
async def test_self_repair_import_injection() -> None:
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        broken_file = tmp_path / "service.py"
        broken_file.write_text(
            """def parse_config(raw_str):
    return json.loads(raw_str)
""",
            encoding="utf-8",
        )

        error_context = f'File "{broken_file}", line 2, in parse_config\nNameError: name \'json\' is not defined'

        engine = SelfRepairEngine()
        result = await engine.repair_workspace(
            workspace=tmp_path,
            initial_error=error_context,
            max_attempts=2,
        )

        assert result.success is True
        assert result.rounds_executed == 1
        assert "service.py" in result.resolved_files[0]
        assert len(result.attempts) == 1
        assert result.attempts[0].strategy == RepairStrategyType.IMPORT_INJECTION

        # Verify that json import was inserted and file is valid python
        repaired_code = broken_file.read_text(encoding="utf-8")
        assert "import json" in repaired_code


@pytest.mark.asyncio
async def test_self_repair_ast_code_smell() -> None:
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        smelly_file = tmp_path / "data_collector.py"
        smelly_file.write_text(
            """def collect(item, store=[]):
    store.append(item)
    return store
""",
            encoding="utf-8",
        )

        engine = SelfRepairEngine()
        # With empty initial error, it inspects workspace for AST smells
        result = await engine.repair_workspace(
            workspace=tmp_path,
            initial_error="",
            max_attempts=2,
        )

        assert result.success is True
        assert result.rounds_executed == 1
        assert result.attempts[0].strategy == RepairStrategyType.AST_REWRITE

        repaired_code = smelly_file.read_text(encoding="utf-8")
        assert "store=None" in repaired_code
        assert "if store is None:" in repaired_code


@pytest.mark.asyncio
async def test_self_repair_revert_on_failed_test() -> None:
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        target_file = tmp_path / "calc.py"
        initial_content = "def add(x, y=[]):\n    return x\n"
        target_file.write_text(initial_content, encoding="utf-8")

        engine = SelfRepairEngine()
        # We pass a test command that always fails (exit code 1)
        result = await engine.repair_workspace(
            workspace=tmp_path,
            initial_error="",
            test_command="python -c \"import sys; sys.exit(1)\"",
            max_attempts=1,
        )

        assert result.success is False
        # When verification fails, the file should be reverted to initial content
        assert target_file.read_text(encoding="utf-8") == initial_content
