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
    --fleet-state-only  only collect the TASK-REL-096 fleet-state bundle
                   (live file state from all six servers + the MySQL
                   'Stratex DB' dump; runs on Oracle Server 2)
    --finalize     merge a fleet-state bundle (and optionally another
                   set's agent dumps, --merge-from) into a backup set and
                   re-verify it as the unified set (TASK-REL-096)

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


#: Where the fleet's repo tree is installed on the servers. Used when
#: this script runs from OUTSIDE the checkout (TASK-REL-096 fix round 7).
FLEET_INSTALLED_ROOT = Path("/opt/friday_universe")


def _fleet_repo_root() -> Path:
    """Repo root for fleet-file lookups (per-agent .env, agent state).

    Normally the checkout containing this script (``scripts/..``). The
    Fleet Backup workflow downloads this script to /tmp (a stale or
    worker-shared checkout must never poison a backup), where the
    script-relative root is meaningless — fall back to the fleet's
    installed root. Run 45587046488 proved the need: from /tmp, the
    per-agent .env lookup silently found nothing and STRATEX, INTELX
    and FORGE dumped nothing ("no Oracle credentials found"), while
    the config/state snapshots silently covered nothing.
    """
    here = Path(__file__).resolve().parents[1]
    if any((here / d).is_dir() for d in AGENT_ENV_DIRS.values()):
        return here
    if FLEET_INSTALLED_ROOT.is_dir():
        return FLEET_INSTALLED_ROOT
    return here


def agent_runtime_env(agent: str, repo_root: Path | None = None) -> dict:
    """Load the agent's own .env (its systemd EnvironmentFile) as a dict.

    This is the production credential source on the servers; the shared
    /etc/friday-universe files are consulted by oracle_db.resolve_target
    separately. Values stay in memory only.
    """
    root = repo_root or _fleet_repo_root()
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
        # TASK-REL-091: python-oracledb LOB.read(offset, amount) takes the
        # 1-based OFFSET first, not the amount. The old read(LOB_CAP_BYTES)
        # started at byte 1,000,000, so every CLOB under 1 MB read back empty
        # (14,414 empty strings in the Nov 22 backup). Read from offset 1.
        raw = value.read(1, LOB_CAP_BYTES)
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
        repo_root = _fleet_repo_root()
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
        repo_root = _fleet_repo_root()
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


# ---------------------------------------------------------------------------
# TASK-REL-096 — fleet-state bundle: the live file state that no schema dump
# can capture (Stratex ledgers + forward record, VyralX renders + data/,
# IntelX/Futuris file stores, FRIDAY conversation state), collected from
# every fleet server into one bundle that --finalize later merges into the
# unified backup set held identically on both Oracle servers.
#
# The bundle builder runs on Oracle Server 2 (the bridge host — the host
# with proven SSH routes to all six servers). Secrets discipline is
# unchanged: file contents are never logged; manifests record paths, sizes
# and SHA-256 only. MySQL credentials are parsed in memory from the fleet
# record (CREDENTIALS.md, itself inside the bundle) and never printed.
#: The fleet's universal key (padlock on all six servers). The collect
#: runs under sudo in the workflow, and root has no keys of its own —
#: run 45587046488 failed EVERY pull with default identity lookup.
#: The absolute path works for root and for the ubuntu owner alike.
UNIVERSAL_KEY_PATH = "/home/ubuntu/.ssh/Oracle-Cloud-x-AWS-Key"
FLEET_STATE_SSH = ("ssh -o BatchMode=yes -o StrictHostKeyChecking=accept-new "
                   f"-o ConnectTimeout=15 -i {UNIVERSAL_KEY_PATH}")
FLEET_STATE_SOURCES = (
    # (label, ssh host, absolute paths, required)
    ("server1", "140.245.208.100", (
        "/opt/friday_universe/Memora/data", "/opt/friday_universe/Memora/state",
        "/opt/friday_universe/Forge/data", "/opt/friday_universe/Forge/state",
        "/opt/friday_universe/Sentinel/data", "/opt/friday_universe/Sentinel/state",
        "/opt/friday_universe/Cortex/data", "/opt/friday_universe/Cortex/state",
    ), False),
    ("server3", "15.134.130.145", (
        "/opt/friday_universe/FRIDAY/data", "/opt/friday_universe/FRIDAY/state",
        "/opt/friday_universe/Inference/data",
    ), True),
    ("server4", "13.211.78.20", (
        "/opt/friday_universe/Stratex/state", "/opt/friday_universe/Stratex/data",
    ), True),
    ("server5", "13.211.162.71", (
        "/opt/friday_universe/VyralX/data", "/opt/friday_universe/VyralX/renders",
    ), True),
    ("server6", "32.236.185.237", (
        "/opt/friday_universe/IntelX/data", "/opt/friday_universe/Futuris/data",
    ), True),
    # Futuris/.data does not exist on IntelX-Server (live collect, run
    # 45589775802: every other source pulled, this one reported
    # "missing" and single-handedly marked the bundle incomplete).
    # Optional: covered whenever it exists, never blocking.
    ("server6", "32.236.185.237", (
        "/opt/friday_universe/Futuris/.data",
    ), False),
)
FLEET_STATE_SUDO_SOURCES = (
    ("server6-soak", "32.236.185.237", ("/var/lib/friday-universe/intelx-soak",), False),
)
FLEET_STATE_LOCAL_FILES = ("/opt/friday_universe/CREDENTIALS.md",)
# Named exclusion (owner rule: nothing is silently scoped out). VyralX's
# media/ tree is ~3.9 GB of downloaded SOURCE clips (du -sh on VyralX-Server,
# 2026-11-25) — re-obtainable from the origin URLs catalogued in the
# VyralX/data manifests, which ARE in the bundle. Her produced work
# (renders/, ~2.2 GB) and all of data/ (~403 MB) are included in full.
FLEET_STATE_EXCLUDED = (
    {"item": "VyralX/media (downloaded source clips) on VyralX-Server",
     "size_evidence": "3.9 GB (du -sh /opt/friday_universe/VyralX/media, 2026-11-25)",
     "reason": "source material re-obtainable from origin URLs recorded in the "
               "backed-up VyralX/data manifests; produced renders and all "
               "state are included"},
)
MYSQL_ENV_KEYS = ("MYSQL_HOST", "MYSQL_PORT", "MYSQL_STRATEX_USER",
                  "MYSQL_STRATEX_PASSWORD", "MYSQL_STRATEX_DB")


def fleet_state_rsync_argv(host: str, path: str, dest_dir: Path, *, sudo: bool = False) -> list:
    """Build the rsync argv for one fleet-state source path (pure, testable)."""
    argv = ["rsync", "-az", "--relative", "-e", FLEET_STATE_SSH]
    if sudo:
        argv.append("--rsync-path=sudo -n rsync")
    argv += [f"ubuntu@{host}:{path}", str(dest_dir)]
    return argv


def parse_mysql_env(text: str) -> dict:
    """Extract the MYSQL_* connection keys from fleet-record text.

    Values are returned in memory only — callers must never log them.
    """
    out: dict = {}
    for line in text.splitlines():
        line = line.strip().lstrip("- ").strip()
        if "=" not in line:
            continue
        key, _, val = line.partition("=")
        key = key.strip()
        if key in MYSQL_ENV_KEYS:
            out[key] = val.strip().strip("`").strip()
    return out


def dump_mysql_stratex(bundle_dir: Path, *, creds_text: str | None = None, log=print) -> dict:
    """Logical dump of the MySQL 'Stratex DB' (stratex_research) into the bundle.

    Credentials are parsed in memory from the fleet record (CREDENTIALS.md)
    — never logged, never written anywhere else. Tooling: mysqldump when
    present, else pymysql. Any gap is recorded in the result, never silent.
    """
    dest_dir = bundle_dir / "mysql"
    dest_dir.mkdir(parents=True, exist_ok=True)
    if creds_text is None:
        cred_path = Path("/opt/friday_universe/CREDENTIALS.md")
        if not cred_path.is_file():
            return {"status": "unavailable",
                    "reason": "fleet record (CREDENTIALS.md) not found on this host"}
        creds_text = cred_path.read_text(errors="replace")
    env = parse_mysql_env(creds_text)
    missing = [k for k in MYSQL_ENV_KEYS if not env.get(k)]
    if missing:
        return {"status": "unavailable",
                "reason": f"fleet record lacks keys: {', '.join(missing)}"}
    host = env["MYSQL_HOST"]
    try:
        port = int(env.get("MYSQL_PORT") or 3306)
    except ValueError:
        port = 3306
    user, password, db = env["MYSQL_STRATEX_USER"], env["MYSQL_STRATEX_PASSWORD"], env["MYSQL_STRATEX_DB"]
    dest = dest_dir / "STRATEX_MYSQL.sql.gz"
    import subprocess

    if shutil.which("mysqldump"):
        run_env = dict(os.environ, MYSQL_PWD=password)
        res = subprocess.run(
            ["mysqldump", "-h", host, "-P", str(port), "-u", user,
             "--single-transaction", "--skip-lock-tables", db],
            capture_output=True, timeout=1800, env=run_env)
        if res.returncode != 0:
            return {"status": "failed", "reason": "mysqldump exited non-zero"}
        with gzip.open(dest, "wb") as fh:
            fh.write(res.stdout)
    else:
        try:
            import pymysql
        except ImportError:
            return {"status": "unavailable",
                    "reason": "no mysqldump binary and pymysql not importable on this host"}
        conn = pymysql.connect(host=host, port=port, user=user, password=password, database=db)
        try:
            with conn.cursor() as cur, gzip.open(dest, "wt", encoding="utf-8") as fh:
                fh.write(f"-- TASK-REL-096 MySQL logical dump of {db} at {utcnow()}\n")
                cur.execute("SHOW TABLES")
                tables = [r[0] for r in cur.fetchall()]
                for table in tables:
                    cur.execute(f"SHOW CREATE TABLE `{table}`")
                    fh.write(cur.fetchone()[1] + ";\n")
                    cur.execute(f"SELECT * FROM `{table}`")
                    cols = [d[0] for d in cur.description]
                    for row in cur.fetchall():
                        vals = ",".join(
                            "NULL" if v is None else
                            (str(v) if isinstance(v, (int, float)) else
                             "'" + str(v).replace("\\", "\\\\").replace("'", "\\'") + "'")
                            for v in row)
                        fh.write(f"INSERT INTO `{table}` ({','.join(cols)}) VALUES ({vals});\n")
        finally:
            conn.close()
    os.chmod(dest, 0o600)
    log(f"[FLEET-STATE] MySQL {db} dumped -> {dest.name}")
    return {"status": "dumped", "file": str(dest.relative_to(bundle_dir)),
            "sha256": sha256_file(dest), "bytes": dest.stat().st_size}


def collect_fleet_state(bundle_dir: Path, *, runner=None, log=print) -> dict:
    """Collect the fleet-state bundle into bundle_dir; returns its manifest."""
    import subprocess

    runner = runner or subprocess.run
    files_root = bundle_dir / "files"
    files_root.mkdir(parents=True, exist_ok=True)
    source_results: list = []
    failed_required: list = []

    def do_source(label, host, paths, required, sudo=False):
        for path in paths:
            dest = files_root / label
            dest.mkdir(parents=True, exist_ok=True)
            try:
                res = runner(fleet_state_rsync_argv(host, path, dest, sudo=sudo),
                             capture_output=True, text=True, timeout=3600)
                rc = res.returncode
            except Exception as exc:  # noqa: BLE001 — recorded, never silent
                source_results.append({"label": label, "path": path, "status": "failed",
                                       "error": type(exc).__name__})
                if required:
                    failed_required.append(f"{label}:{path} (error)")
                log(f"[FLEET-STATE] {label}:{path} -> error ({type(exc).__name__})")
                continue
            status = "ok" if rc == 0 else ("missing" if rc in (23, 24) else "failed")
            source_results.append({"label": label, "path": path, "status": status})
            if status == "failed" or (status == "missing" and required):
                failed_required.append(f"{label}:{path} ({status})")
            log(f"[FLEET-STATE] {label}:{path} -> {status}")

    for label, host, paths, required in FLEET_STATE_SOURCES:
        do_source(label, host, paths, required)
    for label, host, paths, required in FLEET_STATE_SUDO_SOURCES:
        do_source(label, host, paths, required, sudo=True)
    for local_file in FLEET_STATE_LOCAL_FILES:
        src = Path(local_file)
        entry = {"label": "local", "path": local_file, "status": "missing"}
        if src.is_file():
            target = files_root / "local" / src.name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, target)
            os.chmod(target, 0o600)
            entry["status"] = "ok"
        else:
            failed_required.append(f"local:{local_file} (missing)")
        source_results.append(entry)
        log(f"[FLEET-STATE] local:{local_file} -> {entry['status']}")

    mysql = dump_mysql_stratex(bundle_dir, log=log)
    entries = []
    for path in sorted(files_root.rglob("*")):
        if path.is_file():
            entries.append({"path": str(path.relative_to(bundle_dir)),
                            "sha256": sha256_file(path), "bytes": path.stat().st_size})
    if mysql.get("status") == "dumped":
        entries.append({"path": mysql["file"], "sha256": mysql["sha256"],
                        "bytes": mysql["bytes"]})
    complete = not failed_required and mysql.get("status") == "dumped"
    manifest = {"task": "TASK-REL-096", "created_at": utcnow(), "files": entries,
                "sources": source_results, "mysql": mysql,
                "excluded": list(FLEET_STATE_EXCLUDED), "complete": complete,
                "failed_required": failed_required}
    (bundle_dir / "bundle_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    os.chmod(bundle_dir / "bundle_manifest.json", 0o600)
    log(f"[FLEET-STATE] bundle {'complete' if complete else 'INCOMPLETE'}: "
        f"{len(entries)} files, failed_required={failed_required or 'none'}, "
        f"mysql={mysql.get('status')}")
    return manifest


def _localize_manifest_paths(entries: list, set_dir: Path) -> list:
    """Rewrite absolute config paths from another host's set dir to this one."""
    out = []
    for entry in entries or []:
        parts = Path(entry).parts
        if "configs" in parts:
            idx = parts.index("configs")
            out.append(str(set_dir.joinpath(*parts[idx:])))
        else:
            out.append(entry)
    return out


def finalize_unified_set(set_dir: Path, bundle_dir: Path, *, merge_from: Path | None = None,
                         log=print) -> dict:
    """Merge a fleet-state bundle (+ optionally another set's agent dumps)
    into set_dir and re-verify/re-derive its manifest (TASK-REL-096)."""
    manifest = json.loads((set_dir / "manifest.json").read_text())
    if merge_from is not None:
        other = json.loads((merge_from / "manifest.json").read_text())
        have = {e.get("agent") for e in manifest.get("agents", [])}
        for entry in other.get("agents", []):
            if entry.get("agent") in have:
                continue
            for table_entry in entry.get("tables", []):
                src = merge_from / table_entry["file"]
                dst = set_dir / table_entry["file"]
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dst)
                os.chmod(dst, 0o600)
            manifest.setdefault("agents", []).append(entry)
            log(f"[FINALIZE] merged agent {entry.get('agent')} from {merge_from}")
    bundle_manifest = json.loads((bundle_dir / "bundle_manifest.json").read_text())
    fs_dest = set_dir / "fleet-state"
    if fs_dest.exists():
        shutil.rmtree(fs_dest)
    shutil.copytree(bundle_dir, fs_dest)
    for path in fs_dest.rglob("*"):
        if path.is_file():
            os.chmod(path, 0o600)
    fs_entries = [{**e, "path": f"fleet-state/{e['path']}"}
                  for e in bundle_manifest.get("files", [])]
    manifest["fleet_state"] = {
        "complete": bundle_manifest.get("complete"),
        "files": fs_entries,
        "sources": bundle_manifest.get("sources"),
        "mysql": bundle_manifest.get("mysql"),
        "excluded": bundle_manifest.get("excluded"),
        "bundled_at": bundle_manifest.get("created_at"),
    }
    manifest["configs"] = _localize_manifest_paths(manifest.get("configs") or [], set_dir)
    manifest["agent_envs"] = _localize_manifest_paths(manifest.get("agent_envs") or [], set_dir)
    ok, failed = verify_backup(set_dir, manifest, log=log)
    manifest["verify"] = {"ok": ok, "failed": failed, "verified_at": utcnow()}
    manifest["complete"], reasons = derive_manifest_complete(manifest)
    if not manifest["complete"]:
        for reason in reasons:
            log(f"[FINALIZE] INCOMPLETE: {reason}")
    (set_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    os.chmod(set_dir / "manifest.json", 0o600)
    log(f"[FINALIZE] {set_dir}: complete={manifest['complete']} "
        f"(verify {ok} OK / {failed} failed)")
    return manifest


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
    for fentry in (manifest.get("fleet_state") or {}).get("files", []):
        path = out_dir / fentry["path"]
        if not path.is_file():
            log(f"[VERIFY-FAIL] fleet-state file missing: {fentry['path']}")
            failed += 1
        elif sha256_file(path) != fentry["sha256"]:
            log(f"[VERIFY-FAIL] fleet-state checksum mismatch: {fentry['path']}")
            failed += 1
        else:
            ok += 1
    return ok, failed


def derive_manifest_complete(
    manifest: dict, *, live_verify_failed: int | None = None
) -> tuple[bool, list[str]]:
    """Re-derive completeness from a manifest's own contents (TASK-SEN-022).

    The written ``complete`` flag is a claim; this is the audit of it.
    A backup counts as complete only when:

    * no agent failed,
    * the file verification was clean — the manifest's own ``verify``
      block, or a live ``--verify`` count when one is supplied,
    * every requested agent is present in the dump list (when the
      manifest records ``requested_agents`` — a partial run cannot
      silently pass as a full one), and
    * every dumped agent actually dumped at least one table (a
      zero-table dump is a wrong-schema resolution, SEN-009 §4, not a
      backup — an empty schema "backs up" cleanly under the old rule).

    Returns ``(complete, reasons)`` — the reasons name each failing
    condition so callers can say WHY a backup is incomplete instead of
    just that it is. The flag itself is part of the verdict: a run that
    recorded ``complete: false`` stays incomplete even if its contents
    look clean (the run's own verdict is not overruled by re-reading
    its files). A missing or unreadable manifest is the caller's
    problem (``None`` from ``backup_completeness``), not this function's.
    """
    reasons: list[str] = []
    if manifest.get("complete") is False:
        reasons.append("manifest flag complete=false (the run's own verdict)")
    failed_agents = manifest.get("failed_agents") or []
    if failed_agents:
        reasons.append(f"failed agents: {', '.join(str(a) for a in failed_agents)}")
    if live_verify_failed is None:
        verify = manifest.get("verify")
        if not isinstance(verify, dict):
            reasons.append("no verify block (files were never checksum-verified)")
        elif verify.get("failed", 1) != 0:
            reasons.append(f"verify failed: {verify.get('failed')} file(s)")
    elif live_verify_failed != 0:
        reasons.append(f"verify failed: {live_verify_failed} file(s)")
    dumped = {entry.get("agent") for entry in manifest.get("agents") or []}
    requested = manifest.get("requested_agents")
    if requested is not None:
        missing = [a for a in requested if a not in dumped]
        if missing:
            reasons.append(f"requested agents not dumped: {', '.join(missing)}")
    for entry in manifest.get("agents") or []:
        if not entry.get("tables"):
            reasons.append(f"{entry.get('agent')}: dumped 0 tables (wrong-schema resolution?)")
    fleet = manifest.get("fleet_state")
    if fleet is not None:
        if not fleet.get("complete"):
            reasons.append("fleet-state bundle incomplete (TASK-REL-096)")
        if not fleet.get("files"):
            reasons.append("fleet-state bundle recorded no files (TASK-REL-096)")
        mysql = fleet.get("mysql") or {}
        if mysql.get("status") != "dumped":
            reasons.append(f"MySQL Stratex DB not dumped: {mysql.get('status')}")
    return (not reasons, reasons)


def _newest_backup_dir(root: Path) -> Path | None:
    """Newest subdir of a backup root that holds a manifest, else None."""
    if not root.is_dir():
        return None
    candidates = sorted(
        (d for d in root.iterdir() if d.is_dir() and (d / "manifest.json").is_file()),
        reverse=True)
    return candidates[0] if candidates else None


def run(args, log=print) -> int:
    agents = [a.strip().upper() for a in args.agents.split(",") if a.strip()]
    media = bool(args.media or getattr(args, "media_only", False))
    requested = [] if getattr(args, "media_only", False) else (agents or ALL_AGENTS)
    # TASK-SEN-022: the full scope this run was asked for — recorded in
    # the manifest so completeness is auditable downstream and a partial
    # run can never masquerade as a full one.
    requested_all = list(requested) + ([MEDIA_SCHEMA] if media else [])

    if args.verify:
        if args.from_dir:
            base = Path(args.from_dir)
        else:
            # TASK-SEN-022: --verify with no --from-dir verifies the
            # NEWEST backup (the --help text always promised this; the
            # old code verified the root itself and aborted).
            base = _newest_backup_dir(Path(args.out))
            if base is None:
                log(f"VERIFY-ABORT: no backup directory under {args.out}")
                return 2
        manifest_path = base / "manifest.json"
        if not manifest_path.is_file():
            log(f"VERIFY-ABORT: no manifest at {manifest_path}")
            return 2
        manifest = json.loads(manifest_path.read_text())
        ok, failed = verify_backup(base, manifest, log=log)
        # TASK-SEN-022: file checksums alone are not success — the
        # manifest's completeness is part of the verdict now. A backup
        # whose files verify but whose manifest is incomplete (a failed
        # agent, a missing schema, an empty dump) is NOT a success.
        complete, reasons = derive_manifest_complete(manifest, live_verify_failed=failed)
        if manifest.get("complete") is not None and bool(manifest["complete"]) != complete:
            log("[VERIFY-WARN] manifest 'complete' flag disagrees with the "
                f"derived verdict (flag={manifest['complete']!r}, derived={complete}); "
                "trusting the derived verdict")
        if not complete:
            for reason in reasons:
                log(f"[VERIFY-FAIL] manifest incomplete: {reason}")
            log(f"[VERIFY] {ok} files OK, {failed} failed — backup {base} INCOMPLETE, not a success")
            return 1
        log(f"[VERIFY] {ok} files OK, {failed} failed — backup {base} complete")
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
                      "configs": [], "agent_envs": [], "root": str(out_dir),
                      "requested_agents": requested_all}
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
    # TASK-SEN-022: an agent that "dumped" zero tables resolved to the
    # wrong schema (or an empty one) — that is a failure, not a backup.
    # SEN-009 §4 names it explicitly; before this it sailed through as
    # complete because only exceptions counted as failures. Row counts
    # are deliberately NOT judged here: a live-empty schema (STRATEX's
    # tables hold 0 rows in production today) is still a real backup.
    for entry in manifest["agents"]:
        if not entry.get("tables"):
            agent = entry.get("agent")
            log(f"[{agent}] FAILED: dumped 0 tables (wrong-schema resolution?)")
            if agent not in failed_agents:
                failed_agents.append(agent)
    manifest["failed_agents"] = failed_agents
    # TASK-SEN-009: completeness is the retention/freshness currency — a
    # backup only counts as a restorable copy when every requested schema
    # dumped and every written file verified. TASK-SEN-022: the flag is
    # now derived from the manifest's own contents (see
    # derive_manifest_complete), never asserted independently of them.
    manifest["complete"], complete_reasons = derive_manifest_complete(manifest)
    if not manifest["complete"]:
        for reason in complete_reasons:
            log(f"[BACKUP] INCOMPLETE: {reason}")
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    os.chmod(out_dir / "manifest.json", 0o600)
    log(f"[BACKUP] complete: {out_dir} (verify: {ok} OK / {failed} failed; agents failed: {failed_agents or 'none'})")
    if args.keep:
        prune_old_backups(out_root, keep=args.keep, log=log)
    return 0 if manifest["complete"] else 1


