"""Tests for the TASK-MEM-010 provenance re-signing tool (core.security.resign).

Scenario: fixture records are signed under master key A; the fleet rotates
to master key B. The tool must re-sign exactly the A-verifiable set, leave
already-B records byte-identical, and refuse — report, never force-sign —
records that verify under neither key (foreign-key and content-tampered)
and records carrying no signature at all. Dry-run writes nothing; a
second apply run changes nothing (idempotency).
"""
import hashlib
import importlib.util
from pathlib import Path

import pytest

from core.config import settings
from core.identity.service import IdentityService
from core.security.provenance import compute_memory_signature, verify_memory_signature
from core.security.resign import (
    OLD_KEY_ENV,
    TASK_ID,
    ResignRefused,
    resign_records,
    resolve_rotation_keys,
)
from storage.relational.models import LifecycleState, MemoryRecord, MemoryType

KEY_A = "test-old-master-key-AAAA"
KEY_B = "test-new-master-key-BBBB"
KEY_C = "test-foreign-key-CCCC"


def _seed(test_db, specs):
    """Seed records; each spec: {text, secret|None, tamper=False}.

    secret=None leaves the record unsigned. Signing happens after the
    flush so the signature covers the real record id, exactly as the
    write pipeline's provenance does.
    """
    actor = IdentityService.register_agent(test_db, "friday")
    ns = IdentityService.get_namespace_by_path(test_db, "memora://friday/private")
    records = []
    for spec in specs:
        text = spec["text"]
        record = MemoryRecord(
            namespace_id=ns.id,
            owner_id=actor.id,
            memory_type=MemoryType.SEMANTIC,
            content_text=text,
            content_hash=hashlib.sha256(text.strip().encode("utf-8")).hexdigest(),
            lifecycle_state=LifecycleState.ACTIVE,
            provenance={"subject": "mem010-fixture"},
            source="test",
        )
        test_db.add(record)
        test_db.flush()
        if spec.get("secret"):
            record.provenance = {
                "subject": "mem010-fixture",
                "hmac_signature": compute_memory_signature(record, secret=spec["secret"]),
                "signature_version": "v1",
            }
        if spec.get("tamper"):
            record.content_text = text + " — silently edited"
        test_db.commit()
        test_db.refresh(record)
        records.append(record)
    return records


def _standard_store(test_db):
    """2x key A, 1x key B, 1x foreign key C, 1x tampered-under-A, 1x unsigned."""
    return _seed(
        test_db,
        [
            {"text": "The owner prefers tea in the morning.", "secret": KEY_A},
            {"text": "The fleet has two servers.", "secret": KEY_A},
            {"text": "The owner is Surendra.", "secret": KEY_B},
            {"text": "A record from an unknown writer.", "secret": KEY_C},
            {"text": "The launch date is fixed.", "secret": KEY_A, "tamper": True},
            {"text": "An unsigned legacy note.", "secret": None},
        ],
    )


def _signature_of(test_db, record_id):
    record = test_db.query(MemoryRecord).filter(MemoryRecord.id == record_id).one()
    test_db.refresh(record)
    return (record.provenance or {}).get("hmac_signature")


def test_dry_run_reports_counts_and_writes_nothing(test_db):
    records = _standard_store(test_db)
    before = {r.id: (r.provenance or {}).get("hmac_signature") for r in records}

    report = resign_records(test_db, KEY_A, KEY_B, dry_run=True, batch_size=2)

    assert report.scanned == 6
    assert report.resignable == 2
    assert report.current == 1
    assert report.unverifiable == 2
    assert report.unsigned == 1
    assert report.resigned == 0
    assert set(report.unverifiable_ids) == {records[3].id, records[4].id}
    assert report.unsigned_ids == [records[5].id]

    after = {r.id: _signature_of(test_db, r.id) for r in records}
    assert after == before
    # The A records still verify under A only — the dry-run changed nothing.
    assert verify_memory_signature(records[0], secret=KEY_A) is True
    assert verify_memory_signature(records[0], secret=KEY_B) is False


