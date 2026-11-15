"""TASK-INT-011: projection of live research runs into the canonical store.

TASK-INT-010 proved the canonical pipeline (research_runs / sources /
documents / chunks / claims / evidence / findings) was fully built but
never called in production, while all real research flows through the
live path into ``live_research_runs`` only. Option W wires the two
together. These tests pin the contract:

1. ``collect_live_brief`` returns its ``source_documents`` (the seam).
2. Projecting a fixture live run populates all seven canonical tables,
   with claims whose quote == document text at the stored span.
3. Synthesized statements land as origin INFERRED (they can never ground
   a factual finding, TASK-INT-008); verbatim excerpts land EXTRACTED.
4. A quote that cannot be located in the document is never projected —
   no fabricated spans (the Bruker failure mode, one layer down).
5. Projection failure surfaces in the envelope's degradations while the
   live result returns untouched; nothing partial is committed.
6. Re-projecting the same live run is a no-op (idempotency).
7. The default ``research`` action is an honest lookup: it reports the
   canonical store's census instead of claiming synthesis.

Fixtures mirror tests/test_int009_verification_gaps.py (same fake
search/fetch connectors and draft synthesiser).
"""
import hashlib
from types import SimpleNamespace

import pytest
from sqlalchemy import func, select

from intelx.api import canonical_projection
from intelx.api.canonical_projection import project_and_annotate, project_live_run
from intelx.api.live_research_task import collect_live_brief
from intelx.core.enums import ClaimOrigin, RunOutcome, RunStatus
from intelx.db.models import (
    Chunk,
    Claim,
    Document,
    Evidence,
    Finding,
    ResearchRun,
    Source,
)
from intelx.db.session import get_sessionmaker

URL = "https://www.who.int/example"
P1 = ("The aspartame safety assessment concluded that aspartame is safe "
      "within the acceptable daily intake of 0-40 mg/kg body weight for "
      "aspartame consumers.")
P2 = ("The assessment of aspartame safety reviewed aspartame studies "
      "from many countries over several decades of published research.")
HTML = f"<html><body><p>{P1}</p><p>{P2}</p></body></html>"
QUOTE = ("aspartame is safe within the acceptable daily intake of "
         "0-40 mg/kg body weight for aspartame")
STATEMENT = ("The aspartame safety assessment concluded that aspartame "
             "is safe within a daily intake of 40 mg/kg of body weight.")
QUERY = "aspartame safety assessment"


class _Search:
    def __init__(self, urls):
        self._urls = urls

    async def fetch(self, query, max_results=5):
        return [SimpleNamespace(url=u, title="Aspartame assessment") for u in self._urls]


class _Fetch:
    def __init__(self, pages):
        self._pages = pages

    async def fetch(self, url, max_bytes=1_000_000):
        return SimpleNamespace(status_code=200, content_type="text/html",
                               final_url=url, content=self._pages[url].encode())


def _sid(url):
    return hashlib.sha256(url.encode()).hexdigest()[:16]


def _draft(findings):
    async def _synth(query, documents):
        return {"status": "SUCCESS", "findings": findings,
                "answer_kind": "source_attributed_model_draft",
                "quotes_verified": True, "semantic_entailment_verified": True,
                "synthesis_provider": "stub"}
    return _synth


def _draft_finding(url, statement=STATEMENT, quote=QUOTE):
    return {"statement": statement, "quote": quote,
            "status": "source_attributed_model_draft",
            "independently_verified": False, "single_source": True,
            "quote_verified": True, "entailment_verified": True,
            "citations": [{"source_id": _sid(url), "source_title": "Aspartame assessment",
                           "source_url": url}]}


async def _synthesized_brief():
    brief = await collect_live_brief(
        QUERY, _Search([URL]), _Fetch({URL: HTML}),
        synthesize=_draft([_draft_finding(URL)]))
    assert brief["status"] == "SUCCESS"
    assert len(brief["findings"]) == 1
    return brief


async def _extractive_brief():
    brief = await collect_live_brief(QUERY, _Search([URL]), _Fetch({URL: HTML}))
    assert brief["findings"], "expected extractive findings"
    assert all(f["status"] == "source_excerpt" for f in brief["findings"])
    return brief


async def _census():
    sessionmaker = get_sessionmaker()
    async with sessionmaker() as session:
        out = {}
        for label, model in (("research_runs", ResearchRun), ("sources", Source),
                             ("documents", Document), ("chunks", Chunk),
                             ("claims", Claim), ("evidence", Evidence),
                             ("findings", Finding)):
            out[label] = int((await session.execute(
                select(func.count()).select_from(model))).scalar_one())
        return out


