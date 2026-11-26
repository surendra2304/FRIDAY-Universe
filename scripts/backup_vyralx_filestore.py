#!/usr/bin/env python3
"""TASK-DB-007 — scheduled backup for the VyralX file store (VyralX-Server, S5).

The VyralX file store (``/opt/friday_universe/VyralX/``: ``renders/`` 221
files / 2.2G, ``media/`` 702 files / 3.9G, ``data/`` 79 files / 403M at the
TASK-DB-003 audit, 2026-11-25) had no scheduled backup — only an informal,
unscheduled mirror on Oracle Server 1. This script formalises the backup:

- **Backup** stages the three trees (minus the exclusions below), writes a
  per-file SHA-256 manifest into the staged set, and stores the set as one
  snapshot in the TASK-REL-099 incremental store
  (``scripts/backup_fleet_incremental.py``, rsync ``--link-dest``), then
  prunes to retention. A no-change day therefore stores ~zero new bytes.
- **Verify** re-hashes a stored snapshot against its manifest (the
  read-back check the board acceptance asks for).
- **Restore-check** restores a snapshot to a scratch directory, verifies
  it, and parses the VyralX state JSONs — the local restore drill.

Exclusions (recorded in every manifest, never silent): ``data/credentials/``
and ``data/secrets/`` (permission-protected; secrets are restored from
Server 2 ``/opt/friday_universe/CREDENTIALS.md`` via the bridge, never from
a file-store snapshot), ``data/youtube_cookies.txt`` (a live session
cookie), ``data/temp_thumbs/`` (regenerable), plus ``__pycache__``/``*.pyc``.

Retention: 7 daily + 4 weekly (TASK-REL-099 defaults). The hard cap is
VyralX-specific (default 20 GiB): one full snapshot of this store is
~6.5G, which already exceeds the fleet store's 6 GB cap, so the fleet
default must not be reused here. The cap is a prune trigger only — the
newest snapshot is never pruned (TASK-REL-099 rule).

VyralX stays FILES ONLY — no database is read or written here.

Live deployment (installing the systemd timer on S5, first dated backup,
S1 second-copy verification) is gated on the owner stop order; see
``docs/collaboration/TASK-DB-007-VYRALX-FILESTORE-BACKUP.md``.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import importlib.util
import json
import shutil
import sys
from pathlib import Path

TASK_ID = "TASK-DB-007"
MANIFEST_NAME = "vyralx-filestore-manifest.json"
TREES = ("renders", "media", "data")
#: Relative paths (POSIX, under the VyralX root) never staged into a snapshot.
EXCLUDED_DIRS = ("data/credentials", "data/secrets", "data/temp_thumbs")
EXCLUDED_FILES = ("data/youtube_cookies.txt",)
#: VyralX-specific store cap. One snapshot is ~6.5G (TASK-DB-003 audit), so
#: the TASK-REL-099 fleet default (6 GB) cannot hold even one snapshot.
DEFAULT_MAX_BYTES = 20 * 1024 ** 3
DEFAULT_KEEP_DAILY = 7
DEFAULT_KEEP_WEEKLY = 4
#: State files the restore drill parses (TASK-DB-003 audit, data/ listing).
RESTORE_JSON_CHECKS = (
    "data/published_shorts_manifest.json",
    "data/viral_loop_state.json",
    "data/bgm/catalog.json",
)


def _load_store_module():
    """Load scripts/backup_fleet_incremental.py by path (no package import)."""
    here = Path(__file__).resolve().parent
    spec = importlib.util.spec_from_file_location(
        "backup_fleet_incremental", here / "backup_fleet_incremental.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules.setdefault("backup_fleet_incremental", mod)
    spec.loader.exec_module(mod)
    return mod


store_mod = _load_store_module()


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _is_excluded(rel: str) -> bool:
    if rel in EXCLUDED_FILES:
        return True
    if any(rel == d or rel.startswith(d + "/") for d in EXCLUDED_DIRS):
        return True
    parts = rel.split("/")
    return "__pycache__" in parts or rel.endswith(".pyc")


def _iter_store_files(root: Path):
    for tree in TREES:
        base = root / tree
        if not base.is_dir():
            continue
        for path in sorted(base.rglob("*")):
            if path.is_file() and not path.is_symlink():
                rel = path.relative_to(root).as_posix()
                if not _is_excluded(rel):
                    yield rel, path


def build_manifest(source_root: Path, stamp: str) -> dict:
    """Per-file SHA-256 manifest over the staged (non-excluded) file set."""
    files = {}
    per_tree = {tree: {"files": 0, "bytes": 0} for tree in TREES}
    for rel, path in _iter_store_files(source_root):
        size = path.stat().st_size
        files[rel] = {"sha256": _sha256_file(path), "bytes": size}
        tree = rel.split("/", 1)[0]
        per_tree[tree]["files"] += 1
        per_tree[tree]["bytes"] += size
    return {
        "task": TASK_ID,
        "stamp": stamp,
        "source_root": str(source_root),
        "trees": per_tree,
        "files_total": len(files),
        "bytes_total": sum(f["bytes"] for f in files.values()),
        "excluded_dirs": list(EXCLUDED_DIRS),
        "excluded_files": list(EXCLUDED_FILES),
        "files": files,
        "complete": True,
    }


def stage_source(source_root: Path, staging: Path) -> None:
    """Copy the non-excluded trees into a clean staging directory."""
    if staging.exists():
        shutil.rmtree(staging)

    def _ignore(dirpath, names):
        ignored = []
        for name in names:
            rel = (Path(dirpath) / name).relative_to(source_root).as_posix()
            if _is_excluded(rel) or _is_excluded(rel + "/x"):
                ignored.append(name)
        return ignored

    for tree in TREES:
        shutil.copytree(source_root / tree, staging / tree, ignore=_ignore)


def backup_filestore(source_root: Path, store_root: Path,
                     stamp: str | None = None, *,
                     keep_daily: int = DEFAULT_KEEP_DAILY,
                     keep_weekly: int = DEFAULT_KEEP_WEEKLY,
                     max_bytes: int = DEFAULT_MAX_BYTES,
                     prune: bool = True, log=print) -> dict:
    """Stage, manifest, store one snapshot, then prune. Returns the report."""
    source_root, store_root = Path(source_root), Path(store_root)
    for tree in TREES:
        if not (source_root / tree).is_dir():
            raise ValueError(
                f"BACKUP-ABORT: missing VyralX tree: {source_root / tree}")
    if store_root.resolve() == source_root.resolve() or \
            source_root.resolve() in store_root.resolve().parents:
        raise ValueError("BACKUP-ABORT: store root inside the source tree")
    stamp = stamp or store_mod.utc_stamp()
    staging = store_root / f".staging-{stamp}"
    try:
        stage_source(source_root, staging)
        manifest = build_manifest(staging, stamp)
        (staging / MANIFEST_NAME).write_text(
            json.dumps(manifest, indent=2, sort_keys=True) + "\n")
        report = store_mod.store_snapshot(staging, store_root, stamp=stamp,
                                          log=log)
    finally:
        if staging.exists():
            shutil.rmtree(staging, ignore_errors=True)
    result = {"manifest": manifest, "store_report": report}
    if prune:
        result["prune_report"] = store_mod.prune_snapshots(
            store_root, keep_daily=keep_daily, keep_weekly=keep_weekly,
            max_bytes=max_bytes, log=log)
    log(f"[BACKUP] {stamp}: {manifest['files_total']} files, "
        f"{manifest['bytes_total']} bytes, newly stored "
        f"{report['newly_stored_bytes']} bytes")
    return result


def verify_snapshot(snapshot: Path, *, log=print) -> dict:
    """Re-hash a snapshot against its manifest. The read-back check."""
    snapshot = Path(snapshot)
    manifest_path = snapshot / MANIFEST_NAME
    if not manifest_path.is_file():
        raise ValueError(f"VERIFY-ABORT: no manifest in {snapshot}")
    manifest = json.loads(manifest_path.read_text())
    ok, failed, missing = 0, [], []
    for rel, meta in sorted(manifest["files"].items()):
        path = snapshot / rel
        if not path.is_file():
            missing.append(rel)
        elif path.stat().st_size != meta["bytes"] or \
                _sha256_file(path) != meta["sha256"]:
            failed.append(rel)
        else:
            ok += 1
    extra = sorted(
        p.relative_to(snapshot).as_posix()
        for p in snapshot.rglob("*") if p.is_file()
        and p.name != MANIFEST_NAME
        and p.relative_to(snapshot).as_posix() not in manifest["files"])
    result = {"snapshot": snapshot.name, "ok": ok, "failed": failed,
              "missing": missing, "extra": extra,
              "complete": not failed and not missing}
    log(f"[VERIFY] {snapshot.name}: {ok} ok, {len(failed)} failed, "
        f"{len(missing)} missing, {len(extra)} extra")
    return result


def restore_check(snapshot: Path, dest: Path, *, log=print) -> dict:
    """Restore a snapshot to dest, verify it, parse the state JSONs."""
    snapshot, dest = Path(snapshot), Path(dest)
    store_mod.restore_snapshot(snapshot, dest, log=log)
    result = verify_snapshot(dest, log=log)
    parsed = {}
    for rel in RESTORE_JSON_CHECKS:
        path = dest / rel
        if path.is_file():
            json.loads(path.read_text())  # raises on corrupt JSON
            parsed[rel] = "parsed"
        else:
            parsed[rel] = "absent"
    result["json_checks"] = parsed
    result["restored_to"] = str(dest)
    return result


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("backup", help="stage + manifest + store + prune")
    p.add_argument("--source", default="/opt/friday_universe/VyralX")
    p.add_argument("--store",
                   default="/var/backups/friday-universe/vyralx-filestore")
    p.add_argument("--stamp", default="")
    p.add_argument("--keep-daily", type=int, default=DEFAULT_KEEP_DAILY)
    p.add_argument("--keep-weekly", type=int, default=DEFAULT_KEEP_WEEKLY)
    p.add_argument("--max-bytes", type=int, default=DEFAULT_MAX_BYTES)
    p.add_argument("--no-prune", action="store_true")
    p = sub.add_parser("verify", help="re-hash a snapshot vs its manifest")
    p.add_argument("snapshot")
    p = sub.add_parser("restore-check",
                       help="restore a snapshot and verify the copy")
    p.add_argument("snapshot")
    p.add_argument("dest")
    args = ap.parse_args()
    if args.cmd == "backup":
        result = backup_filestore(
            Path(args.source), Path(args.store),
            stamp=args.stamp or None, keep_daily=args.keep_daily,
            keep_weekly=args.keep_weekly, max_bytes=args.max_bytes,
            prune=not args.no_prune)
        print(json.dumps({"stamp": result["manifest"]["stamp"],
                          "files_total": result["manifest"]["files_total"],
                          "bytes_total": result["manifest"]["bytes_total"],
                          "store_report": result["store_report"]}, indent=2))
    elif args.cmd == "verify":
        result = verify_snapshot(Path(args.snapshot))
        print(json.dumps(result, indent=2))
        return 0 if result["complete"] else 1
    elif args.cmd == "restore-check":
        result = restore_check(Path(args.snapshot), Path(args.dest))
        print(json.dumps(result, indent=2))
        return 0 if result["complete"] else 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
