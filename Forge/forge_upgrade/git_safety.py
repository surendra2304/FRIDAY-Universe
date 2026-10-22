from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class GitStatus:
    commit_sha: str
    dirty: bool
    changed_files: tuple[str, ...]


class GitSafety:
    def __init__(self, repo: str):
        self.repo = Path(repo).resolve()

    def _run(self, *args: str) -> str:
        return subprocess.check_output(
            ["git", *args], cwd=self.repo, text=True, stderr=subprocess.STDOUT
        ).strip()

    def status(self) -> GitStatus:
        sha = self._run("rev-parse", "HEAD")
        raw = self._run("status", "--porcelain")
        files = tuple(line[3:] for line in raw.splitlines() if len(line) >= 4)
        return GitStatus(sha, bool(files), files)

    def diff_stat(self) -> str:
        return self._run("diff", "--stat")

    def create_checkpoint_commit(self, message: str) -> str:
        self._run("add", "-A")
        self._run("commit", "-m", message)
        return self._run("rev-parse", "HEAD")

    def reset_to(self, sha: str) -> None:
        current = self._run("rev-parse", "HEAD")
        if current == sha:
            return
        subprocess.run(["git", "reset", "--hard", sha], cwd=self.repo, check=True)
