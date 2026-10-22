"""Regression tests for evidence-first build verification."""

from unittest.mock import MagicMock

import pytest

from app.verification.checkers import BuildChecker


@pytest.mark.asyncio
async def test_build_checker_fails_when_workspace_paths_are_missing():
    engine = MagicMock()
    engine.wm.get_workspace_paths.return_value = None

    evidence = await BuildChecker().run_check("task-without-workspace", engine)

    assert evidence.passed is False
    assert evidence.exit_code != 0
    assert "no workspace paths were produced" in (evidence.stderr or "").lower()
    engine.terminal.run_command.assert_not_called()
