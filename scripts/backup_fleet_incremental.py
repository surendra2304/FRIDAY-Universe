#!/usr/bin/env python3
"""TASK-REL-099 — git-style incremental fleet backup store (rsync --link-dest).

The fleet's daily backup used to write a whole new timestamped set on every
run (scripts/backup_fleet_databases.py: ``shutil.copytree`` of the unified
set, ~2.7 GB per run). This module stores each finished set as one snapshot
in a store where unchanged files are hardlinks to the previous snapshot, so
a no-change run stores only the files that actually changed — the git
behaviour the owner ordered (2026-11-26), without the git binary.

Tool choice (checkpoint 2, probe 2026-11-26 03:00-03:08 IST): restic is
absent on both Oracle servers and rsync is present at /usr/bin/rsync on
both, so the store uses ``rsync -a --link-dest``. A pure-python hardlink
fallback covers hosts without rsync. Restic remains the preferred tool if
it is installed later; the snapshot layout below is tool-neutral (one
directory per snapshot, manifest.json inside each).

Layout: ``<store_root>/<stamp>/`` (stamp ``%Y%m%dT%H%M%SZ``, UTC).

Acceptance hooks (board TASK-REL-099):
- INCREMENTAL: a second consecutive run stores only what changed.
- VERSIONED + BOUNDED: list/diff/restore snapshots; retention enforced by
  the job itself (7 daily + 4 weekly); hard cap 6 GB on the store;
  post-prune free-space check in every run log.
- RESTORE DRILL at the TASK-REL-096 bar (see tests/test_rel099_*).
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

STAMP_FORMAT = "%Y%m%dT%H%M%SZ"
DEFAULT_KEEP_DAILY = 7
DEFAULT_KEEP_WEEKLY = 4
#: Hard cap on the store footprint (board proposal: 6 GB total on Server 2).
DEFAULT_MAX_BYTES = 6 * 1024 ** 3


def utc_stamp(when: dt.datetime | None = None) -> str:
    """UTC stamp for a snapshot directory name."""
    when = when or dt.datetime.now(dt.timezone.utc)
    return when.strftime(STAMP_FORMAT)


def rsync_available() -> bool:
    """True when the rsync binary is on PATH (probe: present on both servers)."""
    return shutil.which("rsync") is not None


def rsync_store_argv(source: Path, dest: Path, link_dest: Path | None) -> list:
    """rsync argv for one snapshot: -a, --link-dest against the previous one."""
    argv = ["rsync", "-a"]
    if link_dest is not None:
        argv.append(f"--link-dest={link_dest}")
    argv += [f"{source}/", f"{dest}/"]
    return argv


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _iter_files(root: Path):
    for dirpath, _dirnames, filenames in os.walk(root):
        for name in filenames:
            yield Path(dirpath) / name


def _file_inodes(root: Path) -> dict[tuple[int, int], int]:
    """``{(st_dev, st_ino): st_size}`` for the regular files under root."""
    out: dict[tuple[int, int], int] = {}
    for path in _iter_files(root):
        if path.is_symlink():
            continue
        st = path.stat()
        out[(st.st_dev, st.st_ino)] = st.st_size
    return out


def newly_stored_bytes(snapshot: Path, previous=()) -> int:
    """Bytes this snapshot stored that no earlier snapshot already holds.

    Ownership is by first appearance: a file hardlinked from an earlier
    snapshot costs this snapshot nothing, and a changed file costs exactly
    its own size. (A link-count test cannot do this — a file linked into
    two snapshots has nlink 2 in both, so it would be owned by neither.)
    """
    seen: set[tuple[int, int]] = set()
    for prev in previous:
        seen |= set(_file_inodes(Path(prev)))
    mine = _file_inodes(Path(snapshot))
    return sum(size for key, size in mine.items() if key not in seen)


def store_total_bytes(store_root: Path) -> int:
    """Disk bytes the whole store owns: each distinct inode counted once."""
    seen: dict[tuple[int, int], int] = {}
    for snap in list_snapshots(store_root):
        seen.update(_file_inodes(snap))
    return sum(seen.values())


def owned_bytes(snapshot: Path, store_root: Path) -> int:
    """Bytes removing this snapshot alone would free."""
    others: dict[tuple[int, int], int] = {}
    for snap in list_snapshots(store_root):
        if snap != Path(snapshot):
            others.update(_file_inodes(snap))
    mine = _file_inodes(Path(snapshot))
    return sum(size for key, size in mine.items() if key not in others)


def list_snapshots(store_root: Path) -> list[Path]:
    """Snapshot directories, newest first (name sort = time sort)."""
    if not store_root.is_dir():
        return []
    snaps = [d for d in store_root.iterdir()
             if d.is_dir() and len(d.name) == 16 and d.name.endswith("Z")]
    return sorted(snaps, reverse=True)


def _hardlink_copy_tree(source: Path, dest: Path, link_dest: Path | None,
                        log=print) -> tuple[int, int]:
    """Pure-python --link-dest: link unchanged files, copy changed ones.

    Returns (linked, copied) file counts. Used when rsync is unavailable.
    A file is unchanged when the same relative path exists under link_dest
    with identical size and mtime; anything else is copied fresh.
    """
    linked = copied = 0
    for src in _iter_files(source):
        rel = src.relative_to(source)
        dst = dest / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        prev = link_dest / rel if link_dest is not None else None
        if prev is not None and prev.is_file():
            sst, pst = src.stat(), prev.stat()
            if sst.st_size == pst.st_size and sst.st_mtime_ns == pst.st_mtime_ns:
                os.link(prev, dst)
                linked += 1
                continue
        if src.is_symlink():
            os.symlink(os.readlink(src), dst)
        else:
            shutil.copy2(src, dst)
        copied += 1
    for dirpath, dirnames, _filenames in os.walk(source):
        for name in dirnames:
            (dest / Path(dirpath).relative_to(source) / name).mkdir(exist_ok=True)
    return linked, copied


def store_snapshot(source_dir: Path, store_root: Path, stamp: str | None = None,
                   *, log=print) -> dict:
    """Store one finished backup set as a new snapshot. Returns the report.

    Unchanged files are hardlinks to the latest snapshot (rsync
    --link-dest, or the pure-python fallback). The report records the
    run-over-run stored bytes, which is the acceptance evidence.
    """
    source_dir = Path(source_dir)
    store_root = Path(store_root)
    if not source_dir.is_dir():
        raise ValueError(f"STORE-ABORT: source set not a directory: {source_dir}")
    stamp = stamp or utc_stamp()
    dest = store_root / stamp
    if dest.exists():
        raise ValueError(f"STORE-ABORT: snapshot already exists: {dest}")
    previous = list_snapshots(store_root)
    link_dest = previous[0] if previous else None
    dest.mkdir(parents=True)
    os.chmod(dest, 0o700)
    if rsync_available():
        argv = rsync_store_argv(source_dir, dest, link_dest)
        log(f"[STORE] {' '.join(argv)}")
        proc = subprocess.run(argv, capture_output=True, text=True)
        if proc.returncode != 0:
            shutil.rmtree(dest, ignore_errors=True)
            raise RuntimeError(f"STORE-ABORT: rsync exit {proc.returncode}: "
                               f"{proc.stderr.strip()[:500]}")
        linked = copied = -1  # rsync does not report per-file link counts
    else:
        log("[STORE] rsync not found; using pure-python hardlink fallback")
        linked, copied = _hardlink_copy_tree(source_dir, dest, link_dest, log=log)
    total_files = sum(1 for _ in _iter_files(dest))
    if linked < 0:  # rsync path: derive counts from link counts
        linked = sum(1 for p in _iter_files(dest)
                     if not p.is_symlink() and p.stat().st_nlink > 1)
        copied = total_files - linked
    new_bytes = newly_stored_bytes(dest, previous)
    total_bytes = store_total_bytes(store_root)
    free_bytes = shutil.disk_usage(store_root).free
    report = {
        "snapshot": stamp,
        "previous": link_dest.name if link_dest else None,
        "files_total": total_files,
        "files_linked": linked,
        "files_copied": copied,
        "newly_stored_bytes": new_bytes,
        "store_total_bytes": total_bytes,
        "free_bytes_after": free_bytes,
        "tool": "rsync" if rsync_available() else "hardlink-fallback",
    }
    (store_root / f"{stamp}.store-report.json").write_text(
        json.dumps(report, indent=2) + "\n")
    log(f"[STORE] {stamp}: {total_files} files, {linked} linked, {copied} copied, "
        f"newly stored {new_bytes} bytes, store total {total_bytes} bytes, "
        f"free {free_bytes} bytes")
    return report


def diff_snapshots(older: Path, newer: Path) -> dict:
    """Added / removed / modified relative paths between two snapshots.

    A path is modified when size or mtime differs and the SHA-256 differs;
    identical content under a new mtime is not a modification.
    """
    def _index(root: Path) -> dict[str, Path]:
        return {str(p.relative_to(root)): p for p in _iter_files(root)}

    old, new = _index(Path(older)), _index(Path(newer))
    added = sorted(set(new) - set(old))
    removed = sorted(set(old) - set(new))
    modified = []
    for rel in sorted(set(old) & set(new)):
        o, n = old[rel], new[rel]
        if o.stat().st_size != n.stat().st_size or \
                o.stat().st_mtime_ns != n.stat().st_mtime_ns:
            if _sha256_file(o) != _sha256_file(n):
                modified.append(rel)
    return {"added": added, "removed": removed, "modified": modified}


def prune_snapshots(store_root: Path, *, keep_daily: int = DEFAULT_KEEP_DAILY,
                    keep_weekly: int = DEFAULT_KEEP_WEEKLY,
                    max_bytes: int = DEFAULT_MAX_BYTES, log=print) -> dict:
    """Enforce retention + hard cap. Never removes the newest snapshot.

    Keeps the newest ``keep_daily`` snapshots, plus the newest snapshot of
    each of the last ``keep_weekly`` ISO weeks beyond the daily window, then
    removes the oldest snapshots until the store fits ``max_bytes``.
    Returns the prune report, including the post-prune free-space check.
    """
    snaps = list_snapshots(store_root)
    if not snaps:
        return {"kept": [], "removed": [], "bytes_freed": 0,
                "store_total_bytes": 0,
                "free_bytes_after": shutil.disk_usage(store_root).free}
    keep: set[Path] = set(snaps[:keep_daily])
    weekly_seen: set[tuple[int, int]] = set()
    for snap in snaps[keep_daily:]:
        try:
            when = dt.datetime.strptime(snap.name, STAMP_FORMAT)
        except ValueError:
            continue
        week = (when.isocalendar().year, when.isocalendar().week)
        if week not in weekly_seen and len(weekly_seen) < keep_weekly:
            weekly_seen.add(week)
            keep.add(snap)
    keep.add(snaps[0])  # the newest snapshot is never pruned
    removed: list[str] = []
    freed = 0
    # Retention first: remove everything outside the keep set, measuring
    # each snapshot's owned bytes BEFORE removal (shared files stay owned
    # by the snapshots that still link them).
    for snap in snaps:
        if snap not in keep:
            owned = owned_bytes(snap, store_root)
            shutil.rmtree(snap)
            removed.append(snap.name)
            freed += owned
            log(f"[PRUNE] removed snapshot {snap.name} (outside retention, "
                f"owned {owned} bytes)")
    # Hard cap: drop the oldest kept snapshots (never the newest) until the
    # store fits ``max_bytes``. Removing a snapshot promotes its shared
    # files to owned-by-the-next-snapshot, so recompute the total after
    # each removal.
    remaining = list_snapshots(store_root)
    while len(remaining) > 1:
        total = store_total_bytes(store_root)
        if total <= max_bytes:
            break
        victim = remaining[-1]
        if victim == snaps[0]:
            break
        owned = owned_bytes(victim, store_root)
        shutil.rmtree(victim)
        removed.append(victim.name)
        freed += owned
        log(f"[PRUNE] removed snapshot {victim.name} "
            f"(over hard cap, owned {owned} bytes)")
        remaining = list_snapshots(store_root)
    kept = [s.name for s in list_snapshots(store_root)]
    total_after = store_total_bytes(store_root)
    free_after = shutil.disk_usage(store_root).free
    log(f"[PRUNE] kept {len(kept)} snapshots, removed {len(removed)}, "
        f"store total {total_after} bytes, free {free_after} bytes")
    return {"kept": kept, "removed": removed, "bytes_freed": freed,
            "store_total_bytes": total_after, "free_bytes_after": free_after}


def restore_snapshot(snapshot: Path, dest_dir: Path, *, log=print) -> Path:
    """Copy a snapshot out as independent files (hardlinks dereferenced)."""
    snapshot, dest_dir = Path(snapshot), Path(dest_dir)
    if not snapshot.is_dir():
        raise ValueError(f"RESTORE-ABORT: no such snapshot: {snapshot}")
    if dest_dir.exists():
        raise ValueError(f"RESTORE-ABORT: destination exists: {dest_dir}")
    shutil.copytree(snapshot, dest_dir)
    for path in dest_dir.rglob("*"):
        if path.is_file():
            os.chmod(path, 0o600)
    log(f"[RESTORE] {snapshot.name} -> {dest_dir}")
    return dest_dir


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("store", help="store a finished set as a new snapshot")
    p.add_argument("--from", dest="source", required=True)
    p.add_argument("--store", required=True)
    p.add_argument("--stamp", default="")
    p = sub.add_parser("list", help="list snapshots")
    p.add_argument("--store", required=True)
    p = sub.add_parser("diff", help="diff two snapshots")
    p.add_argument("older")
    p.add_argument("newer")
    p = sub.add_parser("prune", help="enforce retention + hard cap")
    p.add_argument("--store", required=True)
    p.add_argument("--keep-daily", type=int, default=DEFAULT_KEEP_DAILY)
    p.add_argument("--keep-weekly", type=int, default=DEFAULT_KEEP_WEEKLY)
    p.add_argument("--max-bytes", type=int, default=DEFAULT_MAX_BYTES)
    p = sub.add_parser("restore", help="restore a snapshot to a directory")
    p.add_argument("snapshot")
    p.add_argument("dest")
    args = ap.parse_args()
    if args.cmd == "store":
        store_snapshot(Path(args.source), Path(args.store),
                       stamp=args.stamp or None)
    elif args.cmd == "list":
        snaps = sorted(list_snapshots(Path(args.store)))
        seen: list[Path] = []
        for snap in snaps:
            print(f"{snap.name}  "
                  f"newly-stored={newly_stored_bytes(snap, seen)} bytes")
            seen.append(snap)
    elif args.cmd == "diff":
        print(json.dumps(diff_snapshots(Path(args.older), Path(args.newer)),
                         indent=2))
    elif args.cmd == "prune":
        print(json.dumps(prune_snapshots(
            Path(args.store), keep_daily=args.keep_daily,
            keep_weekly=args.keep_weekly, max_bytes=args.max_bytes), indent=2))
    elif args.cmd == "restore":
        restore_snapshot(Path(args.snapshot), Path(args.dest))
    return 0


if __name__ == "__main__":
    sys.exit(main())
