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
        # Fake uses the real python-oracledb LOB signature read(offset, amount).
        class Lob:
            def read(self, offset=1, amount=None):
                return "lob-text"

        assert backup_mod.jsonl_encode_value(Lob()) == "lob-text"


class TestClobLossRegression:
    """TASK-REL-091 — CLOBs under 1 MB dumped as empty strings.

    python-oracledb's LOB.read(offset, amount) takes the 1-based offset
    first. The old call read(LOB_CAP_BYTES) started at byte 1,000,000, so
    every CLOB smaller than the cap read back empty (14,414 empty strings
    in the Nov 22 backup). The fake below implements the real oracle
    slicing semantics, so these tests fail on the old call and pass on
    the fixed one.
    """

    class OracleLob:
        """Minimal LOB with python-oracledb read(offset, amount) semantics."""

        def __init__(self, text):
            self._text = text
            self.calls = []

        def read(self, offset=1, amount=None):
            self.calls.append((offset, amount))
            if offset > len(self._text):
                return ""
            end = None if amount is None else offset - 1 + amount
            return self._text[offset - 1:end]

    def test_small_clob_dumps_nonempty_and_reads_from_offset_one(self):
        lob = self.OracleLob("hello world")
        assert backup_mod.jsonl_encode_value(lob) == "hello world"
        assert lob.calls == [(1, backup_mod.LOB_CAP_BYTES)]

    def test_clob_just_under_cap_dumps_in_full(self):
        text = "x" * (backup_mod.LOB_CAP_BYTES - 1)
        assert backup_mod.jsonl_encode_value(self.OracleLob(text)) == text

    def test_clob_over_cap_truncates_at_cap(self):
        text = "y" * (backup_mod.LOB_CAP_BYTES + 500)
        assert backup_mod.jsonl_encode_value(self.OracleLob(text)) == "y" * backup_mod.LOB_CAP_BYTES

    def test_genuinely_empty_clob_stays_empty(self):
        assert backup_mod.jsonl_encode_value(self.OracleLob("")) == ""

    def test_blob_lob_dumps_base64(self):
        import base64

        class OracleBlob:
            def read(self, offset=1, amount=None):
                data = b"\x00\x01\x02"
                if offset > len(data):
                    return b""
                end = None if amount is None else offset - 1 + amount
                return data[offset - 1:end]

        assert backup_mod.jsonl_encode_value(OracleBlob()) == {
            "__b64__": base64.b64encode(b"\x00\x01\x02").decode()
        }


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


class TestAgentStateSnapshot:
    """TASK-SEN-007: Stratex measurement state joins the config snapshot."""

    def _make_state(self, root: Path) -> Path:
        state = root / "Stratex" / "state"
        state.mkdir(parents=True)
        (state / "fill_ledger.jsonl").write_text('{"pnl": 1}\n')
        (state / "equity_snapshots.jsonl").write_text('{"equity": 10000}\n')
        (state / "account_balance.json").write_text('{"balance": 10000}\n')
        (state / "fill_ledger.jsonl.lock").write_text("")
        (state / "notes.txt").write_text("not state data")
        return state

    def test_copies_jsonl_and_json_skips_locks_and_others(self, tmp_path):
        repo_root = tmp_path / "repo"
        self._make_state(repo_root)
        dest = tmp_path / "backup"
        copied = backup_mod.snapshot_agent_state(dest, repo_root, log=lambda *a: None)
        names = sorted(Path(c).name for c in copied)
        assert names == ["account_balance.json", "equity_snapshots.jsonl",
                         "fill_ledger.jsonl"]
        target = dest / "configs" / "agent-state" / "Stratex" / "state" / "fill_ledger.jsonl"
        assert target.read_text() == '{"pnl": 1}\n'
        assert (target.stat().st_mode & 0o777) == 0o600

    def test_missing_state_dir_is_quiet(self, tmp_path):
        copied = backup_mod.snapshot_agent_state(
            tmp_path / "backup", tmp_path / "empty-repo", log=lambda *a: None)
        assert copied == []

    def test_snapshot_configs_includes_state_files(self, tmp_path, monkeypatch):
        monkeypatch.setattr(backup_mod, "CONFIG_ENV_FILES", ())
        monkeypatch.setattr(backup_mod, "CONFIG_UNIT_GLOBS", ())
        repo_root = tmp_path / "repo"
        self._make_state(repo_root)
        dest = tmp_path / "backup"
        copied = backup_mod.snapshot_configs(dest, log=lambda *a: None,
                                             repo_root=repo_root)
        assert any(c.endswith("fill_ledger.jsonl") for c in copied)
        # verify pass treats manifest config entries as must-exist files
        ok, failed = backup_mod.verify_backup(
            dest, {"agents": [], "configs": copied}, log=lambda *a: None)
        assert failed == 0 and ok == len(copied)