async def _only_run():
    sessionmaker = get_sessionmaker()
    async with sessionmaker() as session:
        return (await session.execute(select(ResearchRun))).scalar_one()


# ── 1. The seam ─────────────────────────────────────────────────────────────

async def test_brief_returns_source_documents():
    brief = await _synthesized_brief()
    docs = brief.get("source_documents")
    assert docs, "collect_live_brief must return its source_documents"
    assert len(docs) == 1
    assert docs[0]["url"] == URL
    assert docs[0]["source_id"] == _sid(URL)
    assert P1 in docs[0]["text"] and P2 in docs[0]["text"]


# ── 2/3. Projection populates the store, honestly labelled ─────────────────

async def test_projection_populates_all_seven_tables():
    brief = await _synthesized_brief()
    report = await project_live_run(
        live_run_id="lr_int011_a", task_id="task-a", query=QUERY,
        brief=brief, source_documents=brief["source_documents"],
        created_by="int011-test")
    assert report["status"] == "projected", report
    assert report["degradations"] == []
    counts = report["counts"]
    assert counts["sources"] == 1 and counts["documents"] == 1
    assert counts["chunks"] >= 1
    assert counts["claims"] == 1 and counts["evidence"] == 1
    assert counts["findings"] == 1
    assert await _census() == {"research_runs": 1, "sources": 1, "documents": 1,
                               "chunks": counts["chunks"], "claims": 1,
                               "evidence": 1, "findings": 1}

    run = await _only_run()
    assert run.id == report["canonical_run_id"]
    assert run.status == RunStatus.COMPLETED
    assert run.outcome == RunOutcome.ANSWERED
    assert run.idempotency_key == "live:lr_int011_a"
    assert run.objective == QUERY

    sessionmaker = get_sessionmaker()
    async with sessionmaker() as session:
        claim = (await session.execute(select(Claim))).scalar_one()
        document = (await session.execute(select(Document))).scalar_one()
        evidence = (await session.execute(select(Evidence))).scalar_one()
        finding = (await session.execute(select(Finding))).scalar_one()
    # The span invariant, exactly as the citation checker will test it.
    assert document.text[claim.span_start:claim.span_end] == claim.quote
    assert claim.quote == QUOTE
    assert claim.text == STATEMENT
    # A synthesized statement is INFERRED — never EXTRACTED, never
    # presented as verified (TASK-INT-008).
    assert claim.origin == ClaimOrigin.INFERRED
    assert claim.confidence < 0.70
    assert evidence.claim_id == claim.id
    assert evidence.span_start == claim.span_start
    assert evidence.span_end == claim.span_end
    assert evidence.quote == claim.quote
    assert finding.run_id == run.id
    assert finding.claim_ids_json == [claim.id]
    # A projected finding is never "verified" grade at the lookup layer.
    assert finding.confidence < 0.70


async def test_projection_extractive_findings_are_extracted():
    brief = await _extractive_brief()
    report = await project_live_run(
        live_run_id="lr_int011_b", task_id="task-b", query=QUERY,
        brief=brief, source_documents=brief["source_documents"])
    assert report["status"] == "projected", report
    assert report["counts"]["claims"] == len(brief["findings"]) >= 1
    sessionmaker = get_sessionmaker()
    async with sessionmaker() as session:
        claims = list((await session.execute(select(Claim))).scalars().all())
        documents = {d.id: d for d in
                     (await session.execute(select(Document))).scalars().all()}
    for claim in claims:
        assert claim.origin == ClaimOrigin.EXTRACTED
        assert claim.confidence == 1.0
        doc = documents[claim.document_id]
        assert doc.text[claim.span_start:claim.span_end] == claim.quote
        # Extractive: the statement IS the quote, verbatim.
        assert claim.text == claim.quote


# ── 4. No fabricated spans ──────────────────────────────────────────────────

async def test_projection_never_fabricates_a_span():
    brief = await _synthesized_brief()
    brief["findings"] = [_draft_finding(
        URL, statement="Bruker provides specialized solid-state NMR probes.",
        quote="specialized solid-state NMR systems for in-situ research")]
    report = await project_live_run(
        live_run_id="lr_int011_c", task_id="task-c", query=QUERY,
        brief=brief, source_documents=brief["source_documents"])
    assert report["status"] == "failed"
    kinds = [d["kind"] for d in report["degradations"]]
    assert "quote_not_span_locatable" in kinds
    # Nothing partial is committed: no hollow canonical run.
    assert (await _census())["research_runs"] == 0
    assert (await _census())["claims"] == 0


# ── 5. Failure surfaces; the live answer survives ───────────────────────────

