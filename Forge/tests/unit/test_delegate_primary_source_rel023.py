"""TASK-REL-023: the delegate result must carry the produced code.

Round 3 (2026-11-14) production evidence: the palindrome build
(task17414112026145722) produced a working main.py, but the delegate
result carried only artifact PATHS — so FRIDAY's chat reply could name
files yet never show the code the owner explicitly asked to see.
``_task_primary_source`` returns the project's entry source file with
its (bounded) content; these tests pin its selection rules.
"""

from __future__ import annotations

from types import SimpleNamespace

from app.api import delegate


def _with_project(monkeypatch, tmp_path, files: dict[str, str]):
    project = tmp_path / "project"
    project.mkdir()
    for name, content in files.items():
        (project / name).write_text(content, encoding="utf-8")
    paths = SimpleNamespace(project=project, root=tmp_path)
    monkeypatch.setattr(
        delegate.workspace_manager, "get_workspace_paths", lambda task_id: paths
    )
    return paths


def test_prefers_main_py_with_content(monkeypatch, tmp_path):
    _with_project(monkeypatch, tmp_path, {
        "main.py": "def is_palindrome(s):\n    return s == s[::-1]\n",
        "helper.py": "X = 1\n" * 50,
    })
    src = delegate._task_primary_source("task_x")
    assert src is not None
    assert src["name"] == "main.py"
    assert "is_palindrome" in src["content"]
    assert src["truncated"] is False


def test_skips_test_files_and_docs(monkeypatch, tmp_path):
    _with_project(monkeypatch, tmp_path, {
        "test_main.py": "def test_x():\n    assert True\n",
        "conftest.py": "",
        "app.py": "print('real')\n",
    })
    src = delegate._task_primary_source("task_x")
    assert src is not None
    assert src["name"] == "app.py"


def test_no_source_returns_none(monkeypatch, tmp_path):
    _with_project(monkeypatch, tmp_path, {"README.md": "# nothing\n"})
    assert delegate._task_primary_source("task_x") is None


def test_content_is_bounded(monkeypatch, tmp_path):
    _with_project(monkeypatch, tmp_path, {"main.py": "x = 1\n" * 5000})
    src = delegate._task_primary_source("task_x")
    assert src is not None
    assert len(src["content"]) == 8000
    assert src["truncated"] is True


def test_missing_workspace_returns_none(monkeypatch):
    monkeypatch.setattr(
        delegate.workspace_manager, "get_workspace_paths", lambda task_id: None
    )
    assert delegate._task_primary_source("task_gone") is None