def test_apply_resigns_exactly_the_old_key_set(test_db):
    records = _standard_store(test_db)
    foreign_before = dict(records[3].provenance)
    tampered_before = dict(records[4].provenance)
    unsigned_before = dict(records[5].provenance)
    current_before = _signature_of(test_db, records[2].id)

    report = resign_records(test_db, KEY_A, KEY_B, dry_run=False, batch_size=2)

    assert report.resigned == 2
    assert report.resignable == 2

    for record in records[:2]:
        test_db.refresh(record)
        assert verify_memory_signature(record, secret=KEY_B) is True
        assert verify_memory_signature(record, secret=KEY_A) is False
        # Non-signature provenance survives; the resign is annotated.
        assert record.provenance["subject"] == "mem010-fixture"
        assert record.provenance["resigned_by"] == TASK_ID

    # Already-current record: signature byte-identical.
    assert _signature_of(test_db, records[2].id) == current_before

    # Refused records: provenance byte-identical, still unverifiable under B.
    test_db.refresh(records[3])
    test_db.refresh(records[4])
    test_db.refresh(records[5])
    assert records[3].provenance == foreign_before
    assert records[4].provenance == tampered_before
    assert records[5].provenance == unsigned_before
    assert "hmac_signature" not in records[5].provenance
    assert verify_memory_signature(records[3], secret=KEY_B) is False
    assert verify_memory_signature(records[4], secret=KEY_B) is False


def test_second_apply_run_is_a_no_op(test_db):
    records = _standard_store(test_db)
    resign_records(test_db, KEY_A, KEY_B, dry_run=False)
    signatures_after_first = {r.id: _signature_of(test_db, r.id) for r in records}

    second = resign_records(test_db, KEY_A, KEY_B, dry_run=False)

    assert second.resigned == 0
    assert second.resignable == 0
    assert second.current == 3  # the two re-signed + the one already under B
    assert second.unverifiable == 2
    assert second.unsigned == 1
    signatures_after_second = {r.id: _signature_of(test_db, r.id) for r in records}
    assert signatures_after_second == signatures_after_first


def test_resolve_rotation_keys_happy_path(monkeypatch):
    monkeypatch.setattr(settings, "MEMORA_MASTER_KEY", KEY_B)
    old, new = resolve_rotation_keys(KEY_A)
    assert (old, new) == (KEY_A, KEY_B)


def test_resolve_rotation_keys_refuses_without_master(monkeypatch):
    monkeypatch.setattr(settings, "MEMORA_MASTER_KEY", None)
    monkeypatch.setattr(settings, "MEMORA_API_KEY", "some-per-agent-key")
    with pytest.raises(ResignRefused):
        resolve_rotation_keys(KEY_A)


def test_resolve_rotation_keys_refuses_missing_old_key(monkeypatch):
    monkeypatch.setattr(settings, "MEMORA_MASTER_KEY", KEY_B)
    with pytest.raises(ResignRefused):
        resolve_rotation_keys(None)
    with pytest.raises(ResignRefused):
        resolve_rotation_keys("")


def test_resolve_rotation_keys_refuses_identical_keys(monkeypatch):
    monkeypatch.setattr(settings, "MEMORA_MASTER_KEY", KEY_B)
    with pytest.raises(ResignRefused):
        resolve_rotation_keys(KEY_B)


def _load_cli_module():
    path = Path(__file__).resolve().parents[1] / "scripts" / "resign_provenance.py"
    spec = importlib.util.spec_from_file_location("resign_provenance_cli", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _reload(test_db, record_id):
    """Fresh copy of a record (the CLI closes its session, which expunges
    instances the test seeded through the same session object)."""
    return test_db.query(MemoryRecord).filter(MemoryRecord.id == record_id).one()


def test_cli_apply_requires_the_env_gate(test_db, monkeypatch):
    records = _standard_store(test_db)
    first_id = records[0].id
    cli = _load_cli_module()
    monkeypatch.setattr(cli, "SessionLocal", lambda: test_db)
    monkeypatch.setattr(settings, "MEMORA_MASTER_KEY", KEY_B)
    monkeypatch.setenv(OLD_KEY_ENV, KEY_A)
    monkeypatch.delenv("MEMORA_RESIGN_APPLY", raising=False)

    # --apply without the env gate: falls back to dry-run, writes nothing.
    exit_code = cli.main(["--apply"])
    assert exit_code == 2  # refused records exist, but nothing was applied
    reloaded = _reload(test_db, first_id)
    assert verify_memory_signature(reloaded, secret=KEY_A) is True
    assert verify_memory_signature(reloaded, secret=KEY_B) is False

    # With the gate armed, the same invocation applies.
    monkeypatch.setenv("MEMORA_RESIGN_APPLY", "1")
    exit_code = cli.main(["--apply"])
    assert exit_code == 2  # foreign/tampered/unsigned still reported
    reloaded = _reload(test_db, first_id)
    assert verify_memory_signature(reloaded, secret=KEY_B) is True


def test_cli_refuses_without_old_key_env(test_db, monkeypatch):
    _standard_store(test_db)
    cli = _load_cli_module()
    monkeypatch.setattr(cli, "SessionLocal", lambda: test_db)
    monkeypatch.setattr(settings, "MEMORA_MASTER_KEY", KEY_B)
    monkeypatch.delenv(OLD_KEY_ENV, raising=False)
    assert cli.main([]) == 1
