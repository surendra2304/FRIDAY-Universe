from __future__ import annotations

import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class RollbackPoint:
    source: str
    backup_dir: str


class WorkspaceRollback:
    def snapshot(self, root: str | Path) -> RollbackPoint:
        root = Path(root).resolve()
        backup = Path(tempfile.mkdtemp(prefix="forge-rollback-"))
        shutil.copytree(
            root,
            backup / "workspace",
            dirs_exist_ok=True,
            ignore=shutil.ignore_patterns(".git", "__pycache__", "node_modules"),
        )
        return RollbackPoint(str(root), str(backup / "workspace"))

    def restore(self, point: RollbackPoint) -> None:
        root = Path(point.source)
        backup = Path(point.backup_dir)
        if not root.exists():
            root.mkdir(parents=True, exist_ok=True)
        for child in root.iterdir():
            if child.name == ".git":
                continue
            if child.is_dir():
                shutil.rmtree(child)
            else:
                child.unlink()
        shutil.copytree(backup, root, dirs_exist_ok=True)
