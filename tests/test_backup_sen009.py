"""TASK-SEN-009 — backup repair tests.

Covers the SEN-009 changes to scripts/backup_fleet_databases.py (per-agent
.env snapshot, manifest completeness, successful-run retention, media
failures counting as failures, --media-only) and the freshness checker
scripts/check_backup_freshness.py. No live database: backup_agent is
stubbed and all state lives in tmp dirs.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import sys
import types
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[1]


def _load(name: str, rel: str):
    spec = importlib.util.spec_from_file_location(name, _ROOT / rel)
    mod = importlib.util.module_from_spec(spec)
    sys.modules.setdefault(name, mod)
    spec.loader.exec_module(mod)
    return mod


backup_mod = _load("backup_fleet_databases", "scripts/backup_fleet_databases.py")
fresh_mod = _load("check_backup_freshness", "scripts/check_backup_freshness.py")


def _write_manifest(dir_path: Path, manifest: dict) -> Path:
    dir_path.mkdir(parents=True, exist_ok=True)
    (dir_path / "manifest.json").write_text(json.dumps(manifest))
    return dir_path


def _one_table(agent: str) -> dict:
    return {"agent": agent, "tables": [{"table": "T1", "row_count": 1}]}


def _stub_entry(agent: str, out_dir: Path) -> dict:
    """A stub backup_agent entry that satisfies the real verify pass.

    TASK-SEN-022: run() now verifies the files a dump claims, so a stub
    entry must name a real file with a matching checksum — an entry
    with a table but no file is not a dump, it is a KeyError.
    """
    data = b"row\n"
    agent_dir = out_dir / agent
    agent_dir.mkdir(parents=True, exist_ok=True)
    (agent_dir / "T1.jsonl.gz").write_bytes(data)
    return {"agent": agent, "schema": agent,
            "tables": [{"table": "T1", "row_count": 1,
                        "sha256": hashlib.sha256(data).hexdigest(),
                        "file": f"{agent}/T1.jsonl.gz"}]}


def _complete_manifest(ts: str) -> dict:
    # A realistic complete manifest: all ten fleet agents, one table each.
    # TASK-SEN-022: the freshness check requires full-fleet coverage by
    # default, so the fixture must carry the full agent list.
    return {"created_at": ts,
            "agents": [_one_table(a) for a in backup_mod.ALL_AGENTS],
            "failed_agents": [],
            "verify": {"ok": 3, "failed": 0}, "complete": True}


def _incomplete_manifest(ts: str) -> dict:
    return {"created_at": ts, "agents": [], "failed_agents": ["MEMORA"],
            "verify": {"ok": 1, "failed": 0}, "complete": False}


class TestAgentEnvSnapshot:
    def test_copies_only_existing_envs_with_600_and_no_value_leak(self, tmp_path):
        repo = tmp_path / "repo"
        (repo / "FRIDAY").mkdir(parents=True)
        (repo / "FRIDAY" / ".env").write_text("FRIDAY_DATABASE_URL=oracle://x:SECRETVAL@dsn\n")
        (repo / "Memora").mkdir(parents=True)
        (repo / "Memora" / ".env").write_text("MEMORA_DATABASE_URL=oracle://y:SECRETVAL2@dsn\n")
        (repo / "VyralX").mkdir(parents=True)
        (repo / "VyralX" / ".env").write_text("VYRALX_DATABASE_URL=oracle://z:SECRETVAL3@dsn\n")
        dest = tmp_path / "backup"
        dest.mkdir()
        logs: list[str] = []
        copied = backup_mod.snapshot_agent_envs(dest, repo_root=repo, log=logs.append)
        # FRIDAY + Memora + VyralX (VYRALX_MEDIA shares the VyralX dir -> once)
        assert len(copied) == 3
        for path in copied:
            assert os.stat(path).st_mode & 0o777 == 0o600
        assert (dest / "configs" / "agent-env" / "FRIDAY" / ".env").is_file()
        assert (dest / "configs" / "agent-env" / "VyralX" / ".env").is_file()
        # secret values must never reach the log or the returned manifest data
        assert not any("SECRETVAL" in line for line in logs)
        assert not any("SECRETVAL" in path for path in copied)

    def test_missing_envs_are_skipped(self, tmp_path):
        dest = tmp_path / "backup"
        dest.mkdir()
        copied = backup_mod.snapshot_agent_envs(
            dest, repo_root=tmp_path / "empty-repo", log=lambda *a: None)
        assert copied == []


class TestCompleteness:
    def test_explicit_flag(self, tmp_path):
        # TASK-SEN-022: a bare flag is a claim, not proof — without a
        # verify block and dumped tables it does not count as complete.
        d = _write_manifest(tmp_path / "a", {"complete": True})
        assert backup_mod.backup_completeness(d) is False
        d = _write_manifest(tmp_path / "b", {"complete": False})
        assert backup_mod.backup_completeness(d) is False
        # Flag + contents that agree: complete.
        d = _write_manifest(tmp_path / "c", _complete_manifest("2026-11-15T10:00:00Z"))
        assert backup_mod.backup_completeness(d) is True
        # Flag + contents that disagree: the contents win.
        manifest = _complete_manifest("2026-11-15T10:00:00Z")
        manifest["failed_agents"] = ["MEMORA"]
        d = _write_manifest(tmp_path / "d", manifest)
        assert backup_mod.backup_completeness(d) is False

    def test_legacy_manifest_derivation(self, tmp_path):
        d = _write_manifest(tmp_path / "a", {"failed_agents": [],
                                             "verify": {"failed": 0}})
        assert backup_mod.backup_completeness(d) is True
        d = _write_manifest(tmp_path / "b", {"failed_agents": ["MEMORA"],
                                             "verify": {"failed": 0}})
        assert backup_mod.backup_completeness(d) is False
        d = _write_manifest(tmp_path / "c", {"failed_agents": []})  # no verify block
        assert backup_mod.backup_completeness(d) is False

    def test_unjudgeable(self, tmp_path):
        d = tmp_path / "a"
        d.mkdir()
        assert backup_mod.backup_completeness(d) is None
        (d / "manifest.json").write_text("{not json")
        assert backup_mod.backup_completeness(d) is None


class TestPruneRetention:
    def test_keeps_newest_complete_and_prunes_older_complete(self, tmp_path):
        for i in range(5):
            _write_manifest(tmp_path / f"2026111{i}T000000Z",
                            _complete_manifest(f"2026-11-1{i}T00:00:00Z"))
        backup_mod.prune_old_backups(tmp_path, keep=4, log=lambda *a: None)
        remaining = sorted(d.name for d in tmp_path.iterdir())
        assert remaining == [f"2026111{i}T000000Z" for i in (1, 2, 3, 4)]

    def test_one_bad_run_cannot_evict_the_last_good_copy(self, tmp_path):
        for i in range(4):
            _write_manifest(tmp_path / f"2026110{i}T000000Z",
                            _complete_manifest(f"2026-11-0{i}T00:00:00Z"))
        _write_manifest(tmp_path / "20261109T000000Z",
                        _incomplete_manifest("2026-11-09T00:00:00Z"))
        backup_mod.prune_old_backups(tmp_path, keep=4, log=lambda *a: None)
        remaining = sorted(d.name for d in tmp_path.iterdir())
        # all four good backups survive; the newer failed attempt is kept
        # as the forensic record of the latest attempt
        assert remaining == [f"2026110{i}T000000Z" for i in range(4)] + ["20261109T000000Z"]

    def test_superseded_incomplete_backups_are_pruned(self, tmp_path):
        _write_manifest(tmp_path / "20261101T000000Z",
                        _incomplete_manifest("2026-11-01T00:00:00Z"))
        _write_manifest(tmp_path / "20261102T000000Z",
                        _incomplete_manifest("2026-11-02T00:00:00Z"))
        _write_manifest(tmp_path / "20261103T000000Z",
                        _complete_manifest("2026-11-03T00:00:00Z"))
        backup_mod.prune_old_backups(tmp_path, keep=4, log=lambda *a: None)
        remaining = sorted(d.name for d in tmp_path.iterdir())
        assert remaining == ["20261103T000000Z"]

    def test_unjudgeable_dirs_keep_legacy_behaviour(self, tmp_path):
        for i in range(4):
            (tmp_path / f"20261110T00000{i}Z").mkdir()
        backup_mod.prune_old_backups(tmp_path, keep=2, log=lambda *a: None)
        remaining = sorted(d.name for d in tmp_path.iterdir())
        assert remaining == ["20261110T000002Z", "20261110T000003Z"]


def _run_args(tmp_path, **overrides):
    args = types.SimpleNamespace(
        agents="", media=False, media_only=False, verify=False, from_dir="",
        out=str(tmp_path / "backups"), dry_run=False, env_file="",
        no_configs=True, keep=0)
    for key, value in overrides.items():
        setattr(args, key, value)
    return args


class TestRunBehaviour:
    def test_media_failure_is_counted_not_skipped(self, tmp_path, monkeypatch):
        calls: list[str] = []

        def stub(agent, out_dir, **kwargs):
            calls.append(agent)
            if agent == backup_mod.MEDIA_SCHEMA:
                raise backup_mod.OracleConfigError("no media credentials here")
            return _stub_entry(agent, out_dir)

        monkeypatch.setattr(backup_mod, "backup_agent", stub)
        rc = backup_mod.run(_run_args(tmp_path, agents="FRIDAY", media=True),
                            log=lambda *a: None)
        assert rc == 1
        manifests = list((tmp_path / "backups").glob("*/manifest.json"))
        assert len(manifests) == 1
        manifest = json.loads(manifests[0].read_text())
        assert manifest["failed_agents"] == [backup_mod.MEDIA_SCHEMA]
        assert manifest["complete"] is False

    def test_media_only_attempts_no_agent_schemas(self, tmp_path, monkeypatch):
        calls: list[str] = []

        def stub(agent, out_dir, **kwargs):
            calls.append(agent)
            return _stub_entry(agent, out_dir)

        monkeypatch.setattr(backup_mod, "backup_agent", stub)
        rc = backup_mod.run(_run_args(tmp_path, media_only=True), log=lambda *a: None)
        assert rc == 0
        assert calls == [backup_mod.MEDIA_SCHEMA]
        manifests = list((tmp_path / "backups").glob("*/manifest.json"))
        manifest = json.loads(manifests[0].read_text())
        assert manifest["complete"] is True

    def test_all_agents_success_marks_complete(self, tmp_path, monkeypatch):
        def stub(agent, out_dir, **kwargs):
            return _stub_entry(agent, out_dir)

        monkeypatch.setattr(backup_mod, "backup_agent", stub)
        rc = backup_mod.run(_run_args(tmp_path, agents="FRIDAY,MEMORA"),
                            log=lambda *a: None)
        assert rc == 0
        manifests = list((tmp_path / "backups").glob("*/manifest.json"))
        manifest = json.loads(manifests[0].read_text())
        assert manifest["complete"] is True
        assert manifest["failed_agents"] == []


class TestFreshness:
    def _root_with(self, tmp_path, entries):
        root = tmp_path / "backups"
        root.mkdir()
        for name, manifest in entries:
            _write_manifest(root / name, manifest)
        return root

    def test_fresh_backup_is_ok(self, tmp_path):
        import datetime as dt
        now = dt.datetime(2026, 11, 15, 12, 0, tzinfo=dt.timezone.utc)
        root = self._root_with(tmp_path, [
            ("20261115T100000Z", _complete_manifest("2026-11-15T10:00:00Z"))])
        report = fresh_mod.assess(root, now=now, max_age_hours=120)
        assert report["status"] == "ok"
        assert report["age_hours"] == 2.0
        assert report["complete_backups"] == 1
        assert report["latest_attempt_complete"] is True

    def test_old_backup_is_stale(self, tmp_path):
        import datetime as dt
        now = dt.datetime(2026, 11, 15, 12, 0, tzinfo=dt.timezone.utc)
        root = self._root_with(tmp_path, [
            ("20261101T000000Z", _complete_manifest("2026-11-01T00:00:00Z"))])
        report = fresh_mod.assess(root, now=now, max_age_hours=120)
        assert report["status"] == "stale"
        assert report["age_hours"] > 120

    def test_no_complete_backup_is_never(self, tmp_path):
        root = self._root_with(tmp_path, [
            ("20261110T143601Z", _incomplete_manifest("2026-11-10T14:36:01Z")),
            ("20261110T144336Z", _incomplete_manifest("2026-11-10T14:43:36Z"))])
        report = fresh_mod.assess(root, max_age_hours=120)
        assert report["status"] == "never"
        assert report["last_success_at"] is None
        assert report["latest_attempt_complete"] is False
        assert report["complete_backups"] == 0

    def test_missing_root_is_never(self, tmp_path):
        report = fresh_mod.assess(tmp_path / "does-not-exist")
        assert report["status"] == "never"
