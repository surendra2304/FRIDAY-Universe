#!/usr/bin/env python3
"""TASK-INF-003 — Fleet database backup (logical JSONL dumps + config snapshots).

Backs up every agent's Oracle Autonomous Database schema into a timestamped,
permission-protected directory: one compressed JSONL file per table plus a
manifest with row counts and SHA-256 checksums, and (optionally) a snapshot of
the service configuration files (DB credential env files + systemd units),
plus local-only agent state files (Stratex measurement state, TASK-SEN-007).

Connection credentials are resolved by the shared helper ``scripts/oracle_db.py``
(``/etc/friday-universe/db-credentials*.env`` on the servers, or env vars).
Secrets are never printed and never written into the manifest; the credential
env files themselves are only copied inside the protected backup directory.

Modes:
    default        full logical dump of every agent schema
    --agents A,B   subset of agents
    --dry-run      connect + enumerate only (inventory evidence, no files)
    --verify       re-read the last (or --from) backup and validate checksums
    --config-only  only snapshot config files (env files + systemd units)
    --media        include the VyralX media schema (VYRALX_MEDIA)
    --media-only   only the VyralX media schema (for the Server 2 job,
                   TASK-SEN-009: the media credentials live on Server 2)

TASK-SEN-009 additions: per-agent .env files join the config snapshot
(``snapshot_agent_envs``); the manifest records ``complete`` and pruning
keeps the newest successful backups, not merely the newest directories;
a media failure counts as a failure instead of a silent skip.

Runbook: docs/observability/BACKUP_RESTORE_AND_LEDGER_DRILL.md
Repair report: docs/observability/BACKUP_REPAIR_SEN009.md
"""
from __future__ import annotations

import argparse
import datetime as dt
import gzip
import hashlib
import json
import os
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from oracle_db import (  # noqa: E402
    AGENT_SCHEMAS,
    MEDIA_SCHEMA,
    OracleConfigError,
    connect,
    list_tables,
    resolve_target,
    table_columns,
)

ALL_AGENTS = list(AGENT_SCHEMAS.keys())
DEFAULT_OUT_ROOT = "/var/backups/friday-universe"
CONFIG_ENV_FILES = (
    "/etc/friday-universe/db-credentials.env",
    "/etc/friday-universe/db-credentials-media.env",
)
CONFIG_UNIT_GLOBS = ("/etc/systemd/system/FRIDAY*.service", "/etc/systemd/system/*.service")

# Local-only runtime state that no schema dump can capture (TASK-SEN-007):
# the Stratex measurement ledger — fill ledger, equity snapshots, position
# tags — lives in git-ignored JSONL files under Stratex/state/ (see
# Stratex/measurement/fill_ledger.py). Without a copy here, the phase-3
# forward-test evidence trail exists exactly once, on Server 1's disk.
# Paths are repo-relative; STRATEX_STATE_DIR (the daemon's override) is
# honoured as an additional source when set.
AGENT_STATE_GLOBS = ("Stratex/state/*.jsonl", "Stratex/state/*.json")
LOB_CAP_BYTES = 1_000_000

# Where each agent's credentials actually live in production: the per-agent .env
# wired into its systemd unit via EnvironmentFile (deploy/setup_fleet.sh).
AGENT_ENV_DIRS = {
    "FRIDAY": "FRIDAY", "INFERENCE": "Inference", "MEMORA": "Memora",
    "STRATEX": "Stratex", "FUTURIS": "Futuris", "INTELX": "IntelX",
    "FORGE": "Forge", "SENTINEL": "Sentinel", "CORTEX": "Cortex",
    "VYRALX": "VyralX", "VYRALX_MEDIA": "VyralX",
}


def agent_runtime_env(agent: str, repo_root: Path | None = None) -> dict:
    """Load the agent's own .env (its systemd EnvironmentFile) as a dict.

    This is the production credential source on the servers; the shared
    /etc/friday-universe files are consulted by oracle_db.resolve_target
    separately. Values stay in memory only.
    """
    root = repo_root or Path(__file__).resolve().parents[1]
    env_dir = AGENT_ENV_DIRS.get(agent.upper())
    if not env_dir:
        return {}
    path = root / env_dir / ".env"
    if not path.is_file():
        return {}
    from oracle_db import load_env_file

    return load_env_file(path)


