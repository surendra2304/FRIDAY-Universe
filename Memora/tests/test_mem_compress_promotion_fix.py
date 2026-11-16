"""
Regression suite for the capture-compress HTTP 500 (production-proven
2026-11-16 by the memora-probes round-2 crew; journal in that crew's
STATE.md Step 2b).

Failure chain in production:
1. POST /v1/capture/compress on a fresh session persisted the digest,
   then ``MemoryService.promote_to_semantic`` flushed an UPDATE whose
   provenance — copied from the stored row — carried Decimal leaves:
   Oracle's driver decodes stored JSON numbers back as Decimal. The
   ORM JSON serializer was plain ``json.dumps`` -> TypeError mid-flush
   -> poisoned session.
2. compress_session's promotion handler then formatted
   ``result.record.id`` in its log line, lazy-refreshing the expired
   record on the poisoned session -> ``PendingRollbackError`` escaped
   -> ASGI 500. A repeat compress returned ``already_existed`` and
   never retried the promotion, stranding the digest as EPISODIC.
   Handoff hit the identical path.

Locked here:
- the ORM JSON boundary serializes Decimal/datetime/UUID values, with
  Decimal staying a JSON number (house convention: ``default=str``
  everywhere else; numbers stay numbers so stored scores/confidences
  read back typed);
- compress promotes a digest end-to-end when the stored provenance
  reads back with Decimal-typed numerics (Oracle decode shape),
  landing SEMANTIC + VERIFIED — including via the already_existed
  retry for a digest stranded by the original failure;
- a promotion that fails mid-flush degrades to
  ``promoted_to_semantic: False`` with a still-usable session — the
  design contract is "a denied promotion is not a failed compression";
- handoff on a fresh session answers 200 even when promotion fails.
"""

from __future__ import annotations

import importlib
import json
from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID

import pytest
from sqlalchemy import create_engine

from core.identity.service import IdentityService
from core.memory.capture_service import SessionCaptureService
from core.memory.service import MemoryService
from storage.relational import session as _session_module
from storage.relational.models import LifecycleState, MemoryRecord, MemoryType
from storage.relational.session import _ensure_json_serializer

# Present only post-fix; the boundary test asserts against whatever
# serializer is installed so this suite also runs (and fails
# behaviourally) on the pre-fix code.
_json_dumps = getattr(_session_module, "_json_dumps", None)

oracle_module = importlib.import_module("storage.vector.oracle_vector_adapter")


# ----------------------------------------------------------------------
# helpers
# ----------------------------------------------------------------------

def _register(test_db, name: str) -> None:
    IdentityService.register_agent(test_db, name)


def _capture_two(test_db, actor: str = "friday", session_id: str = "sess-compress-fix") -> None:
    SessionCaptureService.capture_event(
        test_db, actor_name=actor, session_id=session_id,
        kind="note", content="The deploy window opens at 09:00 UTC.",
    )
    SessionCaptureService.capture_event(
        test_db, actor_name=actor, session_id=session_id,
        kind="decision", content="Confirmed: deploy window 09:00 UTC, rollback plan attached.",
    )


