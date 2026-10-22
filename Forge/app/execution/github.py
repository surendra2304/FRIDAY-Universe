"""
GitHub Tool for Project FORGE.
Enables branch creation, committing, pushing, and Pull Request automation.
"""

from typing import Any

import httpx
from pydantic import BaseModel, Field

from app.core.config import Settings, get_settings
from app.core.logging import get_logger
from app.core.workspace import WorkspaceManager, workspace_manager
from app.execution.git_tool import GitTool, git_tool
from app.execution.permissions import PermissionManager, ToolPermission, permission_manager
from app.execution.terminal import TerminalTool

logger = get_logger("execution.github")


class PullRequestResult(BaseModel):
    pr_number: int = Field(default=1)
    html_url: str
    title: str
    body: str
    head: str
    base: str
    state: str = "open"


class GitHubTool:
    """Provides GitHub API integration and authenticated Git workflows."""

    def __init__(
        self,
        settings: Settings | None = None,
        wm: WorkspaceManager | None = None,
        pm: PermissionManager | None = None,
        git: GitTool | None = None,
    ):
        self.settings = settings or get_settings()
        self.wm = wm or workspace_manager
        self.pm = pm or permission_manager
        self.git = git or git_tool
        self.terminal = TerminalTool(wm=self.wm, pm=self.pm)

    def _get_token(self, token_override: str | None = None) -> str | None:
        return token_override or self.settings.github_token

    def _get_repo(self, repo_override: str | None = None) -> str | None:
        return repo_override or self.settings.github_repo

    async def create_branch(
        self,
        task_id: str,
        branch_name: str,
        base_branch: str = "main",
        role: str = "release_engineer",
    ) -> dict[str, Any]:
        """Create or checkout a local Git branch for the task."""
        self.pm.check_permission(role, ToolPermission.GIT_WRITE)
        self.wm.get_workspace_paths(task_id) or self.wm.create_workspace(task_id)

        # Initialize repo if needed
        await self.git.init_repo(task_id, role=role)

        # Branch from the requested base. `base_branch` used to be accepted and
        # then ignored, so every branch was cut from whatever HEAD happened to be.
        code, current, _ = await self.git._run_git(task_id, ["rev-parse", "--abbrev-ref", "HEAD"])
        if code == 0 and current.strip() and current.strip() != base_branch:
            base_res = await self.terminal.run_command(
                task_id=task_id,
                command=f"git checkout -B {base_branch}",
                role=role,
            )
            if base_res.exit_code != 0:
                logger.warning(
                    f"[Task {task_id}] Could not checkout base branch '{base_branch}': "
                    f"{base_res.stderr.strip()}"
                )

        # Checkout new branch
        cmd_res = await self.terminal.run_command(
            task_id=task_id,
            command=f"git checkout -B {branch_name}",
            role=role,
        )
        logger.info(
            f"[Task {task_id}] Created and checked out branch '{branch_name}' (exit={cmd_res.exit_code})"
        )
        return {
            "status": "success" if cmd_res.exit_code == 0 else "failed",
            "branch_name": branch_name,
            "base_branch": base_branch,
            "stdout": cmd_res.stdout,
            "stderr": cmd_res.stderr,
        }

    async def commit_files(
        self,
        task_id: str,
        commit_message: str,
        role: str = "release_engineer",
    ) -> dict[str, Any]:
        """Stage and commit all files in the task's project directory."""
        self.pm.check_permission(role, ToolPermission.GIT_WRITE)
        commit_hash = await self.git.commit(
            task_id=task_id,
            message=commit_message,
            role=role,
        )
        return {
            "status": "success",
            "commit_hash": commit_hash,
            "message": commit_message,
        }

    async def push_branch(
        self,
        task_id: str,
        branch_name: str,
        repo: str | None = None,
        token: str | None = None,
        role: str = "release_engineer",
    ) -> dict[str, Any]:
        """Push the branch to the remote GitHub repository."""
        self.pm.check_permission(role, ToolPermission.GIT_WRITE)
        gh_token = self._get_token(token)
        target_repo = self._get_repo(repo)

        if not target_repo:
            return {
                "status": "skipped",
                "message": "No GitHub repository specified (GITHUB_REPO not configured).",
            }

        remote_url = (
            f"https://x-access-token:{gh_token}@github.com/{target_repo}.git"
            if gh_token
            else f"https://github.com/{target_repo}.git"
        )

        # Set or update remote origin
        await self.terminal.run_command(
            task_id=task_id,
            command=f"git remote set-url origin {remote_url} || git remote add origin {remote_url}",
            role=role,
        )

        cmd_res = await self.terminal.run_command(
            task_id=task_id,
            command=f"git push -u origin {branch_name} --force",
            role=role,
        )

        return {
            "status": "success" if cmd_res.exit_code == 0 else "failed",
            "branch_name": branch_name,
            "repo": target_repo,
            "exit_code": cmd_res.exit_code,
            "stdout": cmd_res.stdout,
            "stderr": cmd_res.stderr,
        }

    async def create_pull_request(
        self,
        repo: str | None,
        title: str,
        body: str,
        head_branch: str,
        base_branch: str = "main",
        token: str | None = None,
    ) -> PullRequestResult:
        """Create a Pull Request on GitHub using the REST API."""
        gh_token = self._get_token(token)
        target_repo = self._get_repo(repo)

        if not target_repo:
            target_repo = "owner/repo"

        if not gh_token:
            logger.warning("GITHUB_TOKEN not provided; generating mock Pull Request metadata.")
            return PullRequestResult(
                pr_number=42,
                html_url=f"https://github.com/{target_repo}/pull/42",
                title=title,
                body=body,
                head=head_branch,
                base=base_branch,
                state="open",
            )

        api_url = f"https://api.github.com/repos/{target_repo}/pulls"
        headers = {
            "Authorization": f"Bearer {gh_token}",
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "FORGE-Autonomous-Engine",
        }
        payload = {
            "title": title,
            "body": body,
            "head": head_branch,
            "base": base_branch,
        }

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.post(api_url, json=payload, headers=headers)
                if response.status_code in [200, 201]:
                    data = response.json()
                    logger.info(
                        f"Successfully opened GitHub Pull Request #{data.get('number')} at {data.get('html_url')}"
                    )
                    return PullRequestResult(
                        pr_number=data.get("number", 1),
                        html_url=data.get("html_url", f"https://github.com/{target_repo}/pull/1"),
                        title=title,
                        body=body,
                        head=head_branch,
                        base=base_branch,
                        state=data.get("state", "open"),
                    )
                else:
                    logger.error(
                        f"GitHub API error creating PR ({response.status_code}): {response.text}"
                    )
                    return PullRequestResult(
                        pr_number=1,
                        html_url=f"https://github.com/{target_repo}/pull/1",
                        title=title,
                        body=body,
                        head=head_branch,
                        base=base_branch,
                        state="draft",
                    )
        except Exception as e:
            logger.error(f"Failed to connect to GitHub API: {e}")
            return PullRequestResult(
                pr_number=1,
                html_url=f"https://github.com/{target_repo}/pull/1",
                title=title,
                body=body,
                head=head_branch,
                base=base_branch,
                state="error",
            )


github_tool = GitHubTool()
