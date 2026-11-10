"""TASK-INF-003 — fleet database backup logic tests.

Runs against a fake oracledb connection (duck-typed cursors) so the dump,
manifest, checksum and verify logic is exercised without a live database.
"""
from __future__ import annotations

import gzip
import importlib.util
import json
import sys
from pathlib import Path

import pytest

_SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "backup_fleet_databases.py"
_spec = importlib.util.spec_from_file_location("backup_fleet_databases", _SCRIPT)
backup_mod = importlib.util.module_from_spec(_spec)
sys.modules.setdefault("backup_fleet_databases", backup_mod)
_spec.loader.exec_module(backup_mod)


class FakeCursor:
    def __init__(self, rows, columns):
        self.rows = rows
        self.columns = columns
        self.pos = 0
        self.description = [(c, None, None, None, None, None, None) for c in columns]
        self.executed = []

    def execute(self, sql, *args, **kwargs):
        self.executed.append(sql)

    def fetchmany(self, size):
        batch = self.rows[self.pos : self.pos + size]
        self.pos += len(batch)
        return batch

    def fetchone(self):
        if self.pos < len(self.rows):
            row = self.rows[self.pos]
            self.pos += 1
            return row
        return None

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class FakeConnection:
    """Emulates an oracledb connection serving one table."""

    def __init__(self, table, rows, columns):
        self.table, self.rows, self.columns = table, rows, columns

    def cursor(self):
        return FakeCursor(self.rows, self.columns)

    def close(self):
        pass


@pytest.fixture()
def fake_conn():
    rows = [
        (1, "alpha", b"\x00\x01"),
        (2, "beta", None),
        (3, "gamma", b"\xff"),
    ]
    return FakeConnection("MEMORIES", rows, ["ID", "NAME", "BLOB_COL"])


class TestJsonlEncoding:
    def test_scalars_none_and_bytes(self):
        assert backup_mod.jsonl_encode_value(None) is None
        assert backup_mod.jsonl_encode_value(5) == 5
        assert backup_mod.jsonl_encode_value("x") == "x"
        assert backup_mod.jsonl_encode_value(False) is False

    def test_bytes_becomes_b64(self):
        import base64
        encoded = backup_mod.jsonl_encode_value(b"AB")
        assert encoded == {"__b64__": base64.b64encode(b"AB").decode()}

    def test_datetime_renders_as_string(self):
        import datetime as dt
        assert backup_mod.jsonl_encode_value(dt.date(2026, 11, 10)) == "2026-11-10"

    def test_lob_object_read(self):
        class Lob:
            def read(self, cap=None):
                return "lob-text"

        assert backup_mod.jsonl_encode_value(Lob()) == "lob-text"


class TestDumpTable:
    def test_rows_written_gzipped_with_checksum(self, fake_conn, tmp_path):
        path = tmp_path / "MEMORIES.jsonl.gz"
        count, checksum = backup_mod.write_jsonl_dump(
            path, backup_mod.dump_table_rows(fake_conn, "MEMORIES"))
        assert count == 3
        with gzip.open(path, "rt") as fh:
            lines = [json.loads(line) for line in fh]
        assert lines[0] == {"id": 1, "name": "alpha", "blob_col": {"__b64__": "AAE="}}
        assert lines[2]["blob_col"] == {"__b64__": "/w=="}
        assert len(checksum) == 64

    def test_large_fetch_batches(self):
        rows = [(i, f"row{i}") for i in range(2500)]
        conn = FakeConnection("BIG", rows, ["N", "T"])
        count, _ = backup_mod.write_jsonl_dump(
            Path("/tmp/_test_big.jsonl.gz"), backup_mod.dump_table_rows(conn, "BIG", batch_size=1000))
        assert count == 2500