def utcnow() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def jsonl_encode_value(value):
    """Render one Oracle column value for JSONL, bounded and type-safe."""
    import datetime as _dt

    if value is None:
        return None
    if isinstance(value, bytes):
        return {"__b64__": __import__("base64").b64encode(value[:LOB_CAP_BYTES]).decode()}
    if isinstance(value, (_dt.datetime, _dt.date, _dt.timedelta)):
        return str(value)
    if hasattr(value, "read"):  # LOB
        raw = value.read(LOB_CAP_BYTES)
        if isinstance(raw, bytes):
            return {"__b64__": __import__("base64").b64encode(raw).decode()}
        return str(raw)
    if isinstance(value, (int, float, str, bool)):
        return value
    return str(value)


def dump_table_rows(conn, table: str, batch_size: int = 2000):
    """Yield JSON-encoded row dicts for one table."""
    with conn.cursor() as cur:
        cur.execute(f'SELECT * FROM "{table}"')  # table names come from all_tables
        cols = [d[0].lower() for d in cur.description]
        while True:
            rows = cur.fetchmany(batch_size)
            if not rows:
                break
            for row in rows:
                yield {col: jsonl_encode_value(val) for col, val in zip(cols, row)}


def write_jsonl_dump(path: Path, rows_iter) -> tuple[int, str]:
    """Write rows as gzipped JSONL; return (row_count, sha256 of the written file)."""
    count = 0
    with gzip.open(path, "wt", encoding="utf-8") as fh:
        for row in rows_iter:
            line = json.dumps(row, separators=(",", ":"), default=str) + "\n"
            fh.write(line)
            count += 1
    return count, sha256_file(path)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def snapshot_agent_state(dest: Path, repo_root: Path, log=print) -> list[str]:
    """Copy local-only agent state files into dest/configs/agent-state/ (600).

    Covers files that exist only as local runtime state (TASK-SEN-007) —
    today that is the Stratex measurement state under Stratex/state/.
    Lock sidecars (*.lock) and non-files are skipped; a missing state
    directory is not an error (fresh checkouts and other hosts have none).
    """
    copied: list[str] = []
    sources: list[Path] = []
    for pattern in AGENT_STATE_GLOBS:
        sources.extend(sorted(repo_root.glob(pattern)))
    env_state_dir = os.environ.get("STRATEX_STATE_DIR")
    if env_state_dir:
        env_dir = Path(env_state_dir)
        for pattern in ("*.jsonl", "*.json"):
            sources.extend(sorted(env_dir.glob(pattern)))
    seen_targets: set[Path] = set()
    for src_path in sources:
        if not src_path.is_file() or src_path.name.endswith(".lock"):
            continue
        try:
            rel = src_path.relative_to(repo_root)
        except ValueError:
            rel = Path("Stratex") / "state" / src_path.name
        target = dest / "configs" / "agent-state" / rel
        if target in seen_targets:
            continue
        seen_targets.add(target)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src_path, target)
        os.chmod(target, 0o600)
        copied.append(str(target))
    if copied:
        log(f"[CONFIG] copied {len(copied)} agent state files (mode 600)")
    return copied


def snapshot_configs(dest: Path, log=print, repo_root: Path | None = None) -> list[str]:
    """Copy credential env files + systemd unit files into dest (600 perms).

    Also snapshots local-only agent state (see snapshot_agent_state).
    repo_root defaults to this script's repository root; tests inject a
    fixture tree instead.
    """
    copied: list[str] = []
    env_dir = dest / "configs"
    env_dir.mkdir(parents=True, exist_ok=True)
    for src in CONFIG_ENV_FILES:
        src_path = Path(src)
        if src_path.is_file():
            target = env_dir / src_path.name
            shutil.copy2(src_path, target)
            os.chmod(target, 0o600)
            copied.append(str(target))
            log(f"[CONFIG] copied {src_path} (mode 600)")
    unit_files: set[Path] = set()
    for pattern in CONFIG_UNIT_GLOBS:
        for p in Path("/etc/systemd/system").glob(Path(pattern).name):
            if p.is_file():
                unit_files.add(p)
    if unit_files:
        units_dir = dest / "configs" / "systemd"
        units_dir.mkdir(parents=True, exist_ok=True)
        for src_path in sorted(unit_files):
            target = units_dir / src_path.name
            shutil.copy2(src_path, target)
            os.chmod(target, 0o600)
            copied.append(str(target))
        log(f"[CONFIG] copied {len(unit_files)} systemd unit files (mode 600)")
    if repo_root is None:
        repo_root = Path(__file__).resolve().parents[1]
    copied.extend(snapshot_agent_state(dest, repo_root, log=log))
    return copied


