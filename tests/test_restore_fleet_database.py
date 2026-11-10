"""TASK-INF-003 — restore / drill logic tests (fake oracledb connection)."""
from __future__ import annotations

import gzip
import importlib.util
import json
import sys
from pathlib import Path

import pytest

_SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "restore_fleet_database.py"
_spec = importlib.util.spec_from_file_location("restore_fleet_database", _SCRIPT)
restore_mod = importlib.util.module_from_spec(_spec)
sys.modules.setdefault("restore_fleet_database", restore_mod)
_spec.loader.exec_module(restore_mod)


class FakeCursor:
    def __init__(self, conn):
        self.conn = conn

    def execute(self, sql, params=None, **kwargs):
        if sql.startswith("SELECT COUNT(*)"):
            table = sql.split('"')[1]
            self.result = self.conn.rowcounts.get(table, 0)
        elif sql.startswith("SELECT table_name"):
            self.result = list(self.conn.rowcounts.keys())
        elif sql.startswith("SELECT SYS_CONTEXT") or sql.startswith("SELECT USER"):
            self.result = "MEMORA"
        elif sql.startswith("INSERT"):
            table = sql.split('"')[1]
            self.conn.inserted.setdefault(table, 0)
            self.conn.inserted[table] += 1
            self.conn.insert_log.append((table, params))
        elif sql.startswith("TRUNCATE"):
            table = sql.split('"')[1]
            self.conn.rowcounts[table] = 0
            self.conn.truncated.append(table)
        else:
            self.result = None

    def fetchone(self):
        return (self.result,)

    def fetchall(self):
        return [(r,) for r in self.result]

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class FakeConn:
    def __init__(self, rowcounts):
        self.rowcounts = dict(rowcounts)
        self.inserted = {}
        self.insert_log = []
        self.truncated = []

    def cursor(self):
        return FakeCursor(self)

    def commit(self):
        pass

    def rollback(self):
        pass

    def close(self):
        pass


def make_backup(tmp_path, tables):
    """Write a backup layout with one gz table file per entry; return manifest entry."""
    entries = []
    for name, rows in tables.items():
        rel = f"{name}.jsonl.gz"
        with gzip.open(tmp_path / rel, "wt") as fh:
            for row in rows:
                fh.write(json.dumps(row) + "\n")
        entries.append({"table": name, "row_count": len(rows), "sha256": "x", "file": rel, "columns": 2})
    return {"agent": "MEMORA", "schema": "MEMORA", "tables": entries, "dumped_at": "2026-11-10T00:00:00Z"}


@pytest.fixture()
def backup_dir(tmp_path):
    (tmp_path / "manifest.json").write_text(json.dumps({"agents": []}))
    return tmp_path


class TestLoadManifest:
    def test_missing_manifest_aborts(self, tmp_path):
        with pytest.raises(SystemExit):
            restore_mod.load_manifest(tmp_path, "MEMORA")

    def test_agent_entry_resolution(self, tmp_path):
        entry = {"agent": "MEMORA", "tables": []}
        (tmp_path / "manifest.json").write_text(json.dumps({"agents": [entry]}))
        assert restore_mod.load_manifest(tmp_path, "memora") == entry
        assert restore_mod.load_manifest(tmp_path, "FRIDAY") is None


class TestCompareDrill:
    def test_matching_counts_report_ok(self):
        conn = FakeConn({"MEMORIES": 3, "TASKS": 1})
        entry = {"agent": "MEMORA", "tables": [
            {"table": "MEMORIES", "row_count": 3}, {"table": "TASKS", "row_count": 1}]}
        rep = restore_mod.compare_to_live(conn, entry, log=lambda *a: None)
        assert rep["match"] == 2 and rep["differ"] == [] and rep["missing_in_live"] == []

    def test_drift_is_reported(self):
        conn = FakeConn({"MEMORIES": 5})
        entry = {"agent": "MEMORA", "tables": [{"table": "MEMORIES", "row_count": 3}]}
        rep = restore_mod.compare_to_live(conn, entry, log=lambda *a: None)
        assert rep["differ"] == [{"table": "MEMORIES", "backup": 3, "live": 5, "delta": 2}]

    def test_missing_table_in_live_reported(self):
        conn = FakeConn({})
        entry = {"agent": "MEMORA", "tables": [{"table": "MEMORIES", "row_count": 3}]}
        rep = restore_mod.compare_to_live(conn, entry, log=lambda *a: None)
        assert rep["missing_in_live"] == ["MEMORIES"]

    def test_extra_live_tables_listed(self):
        conn = FakeConn({"MEMORIES": 1, "NEW_TABLE": 4})
        entry = {"agent": "MEMORA", "tables": [{"table": "MEMORIES", "row_count": 1}]}
        rep = restore_mod.compare_to_live(conn, entry, log=lambda *a: None)
        assert rep["extra_in_live"] == ["NEW_TABLE"]


class TestApplyGuards:
    def test_refuses_non_empty_without_replace(self, tmp_path):
        entry = make_backup(tmp_path, {"MEMORIES": [{"id": 1}, {"id": 2}]})
        conn = FakeConn({"MEMORIES": 7})
        results = restore_mod.apply_restore(conn, tmp_path, entry, replace=False, log=lambda *a: None)
        assert results["MEMORIES"]["status"] == "REFUSED_NON_EMPTY"
        assert results["MEMORIES"]["live_rows"] == 7
        assert not conn.inserted  # nothing written

    def test_missing_live_table_reported(self, tmp_path):
        entry = make_backup(tmp_path, {"MEMORIES": [{"id": 1}]})
        conn = FakeConn({})
        results = restore_mod.apply_restore(conn, tmp_path, entry, replace=False, log=lambda *a: None)
        assert results["MEMORIES"]["status"] == "MISSING_IN_LIVE"

    def test_apply_into_empty_table_restores_rows(self, tmp_path):
        rows = [{"id": 1, "t": "a"}, {"id": 2, "t": "b"}, {"id": 3, "t": "c"}]
        entry = make_backup(tmp_path, {"MEMORIES": rows})
        conn = FakeConn({"MEMORIES": 0})
        results = restore_mod.apply_restore(conn, tmp_path, entry, replace=False, log=lambda *a: None)
        assert results["MEMORIES"] == {"status": "RESTORED", "rows": 3}
        assert conn.inserted["MEMORIES"] == 3

    def test_replace_truncates_first(self, tmp_path):
        entry = make_backup(tmp_path, {"MEMORIES": [{"id": 9}]})
        conn = FakeConn({"MEMORIES": 42})
        results = restore_mod.apply_restore(conn, tmp_path, entry, replace=True, log=lambda *a: None)
        assert conn.truncated == ["MEMORIES"]
        assert results["MEMORIES"]["status"] == "RESTORED"

    def test_b64_values_round_trip(self, tmp_path):
        import base64
        rel = "B.jsonl.gz"
        with gzip.open(tmp_path / rel, "wt") as fh:
            fh.write(json.dumps({"id": 1, "payload": {"__b64__": base64.b64encode(b"xyz").decode()}}) + "\n")
        entry = {"agent": "MEMORA", "tables": [{"table": "B", "row_count": 1, "sha256": "x", "file": rel, "columns": 2}]}
        out = list(restore_mod.iter_backup_rows(tmp_path, entry["tables"][0]))
        assert out[0]["payload"] == b"xyz"
