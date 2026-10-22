"""
Workspace Manager for Project FORGE.
Handles isolated workspace provisioning, directory hierarchies, path resolution, and artifact management.
"""

import os
import shutil
from pathlib import Path

from pydantic import BaseModel

from app.core.config import Settings, get_settings
from app.core.logging import get_logger

logger = get_logger("core.workspace")


def canonical_path(path: Path) -> Path:
    """Return a fully resolved, case-corrected path.

    On Windows, Path.resolve() keeps 8.3 short names (C:\\Users\\RUNNER~1\\...)
    when a component of an *existing* parent directory uses them, while paths
    built by joining onto such a parent can carry the long form from a
    different origin. Mixing the two forms breaks relative_to() containment
    checks. os.path.realpath resolves short names to their long form on both
    platforms and is safe on nonexistent leaves.
    """
    return Path(os.path.realpath(str(path)))


class WorkspacePaths(BaseModel):
    """Encapsulates all standard subdirectories of an isolated task workspace."""

    root: Path
    project: Path
    artifacts: Path
    logs: Path
    state: Path
    cache: Path

    model_config = {"arbitrary_types_allowed": True}

    def to_dict(self) -> dict[str, str]:
        return {
            "root": str(self.root.resolve()),
            "project": str(self.project.resolve()),
            "artifacts": str(self.artifacts.resolve()),
            "logs": str(self.logs.resolve()),
            "state": str(self.state.resolve()),
            "cache": str(self.cache.resolve()),
        }


