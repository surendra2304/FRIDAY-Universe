"""
Regression tests for the authorization / input-validation defects found in the
2026-10 audit.

Bug #9   PermissionManager.check_git_push_authorized treated *any* non-empty
         push_token as authorization, so push_token="x" -- or
         "totally-bogus-string-from-attacker" -- satisfied both the general gate
         and the protected-branch gate. GitTool.create_pr had the identical
         hole with pr_token.

Bug #17  DEFAULT_ROLE_PERMISSIONS["release_engineer"] was missing GIT_PUSH and
         PR_CREATE, so the role whose entire job is branch -> commit -> push ->
         PR (ReleaseEngineerRole.execute_step) could not complete its workflow.

Bug #10  WorkspaceManager.validate_repository_url ended its allowlist with a bare
         `^[A-Za-z0-9_.\\-\\/\\\\]+$` catch-all that also matched "/etc",
         "../../..", "file:///etc" and the git option-injection payloads "-bare"
         and "-c". The allowlist filtered nothing.
"""

from pathlib import Path

import pytest

from app.core.config import Settings
from app.core.workspace import WorkspaceManager
from app.execution.git_tool import GitTool
from app.execution.permissions import (
    DEFAULT_ROLE_PERMISSIONS,
    PermissionManager,
    ToolPermission,
    UnauthorizedGitOperationError,
    UnauthorizedGitPushError,
)


@pytest.fixture
def pm() -> PermissionManager:
    return PermissionManager()


# ---------------------------------------------------------------------------
# Bug #9 -- the push gate must fail closed
# ---------------------------------------------------------------------------


def test_arbitrary_push_token_does_not_authorize_a_push(pm: PermissionManager):
    for bogus in ("x", "totally-bogus-string-from-attacker", " ", "0", "null"):
        with pytest.raises(UnauthorizedGitPushError):
            pm.check_git_push_authorized(authorized=False, push_token=bogus)


def test_no_configured_token_means_no_token_can_validate(pm: PermissionManager, monkeypatch):
    settings = Settings()
    settings.git_push_token = None
    monkeypatch.setattr("app.execution.permissions.get_settings", lambda: settings)
    with pytest.raises(UnauthorizedGitPushError):
        pm.check_git_push_authorized(authorized=False, push_token="literally-anything")


def test_correctly_configured_token_does_authorize(pm: PermissionManager, monkeypatch):
    settings = Settings()
    settings.git_push_token = "s3cr3t-elevated-token"
    monkeypatch.setattr("app.execution.permissions.get_settings", lambda: settings)

    # Explicit authorization alone is still sufficient.
    pm.check_git_push_authorized(authorized=True, push_token=None)
    # A token that matches the configured secret is sufficient too.
    pm.check_git_push_authorized(authorized=False, push_token="s3cr3t-elevated-token")
    # A near-miss must not be.
    with pytest.raises(UnauthorizedGitPushError):
        pm.check_git_push_authorized(authorized=False, push_token="s3cr3t-elevated-toke")


def test_git_push_rejects_protected_branch_without_valid_token(tmp_path, monkeypatch):
    settings = Settings()
    settings.workspaces_dir = tmp_path / "workspaces"
    settings.git_push_token = None
    settings.ensure_directories()
    monkeypatch.setattr("app.execution.permissions.get_settings", lambda: settings)

    wm = WorkspaceManager(settings=settings)
    tool = GitTool(wm=wm)

    with pytest.raises(UnauthorizedGitPushError):
        _run(
            tool.push(
                "task_push_gate",
                branch="main",
                role="release_engineer",
                authorized=True,  # explicit authorization is NOT enough for a protected branch
                push_token="totally-bogus-string-from-attacker",
            )
        )


def test_git_push_still_works_with_explicit_authorization(tmp_path, monkeypatch):
    settings = Settings()
    settings.workspaces_dir = tmp_path / "workspaces"
    settings.git_push_token = None
    settings.ensure_directories()
    monkeypatch.setattr("app.execution.permissions.get_settings", lambda: settings)

    wm = WorkspaceManager(settings=settings)
    tool = GitTool(wm=wm)

    # No remote is configured, so git push fails -- but it must fail at the git
    # layer (returns False), not at the authorization layer (raises).
    result = _run(
        tool.push(
            "task_push_ok",
            branch="feature/thing",
            role="release_engineer",
            authorized=True,
            push_token=None,
        )
    )
    assert result is False


def test_create_pr_rejects_arbitrary_pr_token(tmp_path, monkeypatch):
    settings = Settings()
    settings.workspaces_dir = tmp_path / "workspaces"
    settings.git_push_token = None
    settings.ensure_directories()
    monkeypatch.setattr("app.execution.permissions.get_settings", lambda: settings)

    wm = WorkspaceManager(settings=settings)
    tool = GitTool(wm=wm)

    with pytest.raises(UnauthorizedGitOperationError):
        _run(
            tool.create_pr(
                "task_pr_gate",
                title="t",
                body="b",
                head_branch="feature",
                base_branch="main",
                role="release_engineer",
                authorized=False,
                pr_token="totally-bogus-string-from-attacker",
            )
        )


