"""
TASK-IG2-MEM-01 — agentmemory pattern ADAPT: BM25 hybrid recall +
capture-compress-inject session memory.

Contracts locked here:
- the keyword leg of hybrid search ranks with real Okapi BM25 (term
  frequency, idf, length normalisation), not substring-overlap counting:
  a record matching the query's rare terms beats a long record stuffed
  with common words;
- the historical keyword_score contract survives: the best lexical
  match in the candidate set scores exactly 1.0, a record with no
  lexical match scores 0;
- equal-BM25 facts still resolve newest-first (TASK-MEM-002's tie-break
  is preserved under the new ranking signal);
- capture stores session events through the write pipeline with secrets
  scrubbed BEFORE storage, and drops (with a reason) any event whose
  secrets cannot be scrubbed clean;
- compress_session turns a session's events into one SEMANTIC digest
  linked to its sources, idempotently;
- build_session_context injects hybrid recall as a session-start pack
  and says so honestly when nothing is found.
"""
import importlib

import pytest

from core.identity.service import IdentityService
from core.memory.bm25 import BM25Index, tokenize
from core.memory.capture_service import SessionCaptureService, scrub_secrets
from core.memory.search_service import SearchService
from storage.relational.models import LifecycleState, MemoryRecord, MemoryType

oracle_module = importlib.import_module("storage.vector.oracle_vector_adapter")


class StubOracleAdapter:
    """Vector boundary stub (REL-013 pattern): no semantic hits, so the
    keyword leg is what is being measured."""

    def is_oracle_backend(self):
        return True

    def search_similarity(self, query_vector, limit, tenant_id, score_threshold, db=None):
        return []


@pytest.fixture(autouse=True)
def _no_vector(monkeypatch):
    monkeypatch.setattr(oracle_module, "oracle_vector_adapter", StubOracleAdapter())


def _record(test_db, ns, owner_id, content, **kwargs):
    record = MemoryRecord(
        namespace_id=ns.id,
        owner_id=owner_id,
        memory_type=MemoryType.EPISODIC,
        content_text=content,
        confidence=kwargs.pop("confidence", 0.9),
        importance=kwargs.pop("importance", 0.8),
        lifecycle_state=LifecycleState.ACTIVE,
        **kwargs,
    )
    test_db.add(record)
    test_db.commit()
    return record


def _actor_ns(test_db):
    actor = IdentityService.register_agent(test_db, "friday")
    ns = IdentityService.get_namespace_by_path(test_db, "memora://friday/private")
    return actor, ns


# ----------------------------------------------------------------------
# BM25 unit behaviour
# ----------------------------------------------------------------------

def test_bm25_equal_relevance_tie_and_rare_term_wins():
    idx = BM25Index().build([
        ("old", "The workshop door code is 1111."),
        ("new", "The workshop door code is 2222."),
    ])
    scores = idx.score("workshop door code")
    assert scores["old"] == scores["new"]

    idx2 = BM25Index().build([
        ("target", "The vault combination for the storage locker is kept with the caretaker."),
        ("stuffed", "the the the the vault " + "notes about the depot and the roster " * 8),
    ])
    scores2 = idx2.score("what is the vault combination for the storage locker")
    assert scores2["target"] > scores2.get("stuffed", 0.0)


def test_tokenize_drops_single_letters_keeps_digits():
    assert tokenize("Don't use wildcards, UPI 2fa!") == ["don", "use", "wildcards", "upi", "2fa"]


# ----------------------------------------------------------------------
# hybrid search: BM25 leg
# ----------------------------------------------------------------------

def test_hybrid_keyword_leg_ranks_rare_term_record_first(test_db):
    actor, ns = _actor_ns(test_db)
    _record(
        test_db, ns, actor.id,
        "the the the the vault " + "notes about the depot and the roster and the routine " * 8,
        importance=0.95,
    )
    target = _record(
        test_db, ns, actor.id,
        "The vault combination for the storage locker is kept with the caretaker.",
        importance=0.5,
    )
    results = SearchService.hybrid_search(
        db=test_db,
        query_text="what is the vault combination for the storage locker",
        actor_name="friday",
        limit=5,
    )
    assert results, "keyword leg returned nothing"
    assert results[0].record.id == target.id
    # Historical contract: best lexical match in the set scores 1.0.
    assert results[0].keyword_score == 1.0