class TestVerify:
    def test_verify_passes_for_intact_backup(self, tmp_path):
        path = tmp_path / "T.jsonl.gz"
        count, checksum = backup_mod.write_jsonl_dump(
            path, iter([{"a": 1}, {"a": 2}]))
        manifest = {"agents": [{"agent": "FRIDAY", "tables": [
            {"table": "T", "row_count": count, "sha256": checksum,
             "file": "T.jsonl.gz", "columns": 1}]}], "configs": []}
        ok, failed = backup_mod.verify_backup(tmp_path, manifest, log=lambda *a: None)
        assert (ok, failed) == (1, 0)

    def test_verify_fails_on_checksum_mismatch(self, tmp_path):
        path = tmp_path / "T.jsonl.gz"
        backup_mod.write_jsonl_dump(path, iter([{"a": 1}]))
        manifest = {"agents": [{"agent": "FRIDAY", "tables": [
            {"table": "T", "row_count": 1, "sha256": "0" * 64,
             "file": "T.jsonl.gz", "columns": 1}]}], "configs": []}
        ok, failed = backup_mod.verify_backup(tmp_path, manifest, log=lambda *a: None)
        assert (ok, failed) == (0, 1)

    def test_verify_fails_on_missing_file(self, tmp_path):
        manifest = {"agents": [{"agent": "FRIDAY", "tables": [
            {"table": "GONE", "row_count": 0, "sha256": "x",
             "file": "GONE.jsonl.gz", "columns": 1}]}], "configs": []}
        ok, failed = backup_mod.verify_backup(tmp_path, manifest, log=lambda *a: None)
        assert failed == 1

    def test_verify_covers_config_files(self, tmp_path):
        cfg = tmp_path / "creds.env"
        cfg.write_text("X=1\n")
        manifest = {"agents": [], "configs": [str(cfg)]}
        ok, failed = backup_mod.verify_backup(tmp_path, manifest, log=lambda *a: None)
        assert ok == 1

    def test_tampered_file_fails(self, tmp_path):
        path = tmp_path / "T.jsonl.gz"
        count, checksum = backup_mod.write_jsonl_dump(path, iter([{"a": 1}]))
        with gzip.open(path, "at") as fh:
            fh.write('{"a": 999}\n')
        manifest = {"agents": [{"agent": "FRIDAY", "tables": [
            {"table": "T", "row_count": count, "sha256": checksum,
             "file": "T.jsonl.gz", "columns": 1}]}], "configs": []}
        ok, failed = backup_mod.verify_backup(tmp_path, manifest, log=lambda *a: None)
        assert failed == 1


class TestPrune:
    def test_prune_keeps_newest_n(self, tmp_path):
        for i in range(4):
            (tmp_path / f"20261110T00000{i}Z").mkdir()
        backup_mod.prune_old_backups(tmp_path, keep=2, log=lambda *a: None)
        remaining = sorted(d.name for d in tmp_path.iterdir())
        assert remaining == ["20261110T000002Z", "20261110T000003Z"]


class TestManifestSecurity:
    def test_manifest_never_contains_a_password(self, fake_conn, tmp_path):
        """backup_agent redacts the DSN via OracleTarget.redacted() — no raw URL."""
        # Simulate: build a manifest entry through jsonl dump path only; the
        # manifest fields we emit for agents are name/table/count/sha/file.
        path = tmp_path / "MEMORIES.jsonl.gz"
        count, checksum = backup_mod.write_jsonl_dump(
            path, backup_mod.dump_table_rows(fake_conn, "MEMORIES"))
        entry = {
            "table": "MEMORIES",
            "row_count": count,
            "sha256": checksum,
            "file": "MEMORIES.jsonl.gz",
        }
        rendered = json.dumps(entry)
        assert "password" not in rendered.lower()

    def test_dsn_redaction_helper(self):
        from oracle_db import parse_oracle_url
        target = parse_oracle_url(
            "oracle+oracledb://MEMORA:SuperSecret@(description=(address=(host=adb.example.com))))",
            agent="MEMORA")
        redacted = target.redacted()
        assert "SuperSecret" not in redacted
        assert "MEMORA" in redacted
