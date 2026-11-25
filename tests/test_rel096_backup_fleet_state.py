"""TASK-REL-096 — fleet-state bundle + unified-set finalize.

Covers the REL-096 changes to scripts/backup_fleet_databases.py: the
fleet-state source table and rsync argv construction, the MySQL fleet-record
key parsing, bundle collection with an injected runner (no live rsync),
manifest verification of fleet-state files, the completeness derivation's
fleet-state conditions, and --finalize merging a bundle (+ another set's
agent dumps) into a unified set. No live database, no live SSH: every
external effect is stubbed and all state lives in tmp dirs.
"""
from __future__ import annotations

import gzip
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


backup_mod = _load("backup_fleet_databases", "scripts/backup_fleet_databases.py")


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


# ---------------------------------------------------------------------------
# Source table + argv construction
# ---------------------------------------------------------------------------

def test_source_table_covers_all_six_servers_and_required_state():
    labels = {label for label, _host, _paths, _req in backup_mod.FLEET_STATE_SOURCES}
    assert labels == {"server1", "server3", "server4", "server5", "server6"}
    joined = " ".join(
        path for _l, _h, paths, _r in backup_mod.FLEET_STATE_SOURCES for path in paths)
    for needle in ("Stratex/state", "VyralX/data", "VyralX/renders",
                   "FRIDAY/data", "IntelX/data", "Futuris/data"):
        assert needle in joined
    required_paths = " ".join(
        path for _l, _h, paths, req in backup_mod.FLEET_STATE_SOURCES if req
        for path in paths)
    for needle in ("Stratex/state", "VyralX/data", "FRIDAY/data", "IntelX/data"):
        assert needle in required_paths
    # The one named exclusion is recorded with a size, never silent.
    assert backup_mod.FLEET_STATE_EXCLUDED
    assert "GB" in backup_mod.FLEET_STATE_EXCLUDED[0]["size_evidence"]


def test_rsync_argv_shape_and_sudo_variant():
    argv = backup_mod.fleet_state_rsync_argv("13.211.78.20", "/opt/friday_universe/Stratex/state",
                                             Path("/tmp/dest"))
    assert argv[0] == "rsync" and "--relative" in argv
    assert argv[-2] == "ubuntu@13.211.78.20:/opt/friday_universe/Stratex/state"
    assert argv[-1] == "/tmp/dest"
    assert "--rsync-path=sudo -n rsync" not in argv
    sudo_argv = backup_mod.fleet_state_rsync_argv("32.236.185.237", "/var/lib/x",
                                                  Path("/tmp/dest"), sudo=True)
    assert "--rsync-path=sudo -n rsync" in sudo_argv


# ---------------------------------------------------------------------------
# MySQL fleet-record parsing (labels only — fixture values are dummies)
# ---------------------------------------------------------------------------

def test_parse_mysql_env_extracts_only_mysql_keys():
    text = (
        "## Oracle MySQL HeatWave\n"
        "MYSQL_HOST= 10.0.0.182\n"
        "- MYSQL_PORT= 3306\n"
        "MYSQL_STRATEX_USER= stratex\n"
        "MYSQL_STRATEX_PASSWORD=dummy-not-a-secret\n"
        "MYSQL_STRATEX_DB= stratex_research\n"
        "DB_PASSWORD_STRATEX= oracle-side-value\n"
        "UNRELATED= x\n"
    )
    env = backup_mod.parse_mysql_env(text)
    assert env["MYSQL_HOST"] == "10.0.0.182"
    assert env["MYSQL_PORT"] == "3306"
    assert env["MYSQL_STRATEX_DB"] == "stratex_research"
    assert "DB_PASSWORD_STRATEX" not in env
    assert "UNRELATED" not in env


def test_dump_mysql_stratex_records_unavailable_without_creds(tmp_path):
    result = backup_mod.dump_mysql_stratex(tmp_path, creds_text="nothing here")
    assert result["status"] == "unavailable"
    assert "MYSQL_HOST" in result["reason"]


# ---------------------------------------------------------------------------
# Bundle collection with an injected runner
# ---------------------------------------------------------------------------

class _Result:
    def __init__(self, returncode):
        self.returncode = returncode


