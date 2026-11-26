"""TASK-DB-007 — VyralX file-store backup formalisation.

Covers scripts/backup_vyralx_filestore.py: staging with exclusions
(credentials/secrets/cookies/temp_thumbs never enter a snapshot), the
per-file SHA-256 manifest, storing through the TASK-REL-099 incremental
store, verify (read-back) incl. tamper detection, the restore drill with
state-JSON parsing, and abort paths. No live server, no live rsync
required: the TASK-REL-099 fallback path is forced for determinism.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]


def _load(name: str, rel: str):
    spec = importlib.util.spec_from_file_location(name, _ROOT / rel)
    mod = importlib.util.module_from_spec(spec)
    sys.modules.setdefault(name, mod)
    spec.loader.exec_module(mod)
    return mod


backup_mod = _load("backup_vyralx_filestore",
                   "scripts/backup_vyralx_filestore.py")


def _vyralx_tree(root: Path) -> Path:
    """A small stand-in for /opt/friday_universe/VyralX (TASK-DB-003 shape)."""
    (root / "renders").mkdir(parents=True)
    (root / "media").mkdir(parents=True)
    (root / "data" / "bgm").mkdir(parents=True)
    (root / "data" / "exports").mkdir(parents=True)
    (root / "data" / "credentials").mkdir(parents=True)
    (root / "data" / "secrets").mkdir(parents=True)
    (root / "data" / "temp_thumbs").mkdir(parents=True)
    blob = hashlib.sha256(b"render-fixture").digest() * 1024
    (root / "renders" / "framed-fixture.mp4").write_bytes(blob)
    (root / "media" / "clip-fixture.mp4").write_bytes(blob[:4096])
    (root / "data" / "published_shorts_manifest.json").write_text(
        json.dumps({"shorts": [{"id": "fixture-1"}]}) + "\n")
    (root / "data" / "viral_loop_state.json").write_text(
        json.dumps({"state": "held", "cycle": 3}) + "\n")
    (root / "data" / "bgm" / "catalog.json").write_text(
        json.dumps({"tracks": [{"file": "track1.mp3"}]}) + "\n")
    (root / "data" / "bgm" / "track1.mp3").write_bytes(b"ID3-fixture")
    (root / "data" / "exports" / "note.txt").write_text("export fixture\n")
    # Excluded material: must never appear in a snapshot.
    (root / "data" / "credentials" / "api_key.txt").write_text("FIXTURE-ONLY")
    (root / "data" / "secrets" / "token.txt").write_text("FIXTURE-ONLY")
    (root / "data" / "youtube_cookies.txt").write_text("FIXTURE-ONLY")
    (root / "data" / "temp_thumbs" / "thumb.jpg").write_bytes(b"thumb")
    return root


def _no_rsync(monkeypatch):
    monkeypatch.setattr(backup_mod.store_mod, "rsync_available",
                        lambda: False)


def test_backup_stores_trees_with_manifest_and_exclusions(tmp_path,
                                                          monkeypatch):
    _no_rsync(monkeypatch)
    src = _vyralx_tree(tmp_path / "VyralX")
    store = tmp_path / "store"
    result = backup_mod.backup_filestore(
        src, store, stamp="20261126T060000Z", prune=False,
        log=lambda *a: None)
    snap = store / "20261126T060000Z"
    manifest = json.loads((snap / backup_mod.MANIFEST_NAME).read_text())
    assert manifest["complete"] is True
    assert manifest["trees"]["renders"]["files"] == 1
    assert manifest["trees"]["media"]["files"] == 1
    assert manifest["trees"]["data"]["files"] == 5
    assert manifest["files_total"] == 7
    # Exclusions absent from snapshot and manifest.
    for rel in ("data/credentials/api_key.txt", "data/secrets/token.txt",
                "data/youtube_cookies.txt", "data/temp_thumbs/thumb.jpg"):
        assert not (snap / rel).exists()
        assert rel not in manifest["files"]
    assert "data/credentials" in manifest["excluded_dirs"]
    assert result["store_report"]["files_total"] == 8  # 7 files + manifest


def test_verify_passes_then_detects_tamper(tmp_path, monkeypatch):
    _no_rsync(monkeypatch)
    src = _vyralx_tree(tmp_path / "VyralX")
    store = tmp_path / "store"
    backup_mod.backup_filestore(src, store, stamp="20261126T060000Z",
                                prune=False, log=lambda *a: None)
    snap = store / "20261126T060000Z"
    result = backup_mod.verify_snapshot(snap, log=lambda *a: None)
    assert result["complete"] is True and result["ok"] == 7
    (snap / "renders" / "framed-fixture.mp4").write_bytes(b"tampered")
    result = backup_mod.verify_snapshot(snap, log=lambda *a: None)
    assert result["complete"] is False
    assert result["failed"] == ["renders/framed-fixture.mp4"]


def test_second_backup_is_incremental(tmp_path, monkeypatch):
    _no_rsync(monkeypatch)
    src = _vyralx_tree(tmp_path / "VyralX")
    store = tmp_path / "store"
    backup_mod.backup_filestore(src, store, stamp="20261126T060000Z",
                                prune=False, log=lambda *a: None)
    r2 = backup_mod.backup_filestore(src, store, stamp="20261126T070000Z",
                                     prune=False, log=lambda *a: None)
    # Only the new manifest (new stamp) is fresh bytes; media hardlinks.
    assert r2["store_report"]["files_copied"] == 1
    assert r2["store_report"]["newly_stored_bytes"] < 65536


def test_restore_check_reproduces_tree_and_parses_state(tmp_path,
                                                        monkeypatch):
    _no_rsync(monkeypatch)
    src = _vyralx_tree(tmp_path / "VyralX")
    store = tmp_path / "store"
    backup_mod.backup_filestore(src, store, stamp="20261126T060000Z",
                                prune=False, log=lambda *a: None)
    result = backup_mod.restore_check(store / "20261126T060000Z",
                                      tmp_path / "restored",
                                      log=lambda *a: None)
    assert result["complete"] is True
    assert result["json_checks"] == {
        "data/published_shorts_manifest.json": "parsed",
        "data/viral_loop_state.json": "parsed",
        "data/bgm/catalog.json": "parsed",
    }
    restored = tmp_path / "restored"
    assert (restored / "renders" / "framed-fixture.mp4").is_file()
    assert not (restored / "data" / "credentials").exists()
    # Restored files are independent copies, not links into the store.
    assert (restored / "renders" /
            "framed-fixture.mp4").stat().st_nlink == 1


def test_backup_aborts_on_missing_tree(tmp_path):
    src = tmp_path / "VyralX"
    (src / "renders").mkdir(parents=True)  # media/ and data/ missing
    try:
        backup_mod.backup_filestore(src, tmp_path / "store",
                                    stamp="20261126T060000Z",
                                    log=lambda *a: None)
    except ValueError as exc:
        assert "BACKUP-ABORT" in str(exc)
    else:
        raise AssertionError("missing tree was accepted")


def test_backup_aborts_when_store_inside_source(tmp_path):
    src = _vyralx_tree(tmp_path / "VyralX")
    try:
        backup_mod.backup_filestore(src, src / "backups",
                                    stamp="20261126T060000Z",
                                    log=lambda *a: None)
    except ValueError as exc:
        assert "inside the source tree" in str(exc)
    else:
        raise AssertionError("store inside source was accepted")


def test_prune_keeps_newest_snapshot(tmp_path, monkeypatch):
    _no_rsync(monkeypatch)
    src = _vyralx_tree(tmp_path / "VyralX")
    store = tmp_path / "store"
    for day in (24, 25, 26):
        backup_mod.backup_filestore(
            src, store, stamp=f"202611{day}T060000Z", keep_daily=1,
            keep_weekly=0, log=lambda *a: None)
    snaps = backup_mod.store_mod.list_snapshots(store)
    assert [s.name for s in snaps] == ["20261126T060000Z"]
