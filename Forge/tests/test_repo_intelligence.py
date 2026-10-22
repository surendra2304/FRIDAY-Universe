from __future__ import annotations

import hashlib
import json
from pathlib import Path

from forge_upgrade.repo_intelligence import RepoFile, RepoIntelligence, RepoMap


def test_repo_map(tmp_path: Path) -> None:
    source = tmp_path / "a.py"
    source.write_text("def x(): pass\n", encoding="utf-8")

    repo_map = RepoIntelligence(tmp_path).build_map()

    assert repo_map.files[0].language == "python"
    assert repo_map.files[0].path == "a.py"
    assert repo_map.files[0].sha256 == hashlib.sha256(source.read_bytes()).hexdigest()


def test_to_json_serializes_slotted_repo_file_records(tmp_path: Path) -> None:
    source = tmp_path / "module.py"
    source.write_text("print('ok')\n", encoding="utf-8")
    intelligence = RepoIntelligence(tmp_path)
    repo_map = intelligence.build_map()

    encoded = intelligence.to_json(repo_map)
    data = json.loads(encoded)

    assert data["root"] == str(tmp_path.resolve())
    assert data["files"] == [
        {
            "path": "module.py",
            "size": source.stat().st_size,
            "sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
            "language": "python",
        }
    ]
    assert encoded.endswith("\n") is False


def test_to_json_handles_empty_repo_map() -> None:
    intelligence = RepoIntelligence(".")
    encoded = intelligence.to_json(RepoMap(root="/example", files=[]))

    assert json.loads(encoded) == {"root": "/example", "files": []}


def test_to_json_is_deterministic_for_identical_repo_maps(tmp_path: Path) -> None:
    repo_map = RepoMap(
        root=str(tmp_path.resolve()),
        files=[
            RepoFile("z.py", 4, "z" * 64, "python"),
            RepoFile("a.ts", 2, "a" * 64, "typescript"),
        ],
    )
    intelligence = RepoIntelligence(tmp_path)

    assert intelligence.to_json(repo_map) == intelligence.to_json(repo_map)


def test_search_symbols_is_case_insensitive_and_skips_binary_text(tmp_path: Path) -> None:
    source = tmp_path / "module.py"
    source.write_text("def SpecialFunction(): pass\n", encoding="utf-8")
    binary = tmp_path / "binary.py"
    binary.write_bytes(b"\xff\xfe\x00")

    hits = RepoIntelligence(tmp_path).search_symbols("specialfunction")

    assert hits == ["module.py"]


def test_build_map_ignores_files_in_dependency_directories(tmp_path: Path) -> None:
    visible = tmp_path / "src" / "visible.py"
    visible.parent.mkdir()
    visible.write_text("print('visible')\n", encoding="utf-8")
    ignored = tmp_path / "node_modules" / "pkg" / "hidden.py"
    ignored.parent.mkdir(parents=True)
    ignored.write_text("print('hidden')\n", encoding="utf-8")

    repo_map = RepoIntelligence(tmp_path).build_map()

    assert [file.path for file in repo_map.files] == ["src/visible.py"]