class WorkspaceManager:
    """Manages creation, resolution, and lifecycle of task-specific filesystem sandboxes."""

    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()

    def get_task_workspace_dir(self, task_id: str) -> Path:
        """Return the root path for a given task ID."""
        # Sanitize task_id prefix if needed
        folder_name = task_id if task_id.startswith("task") else f"task_{task_id}"
        base_workspaces = self.settings.base_dir / self.settings.workspaces_dir
        return base_workspaces / folder_name

    def create_workspace(
        self,
        task_id: str,
        custom_base: Path | None = None,
        repo_url: str | None = None,
        local_path: str | Path | None = None,
    ) -> WorkspacePaths:
        """
        Create isolated directory hierarchy for task under workspaces/task_<id>/:
        - project/ (optionally cloned from repo_url or copied from local_path)
        - artifacts/
        - logs/
        - state/
        - cache/
        """
        import subprocess

        if custom_base:
            base_workspaces = canonical_path(self.settings.base_dir / self.settings.workspaces_dir)
            resolved_custom = canonical_path(Path(custom_base))
            try:
                resolved_custom.relative_to(base_workspaces)
            except ValueError as exc:
                raise ValueError(
                    f"Custom workspace base '{custom_base}' escapes trusted workspaces root '{base_workspaces}'"
                ) from exc
            root_dir = resolved_custom
        else:
            root_dir = self.get_task_workspace_dir(task_id).resolve()

        subdirs = {
            "project": root_dir / "project",
            "artifacts": root_dir / "artifacts",
            "logs": root_dir / "logs",
            "state": root_dir / "state",
            "cache": root_dir / "cache",
        }

        # Create root and all subdirectories
        root_dir.mkdir(parents=True, exist_ok=True)
        for name, path in subdirs.items():
            if name != "project":
                path.mkdir(parents=True, exist_ok=True)

        # Populate project directory from repo_url, local_path, or create empty
        if repo_url:
            self.validate_repository_url(repo_url)
            logger.info(f"Cloning repository '{repo_url}' into task workspace {task_id}...")
            try:
                subprocess.run(
                    ["git", "clone", "--depth", "1", repo_url, str(subdirs["project"])],
                    capture_output=True,
                    text=True,
                    check=True,
                )
                logger.info(f"Successfully cloned repository into {subdirs['project']}")
            except subprocess.CalledProcessError as e:
                logger.error(f"Failed to clone repository '{repo_url}': {e.stderr}")
                subdirs["project"].mkdir(parents=True, exist_ok=True)
                raise RuntimeError(f"Git clone failed for '{repo_url}': {e.stderr}") from e
        elif local_path:
            src_path = Path(local_path).resolve()
            logger.info(
                f"Copying local codebase from '{src_path}' into task workspace {task_id}..."
            )
            if not src_path.exists():
                raise FileNotFoundError(f"Local codebase path does not exist: {src_path}")
            subdirs["project"].mkdir(parents=True, exist_ok=True)
            shutil.copytree(src_path, subdirs["project"], dirs_exist_ok=True)
            logger.info(
                f"Successfully copied local codebase from '{src_path}' into {subdirs['project']}"
            )
        else:
            subdirs["project"].mkdir(parents=True, exist_ok=True)

        # Write metadata manifest
        manifest_file = root_dir / ".forge_workspace"
        manifest_content = (
            f"task_id: {task_id}\n"
            f"initialized: true\n"
            f"repo_url: {repo_url or 'none'}\n"
            f"local_path: {str(local_path) if local_path else 'none'}\n"
            f"subdirs: [project, artifacts, logs, state, cache]\n"
        )
        manifest_file.write_text(manifest_content, encoding="utf-8")

        paths = WorkspacePaths(
            root=canonical_path(root_dir),
            project=canonical_path(subdirs["project"]),
            artifacts=canonical_path(subdirs["artifacts"]),
            logs=canonical_path(subdirs["logs"]),
            state=canonical_path(subdirs["state"]),
            cache=canonical_path(subdirs["cache"]),
        )
        logger.info(f"Initialized isolated task workspace at {root_dir}")
        return paths

    def get_workspace_paths(self, task_id: str) -> WorkspacePaths | None:
        """Resolve workspace paths for an existing task."""
        root_dir = self.get_task_workspace_dir(task_id)
        if not root_dir.exists():
            return None

        return WorkspacePaths(
            root=canonical_path(root_dir),
            project=canonical_path(root_dir / "project"),
            artifacts=canonical_path(root_dir / "artifacts"),
            logs=canonical_path(root_dir / "logs"),
            state=canonical_path(root_dir / "state"),
            cache=canonical_path(root_dir / "cache"),
        )

    def write_project_file(self, task_id: str, relative_path: str, content: str) -> Path:
        """Safely write a file inside the task's project directory."""
        paths = self.get_workspace_paths(task_id) or self.create_workspace(task_id)
        project_root = canonical_path(paths.project)
        target = (
            project_root / relative_path
            if not Path(relative_path).is_absolute()
            else Path(relative_path)
        )
        target = canonical_path(target)

        # Prevent directory traversal outside project dir
        try:
            target.relative_to(project_root)
        except ValueError as exc:
            raise ValueError(f"Path traversal detected: {relative_path}") from exc

        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        return target

    def read_project_file(self, task_id: str, relative_path: str) -> str | None:
        """Safely read a file from the task's project directory."""
        paths = self.get_workspace_paths(task_id)
        if not paths:
            return None
        project_root = canonical_path(paths.project)
        target = (
            project_root / relative_path
            if not Path(relative_path).is_absolute()
            else Path(relative_path)
        )
        target = canonical_path(target)
        try:
            target.relative_to(project_root)
        except ValueError:
            return None
        if not target.exists() or not target.is_file():
            return None
        return target.read_text(encoding="utf-8")

    def save_artifact(self, task_id: str, artifact_name: str, content: bytes | str) -> Path:
        """Save a generated artifact to the task's artifacts directory."""
        paths = self.get_workspace_paths(task_id) or self.create_workspace(task_id)
        artifacts_root = canonical_path(paths.artifacts)
        target = canonical_path(
            artifacts_root / artifact_name
            if not Path(artifact_name).is_absolute()
            else Path(artifact_name)
        )

        try:
            target.relative_to(artifacts_root)
        except ValueError as exc:
            raise ValueError(f"Invalid artifact path: {artifact_name}") from exc

        target.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(content, str):
            target.write_text(content, encoding="utf-8")
        else:
            target.write_bytes(content)
        return target

    def append_log(self, task_id: str, log_filename: str, log_message: str) -> None:
        """Append log line to specified log file in logs directory."""
        paths = self.get_workspace_paths(task_id) or self.create_workspace(task_id)
        log_file = paths.logs / log_filename
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(log_message.rstrip() + "\n")

    @staticmethod
    def validate_repository_url(repo_url: str) -> None:
        r"""Validate a repository source against the approved allowlist.

        The previous allowlist ended with a bare `^[A-Za-z0-9_.\-\/\\]+$`
        catch-all that also matched absolute host paths ("/etc"), traversal
        payloads ("../../..") and git option-injection payloads ("-bare", "-c"),
        so the allowlist filtered nothing at all.

        Accepted sources:
          * the documented remote hosts (github.com, gitlab.com, https or ssh), or
          * a local directory that exists and lives inside the trusted
            workspaces root.

        Anything else -- including a leading dash, which git would parse as a
        command-line option -- is rejected.
        """
        import re

        clean_url = repo_url.strip()
        if not clean_url:
            raise ValueError("Repository URL must not be empty")

        # A leading dash would be parsed by git as a command-line option.
        if clean_url.startswith("-"):
            raise ValueError(
                f"Repository URL '{repo_url}' is not in the allowed repository allowlist"
            )

        ALLOWED_REMOTE_PATTERNS = [
            r"^https:\/\/github\.com\/[A-Za-z0-9_.-]+\/[A-Za-z0-9_.-]+(\.git)?$",
            r"^git@github\.com:[A-Za-z0-9_.-]+\/[A-Za-z0-9_.-]+(\.git)?$",
            r"^https:\/\/gitlab\.com\/[A-Za-z0-9_.-]+\/[A-Za-z0-9_.-]+(\.git)?$",
        ]
        if any(re.match(pattern, clean_url) for pattern in ALLOWED_REMOTE_PATTERNS):
            return

        # Local source: a file:// URL or a bare filesystem path.
        if clean_url.startswith("file://"):
            local_part = clean_url[len("file://") :]
        else:
            local_part = clean_url

        candidate = Path(local_part)
        if not candidate.is_absolute():
            raise ValueError(
                f"Repository URL '{repo_url}' is not in the allowed repository allowlist"
            )

        normalized = Path(os.path.normpath(str(candidate)))
        if ".." in normalized.parts:
            raise ValueError(
                f"Repository URL '{repo_url}' is not in the allowed repository allowlist"
            )

        if not normalized.is_dir():
            raise ValueError(f"Repository path '{repo_url}' is not an existing directory")

        # Local sources must stay inside the trusted workspaces root, matching
        # the containment rule create_workspace() applies to `custom_base`.
        trusted_root = canonical_path(get_settings().base_dir / get_settings().workspaces_dir)
        resolved_local = canonical_path(normalized)
        try:
            resolved_local.relative_to(trusted_root)
        except ValueError as exc:
            raise ValueError(
                f"Repository path '{repo_url}' is outside the trusted workspaces root"
            ) from exc

    def create_snapshot(self, task_id: str, snapshot_name: str) -> Path:
        """Create a full filesystem snapshot of the project directory."""
        paths = self.get_workspace_paths(task_id) or self.create_workspace(task_id)
        snapshots_dir = paths.state / "snapshots"
        snapshots_dir.mkdir(parents=True, exist_ok=True)

        target_snapshot = snapshots_dir / snapshot_name
        if target_snapshot.exists():
            shutil.rmtree(target_snapshot)

        shutil.copytree(paths.project, target_snapshot, dirs_exist_ok=True)
        logger.info(
            f"Created workspace snapshot '{snapshot_name}' for task '{task_id}' at {target_snapshot}"
        )
        return target_snapshot

    def rollback_snapshot(self, task_id: str, snapshot_name: str) -> bool:
        """Rollback project directory to the state captured in the snapshot."""
        paths = self.get_workspace_paths(task_id)
        if not paths:
            logger.error(f"Cannot rollback: workspace for task '{task_id}' does not exist.")
            return False

        snapshots_dir = paths.state / "snapshots"
        target_snapshot = snapshots_dir / snapshot_name
        if not target_snapshot.exists() or not target_snapshot.is_dir():
            logger.error(f"Snapshot '{snapshot_name}' not found for task '{task_id}'.")
            return False

        # Clear project dir and restore pristine contents from snapshot
        for item in paths.project.iterdir():
            if item.is_dir():
                shutil.rmtree(item)
            else:
                item.unlink()

        shutil.copytree(target_snapshot, paths.project, dirs_exist_ok=True)
        logger.info(
            f"Successfully rolled back project in task '{task_id}' to snapshot '{snapshot_name}'."
        )
        return True

    def list_snapshots(self, task_id: str) -> list[str]:
        """List all available snapshot names for a task."""
        paths = self.get_workspace_paths(task_id)
        if not paths:
            return []
        snapshots_dir = paths.state / "snapshots"
        if not snapshots_dir.exists():
            return []
        return [d.name for d in snapshots_dir.iterdir() if d.is_dir()]

    def cleanup_workspace(self, task_id: str) -> bool:
        """Safely remove a task workspace directory."""
        base_workspaces = canonical_path(self.settings.base_dir / self.settings.workspaces_dir)
        root_dir = canonical_path(self.get_task_workspace_dir(task_id))
        try:
            root_dir.relative_to(base_workspaces)
        except ValueError as exc:
            raise ValueError(
                f"Refusing to clean up workspace '{root_dir}' outside trusted workspaces root '{base_workspaces}'"
            ) from exc

        if root_dir == base_workspaces:
            raise ValueError("Refusing to delete entire workspaces root directory.")

        if root_dir.exists():
            shutil.rmtree(root_dir, ignore_errors=True)
            logger.info(f"Cleaned up workspace at {root_dir}")
            return True
        return False


workspace_manager = WorkspaceManager()