async def test_projection_failure_lands_in_degradations_envelope_intact(monkeypatch):
    brief = await _synthesized_brief()
    documents = brief.pop("source_documents")

    async def _boom(*args, **kwargs):
        raise RuntimeError("ingest exploded")

    monkeypatch.setattr("intelx.memory.normalize.ingest_and_normalize", _boom)
    envelope = {"task_id": "task-d", "target_agent": "intelx",
                "status": "SUCCESS", "result": brief,
                "receipt": {"verification_evidence": {"durable_run": True}}}
    projection = await project_and_annotate(
        envelope, live_run_id="lr_int011_d", task_id="task-d", query=QUERY,
        source_documents=documents)
    assert projection["status"] == "failed"
    # The live answer is untouched and still carries its findings.
    assert envelope["status"] == "SUCCESS"
    assert envelope["result"]["findings"][0]["statement"] == STATEMENT
    # …and the failure is on the record, where a caller looks.
    assert envelope["result"]["canonical_projection"]["status"] == "failed"
    assert envelope["degradations"], "projection failure must surface"
    assert any(d["kind"] == "document_ingest_failed" for d in envelope["degradations"])
    assert envelope["receipt"]["verification_evidence"]["canonical_projection"] == "failed"
    assert (await _census())["research_runs"] == 0


async def test_projection_internal_error_never_raises(monkeypatch):
    brief = await _synthesized_brief()
    documents = brief.pop("source_documents")

    async def _boom(*args, **kwargs):
        raise RuntimeError("db down")

    monkeypatch.setattr("intelx.db.repos.RunRepo.create_run", _boom)
    report = await project_live_run(
        live_run_id="lr_int011_e", task_id="task-e", query=QUERY,
        brief=brief, source_documents=documents)
    assert report["status"] == "failed"
    assert any(d["kind"] == "projection_failed" for d in report["degradations"])


async def test_projection_skipped_without_a_completed_brief():
    envelope = {"task_id": "task-f", "status": "DEGRADED", "result": {},
                "receipt": {"verification_evidence": {}}}
    projection = await project_and_annotate(
        envelope, live_run_id="lr_int011_f", task_id="task-f", query=QUERY,
        source_documents=[])
    assert projection["status"] == "skipped"
    assert envelope["result"]["canonical_projection"]["status"] == "skipped"
    assert (await _census())["research_runs"] == 0


# ── 6. Idempotency ──────────────────────────────────────────────────────────

async def test_double_projection_creates_no_duplicates():
    brief = await _synthesized_brief()
    first = await project_live_run(
        live_run_id="lr_int011_g", task_id="task-g", query=QUERY,
        brief=brief, source_documents=brief["source_documents"])
    assert first["status"] == "projected"
    before = await _census()
    second = await project_live_run(
        live_run_id="lr_int011_g", task_id="task-g", query=QUERY,
        brief=brief, source_documents=brief["source_documents"])
    assert second["status"] == "already_projected"
    assert second["canonical_run_id"] == first["canonical_run_id"]
    assert second["counts"] == first["counts"]
    assert await _census() == before


# ── 7. The lookup action is honest ──────────────────────────────────────────

async def _lookup(query=QUERY):
    from intelx.api.router import execute_task

    api_key = SimpleNamespace(name="int011-test", role="admin")
    return await execute_task(
        {"action": "research", "payload": {"query": query}}, None, api_key)


async def test_lookup_reports_empty_store_honestly():
    response = await _lookup()
    assert response["status"] == "SUCCESS"
    result = response["result"]
    assert result["lookup"]["kind"] == "canonical_store_lookup"
    assert result["lookup"]["fresh_research"] is False
    assert result["lookup"]["store_census"]["research_runs"] == 0
    assert result["lookup"]["store_census"]["claims"] == 0
    assert result["findings_count"] == 0
    assert "lookup" in response["summary"]
    assert "synthesized" not in response["summary"]
    assert any(d["kind"] == "lookup_returned_no_findings"
               for d in response.get("degradations") or [])


async def test_lookup_reports_populated_store():
    brief = await _synthesized_brief()
    report = await project_live_run(
        live_run_id="lr_int011_h", task_id="task-h", query=QUERY,
        brief=brief, source_documents=brief["source_documents"],
        created_by="int011-test")
    assert report["status"] == "projected"
    response = await _lookup()
    census = response["result"]["lookup"]["store_census"]
    assert census["research_runs"] == 1 and census["claims"] == 1
    assert census["findings"] == 1
    assert response["result"]["findings_count"] >= 1
    assert "lookup" in response["summary"]
    assert not response.get("degradations")
    # The stored finding is labelled inference, never verified: the
    # projected finding's confidence is deliberately below the gate.
    assert response["result"]["provenance_chain"]
    assert response["receipt"]["verification_evidence"]["store_census"] == census