def _oracle_like(value):
    """Decode JSON the way the Oracle driver hands it back: numbers as Decimal."""
    if isinstance(value, float):
        return Decimal(str(value))
    if isinstance(value, dict):
        return {k: _oracle_like(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_oracle_like(v) for v in value]
    return value


def _decode_like_oracle(raw):
    if raw is None or isinstance(raw, (dict, list)):
        return _oracle_like(raw)
    return _oracle_like(json.loads(raw))


def _plain_numbers(value):
    """Decimal -> float recursively, for writing a stored JSON document
    in test setup (the stored document holds plain numbers; Decimals
    appear when the Oracle-shaped decoder reads it back)."""
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, dict):
        return {k: _plain_numbers(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_plain_numbers(v) for v in value]
    return value


class StubOracleAdapter:
    """Vector boundary stub (same pattern as the IG2-MEM-01 wiring
    suite): no semantic hits, so recall is the keyword leg —
    deterministic, and no live Oracle vector store is needed."""

    def is_oracle_backend(self):
        return True

    def search_similarity(self, query_vector, limit, tenant_id, score_threshold, db=None):
        return []


@pytest.fixture(autouse=True)
def _no_vector(monkeypatch):
    monkeypatch.setattr(oracle_module, "oracle_vector_adapter", StubOracleAdapter())


def _poisoning_promote(db, memory_id, **kwargs):
    """A promotion that dies mid-flush, poisoning the session.

    Mirrors the production TypeError's session state (a failed flush
    with a pending transaction) without depending on the driver.
    """
    db.add(MemoryRecord(id=memory_id))  # duplicate PK + NOT NULL violations
    db.flush()
    raise AssertionError("flush must have raised")  # pragma: no cover


# ----------------------------------------------------------------------
# 1. the JSON boundary itself
# ----------------------------------------------------------------------

def test_json_boundary_serializes_decimal_and_friends():
    engine = create_engine("sqlite://")
    _ensure_json_serializer(engine)
    serializer = engine.dialect._json_serializer
    if _json_dumps is not None:
        assert serializer is _json_dumps

    payload = {
        "confidence": Decimal("0.85"),
        "nested": {"scores": [Decimal("0.5"), 2]},
        "at": datetime(2026, 11, 16, 12, 0, tzinfo=timezone.utc),
        "uid": UUID(int=7),
    }
    loaded = json.loads(serializer(payload))
    # Numbers stay numbers — a stored confidence must read back typed,
    # not as the string "0.85".
    assert loaded["confidence"] == 0.85 and isinstance(loaded["confidence"], float)
    assert loaded["nested"]["scores"] == [0.5, 2]
    assert loaded["at"].startswith("2026-11-16T12:00")
    assert loaded["uid"] == str(UUID(int=7))

    # The production failure mode, for the record: plain json.dumps —
    # what the boundary used to install — cannot serialize this payload.
    with pytest.raises(TypeError):
        json.dumps(payload)


# ----------------------------------------------------------------------
# 2. compress end-to-end with Decimal-typed stored provenance
# ----------------------------------------------------------------------

def test_compress_promotes_end_to_end_over_oracle_shaped_store(test_db):
    """Happy path end-to-end with the store decoding numbers as Decimal.

    The test engine's JSON deserializer is swapped for an Oracle-shaped
    one (floats -> Decimal), so every row read back from the store
    carries Decimal leaves, as on the fleet's Oracle store. (On the
    create path the same-session identity map can keep in-process
    values; the retry test below forces the stored row to be reloaded
    and proves a Decimal reaches the promotion flush.)
    """
    _ensure_json_serializer(test_db.bind)
    test_db.bind.dialect._json_deserializer = _decode_like_oracle
    _register(test_db, "friday")
    _capture_two(test_db)

    result = SessionCaptureService.compress_session(
        test_db, actor_name="friday", session_id="sess-compress-fix",
    )

    assert result["compressed"] is True
    assert result["promoted_to_semantic"] is True
    test_db.expire_all()
    digest = test_db.query(MemoryRecord).filter(MemoryRecord.id == result["id"]).one()
    assert digest.memory_type == MemoryType.SEMANTIC
    assert digest.lifecycle_state == LifecycleState.VERIFIED
    assert float(digest.provenance["confidence"]) == 0.85


def test_retry_promotion_flushes_decimal_provenance(test_db, monkeypatch):
    """The production crash condition, exercised deterministically.

    A digest stranded EPISODIC by a denied first promotion is reloaded
    from the store (session expired), so its provenance is decoded the
    Oracle way — numeric leaves as Decimal. The already_existed retry
    then flushes the promotion UPDATE with that Decimal in the payload:
    exactly the flush that raised ``TypeError: Object of type Decimal
    is not JSON serializable`` in production. A before_flush spy
    asserts the Decimal really reached the flush, so this test cannot
    silently degrade into a float happy-path.

    One seeding note: promote overwrites the top-level ``confidence``
    leaf itself, so the surviving Decimal must ride a nested leaf. The
    production payload was a rich provenance document (the journal's
    UPDATE parameters run to ~1,200 characters); this test seeds one
    nested numeric leaf (``quality.score``) into the stored row via
    raw SQL, modelling that stored shape.
    """
    from sqlalchemy import event, text
    from sqlalchemy.orm import Session as OrmSession

    _ensure_json_serializer(test_db.bind)
    test_db.bind.dialect._json_deserializer = _decode_like_oracle
    _register(test_db, "friday")
    _capture_two(test_db)

    def _denied(db, memory_id, **kwargs):
        raise PermissionError("promotion denied in test")

    monkeypatch.setattr(MemoryService, "promote_to_semantic", staticmethod(_denied))
    first = SessionCaptureService.compress_session(
        test_db, actor_name="friday", session_id="sess-compress-fix",
    )
    assert first["promoted_to_semantic"] is False
    monkeypatch.undo()

    # Seed the nested numeric leaf into the STORED provenance (raw SQL
    # bypasses the ORM serializer on purpose: this writes the stored
    # document, which the Oracle-shaped decoder will read back with a
    # Decimal at quality.score).
    test_db.expire_all()
    stored = test_db.query(MemoryRecord).filter(MemoryRecord.id == first["id"]).one()
    seeded = _plain_numbers(dict(stored.provenance))
    seeded["quality"] = {"score": 0.5}
    test_db.execute(
        text("UPDATE memory_records SET provenance = :p WHERE id = :id"),
        {"p": json.dumps(seeded), "id": first["id"]},
    )
    test_db.commit()

    decimal_leaf_paths = []

    def _walk(value, path):
        if isinstance(value, Decimal):
            decimal_leaf_paths.append(path)
        elif isinstance(value, dict):
            for key, item in value.items():
                _walk(item, f"{path}.{key}")
        elif isinstance(value, list):
            for idx, item in enumerate(value):
                _walk(item, f"{path}[{idx}]")

    def _spy(session, flush_context, instances):
        for obj in list(session.dirty):
            if isinstance(obj, MemoryRecord):
                _walk(obj.__dict__.get("provenance") or {}, "provenance")

    event.listen(OrmSession, "before_flush", _spy)
    try:
        test_db.expire_all()
        second = SessionCaptureService.compress_session(
            test_db, actor_name="friday", session_id="sess-compress-fix",
        )
    finally:
        event.remove(OrmSession, "before_flush", _spy)

    assert second["already_existed"] is True
    assert second["promoted_to_semantic"] is True
    # The production condition was genuinely exercised: the seeded
    # Decimal leaf reached the promotion flush, and the boundary
    # serialized it instead of raising TypeError.
    assert "provenance.quality.score" in decimal_leaf_paths, decimal_leaf_paths
    test_db.expire_all()
    digest = test_db.query(MemoryRecord).filter(MemoryRecord.id == first["id"]).one()
    assert digest.memory_type == MemoryType.SEMANTIC
    assert digest.lifecycle_state == LifecycleState.VERIFIED
    assert float(digest.provenance["confidence"]) == 0.85
    # The seeded leaf survived the promotion round-trip as a number.
    assert float(digest.provenance["quality"]["score"]) == 0.5


def test_already_existed_retries_a_stranded_promotion(test_db, monkeypatch):
    """A digest stranded EPISODIC by a first failed promotion must heal.

    First compress: promotion is denied (stubbed) -> digest stays
    EPISODIC. Second compress takes the already_existed path; it must
    retry the promotion instead of reporting success while the digest
    stays unpromoted forever (the pre-fix behaviour).
    """
    _ensure_json_serializer(test_db.bind)
    _register(test_db, "friday")
    _capture_two(test_db)

    def _denied(db, memory_id, **kwargs):
        raise PermissionError("promotion denied in test")

    monkeypatch.setattr(MemoryService, "promote_to_semantic", staticmethod(_denied))
    first = SessionCaptureService.compress_session(
        test_db, actor_name="friday", session_id="sess-compress-fix",
    )
    assert first["compressed"] is True
    assert first["promoted_to_semantic"] is False
    test_db.expire_all()
    digest = test_db.query(MemoryRecord).filter(MemoryRecord.id == first["id"]).one()
    assert digest.memory_type == MemoryType.EPISODIC

    monkeypatch.undo()
    second = SessionCaptureService.compress_session(
        test_db, actor_name="friday", session_id="sess-compress-fix",
    )
    assert second["already_existed"] is True
    assert second["promoted_to_semantic"] is True
    test_db.expire_all()
    digest = test_db.query(MemoryRecord).filter(MemoryRecord.id == first["id"]).one()
    assert digest.memory_type == MemoryType.SEMANTIC
    assert digest.lifecycle_state == LifecycleState.VERIFIED


# ----------------------------------------------------------------------
# 3. forced mid-flush promotion failure degrades, never raises
# ----------------------------------------------------------------------

def test_compress_degrades_when_promotion_poisons_the_session(test_db, monkeypatch):
    _ensure_json_serializer(test_db.bind)
    _register(test_db, "friday")
    _capture_two(test_db)
    monkeypatch.setattr(MemoryService, "promote_to_semantic", staticmethod(_poisoning_promote))

    # Pre-fix this raised PendingRollbackError out of the handler.
    result = SessionCaptureService.compress_session(
        test_db, actor_name="friday", session_id="sess-compress-fix",
    )

    assert result["compressed"] is True
    assert result["promoted_to_semantic"] is False
    # The session survived the rollback discipline: still fully usable,
    # and the pipeline-committed digest is intact, still EPISODIC.
    digest = test_db.query(MemoryRecord).filter(MemoryRecord.id == result["id"]).one()
    assert digest.memory_type == MemoryType.EPISODIC


# ----------------------------------------------------------------------
# 4. handoff over HTTP: 200 even when promotion fails
# ----------------------------------------------------------------------

def test_handoff_200_when_promotion_fails(client, test_db, monkeypatch):
    _ensure_json_serializer(test_db.bind)
    _register(test_db, "friday")
    for kind, content in (
        ("note", "The deploy window opens at 09:00 UTC."),
        ("decision", "Confirmed: deploy window 09:00 UTC."),
    ):
        resp = client.post(
            "/v1/capture/events",
            json={"session_id": "sess-handoff-fix", "kind": kind, "content": content},
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["stored"] is True, resp.json()

    monkeypatch.setattr(MemoryService, "promote_to_semantic", staticmethod(_poisoning_promote))
    resp = client.post(
        "/v1/capture/handoff",
        json={"session_id": "sess-handoff-fix", "next_query": "deploy window"},
    )

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["compression"]["compressed"] is True
    assert body["compression"]["promoted_to_semantic"] is False
    assert "context" in body


# ----------------------------------------------------------------------
# 5. already_existed response consistency (no faults injected)
# ----------------------------------------------------------------------

def test_already_existed_reports_promotion_state(test_db):
    _ensure_json_serializer(test_db.bind)
    _register(test_db, "friday")
    _capture_two(test_db)

    SessionCaptureService.compress_session(
        test_db, actor_name="friday", session_id="sess-compress-fix",
    )
    second = SessionCaptureService.compress_session(
        test_db, actor_name="friday", session_id="sess-compress-fix",
    )

    assert second["already_existed"] is True
    assert "promoted_to_semantic" in second
    test_db.expire_all()
    digest = test_db.query(MemoryRecord).filter(MemoryRecord.id == second["id"]).one()
    # Whatever the policy outcome in this environment, the reported
    # flag must match the stored truth.
    assert second["promoted_to_semantic"] == (digest.memory_type == MemoryType.SEMANTIC)
