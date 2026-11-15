"""TASK-IG-FRG-05: project-context digest + checkpoint/rollback.

Corpus source: DX8TWC9yGUh (Unity AI: whole-project context +
checkpoint/rollback of generated changes).
Pinned properties: a checkpoint captures the tree exactly; the diff
names added/modified/deleted precisely; rollback restores the tree
byte-for-byte and *verifies* by hash; a store inside the project is
refused; the digest is deterministic and states its own truncation.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from app.execution.checkpoints import (
    CheckpointError,
    create_checkpoint,
    diff_since_checkpoint,
    list_checkpoints,
    project_context_digest,
    rollback,
)
from app.verification.source_integrity import project_snapshot


def _write(root: Path, rel: str, content: str) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


@pytest.fixture()
def project(tmp_path):
    proj = tmp_path / "proj"
    proj.mkdir()
    _write(proj, "main.py", "print('v1')\n")
    _write(proj, "lib/util.py", "X = 1\n")
    return proj, tmp_path / "store"


def test_create_and_list_checkpoint(project):
    proj, store = project
    cp = create_checkpoint(proj, store, label="before-wave")
    assert cp.file_count == 2
    listed = list_checkpoints(store)
    assert [c.id for c in listed] == [cp.id]
    assert listed[0].label == "before-wave"


def test_diff_names_added_modified_deleted(project):
    proj, store = project
    cp = create_checkpoint(proj, store)
    _write(proj, "main.py", "print('v2')\n")  # modified
    _write(proj, "new_file.py", "Y = 2\n")  # added
    (proj / "lib" / "util.py").unlink()  # deleted
    diff = diff_since_checkpoint(proj, store, cp.id)
    assert diff.added == ["new_file.py"]
    assert diff.modified == ["main.py"]
    assert diff.deleted == ["lib/util.py"]
    assert not diff.is_clean


def test_rollback_restores_exactly_and_verifies(project):
    proj, store = project
    cp = create_checkpoint(proj, store)
    before = project_snapshot(proj)
    _write(proj, "main.py", "print('broken')\n")
    _write(proj, "junk.py", "junk\n")
    (proj / "lib" / "util.py").unlink()
    undone = rollback(proj, store, cp.id)
    assert undone.added == ["junk.py"]
    assert project_snapshot(proj) == before
    assert (proj / "main.py").read_text() == "print('v1')\n"
    assert (proj / "lib" / "util.py").read_text() == "X = 1\n"
    assert not (proj / "junk.py").exists()
    assert diff_since_checkpoint(proj, store, cp.id).is_clean


def test_clean_tree_diff_and_rollback_noop(project):
    proj, store = project
    cp = create_checkpoint(proj, store)
    assert diff_since_checkpoint(proj, store, cp.id).is_clean
    undone = rollback(proj, store, cp.id)
    assert undone.is_clean


def test_store_inside_project_refused(project):
    proj, _store = project
    with pytest.raises(ValueError):
        create_checkpoint(proj, proj / ".forge-checkpoints")


def test_unknown_checkpoint_raises(project):
    proj, store = project
    with pytest.raises(CheckpointError):
        diff_since_checkpoint(proj, store, "9999")


def test_symlink_tree_fails_closed(project):
    proj, store = project
    (proj / "link.py").symlink_to(proj / "main.py")
    with pytest.raises(ValueError):
        create_checkpoint(proj, store)


def test_empty_project_fails_closed(tmp_path):
    proj = tmp_path / "empty"
    proj.mkdir()
    with pytest.raises(ValueError):
        create_checkpoint(proj, tmp_path / "store")


def test_digest_lists_entry_points_first_and_is_deterministic(project):
    proj, _store = project
    digest_a = project_context_digest(proj)
    digest_b = project_context_digest(proj)
    assert digest_a == digest_b
    assert "Entry points: main.py" in digest_a
    assert "lib/util.py" in digest_a
    assert "2 file(s)" in digest_a


def test_digest_states_truncation(project):
    proj, _store = project
    digest = project_context_digest(proj, max_files=1)
    assert "not shown" in digest
    assert "showing 1" in digest
