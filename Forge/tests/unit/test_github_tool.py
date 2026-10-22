"""
Unit tests for GitHubTool and ReleaseEngineerRole GitHub Pull Request automation.
"""

from pathlib import Path
from uuid import uuid4

import pytest

from app.agents.roles import ReleaseEngineerRole
from app.core.config import Settings
from app.core.workspace import WorkspaceManager
from app.execution.engine import ExecutionEngine
from app.execution.github import GitHubTool, PullRequestResult
from app.providers.direct import DirectProvider


@pytest.mark.asyncio
async def test_github_tool_branch_and_commit(temp_dir: Path):
    settings = Settings()
    settings.workspaces_dir = temp_dir / "workspaces"
    settings.github_repo = "org/sample-repo"
    wm = WorkspaceManager(settings=settings)
    engine = ExecutionEngine(wm=wm)
    gh_tool = GitHubTool(settings=settings, wm=wm, pm=engine.pm, git=engine.git)

    task_id = str(uuid4())
    wm.create_workspace(task_id)
    wm.write_project_file(task_id, "main.py", 'print("Hello from FORGE GitHub workflow")\n')

    # 1. Create branch
    branch_res = await gh_tool.create_branch(task_id, branch_name="forge/feature-test")
    assert branch_res["status"] == "success"
    assert branch_res["branch_name"] == "forge/feature-test"

    # 2. Commit files
    commit_res = await gh_tool.commit_files(task_id, commit_message="feat: initial feature commit")
    assert commit_res["status"] == "success"
    assert commit_res["commit_hash"] is not None


@pytest.mark.asyncio
async def test_github_tool_create_pull_request_fallback():
    gh_tool = GitHubTool()
    pr_result = await gh_tool.create_pull_request(
        repo="octocat/Hello-World",
        title="[FORGE] Autonomous Feature Implementation",
        body="## Completion Report\nAll verification checks passed.",
        head_branch="forge/feature-1234",
        base_branch="main",
    )

    assert isinstance(pr_result, PullRequestResult)
    assert pr_result.pr_number >= 1
    assert "github.com/octocat/Hello-World/pull/" in pr_result.html_url
    assert pr_result.head == "forge/feature-1234"
    assert pr_result.base == "main"


@pytest.mark.asyncio
async def test_release_engineer_role_github_pr_workflow(temp_dir: Path):
    settings = Settings()
    settings.workspaces_dir = temp_dir / "workspaces"
    settings.github_repo = "owner/repo"
    wm = WorkspaceManager(settings=settings)
    engine = ExecutionEngine(wm=wm)

    task_id = str(uuid4())
    wm.create_workspace(task_id)
    wm.write_project_file(task_id, "main.py", 'print("Production release ready")\n')

    provider = DirectProvider()
    release_agent = ReleaseEngineerRole(provider=provider)

    context = {
        "goal": "Synthesize microservice and create PR",
        "requirements": ["Production quality code"],
        "push_to_github": True,
        "github_repo": "owner/repo",
    }

    res = await release_agent.execute_step(
        task_id=task_id,
        node_title="Release Packaging & GitHub PR",
        context=context,
        engine=engine,
    )

    assert res["status"] == "success"
    assert res["release_tag"] == "v1.0-forge-delivery"
    assert "pull_request" in res
    assert "pull_request_url" in res
    assert "github.com/owner/repo/pull/" in res["pull_request_url"]
