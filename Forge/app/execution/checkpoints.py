"""TASK-IG-FRG-05: project-context digest + checkpoint/rollback.

Corpus source: DX8TWC9yGUh — Unity's in-editor AI assistant, whose two
transferable properties are (1) it *sees the whole project* when it
generates, and (2) generated changes land behind *checkpoints* the
developer can roll back.

Forge's generation historically worked file-by-file with no way to
undo a wave, and no compact whole-project view to hand a model. This
module adds both, on top of the existing bounded inventory in
``app.verification.source_integrity.project_snapshot`` (which already
fails closed on symlinks, non-regular files, and oversize trees — the
checkpoints inherit those guarantees rather than re-inventing them):

* :func:`create_checkpoint` — snapshot + byte copies of a project into
  a checkpoint store **outside** the project tree (a store inside the
  tree would snapshot itself; that configuration is refused).
* :func:`diff_since_checkpoint` — added / modified / deleted, exactly.
* :func:`rollback` — restore the checkpoint exactly (restore modified
  and deleted files, remove added ones) and then *verify* by
  re-snapshotting: if the restored tree does not hash-match the
  checkpoint, rollback raises instead of claiming success.
* :func:`project_context_digest` — a compact, deterministic
  whole-project view (entry points first, then every file with its
  size and hash prefix) sized to hand to a generation prompt, so the
  model sees the project it is changing instead of one file at a time.

Bounds are the snapshot's bounds (2048 files / 32MB); a project beyond
them cannot be checkpointed and the refusal is explicit.
"""
from __future__ import annotations

import json
import os
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List

from app.verification.source_integrity import project_snapshot

_ENTRY_POINT_NAMES = frozenset(
    {
        "main.py",
        "app.py",
        "index.html",
        "index.js",
        "index.ts",
        "package.json",
        "pyproject.toml",
        "requirements.txt",
    }
)


class CheckpointError(RuntimeError):
    """A checkpoint operation could not be completed or verified."""


@dataclass
class Checkpoint:
    id: str
    label: str
    file_count: int
    snapshot: Dict[str, str]  # relpath -> sha256 (project_snapshot's files map)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "label": self.label,
            "file_count": self.file_count,
            "files": sorted(self.snapshot.keys()),
        }


@dataclass
class CheckpointDiff:
    added: List[str] = field(default_factory=list)
    modified: List[str] = field(default_factory=list)
    deleted: List[str] = field(default_factory=list)

    @property
    def is_clean(self) -> bool:
        return not (self.added or self.modified or self.deleted)

    def to_dict(self) -> dict:
        return {
            "added": self.added,
            "modified": self.modified,
            "deleted": self.deleted,
            "is_clean": self.is_clean,
        }


# ---------------------------------------------------------------------------
# Store layout: <store_root>/<checkpoint-id>/manifest.json + files/<relpath>
# ---------------------------------------------------------------------------


def _store_dir(store_root: Path, checkpoint_id: str) -> Path:
    return Path(store_root) / checkpoint_id


def _check_store_outside_project(project: Path, store_root: Path) -> None:
    project_resolved = Path(project).resolve()
    store_resolved = Path(store_root).resolve()
    if store_resolved == project_resolved or project_resolved in store_resolved.parents:
        raise ValueError(
            "checkpoint store must live outside the project tree "
            "(a store inside the tree would snapshot itself)"
        )


def _next_checkpoint_id(store_root: Path) -> str:
    existing = []
    root = Path(store_root)
    if root.is_dir():
        for child in root.iterdir():
            if child.is_dir() and child.name.isdigit():
                existing.append(int(child.name))
    return f"{(max(existing) + 1) if existing else 1:04d}"


def _load_manifest(store_root: Path, checkpoint_id: str) -> dict:
    manifest_path = _store_dir(store_root, checkpoint_id) / "manifest.json"
    if not manifest_path.is_file():
        raise CheckpointError(f"unknown checkpoint: {checkpoint_id}")
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise CheckpointError(f"checkpoint {checkpoint_id} manifest unreadable: {exc}")
    files = manifest.get("files") if isinstance(manifest, dict) else None
    if manifest.get("version") != 1 or not isinstance(files, dict) or not files:
        raise CheckpointError(f"checkpoint {checkpoint_id} manifest is malformed")
    return manifest


def list_checkpoints(store_root: Path) -> List[Checkpoint]:
    root = Path(store_root)
    out: List[Checkpoint] = []
    if not root.is_dir():
        return out
    for child in sorted(root.iterdir()):
        if not child.is_dir():
            continue
        try:
            manifest = _load_manifest(root, child.name)
        except CheckpointError:
            continue  # a corrupt entry is skipped here; loading it by id raises
        out.append(
            Checkpoint(
                id=child.name,
                label=str(manifest.get("label", "")),
                file_count=len(manifest["files"]),
                snapshot=dict(manifest["files"]),
            )
        )
    return out


