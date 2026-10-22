from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path

IGNORED = {".git", ".venv", "node_modules", "__pycache__", ".pytest_cache", "dist", "build"}


@dataclass(frozen=True, slots=True)
class RepoFile:
    path: str
    size: int
    sha256: str
    language: str


@dataclass(slots=True)
class RepoMap:
    root: str
    files: list[RepoFile] = field(default_factory=list)

    def by_language(self) -> dict[str, int]:
        result: dict[str, int] = {}
        for f in self.files:
            result[f.language] = result.get(f.language, 0) + 1
        return result


class RepoIntelligence:
    def __init__(self, root: str | Path):
        self.root = Path(root).resolve()

    def build_map(self, max_files: int = 50000) -> RepoMap:
        files: list[RepoFile] = []
        for path in self.root.rglob("*"):
            if len(files) >= max_files:
                break
            if not path.is_file() or any(part in IGNORED for part in path.parts):
                continue
            rel = path.relative_to(self.root).as_posix()
            suffix = path.suffix.lower()
            language = {
                ".py": "python",
                ".ts": "typescript",
                ".tsx": "typescript",
                ".js": "javascript",
                ".jsx": "javascript",
                ".go": "go",
                ".rs": "rust",
                ".java": "java",
                ".cs": "csharp",
            }.get(suffix, "other")
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            files.append(RepoFile(rel, path.stat().st_size, digest, language))
        files.sort(key=lambda x: x.path)
        return RepoMap(str(self.root), files)

    def search_symbols(self, query: str, limit: int = 50) -> list[str]:
        hits: list[str] = []
        for path in self.root.rglob("*"):
            if (
                len(hits) >= limit
                or not path.is_file()
                or any(part in IGNORED for part in path.parts)
            ):
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue
            if query.casefold() in text.casefold():
                hits.append(path.relative_to(self.root).as_posix())
        return hits

    def suspicious_files(self) -> list[str]:
        patterns = [
            r"eval\s*\(",
            r"exec\s*\(",
            r"subprocess\.(run|Popen|call)\([^)]*shell\s*=\s*True",
            r"pickle\.(load|loads)\(",
            r"os\.system\(",
        ]
        hits = []
        for path in self.root.rglob("*.py"):
            text = path.read_text(encoding="utf-8", errors="ignore")
            if any(re.search(p, text) for p in patterns):
                hits.append(path.relative_to(self.root).as_posix())
        return sorted(hits)

    def to_json(self, repo_map: RepoMap) -> str:
        return json.dumps(
            {"root": repo_map.root, "files": [asdict(file) for file in repo_map.files]},
            indent=2,
        )
