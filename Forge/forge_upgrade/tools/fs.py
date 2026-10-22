from __future__ import annotations

from ..path_guard import PathGuard


class FilesystemOps:
    def __init__(self, root: str):
        self.guard = PathGuard(root)

    def read(self, path: str, max_bytes: int = 2_000_000) -> str:
        p = self.guard.ensure_file(path)
        data = p.read_bytes()
        return data[:max_bytes].decode("utf-8", "replace")

    def write(self, path: str, content: str) -> None:
        p = self.guard.resolve(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")

    def list(self, path: str = ".") -> list[str]:
        p = self.guard.ensure_dir(path)
        return sorted(
            x.relative_to(self.guard.root).as_posix() for x in p.rglob("*") if x.is_file()
        )