# ---------------------------------------------------------------------------
# Operations
# ---------------------------------------------------------------------------


def create_checkpoint(project: Path, store_root: Path, label: str = "") -> Checkpoint:
    """Snapshot a project into the store. Fails closed (ValueError
    from the inventory layer) on unsafe or empty trees."""
    project = Path(project)
    store_root = Path(store_root)
    _check_store_outside_project(project, store_root)
    snapshot = project_snapshot(project)  # raises on unsafe/empty/oversize
    checkpoint_id = _next_checkpoint_id(store_root)
    dest = _store_dir(store_root, checkpoint_id)
    files_dir = dest / "files"
    files_dir.mkdir(parents=True, exist_ok=False)
    for rel in sorted(snapshot["files"]):
        target = files_dir / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(project / rel, target)
    manifest = {
        "version": 1,
        "id": checkpoint_id,
        "label": label,
        "files": snapshot["files"],
    }
    (dest / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8"
    )
    return Checkpoint(
        id=checkpoint_id,
        label=label,
        file_count=len(snapshot["files"]),
        snapshot=dict(snapshot["files"]),
    )


def diff_since_checkpoint(
    project: Path, store_root: Path, checkpoint_id: str
) -> CheckpointDiff:
    manifest = _load_manifest(store_root, checkpoint_id)
    then: Dict[str, str] = dict(manifest["files"])
    now = project_snapshot(Path(project))["files"]
    added = sorted(set(now) - set(then))
    deleted = sorted(set(then) - set(now))
    modified = sorted(
        rel for rel in set(now) & set(then) if now[rel] != then[rel]
    )
    return CheckpointDiff(added=added, modified=modified, deleted=deleted)


def rollback(project: Path, store_root: Path, checkpoint_id: str) -> CheckpointDiff:
    """Restore the checkpoint exactly, then verify by re-snapshotting.

    Returns the diff that was undone. Raises CheckpointError if the
    restored tree does not hash-match the checkpoint — a rollback that
    cannot be verified is reported as failed, never as done.
    """
    project = Path(project)
    manifest = _load_manifest(store_root, checkpoint_id)
    then: Dict[str, str] = dict(manifest["files"])
    undone = diff_since_checkpoint(project, store_root, checkpoint_id)
    files_dir = _store_dir(store_root, checkpoint_id) / "files"
    # Remove files added since the checkpoint.
    for rel in undone.added:
        target = project / rel
        if target.is_file() and not target.is_symlink():
            target.unlink()
    # Restore modified and deleted files from the stored copies.
    for rel in undone.modified + undone.deleted:
        source = files_dir / rel
        if not source.is_file():
            raise CheckpointError(
                f"checkpoint {checkpoint_id} is missing its stored copy of {rel}"
            )
        target = project / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
    # Prune directories left empty by removals (deepest first), never the root.
    for dirpath, _dirs, _files in os.walk(project, topdown=False):
        path = Path(dirpath)
        if path == project:
            continue
        try:
            path.rmdir()  # only succeeds when empty
        except OSError:
            pass
    # Verify: the restored tree must hash-match the checkpoint exactly.
    try:
        now = project_snapshot(project)["files"]
    except (OSError, ValueError) as exc:
        raise CheckpointError(f"rollback verification failed: {exc}")
    if now != then:
        raise CheckpointError(
            "rollback verification failed: restored tree does not match "
            f"checkpoint {checkpoint_id}"
        )
    return undone


# ---------------------------------------------------------------------------
# Whole-project context digest
# ---------------------------------------------------------------------------


def project_context_digest(project: Path, max_files: int = 200) -> str:
    """A compact whole-project view for a generation prompt.

    Deterministic: entry points first (in path order), then every
    other file in path order, each with byte size and hash prefix.
    Truncation past ``max_files`` is stated in the digest itself —
    never silent.
    """
    project = Path(project)
    snapshot = project_snapshot(project)["files"]
    rels = sorted(snapshot)
    entry_points = [r for r in rels if Path(r).name in _ENTRY_POINT_NAMES]
    rest = [r for r in rels if Path(r).name not in _ENTRY_POINT_NAMES]
    ordered = entry_points + rest
    shown = ordered[:max_files]
    lines = [
        f"Project context: {len(rels)} file(s)"
        + (f", showing {len(shown)}" if len(shown) < len(ordered) else ""),
        "Entry points: " + (", ".join(entry_points) if entry_points else "(none)"),
        "Files:",
    ]
    for rel in shown:
        size = (project / rel).stat().st_size
        lines.append(f"- {rel} ({size} bytes, sha256 {snapshot[rel][:12]})")
    if len(shown) < len(ordered):
        lines.append(
            f"[... {len(ordered) - len(shown)} more file(s) not shown — "
            "the digest is truncated, the project is larger than shown ...]"
        )
    return "\n".join(lines)
