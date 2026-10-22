"""
Unit tests for WorkspaceManager (app/core/workspace.py).
"""

from pathlib import Path

import pytest

from app.core.config import Settings
from app.core.workspace import WorkspaceManager


def test_create_workspace_subdirectories(temp_dir: Path):
    settings = Settings()
    settings.workspaces_dir = temp_dir / "workspaces"
    wm = WorkspaceManager(settings=settings)

    task_id = "test_task_001"
    paths = wm.create_workspace(task_id)

    assert paths.root.exists()
    assert (paths.root / "project").is_dir()
    assert (paths.root / "artifacts").is_dir()
    assert (paths.root / "logs").is_dir()
    assert (paths.root / "state").is_dir()
    assert (paths.root / "cache").is_dir()
    assert (paths.root / ".forge_workspace").is_file()


def test_write_and_read_project_file(temp_dir: Path):
    settings = Settings()
    settings.workspaces_dir = temp_dir / "workspaces"
    wm = WorkspaceManager(settings=settings)

    task_id = "test_task_002"
    file_rel_path = "src/calculator.py"
    code = "def add(a, b):\n    return a + b\n"

    written_path = wm.write_project_file(task_id, file_rel_path, code)
    assert written_path.exists()

    content = wm.read_project_file(task_id, file_rel_path)
    assert content == code


def test_path_traversal_protection(temp_dir: Path):
    settings = Settings()
    settings.workspaces_dir = temp_dir / "workspaces"
    wm = WorkspaceManager(settings=settings)

    task_id = "test_task_003"
    with pytest.raises(ValueError, match="Path traversal detected"):
        wm.write_project_file(task_id, "../../outside.txt", "malicious content")


def test_save_artifact_and_append_log(temp_dir: Path):
    settings = Settings()
    settings.workspaces_dir = temp_dir / "workspaces"
    wm = WorkspaceManager(settings=settings)

    task_id = "test_task_004"
    artifact_path = wm.save_artifact(task_id, "build_report.json", '{"status": "ok"}')
    assert artifact_path.exists()
    assert artifact_path.read_text(encoding="utf-8") == '{"status": "ok"}'

    wm.append_log(task_id, "agent.log", "Step 1 started")
    wm.append_log(task_id, "agent.log", "Step 1 finished")

    paths = wm.get_workspace_paths(task_id)
    log_content = (paths.logs / "agent.log").read_text(encoding="utf-8")
    assert "Step 1 started" in log_content
    assert "Step 1 finished" in log_content


def test_cleanup_workspace(temp_dir: Path):
    settings = Settings()
    settings.workspaces_dir = temp_dir / "workspaces"
    wm = WorkspaceManager(settings=settings)

    task_id = "test_task_cleanup"
    paths = wm.create_workspace(task_id)
    assert paths.root.exists()

    cleaned = wm.cleanup_workspace(task_id)
    assert cleaned is True
    assert not paths.root.exists()