def _fake_runner_factory(fail_paths=(), missing_paths=()):
    def runner(argv, **_kwargs):
        source = argv[-2].split(":", 1)[1]
        dest = Path(argv[-1])
        if source in fail_paths:
            return _Result(12)
        if source in missing_paths:
            return _Result(23)
        # Simulate rsync --relative: dest/<source path>/payload.txt
        target = dest / source.lstrip("/")
        target.mkdir(parents=True, exist_ok=True)
        (target / "payload.txt").write_text(f"payload for {source}\n")
        return _Result(0)
    return runner


def _collect(tmp_path, monkeypatch, runner):
    local_record = tmp_path / "CREDENTIALS.md"
    local_record.write_text("fixture fleet record\n")
    monkeypatch.setattr(backup_mod, "FLEET_STATE_LOCAL_FILES", (str(local_record),))
    monkeypatch.setattr(backup_mod, "dump_mysql_stratex",
                        lambda bundle_dir, **kw: {"status": "dumped",
                                                  "file": "mysql/STRATEX_MYSQL.sql.gz",
                                                  "sha256": "0" * 64, "bytes": 3})
    bundle = tmp_path / "bundle"
    bundle.mkdir()
    (bundle / "mysql").mkdir()
    (bundle / "mysql" / "STRATEX_MYSQL.sql.gz").write_bytes(b"sql")
    return backup_mod.collect_fleet_state(bundle, runner=runner, log=lambda *a: None)


def test_collect_fleet_state_happy_path(tmp_path, monkeypatch):
    manifest = _collect(tmp_path, monkeypatch, _fake_runner_factory())
    assert manifest["complete"] is True
    assert manifest["failed_required"] == []
    assert manifest["mysql"]["status"] == "dumped"
    assert manifest["excluded"]  # the named VyralX/media exclusion rides along
    paths = {e["path"] for e in manifest["files"]}
    assert any("Stratex/state" in p for p in paths)
    assert any("VyralX/renders" in p for p in paths)
    assert any(p == "mysql/STRATEX_MYSQL.sql.gz" for p in paths)
    for entry in manifest["files"]:
        if entry["path"].startswith("files/"):
            assert entry["sha256"] == _sha(tmp_path / "bundle" / entry["path"])


def test_collect_fleet_state_required_missing_fails(tmp_path, monkeypatch):
    runner = _fake_runner_factory(missing_paths=("/opt/friday_universe/Stratex/state",))
    manifest = _collect(tmp_path, monkeypatch, runner)
    assert manifest["complete"] is False
    assert any("Stratex/state" in f for f in manifest["failed_required"])


def test_collect_fleet_state_optional_missing_is_recorded_not_fatal(tmp_path, monkeypatch):
    runner = _fake_runner_factory(missing_paths=("/opt/friday_universe/Memora/data",))
    manifest = _collect(tmp_path, monkeypatch, runner)
    assert manifest["complete"] is True
    statuses = {(s["label"], s["path"]): s["status"] for s in manifest["sources"]}
    assert statuses[("server1", "/opt/friday_universe/Memora/data")] == "missing"


# ---------------------------------------------------------------------------
# Verify + completeness derivation with fleet-state files
# ---------------------------------------------------------------------------

def _write_set(tmp_path, *, fleet_complete=True, fleet_files=True):
    set_dir = tmp_path / "set"
    set_dir.mkdir()
    agent_dir = set_dir / "MEMORA"
    agent_dir.mkdir()
    dump = agent_dir / "T1.jsonl.gz"
    with gzip.open(dump, "wt", encoding="utf-8") as fh:
        fh.write('{"a": 1}\n')
    manifest = {
        "agents": [{"agent": "MEMORA", "tables": [
            {"table": "T1", "file": "MEMORA/T1.jsonl.gz", "sha256": _sha(dump),
             "row_count": 1}]}],
        "requested_agents": ["MEMORA"],
        "configs": [], "agent_envs": [],
        "verify": {"ok": 1, "failed": 0},
    }
    if fleet_files:
        fs_file = set_dir / "fleet-state" / "files" / "x.txt"
        fs_file.parent.mkdir(parents=True)
        fs_file.write_text("state\n")
        manifest["fleet_state"] = {
            "complete": fleet_complete,
            "files": [{"path": "fleet-state/files/x.txt", "sha256": _sha(fs_file),
                       "bytes": fs_file.stat().st_size}],
            "mysql": {"status": "dumped"},
        }
    (set_dir / "manifest.json").write_text(json.dumps(manifest))
    return set_dir, manifest


