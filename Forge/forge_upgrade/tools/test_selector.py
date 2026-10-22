from __future__ import annotations

from pathlib import Path


class TestSelector:
    """Maps changed files to likely test commands without assuming one language."""

    def __init__(self, root: str | Path):
        self.root = Path(root)

    def commands_for(self, changed_files: list[str]) -> list[str]:
        suffixes = {Path(x).suffix.lower() for x in changed_files}
        commands = []
        if ".py" in suffixes:
            commands.append("pytest -q")
        if suffixes & {".ts", ".tsx", ".js", ".jsx"}:
            commands.append("npm test")
        if ".go" in suffixes:
            commands.append("go test ./...")
        if ".rs" in suffixes:
            commands.append("cargo test")
        return commands or ["python -m compileall ."]