def snapshot_agent_envs(dest: Path, repo_root: Path | None = None, log=print) -> list[str]:
    """Copy per-agent .env files into dest/configs/agent-env/ (600 perms).

    TASK-SEN-009 (SEN-007 gap G7): the per-agent .env files are each agent's
    systemd EnvironmentFile and hold the values a rebuilt server needs; until
    now no backup covered them. They are SECRETS: they are copied only into
    the backup directory itself (mode 700, created by the caller) with mode
    600, exactly like the /etc credential files in snapshot_configs; their
    contents are never logged and never enter the manifest (paths only).
    Agents whose .env does not exist on this host are skipped silently —
    each server snapshots the env files of the agents it actually hosts.
    """
    if repo_root is None:
        repo_root = Path(__file__).resolve().parents[1]
    copied: list[str] = []
    seen_dirs: set[str] = set()
    for agent, env_dir_name in sorted(AGENT_ENV_DIRS.items()):
        if env_dir_name in seen_dirs:
            continue  # VYRALX_MEDIA shares the VyralX directory
        seen_dirs.add(env_dir_name)
        src_path = repo_root / env_dir_name / ".env"
        if not src_path.is_file():
            continue
        target = dest / "configs" / "agent-env" / env_dir_name / ".env"
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src_path, target)
        os.chmod(target, 0o600)
        copied.append(str(target))
    if copied:
        log(f"[CONFIG] copied {len(copied)} per-agent .env files (mode 600)")
    return copied


def backup_agent(agent: str, out_dir: Path, *, env_file: str | None, media: bool,
                 dry_run: bool, log=print) -> dict:
    """Dump one agent schema. Returns the manifest entry (or inventory for dry-run)."""
    runtime_env = agent_runtime_env(agent)
    target = resolve_target(agent, env_file=env_file, media=media, env=runtime_env or None)
    log(f"[{agent}] connecting as {target.redacted()}")
    conn = connect(target)
    try:
        tables = list_tables(conn)
        cols = table_columns(conn)
        if dry_run:
            counts = {}
            for table in tables:
                with conn.cursor() as cur:
                    cur.execute(f'SELECT COUNT(*) FROM "{table}"')
                    counts[table] = int(cur.fetchone()[0])
            log(f"[{agent}] DRY-RUN inventory: {len(tables)} tables, {sum(counts.values())} rows")
            return {"agent": agent, "schema": target.user, "tables": tables,
                    "row_counts": counts, "inventoried_at": utcnow()}
        agent_dir = out_dir / agent
        agent_dir.mkdir(parents=True, exist_ok=True)
        entries = []
        for table in tables:
            dump_path = agent_dir / f"{table}.jsonl.gz"
            count, checksum = write_jsonl_dump(dump_path, dump_table_rows(conn, table))
            os.chmod(dump_path, 0o600)
            entries.append({
                "table": table,
                "columns": cols.get(table),
                "row_count": count,
                "sha256": checksum,
                "file": str(dump_path.relative_to(out_dir)),
            })
            log(f"[{agent}] {table}: {count} rows -> {dump_path.name} (sha256 {checksum[:12]})")
        return {"agent": agent, "schema": target.user, "dsn_redacted": target.redacted(),
                "tables": entries, "dumped_at": utcnow()}
    finally:
        conn.close()