def test_create_pr_accepts_a_valid_elevated_token(tmp_path, monkeypatch):
    """The gate must let a validated token through -- and stop fabricating URLs."""
    from app.execution.github import GitHubTool, PullRequestResult

    settings = Settings()
    settings.workspaces_dir = tmp_path / "workspaces"
    settings.git_push_token = "elevated-secret"
    settings.ensure_directories()
    monkeypatch.setattr("app.execution.permissions.get_settings", lambda: settings)

    async def fake_create_pr(self, **kwargs):
        return PullRequestResult(
            pr_number=7,
            html_url="https://github.com/real-org/real-repo/pull/7",
            title=kwargs["title"],
            body=kwargs["body"],
            head=kwargs["head_branch"],
            base=kwargs["base_branch"],
        )

    monkeypatch.setattr(GitHubTool, "create_pull_request", fake_create_pr)

    wm = WorkspaceManager(settings=settings)
    tool = GitTool(wm=wm)

    result = _run(
        tool.create_pr(
            "task_pr_ok",
            title="t",
            body="b",
            head_branch="feature",
            base_branch="main",
            role="release_engineer",
            authorized=False,
            pr_token="elevated-secret",
        )
    )
    assert result["status"] == "open"
    assert result["head"] == "feature"
    assert result["pr_url"] == "https://github.com/real-org/real-repo/pull/7"
    assert result["pr_number"] == 7


def test_create_pr_never_returns_the_hardcoded_mock_url(tmp_path, monkeypatch):
    """GitTool.create_pr used to return https://github.com/mock-repo/pulls/<id>
    and report status 'created' without contacting GitHub at all."""
    settings = Settings()
    settings.workspaces_dir = tmp_path / "workspaces"
    settings.git_push_token = "elevated-secret"
    settings.ensure_directories()
    monkeypatch.setattr("app.execution.permissions.get_settings", lambda: settings)

    wm = WorkspaceManager(settings=settings)
    tool = GitTool(wm=wm)

    result = _run(
        tool.create_pr(
            "task_pr_mock",
            title="t",
            body="b",
            head_branch="feature",
            base_branch="main",
            role="release_engineer",
            authorized=True,
            pr_token=None,
        )
    )
    assert "mock-repo" not in result["pr_url"], (
        f"create_pr still fabricates a PR URL: {result['pr_url']}"
    )
    assert result["status"] != "created"


# ---------------------------------------------------------------------------
# Bug #17 -- release_engineer must hold the permissions its workflow needs
# ---------------------------------------------------------------------------


def test_release_engineer_can_push_and_create_prs():
    perms = DEFAULT_ROLE_PERMISSIONS["release_engineer"]
    assert ToolPermission.GIT_PUSH in perms, "release_engineer cannot git push"
    assert ToolPermission.PR_CREATE in perms, "release_engineer cannot create PRs"
    assert ToolPermission.GIT_COMMIT in perms, "release_engineer cannot commit"


def test_release_engineer_workflow_is_not_permission_blocked():
    """The full branch->commit->push->PR step must clear the permission layer."""
    pm = PermissionManager()
    for permission in (
        ToolPermission.GIT_WRITE,
        ToolPermission.GIT_COMMIT,
        ToolPermission.GIT_PUSH,
        ToolPermission.PR_CREATE,
    ):
        # Must not raise PermissionDeniedError.
        pm.check_permission("release_engineer", permission)


# ---------------------------------------------------------------------------
# Bug #10 -- the repository allowlist must actually filter
# ---------------------------------------------------------------------------


def test_allowlist_accepts_the_documented_remote_hosts():
    for url in (
        "https://github.com/surendra2304/FRIDAY.git",
        "https://github.com/surendra2304/Forge",
        "git@github.com:surendra2304/Forge.git",
        "https://gitlab.com/group/project.git",
    ):
        WorkspaceManager.validate_repository_url(url)


def test_allowlist_accepts_a_local_repository_inside_the_workspaces_root(
    tmp_path: Path, monkeypatch
):
    settings = Settings()
    settings.workspaces_dir = tmp_path / "workspaces"
    settings.ensure_directories()
    monkeypatch.setattr("app.core.workspace.get_settings", lambda: settings)

    repo = settings.base_dir / settings.workspaces_dir / "local_src"
    repo.mkdir(parents=True)
    (repo / ".git").mkdir()

    WorkspaceManager.validate_repository_url(str(repo))
    WorkspaceManager.validate_repository_url(f"file://{repo}")


def test_allowlist_rejects_a_local_repository_outside_the_workspaces_root(
    tmp_path: Path, monkeypatch
):
    settings = Settings()
    settings.workspaces_dir = tmp_path / "workspaces"
    settings.ensure_directories()
    monkeypatch.setattr("app.core.workspace.get_settings", lambda: settings)

    outside = tmp_path / "outside_src"
    outside.mkdir()
    (outside / ".git").mkdir()

    with pytest.raises(ValueError):
        WorkspaceManager.validate_repository_url(str(outside))
    with pytest.raises(ValueError):
        WorkspaceManager.validate_repository_url(f"file://{outside}")


@pytest.mark.parametrize(
    "payload",
    [
        "javascript:alert(1)",
        "http://insecure-untrusted-repo.org/malware.git",
        "/etc",
        "/home/user/Forge",
        "../../..",
        "file:///etc",
        "-bare",
        "-c",
        "--upload-pack=touch /tmp/pwn",
        "",
        "   ",
        "relative/path",
        "https://evil.example.com/org/repo.git",
        "git@evil.example.com:org/repo.git",
    ],
)
def test_allowlist_rejects_everything_else(payload: str):
    with pytest.raises(ValueError):
        WorkspaceManager.validate_repository_url(payload)


def test_option_injection_payload_cannot_reach_git(tmp_path: Path):
    """The validator must refuse before git ever sees a leading-dash argument."""
    settings = Settings()
    settings.workspaces_dir = tmp_path / "workspaces"
    settings.ensure_directories()
    wm = WorkspaceManager(settings=settings)

    with pytest.raises(ValueError):
        wm.create_workspace("task_inject", repo_url="--upload-pack=touch /tmp/pwn")

    assert not Path("/tmp/pwn").exists()


def _run(coro):
    import asyncio

    return asyncio.run(coro)
