"""Real sandbox test isolation and honest unsupported offline generation."""
import pytest
from app.agents.roles import TesterRole
from app.agents.synthesis import ProjectKind, parse_goal, synthesize_project
from app.verification.checkers import TestChecker
from app.core.config import Settings
from app.core.workspace import WorkspaceManager
from app.execution.engine import ExecutionEngine


@pytest.mark.asyncio
async def test_host_pytest_options_and_conftest_cannot_leak_into_generated_project(tmp_path):
    # The live host's --asyncio-mode option required a missing plugin. Unknown
    # options + raising conftest are stronger deterministic isolation probes.
    (tmp_path / 'pyproject.toml').write_text('[tool.pytest.ini_options]\naddopts = "--forbidden-host-option"\n')
    (tmp_path / 'conftest.py').write_text('raise RuntimeError("host conftest must not execute")\n')
    wm = WorkspaceManager(settings=Settings(workspaces_dir=tmp_path / 'workspaces'))
    wm.write_project_file('fixture', 'test_extra.py', 'def test_extra():\n    assert 2 + 2 == 4\n')
    engine = ExecutionEngine(wm=wm)
    evidence = await TestChecker().run_check('fixture', engine)
    assert evidence.passed, evidence.stderr
    assert '1 passed' in evidence.stdout
    assert '--confcutdir=.' in evidence.command and '--rootdir=.' in evidence.command
    result = await TesterRole().execute_step('fixture', 'test', {'goal': 'CSV using pytest'}, engine)
    assert result['exit_code'] == 0 and '1 passed' in result['stdout']


def test_standard_library_constraint_is_not_a_library_project():
    assert parse_goal('Write a Python CSV to JSON converter using only the standard library. Report artifact paths.').kind is ProjectKind.SCRIPT
    assert parse_goal('Build a Python path utility library.').kind is ProjectKind.LIBRARY


@pytest.mark.parametrize('goal', [
    'Write a Python CSV to JSON converter using only the standard library. Report artifact paths.',
    'Convert CSV into JSON, run unittest tests and report real paths.',
    'Build a CSV -> JSON script.',
])
def test_unsupported_offline_conversion_declines_instead_of_inventing_path_utility(goal):
    assert synthesize_project(goal) == {}


def test_supported_opposite_direction_is_not_removed():
    files = synthesize_project('Create a Python script that converts a JSON file to CSV using the standard library')
    assert any('def json_to_csv' in source for source in files.values())


@pytest.mark.asyncio
async def test_only_delivered_project_pytest_config_is_honored(tmp_path):
    (tmp_path / 'pytest.ini').write_text('[pytest]\naddopts = --forbidden-host-option\n')
    wm = WorkspaceManager(settings=Settings(workspaces_dir=tmp_path / 'workspaces'))
    wm.write_project_file('fixture', 'pytest.ini', '[pytest]\naddopts = -k chosen\n')
    wm.write_project_file('fixture', 'test_config.py', 'def test_chosen():\n assert True\ndef test_other():\n assert False\n')
    evidence = await TestChecker().run_check('fixture', ExecutionEngine(wm=wm))
    assert evidence.passed, evidence.stderr
    assert '-c pytest.ini' in evidence.command
    assert '1 passed' in evidence.stdout and '1 deselected' in evidence.stdout