def test_verify_backup_counts_fleet_state_files(tmp_path):
    set_dir, manifest = _write_set(tmp_path)
    ok, failed = backup_mod.verify_backup(set_dir, manifest, log=lambda *a: None)
    assert (ok, failed) == (2, 0)
    (set_dir / "fleet-state" / "files" / "x.txt").write_text("tampered\n")
    ok, failed = backup_mod.verify_backup(set_dir, manifest, log=lambda *a: None)
    assert failed == 1


def test_derive_complete_fleet_state_conditions(tmp_path):
    _set_dir, manifest = _write_set(tmp_path)
    complete, reasons = backup_mod.derive_manifest_complete(manifest)
    assert complete, reasons
    manifest2 = json.loads(json.dumps(manifest))
    manifest2["fleet_state"]["complete"] = False
    complete, reasons = backup_mod.derive_manifest_complete(manifest2)
    assert not complete and any("fleet-state" in r for r in reasons)
    manifest3 = json.loads(json.dumps(manifest))
    manifest3["fleet_state"]["mysql"] = {"status": "unavailable"}
    complete, reasons = backup_mod.derive_manifest_complete(manifest3)
    assert not complete and any("MySQL" in r for r in reasons)
    # A manifest with no fleet_state key (pre-REL-096 sets) is unaffected.
    manifest4 = json.loads(json.dumps(manifest))
    del manifest4["fleet_state"]
    complete, _reasons = backup_mod.derive_manifest_complete(manifest4)
    assert complete


# ---------------------------------------------------------------------------
# Finalize: bundle + media set merged into the unified set
# ---------------------------------------------------------------------------

def test_finalize_merges_bundle_and_agents(tmp_path):
    set_dir, _manifest = _write_set(tmp_path, fleet_files=False)
    # Bundle fixture.
    bundle = tmp_path / "bundle"
    payload = bundle / "files" / "server4" / "opt" / "friday_universe" / "Stratex" / "state"
    payload.mkdir(parents=True)
    state_file = payload / "forward_scorecard.json"
    state_file.write_text('{"open": 30}\n')
    (bundle / "mysql").mkdir()
    sql = bundle / "mysql" / "STRATEX_MYSQL.sql.gz"
    sql.write_bytes(b"sql-bytes")
    bundle_manifest = {
        "complete": True,
        "files": [
            {"path": "files/server4/opt/friday_universe/Stratex/state/forward_scorecard.json",
             "sha256": _sha(state_file), "bytes": state_file.stat().st_size},
            {"path": "mysql/STRATEX_MYSQL.sql.gz", "sha256": _sha(sql),
             "bytes": sql.stat().st_size},
        ],
        "sources": [], "mysql": {"status": "dumped"}, "excluded": [],
        "created_at": "2026-11-25T00:00:00Z",
    }
    (bundle / "bundle_manifest.json").write_text(json.dumps(bundle_manifest))
    # Media set fixture (another set holding only VYRALX_MEDIA).
    media_set = tmp_path / "media_set"
    media_dir = media_set / "VYRALX_MEDIA"
    media_dir.mkdir(parents=True)
    media_dump = media_dir / "MEDIA_FILES.jsonl.gz"
    with gzip.open(media_dump, "wt", encoding="utf-8") as fh:
        fh.write('{"id": 1}\n')
    (media_set / "manifest.json").write_text(json.dumps({
        "agents": [{"agent": "VYRALX_MEDIA", "tables": [
            {"table": "MEDIA_FILES", "file": "VYRALX_MEDIA/MEDIA_FILES.jsonl.gz",
             "sha256": _sha(media_dump), "row_count": 1}]}],
    }))
    merged = backup_mod.finalize_unified_set(set_dir, bundle, merge_from=media_set,
                                             log=lambda *a: None)
    assert merged["complete"] is True
    agents = {e["agent"] for e in merged["agents"]}
    assert agents == {"MEMORA", "VYRALX_MEDIA"}
    assert merged["fleet_state"]["complete"] is True
    assert (set_dir / "fleet-state" / "files" / "server4" / "opt" / "friday_universe"
            / "Stratex" / "state" / "forward_scorecard.json").is_file()
    ok, failed = backup_mod.verify_backup(set_dir, merged, log=lambda *a: None)
    assert failed == 0 and ok >= 3
