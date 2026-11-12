"""Artifact receipts use real confined paths, never fabricated temp files."""
import json
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from app.api import delegate
from app.core.config import Settings
from app.core.workspace import WorkspaceManager
from app.memory.models import TaskState
from app.verification.source_integrity import project_snapshot


def setup_workspace(tmp_path, monkeypatch):
    wm = WorkspaceManager(settings=Settings(workspaces_dir=tmp_path/'workspaces'))
    paths = wm.create_workspace('fixture')
    wm.write_project_file('fixture', 'main.py', 'def convert(): return []\n')
    monkeypatch.setattr(delegate, 'workspace_manager', wm)
    return paths


def test_receipt_contains_existing_files_not_git_hidden_caches_or_escape(tmp_path, monkeypatch):
    paths = setup_workspace(tmp_path, monkeypatch)
    (paths.artifacts/'verification_manifest.json').write_text('{}')
    (paths.project/'.env').write_text('fixture-not-a-secret')
    (paths.project/'.git').mkdir(exist_ok=True)
    (paths.project/'.git/config').write_text('fixture')
    (paths.project/'__pycache__').mkdir()
    (paths.project/'__pycache__/cache.pyc').write_bytes(b'not source')
    outside = tmp_path/'outside.py';outside.write_text('outside')
    (paths.project/'escape.py').symlink_to(outside)
    (paths.project/'hidden_link').symlink_to(paths.project/'.git/config')
    artifacts = delegate._task_artifact_paths('fixture')
    assert str((paths.project/'main.py').resolve()) in artifacts
    assert str((paths.artifacts/'verification_manifest.json').resolve()) in artifacts
    assert all('.git' not in p and '.env' not in p and '__pycache__' not in p and 'outside' not in p for p in artifacts)
    assert not any('completion_report.json' in p for p in artifacts)


def test_receipt_bound_and_missing_workspace(tmp_path, monkeypatch):
    paths = setup_workspace(tmp_path, monkeypatch)
    for i in range(90):
        (paths.project/f'module_{i}.py').write_text('x = 1')
    assert len(delegate._task_artifact_paths('fixture')) == 40
    assert delegate._task_artifact_paths('absent') == []


@pytest.mark.asyncio
async def test_status_read_reports_same_completed_task_files_without_rebuilding(tmp_path, monkeypatch):
    paths = setup_workspace(tmp_path, monkeypatch)
    manifest = {'source_snapshot': project_snapshot(paths.project), 'all_passed': True, 'failed_stages': 0, 'stages': {
        'tests': {'passed': True, 'exit_code': 0, 'category': 'test', 'command': 'python -m unittest'}}}
    (paths.artifacts/'verification_manifest.json').write_text(json.dumps(manifest))
    task = SimpleNamespace(state=TaskState.COMPLETED, goal='Converter', progress_percentage=100,
                           created_at=datetime.now(timezone.utc), error_message=None)
    result = await delegate.get_task_status('fixture', store=SimpleNamespace(get_task=AsyncMock(return_value=task)))
    assert result.status == 'SUCCESS'
    assert result.result['artifacts'] == delegate._task_artifact_paths('fixture')
    assert str((paths.project/'main.py').resolve()) in result.result['artifacts']
    assert result.verification_manifest == manifest
