"""Release capability is not authorization; fixtures never contact GitHub."""
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from app.agents.roles import ReleaseEngineerRole
from app.execution.delivery import CompletionReportData


@pytest.mark.asyncio
@pytest.mark.parametrize('context,verified', [
    ({}, True),
    ({'push_to_github': False}, True),
    ({'push_to_github': 'true'}, True),
    ({'push_to_github': 1}, True),
    ({'push_to_github': True, 'goal': 'Build tool. Do not push or deploy generated code.'}, True),
    ({'push_to_github': True, 'requirements': ["Don't publish generated code"]}, True),
    ({'push_to_github': True, 'requirements': ['Never upload artifacts']}, True),
    ({'push_to_github': True}, False),
    ({'push_to_github': True}, None),
])
async def test_credentials_do_not_bypass_consent_prohibition_or_verification(monkeypatch, context, verified):
    report = CompletionReportData(task_id='fixture', objective='Build tool',
                                  test_build_status={'all_passed': verified})
    monkeypatch.setattr('app.execution.delivery.DeliveryPackager.package_delivery', AsyncMock(return_value=report))
    gh = SimpleNamespace(settings=SimpleNamespace(github_token='fixture-not-a-token', github_repo='org/repo'),
                         create_branch=AsyncMock(), commit_files=AsyncMock(), push_branch=AsyncMock(),
                         create_pull_request=AsyncMock())
    engine = SimpleNamespace(github=gh, wm=None)
    result = await ReleaseEngineerRole().execute_step('fixture', 'Release', context, engine)
    assert 'pull_request' not in result and 'pull_request_url' not in result
    for method in [gh.create_branch, gh.commit_files, gh.push_branch, gh.create_pull_request]:
        method.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize('push_result', [
    {'status': 'failed', 'exit_code': 1},
    {'status': 'skipped'},
    {'status': 'success', 'exit_code': 1},
    {'status': 'success'},
])
async def test_failed_or_unconfirmed_push_cannot_create_pr(monkeypatch, push_result):
    report = CompletionReportData(task_id='fixture', objective='Build tool', test_build_status={'all_passed': True})
    monkeypatch.setattr('app.execution.delivery.DeliveryPackager.package_delivery', AsyncMock(return_value=report))
    gh = SimpleNamespace(settings=SimpleNamespace(github_token='fixture-not-a-token', github_repo='org/repo'),
                         create_branch=AsyncMock(), commit_files=AsyncMock(), push_branch=AsyncMock(return_value=push_result),
                         create_pull_request=AsyncMock())
    result = await ReleaseEngineerRole().execute_step('fixture', 'Release', {'push_to_github': True}, SimpleNamespace(github=gh, wm=None))
    assert result['status'] == 'failed'
    assert result['publication_status'] == 'push_failed_or_denied'
    gh.create_pull_request.assert_not_awaited()


@pytest.mark.asyncio
async def test_explicit_verified_release_preserves_existing_separate_push_gate(monkeypatch, tmp_path):
    report = CompletionReportData(task_id='fixture', objective='Build tool', test_build_status={'all_passed': True})
    monkeypatch.setattr('app.execution.delivery.DeliveryPackager.package_delivery', AsyncMock(return_value=report))
    pr = SimpleNamespace(html_url='https://github.com/org/repo/pull/7',
                         model_dump=lambda **kwargs: {'html_url': 'https://github.com/org/repo/pull/7'})
    gh = SimpleNamespace(settings=SimpleNamespace(github_token='fixture-not-a-token', github_repo='org/repo'),
                         create_branch=AsyncMock(), commit_files=AsyncMock(),
                         push_branch=AsyncMock(return_value={'status': 'success', 'exit_code': 0}),
                         create_pull_request=AsyncMock(return_value=pr))
    engine = SimpleNamespace(github=gh, wm=SimpleNamespace(get_workspace_paths=lambda _: None))
    result = await ReleaseEngineerRole().execute_step('fixture', 'Release', {'push_to_github': True}, engine)
    assert result['pull_request_url'] == pr.html_url
    assert gh.push_branch.await_args.kwargs['role'] == 'release_engineer'
    assert 'allow_git_push' not in gh.push_branch.await_args.kwargs
    gh.create_pull_request.assert_awaited_once()