def verify_backup(out_dir: Path, manifest: dict, log=print) -> tuple[int, int]:
    """Validate every dump file against the manifest. Returns (ok, failed)."""
    ok = failed = 0
    for agent_entry in manifest.get("agents", []):
        for table_entry in agent_entry.get("tables", []):
            path = out_dir / table_entry["file"]
            if not path.is_file():
                log(f"[VERIFY-FAIL] {agent_entry['agent']}/{table_entry['table']}: file missing")
                failed += 1
                continue
            if sha256_file(path) != table_entry["sha256"]:
                log(f"[VERIFY-FAIL] {agent_entry['agent']}/{table_entry['table']}: checksum mismatch")
                failed += 1
            else:
                ok += 1
    for key in ("configs", "agent_envs"):
        for cfg in manifest.get(key) or []:
            if Path(cfg).is_file():
                ok += 1
            else:
                log(f"[VERIFY-FAIL] {key} file missing: {cfg}")
                failed += 1
    return ok, failed


def run(args, log=print) -> int:
    agents = [a.strip().upper() for a in args.agents.split(",") if a.strip()]
    media = bool(args.media or getattr(args, "media_only", False))
    requested = [] if getattr(args, "media_only", False) else (agents or ALL_AGENTS)

    if args.verify:
        base = Path(args.from_dir or args.out)
        manifest_path = base / "manifest.json"
        if not manifest_path.is_file():
            log(f"VERIFY-ABORT: no manifest at {manifest_path}")
            return 2
        manifest = json.loads(manifest_path.read_text())
        ok, failed = verify_backup(base, manifest, log=log)
        log(f"[VERIFY] {ok} files OK, {failed} failed — backup {base}")
        return 0 if failed == 0 else 1

    if args.dry_run:
        inventory = {"mode": "dry-run", "at": utcnow(), "agents": []}
        for agent in requested:
            try:
                inventory["agents"].append(
                    backup_agent(agent, Path(args.out), env_file=args.env_file,
                                 media=media, dry_run=True, log=log))
            except OracleConfigError as exc:
                log(f"[{agent}] SKIP: {exc}")
        log(json.dumps(inventory, indent=2)[:2000])
        return 0

    out_root = Path(args.out) if args.out != DEFAULT_OUT_ROOT else Path(DEFAULT_OUT_ROOT)
    stamp = dt.datetime.now().strftime("%Y%m%dT%H%M%SZ")
    out_dir = out_root / stamp
    out_dir.mkdir(parents=True, exist_ok=True)
    os.chmod(out_dir, 0o700)

    manifest: dict = {"task": "TASK-INF-003", "created_at": utcnow(), "agents": [],
                      "configs": [], "agent_envs": [], "root": str(out_dir)}
    failed_agents = []
    for agent in requested:
        try:
            manifest["agents"].append(
                backup_agent(agent, out_dir, env_file=args.env_file, media=False,
                             dry_run=False, log=log))
        except Exception as exc:  # noqa: BLE001 — keep going per agent
            log(f"[{agent}] FAILED: {exc}")
            failed_agents.append(agent)
    if media:
        try:
            manifest["agents"].append(
                backup_agent(MEDIA_SCHEMA, out_dir, env_file=args.env_file, media=True,
                             dry_run=False, log=log))
        except Exception as exc:  # noqa: BLE001 — TASK-SEN-009: a requested media
            # backup that fails is a FAILURE (counted, exit 1), never a silent
            # skip, and it must not take the whole manifest down with it.
            log(f"[{MEDIA_SCHEMA}] FAILED: {exc}")
            failed_agents.append(MEDIA_SCHEMA)
    if not args.no_configs:
        manifest["configs"] = snapshot_configs(out_dir, log=log)
        manifest["agent_envs"] = snapshot_agent_envs(out_dir, log=log)

    ok, failed = verify_backup(out_dir, manifest, log=log)
    manifest["verify"] = {"ok": ok, "failed": failed, "verified_at": utcnow()}
    manifest["failed_agents"] = failed_agents
    # TASK-SEN-009: completeness is the retention/freshness currency — a
    # backup only counts as a restorable copy when every requested schema
    # dumped and every written file verified.
    manifest["complete"] = not failed_agents and failed == 0
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    os.chmod(out_dir / "manifest.json", 0o600)
    log(f"[BACKUP] complete: {out_dir} (verify: {ok} OK / {failed} failed; agents failed: {failed_agents or 'none'})")
    if args.keep:
        prune_old_backups(out_root, keep=args.keep, log=log)
    return 0 if not failed_agents and failed == 0 else 1


