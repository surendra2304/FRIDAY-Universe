"""
Git Tool for Project FORGE Execution Engine.
Manages version control, commits, diffs, branches, checkpoints, and rollbacks inside the workspace project directory.
"""

import asyncio
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from app.core.logging import get_logger
from app.core.workspace import WorkspaceManager, workspace_manager
from app.execution.permissions import (
    PermissionManager,
    ToolPermission,
    UnauthorizedGitOperationError,
    UnauthorizedGitPushError,
    permission_manager,
)

logger = get_logger("execution.git")


class GitStatusResult(BaseModel):
    clean: bool
    current_branch: str
    staged_files: list[str] = Field(default_factory=list)
    unstaged_files: list[str] = Field(default_factory=list)
    untracked_files: list[str] = Field(default_factory=list)
    raw_status: str = ""


class GitTool:
    """Provides sandboxed Git version control inside a task workspace."""

    def __init__(
        self,
        wm: WorkspaceManager | None = None,
        pm: PermissionManager | None = None,
    ):
        self.wm = wm or workspace_manager
        self.pm = pm or permission_manager

    def _get_project_root(self, task_id: str) -> Path:
        paths = self.wm.get_workspace_paths(task_id) or self.wm.create_workspace(task_id)
        return paths.project

    async def _run_git(self, task_id: str, args: list[str]) -> tuple[int, str, str]:
        root = self._get_project_root(task_id)
        proc = await asyncio.create_subprocess_exec(
            "git",
            *args,
            cwd=str(root.resolve()),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        return (
            proc.returncode or 0,
            stdout.decode("utf-8", errors="replace"),
            stderr.decode("utf-8", errors="replace"),
        )

    async def init_repo(self, task_id: str, role: str = "developer") -> bool:
        """Initialize git repo inside the project workspace if not present."""
        self.pm.check_permission(role, ToolPermission.GIT_WRITE)
        root = self._get_project_root(task_id)
        if (root / ".git").exists():
            return True

        code, out, err = await self._run_git(task_id, ["init", "-b", "main"])
        if code == 0:
            await self._run_git(task_id, ["config", "user.name", "FORGE Agent"])
            await self._run_git(task_id, ["config", "user.email", "agent@forge.local"])
            return True
        logger.error(f"Git init failed: {err}")
        return False

    async def status(self, task_id: str, role: str = "developer") -> GitStatusResult:
        """Get repository status and modified files."""
        self.pm.check_permission(role, ToolPermission.GIT_READ)
        await self.init_repo(task_id, role=role)

        code, branch_out, _ = await self._run_git(task_id, ["branch", "--show-current"])
        branch = branch_out.strip() or "main"

        code, status_out, _ = await self._run_git(task_id, ["status", "--porcelain"])

        staged, unstaged, untracked = [], [], []
        for line in status_out.splitlines():
            if not line or len(line) < 3:
                continue
            index_status = line[0]
            worktree_status = line[1]
            filepath = line[3:].strip()

            if index_status in ["M", "A", "D", "R"]:
                staged.append(filepath)
            if worktree_status in ["M", "D"]:
                unstaged.append(filepath)
            if index_status == "?" and worktree_status == "?":
                untracked.append(filepath)

        return GitStatusResult(
            clean=(len(staged) == 0 and len(unstaged) == 0 and len(untracked) == 0),
            current_branch=branch,
            staged_files=staged,
            unstaged_files=unstaged,
            untracked_files=untracked,
            raw_status=status_out,
        )

    async def diff(self, task_id: str, cached: bool = False, role: str = "developer") -> str:
        """Get git diff of changes."""
        self.pm.check_permission(role, ToolPermission.GIT_READ)
        args = ["diff", "--cached"] if cached else ["diff"]
        code, out, err = await self._run_git(task_id, args)
        return out

    # Alias for API parity
    get_diff = diff

    async def branch(self, task_id: str, branch_name: str, role: str = "developer") -> bool:
        """Create and checkout a new branch."""
        self.pm.check_permission(role, ToolPermission.GIT_WRITE)
        code, out, err = await self._run_git(task_id, ["checkout", "-b", branch_name])
        return code == 0

    async def commit(
        self,
        task_id: str,
        message: str,
        role: str = "developer",
        authorized: bool = True,
    ) -> str:
        """Stage all files and commit with a message. Returns commit SHA."""
        if not authorized:
            raise UnauthorizedGitOperationError(
                "Security Violation: Git commit requires explicit authorization."
            )
        self.pm.check_permission(role, ToolPermission.GIT_WRITE)
        await self.init_repo(task_id, role=role)
        await self._run_git(task_id, ["add", "."])
        code, out, err = await self._run_git(task_id, ["commit", "-m", message])

        code, sha_out, _ = await self._run_git(task_id, ["rev-parse", "HEAD"])
        return sha_out.strip()

    async def push(
        self,
        task_id: str,
        remote: str = "origin",
        branch: str = "main",
        role: str = "developer",
        authorized: bool = False,
        push_token: str | None = None,
    ) -> bool:
        """
        Push local commits to remote repository.
        Requires explicit, separate authorization. Unauthorized attempts are rejected.
        """
        self.pm.check_git_push_authorized(authorized=authorized, push_token=push_token)
        self.pm.check_permission(role, ToolPermission.GIT_PUSH)

        # Enforce branch policy. The elevated token must actually validate --
        # a bare non-empty string used to be enough.
        protected_branches = {"main", "master", "production", "release"}
        if branch.lower() in protected_branches and not self.pm._elevated_token_is_valid(
            push_token
        ):
            logger.warning(
                f"Direct push to protected branch '{branch}' rejected without elevated push token"
            )
            raise UnauthorizedGitPushError(
                f"Direct push to protected branch '{branch}' requires elevated authorization token"
            )

        code, out, err = await self._run_git(task_id, ["push", remote, branch])
        if code != 0:
            logger.error(f"Git push failed: {err}")
            return False
        return True

    async def create_pr(
        self,
        task_id: str,
        title: str,
        body: str,
        head_branch: str,
        base_branch: str = "main",
        role: str = "developer",
        authorized: bool = False,
        pr_token: str | None = None,
    ) -> dict[str, Any]:
        """
        Create a pull request for changes.
        Requires separate authorization.
        """
        if not authorized and not self.pm._elevated_token_is_valid(pr_token):
            raise UnauthorizedGitOperationError(
                "Security Violation: Pull request creation requires separate authorization."
            )
        self.pm.check_permission(role, ToolPermission.PR_CREATE)
        # This used to return a hardcoded https://github.com/mock-repo/pulls/<id>
        # URL and report status "created" without contacting GitHub at all, so
        # callers could not distinguish a real PR from a fabricated one. Delegate
        # to GitHubTool, which performs a real API call when a token/repo are
        # configured and otherwise fails loudly.
        from app.execution.github import GitHubTool

        github = GitHubTool(wm=self.wm, pm=self.pm)
        repo = self.wm.get_workspace_paths(task_id)
        remote_url = ""
        if repo:
            try:
                code, out, _ = await self._run_git(task_id, ["remote", "get-url", "origin"])
                if code == 0:
                    remote_url = out.strip()
            except Exception:
                remote_url = ""

        result = await github.create_pull_request(
            repo=None,
            title=title,
            body=body,
            head_branch=head_branch,
            base_branch=base_branch,
        )
        return {
            "task_id": task_id,
            "title": result.title,
            "head": result.head,
            "base": result.base,
            "status": result.state,
            "pr_url": result.html_url,
            "pr_number": result.pr_number,
            "remote_url": remote_url,
        }

    async def checkpoint(self, task_id: str, checkpoint_name: str, role: str = "developer") -> str:
        """Create a commit and lightweight git tag for recovery."""
        self.pm.check_permission(role, ToolPermission.GIT_WRITE)
        sha = await self.commit(task_id, f"Checkpoint: {checkpoint_name}", role=role)
        tag_name = f"checkpoint_{checkpoint_name}".replace(" ", "_").replace(":", "_")
        await self._run_git(task_id, ["tag", "-f", tag_name])
        logger.info(f"Created git checkpoint tag '{tag_name}' (sha={sha[:8]}) in task {task_id}")
        return tag_name

    async def tag_release(
        self, task_id: str, tag_name: str = "v1.0-forge-delivery", role: str = "release_engineer"
    ) -> str:
        """Create a final tagged release checkpoint before delivery."""
        self.pm.check_permission(role, ToolPermission.GIT_WRITE)
        await self.init_repo(task_id, role=role)
        await self.commit(task_id, f"Release delivery: {tag_name}", role=role)
        await self._run_git(task_id, ["tag", "-f", tag_name])
        logger.info(f"Created git release tag '{tag_name}' in task {task_id}")
        return tag_name

    async def get_log(self, task_id: str, max_count: int = 10, role: str = "developer") -> str:
        """Retrieve recent git commit log."""
        self.pm.check_permission(role, ToolPermission.GIT_READ)
        code, out, err = await self._run_git(task_id, ["log", f"-n{max_count}", "--oneline"])
        return out.strip() if code == 0 else ""

    async def rollback(self, task_id: str, target_tag_or_sha: str, role: str = "developer") -> bool:
        """Hard reset workspace to the specified checkpoint tag or commit SHA."""
        self.pm.check_permission(role, ToolPermission.GIT_WRITE)
        code, out, err = await self._run_git(task_id, ["reset", "--hard", target_tag_or_sha])
        if code == 0:
            await self._run_git(task_id, ["clean", "-fd"])
            logger.info(f"Rolled back workspace in task {task_id} to '{target_tag_or_sha}'")
            return True
        logger.error(f"Rollback failed: {err}")
        return False



git_tool = GitTool()
