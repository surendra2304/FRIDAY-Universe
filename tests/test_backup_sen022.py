"""TASK-SEN-022 — manifest completeness inside the backup success criteria.

Covers the SEN-022 changes to scripts/backup_fleet_databases.py (the
manifest records what was requested; a zero-table dump is a failure;
--verify judges the manifest's completeness, not just its files; the
newest backup is the --verify default) and to
scripts/check_backup_freshness.py (the flag is audited against the
manifest's contents; a subset run cannot reset the fleet freshness
clock). No live database: backup_agent is stubbed and all state lives
in tmp dirs.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
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


def _table(agent: str, table: str = "T1", rows: int = 1) -> dict:
    return {"agent": agent, "tables": [{"table": table, "row_count": rows}]}


def _stub_entry(agent: str, out_dir: Path) -> dict:
    """A stub backup_agent entry that satisfies the real verify pass."""
    data = b"row\n"
    agent_dir = out_dir / agent
    agent_dir.mkdir(parents=True, exist_ok=True)
    (agent_dir / "T1.jsonl.gz").write_bytes(data)
    return {"agent": agent, "schema": agent,
            "tables": [{"table": "T1", "row_count": 1,
                        "sha256": hashlib.sha256(data).hexdigest(),
                        "file": f"{agent}/T1.jsonl.gz"}]}


def _full_manifest(ts: str = "2026-11-22T11:49:29Z", **overrides) -> dict:
    manifest = {
        "created_at": ts,
        "agents": [_table(a) for a in backup_mod.ALL_AGENTS],
        "requested_agents": list(backup_mod.ALL_AGENTS),
        "failed_agents": [],
        "verify": {"ok": 10, "failed": 0},
        "complete": True,
    }
    manifest.update(overrides)
    return manifest


def _write_manifest(dir_path: Path, manifest: dict) -> Path:
    dir_path.mkdir(parents=True, exist_ok=True)
    (dir_path / "manifest.json").write_text(json.dumps(manifest))
    return dir_path


def _write_dumped_backup(dir_path: Path, manifest: dict) -> Path:
    """A backup dir whose table files exist with matching checksums."""
    dir_path.mkdir(parents=True, exist_ok=True)
    for agent_entry in manifest.get("agents", []):
        for table_entry in agent_entry.get("tables", []):
            target = dir_path / table_entry["file"]
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(b"row\n")
            table_entry["sha256"] = hashlib.sha256(b"row\n").hexdigest()
    manifest.setdefault("configs", [])
    manifest.setdefault("agent_envs", [])
    (dir_path / "manifest.json").write_text(json.dumps(manifest))
    return dir_path


def _run_args(tmp_path, **overrides):
    args = types.SimpleNamespace(
        agents="", media=False, media_only=False, verify=False, from_dir="",
        out=str(tmp_path / "backups"), dry_run=False, env_file="",
        no_configs=True, keep=0)
    for key, value in overrides.items():
        setattr(args, key, value)
    return args


class TestDeriveManifestComplete:
    def test_full_manifest_is_complete(self):
        complete, reasons = backup_mod.derive_manifest_complete(_full_manifest())
        assert complete is True
        assert reasons == []

    def test_flag_false_is_never_overruled(self):
        manifest = _full_manifest(complete=False)
        complete, reasons = backup_mod.derive_manifest_complete(manifest)
        assert complete is False
        assert any("flag" in r for r in reasons)

    def test_failed_agent_fails(self):
        manifest = _full_manifest(failed_agents=["MEMORA"])
        complete, reasons = backup_mod.derive_manifest_complete(manifest)
        assert complete is False
        assert any("MEMORA" in r for r in reasons)

    def test_dirty_verify_fails(self):
        manifest = _full_manifest(verify={"ok": 9, "failed": 1})
        complete, _ = backup_mod.derive_manifest_complete(manifest)
        assert complete is False

    def test_missing_verify_block_fails(self):
        manifest = _full_manifest()
        del manifest["verify"]
        complete, reasons = backup_mod.derive_manifest_complete(manifest)
        assert complete is False
        assert any("verify" in r for r in reasons)

    def test_missing_requested_agent_fails(self):
        manifest = _full_manifest()
        manifest["agents"] = [e for e in manifest["agents"] if e["agent"] != "MEMORA"]
        complete, reasons = backup_mod.derive_manifest_complete(manifest)
        assert complete is False
        assert any("MEMORA" in r for r in reasons)

    def test_zero_table_dump_fails(self):
        manifest = _full_manifest()
        manifest["agents"][0]["tables"] = []
        complete, reasons = backup_mod.derive_manifest_complete(manifest)
        assert complete is False
        assert any("0 tables" in r for r in reasons)

    def test_zero_rows_are_not_a_failure(self):
        # A live-empty schema (STRATEX holds 0 rows in production today)
        # is still a real backup: tables present, rows zero.
        manifest = _full_manifest()
        for entry in manifest["agents"]:
            for table in entry["tables"]:
                table["row_count"] = 0
        complete, _ = backup_mod.derive_manifest_complete(manifest)
        assert complete is True

    def test_legacy_manifest_without_flag_derives(self):
        manifest = {"failed_agents": [], "verify": {"failed": 0},
                    "agents": [_table("FRIDAY")]}
        complete, _ = backup_mod.derive_manifest_complete(manifest)
        assert complete is True

    def test_live_verify_count_overrides_missing_block(self):
        # --verify re-checks the files itself: a live clean count stands
        # in for the manifest's own (absent) verify block.
        manifest = _full_manifest()
        del manifest["verify"]
        complete, _ = backup_mod.derive_manifest_complete(
            manifest, live_verify_failed=0)
        assert complete is True
        complete, _ = backup_mod.derive_manifest_complete(
            manifest, live_verify_failed=2)
        assert complete is False


class TestRunRecordsScope:
    def test_full_run_records_all_requested_agents(self, tmp_path, monkeypatch):
        def stub(agent, out_dir, **kwargs):
            return _stub_entry(agent, out_dir)

        monkeypatch.setattr(backup_mod, "backup_agent", stub)
        rc = backup_mod.run(_run_args(tmp_path), log=lambda *a: None)
        assert rc == 0
        manifests = list((tmp_path / "backups").glob("*/manifest.json"))
        manifest = json.loads(manifests[0].read_text())
        assert manifest["requested_agents"] == list(backup_mod.ALL_AGENTS)
        assert manifest["complete"] is True

    def test_subset_run_is_honest_about_scope(self, tmp_path, monkeypatch):
        def stub(agent, out_dir, **kwargs):
            return _stub_entry(agent, out_dir)

        monkeypatch.setattr(backup_mod, "backup_agent", stub)
        rc = backup_mod.run(_run_args(tmp_path, agents="FRIDAY,MEMORA"),
                            log=lambda *a: None)
        assert rc == 0
        manifests = list((tmp_path / "backups").glob("*/manifest.json"))
        manifest = json.loads(manifests[0].read_text())
        # The run completed what it was asked — and says so.
        assert manifest["requested_agents"] == ["FRIDAY", "MEMORA"]
        assert manifest["complete"] is True

    def test_media_only_records_media_scope(self, tmp_path, monkeypatch):
        def stub(agent, out_dir, **kwargs):
            return _stub_entry(agent, out_dir)

        monkeypatch.setattr(backup_mod, "backup_agent", stub)
        rc = backup_mod.run(_run_args(tmp_path, media_only=True),
                            log=lambda *a: None)
        assert rc == 0
        manifests = list((tmp_path / "backups").glob("*/manifest.json"))
        manifest = json.loads(manifests[0].read_text())
        assert manifest["requested_agents"] == [backup_mod.MEDIA_SCHEMA]

    def test_zero_table_dump_is_a_failure(self, tmp_path, monkeypatch):
        calls: list[str] = []

        def stub(agent, out_dir, **kwargs):
            calls.append(agent)
            if agent == "MEMORA":
                # Resolved to an empty schema: no exception, no tables.
                return {"agent": agent, "schema": agent, "tables": []}
            return _stub_entry(agent, out_dir)

        monkeypatch.setattr(backup_mod, "backup_agent", stub)
        logs: list[str] = []
        rc = backup_mod.run(_run_args(tmp_path, agents="FRIDAY,MEMORA"),
                            log=lambda *a: logs.append(" ".join(map(str, a))))
        assert rc == 1
        manifests = list((tmp_path / "backups").glob("*/manifest.json"))
        manifest = json.loads(manifests[0].read_text())
        assert manifest["failed_agents"] == ["MEMORA"]
        assert manifest["complete"] is False
        assert any("MEMORA" in line and "0 tables" in line for line in logs)
        assert any("INCOMPLETE" in line for line in logs)


class TestVerifyJudgesCompleteness:
    def _verify_args(self, tmp_path, **overrides):
        return _run_args(tmp_path, verify=True, **overrides)

    def test_verify_passes_for_complete_backup(self, tmp_path):
        manifest = _full_manifest()
        for entry in manifest["agents"]:
            for table in entry["tables"]:
                table["file"] = f"{entry['agent']}/T1.jsonl.gz"
        backup_dir = _write_dumped_backup(tmp_path / "backups" / "20261122T114929Z", manifest)
        rc = backup_mod.run(self._verify_args(tmp_path, from_dir=str(backup_dir)),
                            log=lambda *a: None)
        assert rc == 0

    def test_verify_fails_for_incomplete_manifest(self, tmp_path):
        manifest = _full_manifest(failed_agents=["MEMORA"], complete=False)
        for entry in manifest["agents"]:
            for table in entry["tables"]:
                table["file"] = f"{entry['agent']}/T1.jsonl.gz"
        backup_dir = _write_dumped_backup(tmp_path / "backups" / "20261122T114929Z", manifest)
        logs: list[str] = []
        rc = backup_mod.run(self._verify_args(tmp_path, from_dir=str(backup_dir)),
                            log=lambda *a: logs.append(" ".join(map(str, a))))
        assert rc == 1
        # The files are all intact — the failure is the manifest, said loudly.
        assert any("manifest incomplete" in line for line in logs)
        assert any("MEMORA" in line for line in logs)

    def test_verify_fails_when_flag_lies(self, tmp_path):
        # Flag says complete; the contents say an agent is missing.
        manifest = _full_manifest()
        manifest["agents"] = [e for e in manifest["agents"] if e["agent"] != "CORTEX"]
        for entry in manifest["agents"]:
            for table in entry["tables"]:
                table["file"] = f"{entry['agent']}/T1.jsonl.gz"
        backup_dir = _write_dumped_backup(tmp_path / "backups" / "20261122T114929Z", manifest)
        logs: list[str] = []
        rc = backup_mod.run(self._verify_args(tmp_path, from_dir=str(backup_dir)),
                            log=lambda *a: logs.append(" ".join(map(str, a))))
        assert rc == 1
        assert any("disagrees" in line for line in logs)

    def test_verify_defaults_to_newest_backup(self, tmp_path):
        old = _full_manifest(ts="2026-11-18T17:37:01Z")
        new = _full_manifest(ts="2026-11-22T11:49:29Z")
        for manifest, name in ((old, "20261118T173701Z"), (new, "20261122T171929Z")):
            for entry in manifest["agents"]:
                for table in entry["tables"]:
                    table["file"] = f"{entry['agent']}/T1.jsonl.gz"
            _write_dumped_backup(tmp_path / "backups" / name, manifest)
        # No --from-dir: the newest backup is verified (and its summary names it).
        logs: list[str] = []
        rc = backup_mod.run(self._verify_args(tmp_path),
                            log=lambda *a: logs.append(" ".join(map(str, a))))
        assert rc == 0
        assert any("20261122T171929Z" in line for line in logs)

    def test_verify_aborts_when_no_backup_exists(self, tmp_path):
        rc = backup_mod.run(self._verify_args(tmp_path), log=lambda *a: None)
        assert rc == 2


class TestFreshnessScope:
    def test_subset_run_does_not_reset_the_clock(self, tmp_path):
        import datetime as dt
        now = dt.datetime(2026, 11, 22, 12, 0, tzinfo=dt.UTC)
        root = tmp_path / "backups"
        manifest = _full_manifest(ts="2026-11-22T11:49:29Z")
        manifest["agents"] = [_table("FRIDAY")]
        manifest["requested_agents"] = ["FRIDAY"]
        _write_manifest(root / "20261122T114929Z", manifest)
        report = fresh_mod.assess(root, now=now, max_age_hours=120)
        assert report["status"] == "never"
        assert report["complete_backups"] == 0
        assert report["latest_attempt_complete"] is False

    def test_explicit_scope_requirement_is_honoured(self, tmp_path):
        import datetime as dt
        now = dt.datetime(2026, 11, 22, 12, 0, tzinfo=dt.UTC)
        root = tmp_path / "backups"
        manifest = _full_manifest(ts="2026-11-22T11:49:29Z")
        manifest["agents"] = [_table("FRIDAY")]
        manifest["requested_agents"] = ["FRIDAY"]
        _write_manifest(root / "20261122T114929Z", manifest)
        # Judged as a single-agent root, the same manifest is a success.
        report = fresh_mod.assess(root, now=now, max_age_hours=120,
                                  require_agents=("FRIDAY",))
        assert report["status"] == "ok"

    def test_flag_true_with_failed_agent_is_not_complete(self, tmp_path):
        manifest = _full_manifest(failed_agents=["MEMORA"])
        assert fresh_mod.manifest_completeness(manifest) is False


class TestReaderWriterAgreement:
    @pytest.mark.parametrize("mutate", [
        lambda m: None,
        lambda m: m.update(failed_agents=["MEMORA"]),
        lambda m: m.update(verify={"ok": 0, "failed": 3}),
        lambda m: m.update(complete=False),
        lambda m: m["agents"].__setitem__(0, _table(m["agents"][0]["agent"], rows=0)),
        lambda m: m["agents"].__setitem__(0, {"agent": m["agents"][0]["agent"], "tables": []}),
        lambda m: m.update(requested_agents=list(backup_mod.ALL_AGENTS) + ["NOPE"]),
    ])
    def test_derive_and_freshness_agree(self, mutate):
        manifest = _full_manifest()
        mutate(manifest)
        derived, _ = backup_mod.derive_manifest_complete(manifest)
        assert fresh_mod.manifest_completeness(manifest, require_agents=None) is derived
