"""TASK-REL-099 checkpoint 2 — rsync --link-dest incremental backup store.

Covers scripts/backup_fleet_incremental.py: the rsync argv shape, the
pure-python hardlink fallback, no-change runs storing (near-)zero new
bytes, changed files stored exactly once, versioned snapshots (old content
survives), diff, retention + hard-cap pruning with the post-prune
free-space check, and restore at the TASK-REL-096 bar. No live database,
no live SSH, no live rsync required: the fallback path is exercised
directly and the rsync path is exercised when the binary is present.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import shutil
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]


def _load(name: str, rel: str):
    spec = importlib.util.spec_from_file_location(name, _ROOT / rel)
    mod = importlib.util.module_from_spec(spec)
    sys.modules.setdefault(name, mod)
    spec.loader.exec_module(mod)
    return mod


store_mod = _load("backup_fleet_incremental",
                  "scripts/backup_fleet_incremental.py")


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _fleet_set(root: Path, *, renders_mb: int = 2, seed: str = ""):
    """A small stand-in for a finished unified backup set.

    VyralX renders (binary blobs), a Stratex fill ledger (JSONL), a
    forward scorecard (JSON), the fleet manifest, and CREDENTIALS.md —
    the files the TASK-REL-096 restore drill checks.
    """
    root.mkdir(parents=True, exist_ok=True)
    (root / "vyralx" / "renders").mkdir(parents=True, exist_ok=True)
    for i in range(3):
        # Deterministic bytes: the same render is byte-identical across
        # runs unless the fixture changes it, so linking is testable.
        # A seed makes a whole day's renders distinct from another day's.
        seed = hashlib.sha256(f"render-{i}-{seed}".encode()).digest()
        blob = (seed * (renders_mb * 1024 * 1024 // 3 // len(seed) + 1))[
            :renders_mb * 1024 * 1024 // 3]
        (root / "vyralx" / "renders" / f"render_{i}.mp4").write_bytes(blob)
    (root / "vyralx" / "manifest.json").write_text(
        json.dumps({"renders": 3, "complete": True}) + "\n")
    (root / "stratex").mkdir(exist_ok=True)
    (root / "stratex" / "fill_ledger.jsonl").write_text(
        "".join(json.dumps({"i": i, "fill": 100 + i}) + "\n" for i in range(5)))
    (root / "stratex" / "forward_scorecard.json").write_text(
        json.dumps({"score": 0.61, "n": 42}) + "\n")
    (root / "manifest.json").write_text(
        json.dumps({"complete": True, "agents": ["STRATEX", "VYRALX"]}) + "\n")
    (root / "CREDENTIALS.md").write_text("# fleet credentials (fixture)\n")
    return root


def _changed_set(src: Path, dst: Path) -> Path:
    """A second run's source: copy of the first set (mtimes preserved),
    with only the Stratex fill ledger changed — the realistic shape of a
    daily re-dump, where unchanged files keep their mtime."""
    shutil.copytree(src, dst)
    (dst / "stratex" / "fill_ledger.jsonl").write_text(
        "".join(json.dumps({"i": i, "fill": 100 + i}) + "\n"
                for i in range(6)))
    return dst


# ---------------------------------------------------------------------------
# Tooling
# ---------------------------------------------------------------------------

def test_rsync_argv_shape_and_link_dest():
    argv = store_mod.rsync_store_argv(Path("/set"), Path("/store/snap"),
                                      Path("/store/prev"))
    assert argv[0] == "rsync" and "-a" in argv
    assert "--link-dest=/store/prev" in argv
    assert argv[-2:] == ["/set/", "/store/snap/"]
    argv2 = store_mod.rsync_store_argv(Path("/set"), Path("/store/snap"), None)
    assert not any(a.startswith("--link-dest") for a in argv2)


def test_rsync_available_returns_bool():
    assert isinstance(store_mod.rsync_available(), bool)


# ---------------------------------------------------------------------------
# Incremental behaviour (fallback path — deterministic everywhere)
# ---------------------------------------------------------------------------

def test_no_change_second_run_stores_only_the_report(tmp_path, monkeypatch):
    monkeypatch.setattr(store_mod, "rsync_available", lambda: False)
    src = _fleet_set(tmp_path / "set1")
    store = tmp_path / "store"
    r1 = store_mod.store_snapshot(src, store, stamp="20261126T040000Z",
                                  log=lambda *a: None)
    assert r1["files_copied"] == r1["files_total"] and r1["files_linked"] == 0
    r2 = store_mod.store_snapshot(src, store, stamp="20261126T050000Z",
                                  log=lambda *a: None)
    # Every set file is a hardlink to run 1; only the run's own report is new.
    assert r2["files_linked"] == r2["files_total"]
    assert r2["files_copied"] == 0
    assert r2["newly_stored_bytes"] < 1024
    assert r2["store_total_bytes"] == r1["newly_stored_bytes"] + \
        r2["newly_stored_bytes"]


def test_changed_file_stored_once_unchanged_file_shares_inode(tmp_path,
                                                             monkeypatch):
    monkeypatch.setattr(store_mod, "rsync_available", lambda: False)
    src = _fleet_set(tmp_path / "set1")
    store = tmp_path / "store"
    store_mod.store_snapshot(src, store, stamp="20261126T040000Z",
                             log=lambda *a: None)
    snap1 = store / "20261126T040000Z"
    src2 = _changed_set(src, tmp_path / "set2")
    store_mod.store_snapshot(src2, store, stamp="20261126T050000Z",
                             log=lambda *a: None)
    snap2 = store / "20261126T050000Z"
    render1 = snap1 / "vyralx" / "renders" / "render_0.mp4"
    render2 = snap2 / "vyralx" / "renders" / "render_0.mp4"
    assert render1.stat().st_ino == render2.stat().st_ino  # same content, once
    assert render1.stat().st_nlink == 2
    ledger1 = snap1 / "stratex" / "fill_ledger.jsonl"
    ledger2 = snap2 / "stratex" / "fill_ledger.jsonl"
    assert ledger1.stat().st_ino != ledger2.stat().st_ino  # changed: new copy
    assert _sha(ledger1) != _sha(ledger2)
    assert _sha(render1) == _sha(render2)


def test_old_snapshot_keeps_old_content_after_change(tmp_path, monkeypatch):
    monkeypatch.setattr(store_mod, "rsync_available", lambda: False)
    src = _fleet_set(tmp_path / "set1")
    store = tmp_path / "store"
    store_mod.store_snapshot(src, store, stamp="20261126T040000Z",
                             log=lambda *a: None)
    _changed_set(src, tmp_path / "set2")
    store_mod.store_snapshot(tmp_path / "set2", store,
                             stamp="20261126T050000Z", log=lambda *a: None)
    old = (store / "20261126T040000Z" / "stratex" /
           "fill_ledger.jsonl").read_text()
    new = (store / "20261126T050000Z" / "stratex" /
           "fill_ledger.jsonl").read_text()
    assert len(old.strip().splitlines()) == 5
    assert len(new.strip().splitlines()) == 6


def test_diff_reports_added_removed_modified(tmp_path, monkeypatch):
    monkeypatch.setattr(store_mod, "rsync_available", lambda: False)
    src = _fleet_set(tmp_path / "set1")
    store = tmp_path / "store"
    store_mod.store_snapshot(src, store, stamp="20261126T040000Z",
                             log=lambda *a: None)
    src2 = _changed_set(src, tmp_path / "set2")
    (src2 / "vyralx" / "renders" / "render_2.mp4").unlink()
    (src2 / "vyralx" / "renders" / "render_3.mp4").write_bytes(b"new render")
    store_mod.store_snapshot(src2, store, stamp="20261126T050000Z",
                             log=lambda *a: None)
    diff = store_mod.diff_snapshots(store / "20261126T040000Z",
                                    store / "20261126T050000Z")
    assert diff["added"] == ["vyralx/renders/render_3.mp4"]
    assert diff["removed"] == ["vyralx/renders/render_2.mp4"]
    assert diff["modified"] == ["stratex/fill_ledger.jsonl"]


def test_rsync_path_links_unchanged_files_when_binary_present(tmp_path):
    if not store_mod.rsync_available():
        return  # covered by the fallback tests above
    src = _fleet_set(tmp_path / "set1", renders_mb=1)
    store = tmp_path / "store"
    store_mod.store_snapshot(src, store, stamp="20261126T040000Z",
                             log=lambda *a: None)
    r2 = store_mod.store_snapshot(src, store, stamp="20261126T050000Z",
                                  log=lambda *a: None)
    assert r2["tool"] == "rsync"
    assert r2["files_linked"] == r2["files_total"]
    assert r2["newly_stored_bytes"] < 1024


# ---------------------------------------------------------------------------
# Retention, hard cap, restore
# ---------------------------------------------------------------------------

def test_prune_keeps_newest_daily_and_never_the_newest(tmp_path, monkeypatch):
    monkeypatch.setattr(store_mod, "rsync_available", lambda: False)
    store = tmp_path / "store"
    for day in range(1, 11):
        src = _fleet_set(tmp_path / f"set{day}", renders_mb=0)
        (src / "marker.txt").write_text(f"day {day}\n")
        store_mod.store_snapshot(src, store, stamp=f"202611{day:02d}T040000Z",
                                 log=lambda *a: None)
    report = store_mod.prune_snapshots(store, keep_daily=7, keep_weekly=0,
                                       log=lambda *a: None)
    assert len(report["kept"]) == 7
    assert report["kept"][0] == "20261110T040000Z"  # newest survives
    assert "20261101T040000Z" in report["removed"]
    assert report["free_bytes_after"] > 0
    assert report["store_total_bytes"] >= 0


def test_prune_hard_cap_removes_oldest_until_fit(tmp_path, monkeypatch):
    monkeypatch.setattr(store_mod, "rsync_available", lambda: False)
    store = tmp_path / "store"
    for day in range(1, 4):
        # Each day's renders are distinct, so each snapshot owns its bytes.
        src = _fleet_set(tmp_path / f"set{day}", renders_mb=1, seed=f"day{day}")
        store_mod.store_snapshot(src, store, stamp=f"202611{day:02d}T040000Z",
                                 log=lambda *a: None)
    # Cap below the store total: oldest snapshots go, newest stays.
    total = store_mod.store_total_bytes(store)
    report = store_mod.prune_snapshots(store, keep_daily=7, keep_weekly=4,
                                       max_bytes=total // 2,
                                       log=lambda *a: None)
    assert report["store_total_bytes"] <= total // 2
    assert "20261103T040000Z" in report["kept"]


def test_restore_reproduces_tree_at_rel096_bar(tmp_path, monkeypatch):
    monkeypatch.setattr(store_mod, "rsync_available", lambda: False)
    src = _fleet_set(tmp_path / "set1")
    store = tmp_path / "store"
    store_mod.store_snapshot(src, store, stamp="20261126T040000Z",
                             log=lambda *a: None)
    dest = store_mod.restore_snapshot(store / "20261126T040000Z",
                                      tmp_path / "restored",
                                      log=lambda *a: None)
    # REL-096 restore-drill bar on the restored tree:
    manifest = json.loads((dest / "manifest.json").read_text())
    assert manifest["complete"] is True
    ledger_lines = (dest / "stratex" / "fill_ledger.jsonl").read_text() \
        .strip().splitlines()
    assert len(ledger_lines) == 5
    for line in ledger_lines:
        json.loads(line)  # line-complete JSON
    scorecard = json.loads((dest / "stratex" / "forward_scorecard.json")
                           .read_text())
    assert scorecard["n"] == 42
    assert (dest / "CREDENTIALS.md").is_file()
    assert (dest / "vyralx" / "manifest.json").is_file()
    # Restored files are independent copies, not links into the store.
    assert (dest / "manifest.json").stat().st_nlink == 1


def test_store_rejects_missing_source_and_existing_snapshot(tmp_path):
    store = tmp_path / "store"
    try:
        store_mod.store_snapshot(tmp_path / "nope", store,
                                 stamp="20261126T040000Z",
                                 log=lambda *a: None)
    except ValueError as exc:
        assert "STORE-ABORT" in str(exc)
    else:
        raise AssertionError("missing source was accepted")
    src = _fleet_set(tmp_path / "set1", renders_mb=0)
    store_mod.store_snapshot(src, store, stamp="20261126T040000Z",
                             log=lambda *a: None)
    try:
        store_mod.store_snapshot(src, store, stamp="20261126T040000Z",
                                 log=lambda *a: None)
    except ValueError as exc:
        assert "already exists" in str(exc)
    else:
        raise AssertionError("duplicate snapshot was accepted")
