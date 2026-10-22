"""
Filesystem Tool for Project FORGE Execution Engine.
Provides sandboxed file operations (list, read, create, edit, move, delete, search) within a task workspace.
"""

import fnmatch
import shutil
from pathlib import Path

from pydantic import BaseModel

from app.core.logging import get_logger
from app.core.workspace import WorkspaceManager, workspace_manager
from app.execution.permissions import (
    PermissionManager,
    ToolPermission,
    permission_manager,
)

logger = get_logger("execution.filesystem")


class FileItem(BaseModel):
    name: str
    relative_path: str
    is_dir: bool
    size_bytes: int = 0


class FilesystemTool:
    """Provides sandboxed filesystem operations for task execution."""

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

    def list_dir(
        self, task_id: str, relative_path: str = ".", role: str = "developer"
    ) -> list[FileItem]:
        """List files and directories within the sandbox project root."""
        self.pm.check_permission(role, ToolPermission.FS_READ)
        root = self._get_project_root(task_id)
        target = self.pm.validate_sandbox_path(Path(relative_path), root)

        if not target.exists() or not target.is_dir():
            raise FileNotFoundError(f"Directory '{relative_path}' does not exist in workspace")

        items = []
        for p in sorted(target.iterdir()):
            rel = p.relative_to(root).as_posix()
            items.append(
                FileItem(
                    name=p.name,
                    relative_path=rel,
                    is_dir=p.is_dir(),
                    size_bytes=p.stat().st_size if p.is_file() else 0,
                )
            )
        return items

    def read_file(self, task_id: str, relative_path: str, role: str = "developer") -> str:
        """Read text content of a file inside the task sandbox."""
        self.pm.check_permission(role, ToolPermission.FS_READ)
        root = self._get_project_root(task_id)
        target = self.pm.validate_sandbox_path(Path(relative_path), root)

        if not target.exists() or not target.is_file():
            raise FileNotFoundError(f"File '{relative_path}' not found")

        return target.read_text(encoding="utf-8")

    def create_file(
        self, task_id: str, relative_path: str, content: str, role: str = "developer"
    ) -> str:
        """Create a new file inside the task sandbox."""
        self.pm.check_permission(role, ToolPermission.FS_WRITE)
        root = self._get_project_root(task_id)
        target = self.pm.validate_sandbox_path(Path(relative_path), root)

        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        logger.debug(f"Created file {relative_path} in task {task_id}")
        return target.relative_to(root).as_posix()

    def edit_file(
        self,
        task_id: str,
        relative_path: str,
        target_content: str,
        replacement_content: str,
        role: str = "developer",
    ) -> str:
        """Replace target content substring with replacement content inside a file."""
        self.pm.check_permission(role, ToolPermission.FS_WRITE)
        root = self._get_project_root(task_id)
        target = self.pm.validate_sandbox_path(Path(relative_path), root)

        if not target.exists():
            raise FileNotFoundError(f"Cannot edit non-existent file '{relative_path}'")

        original = target.read_text(encoding="utf-8")
        if target_content not in original:
            raise ValueError(f"Target snippet not found in '{relative_path}'")

        modified = original.replace(target_content, replacement_content, 1)
        target.write_text(modified, encoding="utf-8")
        logger.debug(f"Edited file {relative_path} in task {task_id}")
        return target.relative_to(root).as_posix()

    def move_file(
        self, task_id: str, source_path: str, dest_path: str, role: str = "developer"
    ) -> str:
        """Move or rename a file within the sandbox."""
        self.pm.check_permission(role, ToolPermission.FS_WRITE)
        root = self._get_project_root(task_id)
        src = self.pm.validate_sandbox_path(Path(source_path), root)
        dst = self.pm.validate_sandbox_path(Path(dest_path), root)

        if not src.exists():
            raise FileNotFoundError(f"Source file '{source_path}' does not exist")

        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(src, dst)
        return dst.relative_to(root).as_posix()

    def delete_file(self, task_id: str, relative_path: str, role: str = "developer") -> bool:
        """Delete a file or directory within the sandbox."""
        self.pm.check_permission(role, ToolPermission.FS_DELETE)
        root = self._get_project_root(task_id)
        target = self.pm.validate_sandbox_path(Path(relative_path), root)

        if not target.exists():
            return False

        if target.is_dir():
            shutil.rmtree(target)
        else:
            target.unlink()
        return True

    def search_files(
        self,
        task_id: str,
        pattern: str = "*",
        relative_path: str = ".",
        role: str = "developer",
    ) -> list[str]:
        """Search for files matching glob pattern inside the sandbox."""
        self.pm.check_permission(role, ToolPermission.FS_READ)
        root = self._get_project_root(task_id)
        target = self.pm.validate_sandbox_path(Path(relative_path), root)

        matches = []
        for p in target.rglob("*"):
            if p.is_file() and fnmatch.fnmatch(p.name, pattern):
                matches.append(p.relative_to(root).as_posix())
        return matches
