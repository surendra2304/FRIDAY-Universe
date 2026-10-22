from __future__ import annotations

from pathlib import Path


class SandboxViolation(Exception):
    pass


class PathGuard:
    def __init__(self, root: str | Path):
        self.root = Path(root).resolve()

    def resolve(self, path: str | Path) -> Path:
        candidate = Path(path)
        resolved = (self.root / candidate if not candidate.is_absolute() else candidate).resolve()
        try:
            resolved.relative_to(self.root)
        except ValueError as exc:
            raise SandboxViolation(f"path escapes sandbox: {path}") from exc
        return resolved

    def ensure_file(self, path: str | Path) -> Path:
        resolved = self.resolve(path)
        if not resolved.is_file():
            raise FileNotFoundError(str(resolved))
        return resolved

    def ensure_dir(self, path: str | Path) -> Path:
        resolved = self.resolve(path)
        if not resolved.is_dir():
            raise NotADirectoryError(str(resolved))
        return resolved
