"""Real byte inventories and execution; only DB/provider inputs use fixtures."""
import json
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from app.api import delegate
from app.core.config import Settings
from app.core.workspace import WorkspaceManager
from app.execution.engine import ExecutionEngine
from app.memory.models import TaskState
from app.verification.engine import VerificationEngine
from app.verification.checkers import TestChecker as ActualTestChecker
from app.verification.evidence import CheckCategory, VerificationEvidence, VerificationReport
from app.verification import source_integrity


@pytest.fixture
def context(tmp_path, monkeypatch):
    wm = WorkspaceManager(settings=Settings(workspaces_dir=tmp_path/'workspaces'))
    paths = wm.create_workspace('integrity')
    wm.write_project_file('integrity', 'main.py', 'def value():\n    return 42\n')
    wm.write_project_file('integrity', 'test_main.py', 'from main import value\ndef test_value():\n    assert value() == 42\n')
    monkeypatch.setattr(delegate, 'workspace_manager', wm)
    return wm, paths


async def status():
    task = SimpleNamespace(state=TaskState.COMPLETED, goal='Fixture', progress_percentage=100,
                           created_at=datetime.now(timezone.utc), error_message=None)
    return await delegate.get_task_status('integrity', store=SimpleNamespace(get_task=AsyncMock(return_value=task)))


@pytest.mark.asyncio
@pytest.mark.parametrize('mutation', ['change', 'delete', 'add', 'symlink', 'legacy'])
async def test_actual_suite_then_status_rejects_drift(context, mutation, tmp_path):
    wm, paths = context
    report = await VerificationEngine(engine=ExecutionEngine(wm=wm), wm=wm,
                                      custom_checkers=[ActualTestChecker()]).verify_task('integrity')
    assert report.all_passed and report.source_snapshot
    assert (await status()).status == 'SUCCESS'
    if mutation == 'change':
        (paths.project/'main.py').write_text('def value():\n    return 0\n')
    elif mutation == 'delete':
        (paths.project/'test_main.py').unlink()
    elif mutation == 'add':
        (paths.project/'extra.py').write_text('x = 1\n')
    elif mutation == 'symlink':
        outside = tmp_path/'outside';outside.write_text('outside')
        (paths.project/'link').symlink_to(outside)
    else:
        p = paths.artifacts/'verification_manifest.json'
        data = json.loads(p.read_text());data.pop('source_snapshot');p.write_text(json.dumps(data))
    result = await status()
    assert result.status == 'DEGRADED' and 're-run verification' in result.error


@pytest.mark.asyncio
async def test_source_changes_during_battery_cannot_be_stamped_passing(context):
    wm, paths = context
    class MutatingChecker:
        name = 'mutating fixture'
        category = CheckCategory.TEST
        async def run_check(self, task_id, engine):
            (paths.project/'main.py').write_text('changed during verification')
            return VerificationEvidence(check_name=self.name, category=self.category, passed=True, exit_code=0)
    report = await VerificationEngine(engine=ExecutionEngine(wm=wm), wm=wm,
                                      custom_checkers=[MutatingChecker()]).verify_task('integrity')
    assert not report.all_passed and report.source_snapshot is None
    assert report.evidence[-1].check_name == 'Project Source Integrity'
    assert report.evidence[-1].exit_code == 1
    assert (await status()).status != 'SUCCESS'


def test_old_report_regeneration_never_blesses_current_source(context):
    wm, paths = context
    report = VerificationReport(task_id='integrity', all_passed=True, total_checks=1,
                                passed_checks=1, failed_checks=0, evidence=[
                                    VerificationEvidence(check_name='old test', category=CheckCategory.TEST)])
    manifest = VerificationEngine(wm=wm).generate_manifest('integrity', report)
    assert manifest.source_snapshot is None


def test_cache_changes_ignored_but_hidden_config_bound(context):
    _, paths = context
    snap = source_integrity.project_snapshot(paths.project)
    (paths.project/'__pycache__').mkdir();(paths.project/'__pycache__/main.pyc').write_bytes(b'cache')
    assert source_integrity.snapshot_matches(paths.project, snap)
    (paths.project/'.config').write_text('config')
    assert not source_integrity.snapshot_matches(paths.project, snap)


@pytest.mark.parametrize('bound', ['MAX_FILES', 'MAX_BYTES'])
def test_limits_fail_closed(context, monkeypatch, bound):
    _, paths = context
    monkeypatch.setattr(source_integrity, bound, 1)
    assert not source_integrity.snapshot_matches(paths.project, {'version': 1, 'files': {'main.py': 'fake'}})


def test_unsafe_or_unavailable_inventory_fails_closed(context, monkeypatch):
    _, paths = context
    snap = source_integrity.project_snapshot(paths.project)
    monkeypatch.setattr(source_integrity.os, 'walk', lambda *a, **kw: (_ for _ in ()).throw(PermissionError()))
    assert not source_integrity.snapshot_matches(paths.project, snap)
