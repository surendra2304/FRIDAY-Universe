"""
Unit and regression tests for scripts/backup_postgres_to_oci_object_storage.py.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from backup_postgres_to_oci_object_storage import (
    AGENT_DATABASES,
    create_backup_manifest,
    dump_all_globals,
    dump_database,
    execute_full_backup,
    sha256_file,
    utc_now_iso,
)


def test_agent_databases_list_matches_ten_agent_invariants():
    assert len(AGENT_DATABASES) == 10
    assert "vyralx_db" in AGENT_DATABASES
    assert "friday_db" in AGENT_DATABASES
    assert "memora_db" in AGENT_DATABASES
    assert "stratex_db" in AGENT_DATABASES
    assert "inference_db" in AGENT_DATABASES


def test_sha256_file(tmp_path: Path):
    sample = tmp_path / "sample.txt"
    sample.write_bytes(b"FRIDAY UNIVERSE TEST DATA")
    digest = sha256_file(sample)
    assert len(digest) == 64
    assert digest == hashlib.sha256(b"FRIDAY UNIVERSE TEST DATA").hexdigest()


def test_create_backup_manifest():
    dumps = {
        "globals": {"file": "globals.sql", "size_bytes": 1024, "sha256": "abc"},
        "friday_db": {"file": "friday_db.sql", "size_bytes": 2048, "sha256": "def", "status": "SUCCESS"},
    }
    manifest = create_backup_manifest("bk_001", dumps, "test-bucket", "backups/bk_001.tar.gz")
    assert manifest["backup_id"] == "bk_001"
    assert manifest["database_version"] == "PostgreSQL 18-alpine"
    assert len(manifest["agent_databases"]) == 10
    assert manifest["oci_storage"]["verified"] is True
    assert manifest["dumps"]["friday_db"]["status"] == "SUCCESS"


def test_dump_database_execution(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    target = tmp_path / "friday_db.sql"
    
    def fake_run(cmd, stdout, stderr, text):
        stdout.write("CREATE TABLE conversations (id text);")
        return MagicMock(returncode=0)

    monkeypatch.setattr("subprocess.run", fake_run)
    size = dump_database("fake-cid", "friday_db", target)
    assert size > 0
    assert target.read_text(encoding="utf-8") == "CREATE TABLE conversations (id text);"


def test_execute_full_backup_workflow(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr("backup_postgres_to_oci_object_storage.get_postgres_container_id", lambda: "cid-1234")
    monkeypatch.setattr("backup_postgres_to_oci_object_storage.dump_all_globals", lambda cid, path: path.write_text("GLOBALS") or 7)
    monkeypatch.setattr("backup_postgres_to_oci_object_storage.dump_database", lambda cid, db, path: path.write_text(f"-- {db}") or 10)
    
    # Mock tarball creation
    def fake_tar(cmd, check):
        Path(cmd[2]).write_bytes(b"tarball_content")
        return MagicMock(returncode=0)
    
    monkeypatch.setattr("subprocess.run", fake_tar)

    manifest_path = execute_full_backup(output_dir=tmp_path, upload=False)
    assert manifest_path.is_file()
    
    with open(manifest_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    assert data["database_version"] == "PostgreSQL 18-alpine"
    assert len(data["dumps"]) == 11  # globals + 10 agent databases
    assert data["dumps"]["vyralx_db"]["status"] == "SUCCESS"