def backup_completeness(backup_dir: Path) -> bool | None:
    """True/False from a backup dir's manifest; None when it cannot be judged.

    TASK-SEN-009: manifests written by this version carry an explicit
    ``complete`` flag. Older manifests are judged by the fields they do
    have (no failed agents and a clean verify). A missing or unreadable
    manifest is None (unknown) — such directories are treated
    conservatively by the pruner.
    """
    manifest_path = backup_dir / "manifest.json"
    if not manifest_path.is_file():
        return None
    try:
        manifest = json.loads(manifest_path.read_text())
    except Exception:  # noqa: BLE001 — unreadable manifest = unknown
        return None
    if "complete" in manifest:
        return bool(manifest["complete"])
    verify = manifest.get("verify") or {}
    return not manifest.get("failed_agents") and verify.get("failed", 1) == 0


def prune_old_backups(root: Path, *, keep: int, log=print) -> None:
    """Retention (TASK-SEN-009, owner mandate "maintain a backup").

    The unit of retention is the SUCCESSFUL backup, so one bad run can
    never push out the last good copy:

    * complete backups: keep the newest ``keep``;
    * incomplete backups (manifest present, not complete): keep only the
      newest one, and only while it is newer than the newest complete
      backup (it is the forensic record of the latest failed attempt);
    * unjudgeable directories (no/unreadable manifest): keep the newest
      ``keep`` — never destroy what cannot be classified.
    """
    if not root.is_dir():
        return
    dirs = sorted([d for d in root.iterdir() if d.is_dir()], reverse=True)
    judged = {d: backup_completeness(d) for d in dirs}
    complete = [d for d in dirs if judged[d] is True]
    incomplete = [d for d in dirs if judged[d] is False]
    unknown = [d for d in dirs if judged[d] is None]
    keep_set = set(complete[:keep]) | set(unknown[:keep])
    if incomplete and (not complete or incomplete[0] > complete[0]):
        keep_set.add(incomplete[0])
    for old in dirs:
        if old not in keep_set:
            shutil.rmtree(old)
            log(f"[PRUNE] removed old backup {old}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--agents", default="", help="comma list (default: all ten)")
    ap.add_argument("--media", action="store_true", help="include the VyralX media schema")
    ap.add_argument("--media-only", action="store_true",
                    help="only the VyralX media schema (Server 2 job, TASK-SEN-009)")
    ap.add_argument("--out", default=DEFAULT_OUT_ROOT, help="backup root (a timestamped dir is created inside)")
    ap.add_argument("--from-dir", default="", help="(verify) backup dir to verify")
    ap.add_argument("--dry-run", action="store_true", help="inventory only, no files written")
    ap.add_argument("--verify", action="store_true", help="verify the last (or --from) backup")
    ap.add_argument("--config-only", action="store_true", help="only snapshot config files")
    ap.add_argument("--no-configs", action="store_true", help="skip config snapshot during DB dump")
    ap.add_argument("--env-file", default="", help="explicit credentials env file")
    ap.add_argument("--keep", type=int, default=0, help="prune, keeping only N newest backups")
    args = ap.parse_args()
    if args.config_only:
        stamp = dt.datetime.now().strftime("%Y%m%dT%H%M%SZ")
        out_dir = Path(args.out) / stamp
        out_dir.mkdir(parents=True, exist_ok=True)
        os.chmod(out_dir, 0o700)
        copied = snapshot_configs(out_dir)
        env_copied = snapshot_agent_envs(out_dir)
        (out_dir / "manifest.json").write_text(
            json.dumps({"task": "TASK-INF-003", "created_at": utcnow(),
                        "configs": copied, "agent_envs": env_copied}, indent=2) + "\n")
        print(f"[CONFIG-ONLY] {len(copied) + len(env_copied)} files -> {out_dir}")
        return 0
    return run(args)


if __name__ == "__main__":
    sys.exit(main())