def backup_completeness(backup_dir: Path) -> bool | None:
    """True/False from a backup dir's manifest; None when it cannot be judged.

    TASK-SEN-009: manifests written by this version carry an explicit
    ``complete`` flag. Older manifests are judged by the fields they do
    have (no failed agents and a clean verify). A missing or unreadable
    manifest is None (unknown) — such directories are treated
    conservatively by the pruner.

    TASK-SEN-022: the flag is no longer trusted on its own — the verdict
    is re-derived from the manifest's contents (see
    derive_manifest_complete), so a flag that disagrees with its own
    manifest cannot mark a partial backup complete. The flag is still
    written (it is the run's own claim); this function is the audit.
    """
    manifest_path = backup_dir / "manifest.json"
    if not manifest_path.is_file():
        return None
    try:
        manifest = json.loads(manifest_path.read_text())
    except Exception:  # noqa: BLE001 — unreadable manifest = unknown
        return None
    complete, _reasons = derive_manifest_complete(manifest)
    return complete


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
    ap.add_argument("--fleet-state-only", action="store_true",
                    help="only collect the TASK-REL-096 fleet-state bundle (runs on Server 2)")
    ap.add_argument("--finalize", action="store_true",
                    help="merge a fleet-state bundle into the --from-dir backup set and re-verify")
    ap.add_argument("--bundle-dir", default="", help="(finalize) fleet-state bundle directory")
    ap.add_argument("--merge-from", default="",
                    help="(finalize) another backup set whose agent dumps should be merged in")
    ap.add_argument("--prune-only", action="store_true",
                    help="only prune old backups under --out (with --keep)")
    args = ap.parse_args()
    if args.prune_only:
        prune_old_backups(Path(args.out), keep=args.keep or 4)
        return 0
    if args.fleet_state_only:
        stamp = dt.datetime.now().strftime("%Y%m%dT%H%M%SZ")
        bundle_dir = Path(args.out) / f"{stamp}-fleetstate"
        bundle_dir.mkdir(parents=True, exist_ok=True)
        os.chmod(bundle_dir, 0o700)
        bundle_manifest = collect_fleet_state(bundle_dir)
        # Bundles are staging for --finalize: keep only the newest two.
        root = Path(args.out)
        bundles = sorted((d for d in root.iterdir()
                          if d.is_dir() and d.name.endswith("-fleetstate")), reverse=True)
        for old in bundles[2:]:
            shutil.rmtree(old)
            print(f"[PRUNE] removed old fleet-state bundle {old}")
        return 0 if bundle_manifest["complete"] else 1
    if args.finalize:
        if not args.from_dir or not args.bundle_dir:
            print("FINALIZE-ABORT: --finalize needs --from-dir and --bundle-dir")
            return 2
        merged = finalize_unified_set(
            Path(args.from_dir), Path(args.bundle_dir),
            merge_from=Path(args.merge_from) if args.merge_from else None)
        return 0 if merged["complete"] else 1
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
