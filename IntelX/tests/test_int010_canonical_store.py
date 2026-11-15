"""TASK-INT-010 — canonical research store repairs.

The classic research store (research_runs / sources / documents / chunks /
claims / evidence / findings) held zero production rows. The live route
persists only to ``live_research_runs``; the store's own write path is the
job pipeline (POST /v1/research/jobs -> OrchestrationWorker -> agents ->
repos). Two defects in that path's persistence layer are repaired here:

1. Every JSON column on the classic models used SQLAlchemy's stock JSON
   type. On Oracle 23ai, python-oracledb returns native JSON values
   pre-deserialized (dict/list), and the stock result processor raises
   TypeError on them — writes succeed, reads crash. TASK-REL-038 observed
   exactly this live and fixed only LiveResearchRun (TolerantJSON). These
   tests pin the invariant for the whole module: no stock-JSON columns
   remain, and the classic columns' processors accept the
   pre-deserialized values an Oracle driver returns. The metadata and
   processor tests FAIL on the unpatched models.

2. The retriever's cache check compared ``Source.location`` (Text — a
   CLOB on Oracle) with "=". Oracle rejects equality predicates on CLOB
   columns. ``SourceRepo.get_source_by_location`` replaces it with a
   SUBSTR-prefix pre-filter plus an exact in-Python match. The CLOB
   failure itself is Oracle-only and cannot be reproduced on SQLite;
   these tests pin the replacement's semantics (exact match, prefix
   collisions, >4000-char locations, absent locations).
"""

import pytest
from sqlalchemy import JSON
from sqlalchemy.dialects import sqlite

from intelx.db.base import Base
from intelx.db.models import Claim, Finding, ResearchRun, Task, TolerantJSON
from intelx.db.repos import SourceRepo
from intelx.db.session import get_sessionmaker

CANONICAL_TABLES = {
    "research_runs",
    "sources",
    "documents",
    "chunks",
    "claims",
    "evidence",
    "findings",
}


def test_no_stock_json_columns_remain():
    """Every JSON-typed column in the models module must be TolerantJSON.

    A single remaining stock-JSON column reintroduces the Oracle read
    crash (TypeError on pre-deserialized values) for that table.
    """
    assert CANONICAL_TABLES <= set(Base.metadata.tables)
    offenders = []
    tolerant = 0
    for table in Base.metadata.tables.values():
        for column in table.columns:
            if isinstance(column.type, TolerantJSON):
                tolerant += 1
            elif type(column.type) is JSON:
                offenders.append(f"{table.name}.{column.name}")
    assert offenders == [], f"stock JSON columns remain: {offenders}"
    # 15 classic columns converted by TASK-INT-010 + LiveResearchRun's 2.
    assert tolerant >= 17


def test_classic_json_processors_accept_predeserialized_values():
    """The classic models' JSON processors must accept dict/list values
    (what python-oracledb returns for Oracle native JSON) as well as
    encoded text (what SQLite returns). Stock JSON raises TypeError on
    the dict/list form — that is the production read crash."""
    dialect = sqlite.dialect()
    columns = [
        ResearchRun.__table__.c.scope_json,
        Task.__table__.c.payload_json,
        Claim.__table__.c.entities_json,
        Finding.__table__.c.claim_ids_json,
    ]
    for column in columns:
        processor = column.type.result_processor(dialect, None)
        assert processor is not None, column
        assert processor({"k": "v"}) == {"k": "v"}, column
        assert processor([1, 2]) == [1, 2], column
        assert processor('{"k": "v"}') == {"k": "v"}, column
        assert processor(None) is None, column


@pytest.fixture
def db_session_factory():
    return get_sessionmaker()


async def _seed_source(session, *, location, domain, fingerprint, kind):
    from intelx.core.enums import SourceKind  # noqa: F401  (kept explicit)

    return await SourceRepo.create_source(
        session=session,
        kind=kind,
        location=location,
        domain=domain,
        title="INT-010 fixture",
        fingerprint=fingerprint,
    )


@pytest.mark.asyncio
async def test_get_source_by_location_exact_match(db_session_factory):
    from intelx.core.enums import SourceKind

    long_location = "https://example.com/" + "x" * 5000
    async with db_session_factory() as session:
        a = await _seed_source(
            session,
            location="https://example.com/a",
            domain="example.com",
            fingerprint="int010-loc-a",
            kind=SourceKind.WEB,
        )
        b = await _seed_source(
            session,
            location="https://example.com/b",
            domain="example.com",
            fingerprint="int010-loc-b",
            kind=SourceKind.WEB,
        )
        c = await _seed_source(
            session,
            location=long_location,
            domain="example.com",
            fingerprint="int010-loc-c",
            kind=SourceKind.WEB,
        )
        # Shares the entire long location as a prefix: the SUBSTR
        # pre-filter returns both, the exact match must pick correctly.
        d = await _seed_source(
            session,
            location=long_location + "y",
            domain="example.com",
            fingerprint="int010-loc-d",
            kind=SourceKind.WEB,
        )
        e = await _seed_source(
            session,
            location="file:///fixtures/int010.txt",
            domain="archive.example",
            fingerprint="int010-loc-e",
            kind=SourceKind.FILE,
        )
        await session.commit()

        assert (await SourceRepo.get_source_by_location(session, "https://example.com/a")).id == a.id
        assert (await SourceRepo.get_source_by_location(session, "https://example.com/b")).id == b.id
        assert (await SourceRepo.get_source_by_location(session, long_location)).id == c.id
        assert (await SourceRepo.get_source_by_location(session, long_location + "y")).id == d.id
        assert (await SourceRepo.get_source_by_location(session, "file:///fixtures/int010.txt")).id == e.id
        assert await SourceRepo.get_source_by_location(session, "https://example.com/absent") is None
        assert await SourceRepo.get_source_by_location(session, "") is None


@pytest.mark.asyncio
async def test_retriever_cache_hit_via_location_lookup(db_session_factory):
    """The retriever's cache path must find an already-ingested source
    through the new lookup (no fetch attempted) — the behaviour the
    CLOB-equality query used to provide on SQLite."""
    from intelx.agents.retriever import RetrieverAgent
    from intelx.agents.scout import SourceCandidate
    from intelx.core.enums import SourceKind

    location = "https://cache-int010.example/doc"
    async with db_session_factory() as session:
        source = await SourceRepo.create_source(
            session=session,
            kind=SourceKind.WEB,
            location=location,
            domain="cache-int010.example",
            title="Cached INT-010 doc",
            fingerprint="int010-cache-hit",
        )
        await SourceRepo.create_document(
            session=session,
            source_id=source.id,
            text_content="Cached body text for the INT-010 retriever cache test.",
        )
        await session.commit()

        result = await RetrieverAgent().execute(
            candidates=[
                SourceCandidate(location=location, title="Cached INT-010 doc", reason="test")
            ],
            session=session,
        )
        assert len(result.retrieved) == 1
        assert result.retrieved[0].source_id == source.id
        assert result.failures == []