def test_hybrid_equal_bm25_newer_fact_ranks_first(test_db):
    actor, ns = _actor_ns(test_db)
    from datetime import datetime, timedelta, timezone

    base = datetime(2026, 11, 1, tzinfo=timezone.utc)
    older = _record(
        test_db, ns, actor.id, "The workshop door code is 1111.",
        id="aaaaaaaa-0000-4000-8000-000000000001", created_at=base,
    )
    newer = _record(
        test_db, ns, actor.id, "The workshop door code is 2222.",
        id="zzzzzzzz-0000-4000-8000-000000000002", created_at=base + timedelta(minutes=5),
    )
    results = SearchService.hybrid_search(
        db=test_db, query_text="workshop door code", actor_name="friday", limit=5
    )
    ids = [r.record.id for r in results]
    assert ids.index(newer.id) < ids.index(older.id)


# ----------------------------------------------------------------------
# capture → compress → inject
# ----------------------------------------------------------------------

def test_capture_scrubs_secrets_before_storage(test_db):
    _actor_ns(test_db)
    result = SessionCaptureService.capture_event(
        test_db,
        actor_name="friday",
        session_id="sess-scrub",
        kind="tool_call",
        content="deploy used key sk-abcdefghijklmnopqrstuvwx to push the build",
    )
    assert result["stored"] is True
    assert "OpenAI API Key" in result["scrubbed_secret_types"]
    stored = test_db.query(MemoryRecord).filter(MemoryRecord.id == result["id"]).one()
    assert "sk-abcdefghijklmnopqrstuvwx" not in stored.content_text
    assert "[REDACTED]" in stored.content_text
    assert (stored.provenance or {}).get("session_id") == "sess-scrub"


def test_capture_drops_unscrubbable_event(test_db, monkeypatch):
    _actor_ns(test_db)
    monkeypatch.setattr(
        "core.memory.capture_service.SecretScanner.scan_content",
        staticmethod(lambda content: ["Residual Secret"]),
    )
    result = SessionCaptureService.capture_event(
        test_db,
        actor_name="friday",
        session_id="sess-drop",
        kind="note",
        content="anything at all",
    )
    assert result["stored"] is False
    assert result["reason"] == "unscrubbable_secret"


def test_compress_and_inject_roundtrip(test_db):
    _actor_ns(test_db)
    for kind, content in [
        ("decision", "Decided to keep Redis and Qdrant until the ARM server is allocated."),
        ("tool_call", "Ran the fleet health probe; all ten agents returned 200."),
        ("correction", "Owner corrected the plan: latency is not a constraint for Chicago."),
    ]:
        out = SessionCaptureService.capture_event(
            test_db, actor_name="friday", session_id="sess-1", kind=kind, content=content
        )
        assert out["stored"] is True, out

    compressed = SessionCaptureService.compress_session(
        test_db, actor_name="friday", session_id="sess-1"
    )
    assert compressed["compressed"] is True
    assert compressed["event_count"] == 3
    digest = test_db.query(MemoryRecord).filter(MemoryRecord.id == compressed["id"]).one()
    assert digest.memory_type == MemoryType.SEMANTIC
    assert len((digest.provenance or {}).get("compressed_from") or []) == 3
    assert "ARM server" in digest.content_text

    again = SessionCaptureService.compress_session(
        test_db, actor_name="friday", session_id="sess-1"
    )
    assert again["already_existed"] is True
    assert again["id"] == compressed["id"]

    pack = SessionCaptureService.build_session_context(
        test_db, actor_name="friday", query="Redis Qdrant ARM server decision"
    )
    assert pack["hit_count"] >= 1
    assert "Relevant memory" in pack["context"]


def test_inject_empty_is_honest(test_db):
    _actor_ns(test_db)
    pack = SessionCaptureService.build_session_context(
        test_db, actor_name="friday", query="something never stored anywhere"
    )
    assert pack["hit_count"] == 0
    assert "nothing was invented" in pack["context"]


def test_scrub_secrets_benign_text_untouched():
    text = "Rotated the Stratex bot token after the 409 storm; realised PnL unchanged."
    cleaned, matched = scrub_secrets(text)
    assert cleaned == text
    assert matched == []
