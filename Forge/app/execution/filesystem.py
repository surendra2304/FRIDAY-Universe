"""
Filesystem Tool for Project FORGE Execution Engine.
Provides sandboxed file operations (list, read, create, edit, move, delete, search) within a task workspace.
"""

import ast
import fnmatch
import re
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

    # Generated test suites keep assuming the test file lives one directory
    # BELOW the code under test -- Path(__file__).parent.parent / "main.py"
    # -- while Forge's layout is flat: tests and code share the project
    # directory (production tasks task18914112026200449 and
    # task19014112026201012 both died at collection on exactly this). The
    # lookahead-free pattern captures the two consecutive .parent hops and
    # the referenced python file name.
    _PARENT_PARENT_RE = re.compile(
        r"(?P<head>\.parent)\.parent(?P<slash>\s*/\s*['\"])"
        r"(?P<name>[A-Za-z0-9_.\-]+\.py)(?P<quote>['\"])"
    )

    def _repair_sibling_paths(
        self, content: str, task_id: str | None, relative_path: str
    ) -> str | None:
        """Drop a spurious ``.parent`` hop when the referenced file is a
        sibling of the file being written and does NOT exist one level up.

        Conservative by construction: the rewrite happens only when the
        flat-layout reading is provably the real one (sibling present,
        parent-level file absent) and the result still compiles.
        """
        if not task_id or "/" in relative_path or "\\" in relative_path:
            return None
        try:
            paths = self.wm.get_workspace_paths(task_id)
        except Exception:
            return None
        if paths is None:
            return None

        def _sub(match: re.Match[str]) -> str:
            name = match.group("name")
            if (paths.project / name).exists() and not (paths.root / name).exists():
                return (
                    f"{match.group('head')}{match.group('slash')}"
                    f"{name}{match.group('quote')}"
                )
            return match.group(0)

        repaired = self._PARENT_PARENT_RE.sub(_sub, content)
        if repaired == content:
            return None
        try:
            compile(repaired, relative_path, "exec")
        except (SyntaxError, ValueError):
            return None
        return repaired

    @staticmethod
    def _has_top_level_raise(content: str) -> bool:
        """True when a module unconditionally raises at import time.

        A ``raise`` that is a direct statement of the module body (not
        nested in an if/try/function) fires on every import, so the module
        can never be imported at all. TASK-REL-028 run 5: a repair patch
        rewrote a working recovery-created module into exactly that shape
        (``raise ImportError("Simulated import failure ...")``) to satisfy
        an import-error test, permanently breaking the runtime check.
        Version guards and the like nest their raise, so they are
        unaffected.
        """
        try:
            tree = ast.parse(content)
        except (SyntaxError, ValueError):
            return False
        return any(isinstance(stmt, ast.Raise) for stmt in tree.body)

    def _guard_python_content(
        self, relative_path: str, content: str, task_id: str | None = None
    ) -> str:
        """Never persist Python source that does not parse (TASK-REL-028).

        Content that already parses is returned byte-identical -- legitimate
        code full of escaped newlines inside string literals is untouched.
        Content in the escape-corrupted shape (a model emitted the file in
        its string-escaped form, so the text cannot parse at all) is decoded
        and returned when the decoded form parses. Anything else raises
        ValueError: writing it would plant a broken file that the
        verification battery can only indict after every repair budget has
        been spent on other targets, and no repair route accepts an
        unparseable file. Callers that can fall back (extraction, synthesis)
        already catch per-file write exceptions; the rest fail the node
        honestly instead of shipping garbage.
        """
        try:
            compile(content, relative_path, "exec")
        except (SyntaxError, ValueError) as exc:
            original_error = exc
        else:
            # Parseable content is normally returned byte-identical; the
            # exceptions are the parent.parent sibling-path misconception
            # (repaired only when the flat layout is provably the real one)
            # and a module that unconditionally raises at import time,
            # which no consumer can ever import -- refused, not persisted.
            if self._has_top_level_raise(content):
                raise ValueError(
                    f"Refusing to write '{relative_path}': the module "
                    "unconditionally raises at import time (top-level raise), "
                    "so it could never be imported."
                )
            repaired = self._repair_sibling_paths(content, task_id, relative_path)
            if repaired is not None:
                logger.warning(
                    f"Repaired parent.parent sibling path in '{relative_path}' "
                    "at write time (flat project layout)"
                )
                return repaired
            return content

        from app.recovery.syntax_repair import _unescape_literal_escapes

        decoded = _unescape_literal_escapes(content)
        if decoded is not None:
            try:
                compile(decoded, relative_path, "exec")
            except (SyntaxError, ValueError):
                decoded = None
        if decoded is not None:
            logger.warning(
                f"Normalized escape-corrupted Python source for '{relative_path}' at write time"
            )
            return decoded
        raise ValueError(
            f"Refusing to write syntactically invalid Python to '{relative_path}': "
            f"{original_error}"
        ) from original_error

    def create_file(
        self, task_id: str, relative_path: str, content: str, role: str = "developer"
    ) -> str:
        """Create a new file inside the task sandbox."""
        self.pm.check_permission(role, ToolPermission.FS_WRITE)
        root = self._get_project_root(task_id)
        target = self.pm.validate_sandbox_path(Path(relative_path), root)

        if relative_path.lower().endswith(".py") and isinstance(content, str):
            content = self._guard_python_content(relative_path, content, task_id=task_id)

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
        if (
            relative_path.endswith(".py")
            and self._has_top_level_raise(modified)
            and not self._has_top_level_raise(original)
        ):
            # Same write-boundary rule as create_file (TASK-REL-028): an
            # edit must not turn an importable module into one that
            # unconditionally raises at import time. Edits to a file that
            # already has the defect stay allowed so it can be repaired.
            raise ValueError(
                f"Refusing edit to '{relative_path}': it would make the module "
                "unconditionally raise at import time (top-level raise)."
            )
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
