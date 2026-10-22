from __future__ import annotations

import difflib
import hashlib
from dataclasses import dataclass
from pathlib import Path

from .models import FileChange
from .path_guard import PathGuard


@dataclass(frozen=True, slots=True)
class PatchPreview:
    files: tuple[str, ...]
    additions: int
    deletions: int
    unified_diff: str
    changed_bytes: int


class SafePatcher:
    def __init__(self, project_root: str | Path):
        self.guard = PathGuard(project_root)

    def preview(self, changes: dict[str, str]) -> PatchPreview:
        diff_parts = []
        additions = deletions = changed_bytes = 0
        for rel, new_text in sorted(changes.items()):
            path = self.guard.resolve(rel)
            old_text = path.read_text(encoding="utf-8") if path.exists() else ""
            diff = "".join(
                difflib.unified_diff(
                    old_text.splitlines(keepends=True),
                    new_text.splitlines(keepends=True),
                    fromfile=str(rel),
                    tofile=str(rel),
                )
            )
            diff_parts.append(diff)
            additions += sum(
                x.startswith("+") and not x.startswith("+++") for x in diff.splitlines()
            )
            deletions += sum(
                x.startswith("-") and not x.startswith("---") for x in diff.splitlines()
            )
            changed_bytes += abs(len(new_text.encode()) - len(old_text.encode()))
        return PatchPreview(
            tuple(changes), additions, deletions, "".join(diff_parts), changed_bytes
        )

    def apply(
        self, changes: dict[str, str], expected_sha: dict[str, str | None] | None = None
    ) -> tuple[FileChange, ...]:
        results = []
        for rel, new_text in sorted(changes.items()):
            path = self.guard.resolve(rel)
            current = path.read_bytes() if path.exists() else None
            current_sha = hashlib.sha256(current).hexdigest() if current is not None else None
            if expected_sha and rel in expected_sha and current_sha != expected_sha[rel]:
                raise RuntimeError(f"concurrent modification detected: {rel}")
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(new_text, encoding="utf-8")
            after_sha = hashlib.sha256(new_text.encode()).hexdigest()
            results.append(
                FileChange(
                    rel,
                    current_sha,
                    after_sha,
                    "create" if current is None else "modify",
                    len(new_text.encode()),
                )
            )
        return tuple(results)
