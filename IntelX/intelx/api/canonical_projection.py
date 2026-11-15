"""Canonical-store projection for completed live-research runs (TASK-INT-011).

TASK-INT-010 established that IntelX's canonical research store (the seven
tables research_runs / sources / documents / chunks / claims / evidence /
findings) was fully built but never written: all real research flows through
the synchronous live route, which persists verbatim only to
``live_research_runs``. The coordinator's Option W decision wires the two
together: every completed live run is ALSO projected into the canonical
tables, so the citation-integrity machinery (TASK-INT-008) has the corpus
it was built to audit.

Projection rules (fail-closed, mirroring the live path's honesty contract):

* The projection consumes the live path's VERIFIED output — the brief as it
  stands after TASK-INT-009's gates (verbatim quote gate, entailment
  screen, live re-verification). Downgraded findings never reach the
  brief's finding list and are never projected.
* Claims are written only through ``ClaimRepo.create_claim``, which
  enforces quote == document text at the span, at write time. A quote that
  cannot be located verbatim in the ingested document text is NOT
  projected; it is recorded as a degradation instead. No span is ever
  fabricated.
* Origin: a finding whose statement is the verbatim excerpt itself
  (``status == "source_excerpt"``) is EXTRACTED. Every other shape — above
  all the source-attributed model draft — is INFERRED: a synthesized
  statement can never ground a factual finding (TASK-INT-008), however
  well its quote verifies. Unknown finding shapes default to INFERRED.
* Idempotency: the canonical run carries idempotency key
  ``live:<live_run_id>``; re-projecting the same live run returns
  ``already_projected`` and writes nothing.
* Failure surfacing: projection NEVER raises into the live answer and
  never fails silently. The report (status, counts, degradations) is
  returned to the router, which stamps it onto the envelope result, the
  receipt evidence, and a top-level ``degradations`` list (the MEM-008
  pattern: a side effect that fails must say so where the caller looks).
"""
from __future__ import annotations

import logging
from typing import Any
from urllib.parse import urlsplit

logger = logging.getLogger(__name__)

PROJECTION_AGENT = "live_projection"
CONFIDENCE_METHOD = "live-projection-v1"
# An extractive claim's statement IS its span-verified quote, so its
# attribution confidence is exact. A synthesized statement is model prose:
# its quote is verified, the statement itself is not — 0.5 records that
# distinction without inventing a measured accuracy. A projected Finding
# is likewise never "verified" grade (nothing here is independently
# corroborated), whatever its claims' origins.
EXTRACTIVE_CONFIDENCE = 1.0
INFERRED_CONFIDENCE = 0.5
FINDING_CONFIDENCE = 0.5

_ZERO_COUNTS = {"sources": 0, "documents": 0, "chunks": 0,
                "claims": 0, "evidence": 0, "findings": 0}


def _idempotency_key(live_run_id: str) -> str:
    return f"live:{live_run_id}"[:128]


def _locate_span(text: str, quote: str) -> tuple[int, int] | None:
    """Locate ``quote`` in ``text``; return (start, end) over the raw text.

    Exact match first. The synthesis quote gate compares whitespace-
    normalised text, so a model-copied quote may differ from the document
    in whitespace runs alone; fall back to a normalised search and map the
    match back to raw offsets. The caller stores the raw slice as the
    quote, so the stored quote is verbatim by construction either way.
    """
    if not quote:
        return None
    idx = text.find(quote)
    if idx >= 0:
        return idx, idx + len(quote)
    norm_chars: list[str] = []
    raw_index: list[int] = []
    in_ws = False
    for i, ch in enumerate(text):
        if ch.isspace():
            if not in_ws:
                norm_chars.append(" ")
                raw_index.append(i)
            in_ws = True
        else:
            norm_chars.append(ch)
            raw_index.append(i)
            in_ws = False
    norm_quote = " ".join(quote.split())
    if not norm_quote:
        return None
    nidx = "".join(norm_chars).find(norm_quote)
    if nidx < 0:
        return None
    start = raw_index[nidx]
    end = raw_index[nidx + len(norm_quote) - 1] + 1
    # Trim whitespace at the edges for a clean passage boundary.
    while start < end and text[start].isspace():
        start += 1
    while end > start and text[end - 1].isspace():
        end -= 1
    return (start, end) if end > start else None


def _chunk_for_span(chunks: list, start: int, end: int):
    """Pick the chunk a claim span belongs to: the smallest chunk fully
    containing the span, else the chunk containing its start."""
    containing = [c for c in chunks if c.start_char <= start and c.end_char >= end]
    if containing:
        return min(containing, key=lambda c: c.end_char - c.start_char)
    for c in chunks:
        if c.start_char <= start < c.end_char:
            return c
    return chunks[0] if chunks else None


async def _run_counts(session, run_id: str) -> dict:
    """Exact row counts a canonical run already holds (idempotent replay)."""
    from sqlalchemy import func, select

    from intelx.db.models import Chunk, Claim, Document, Evidence, Finding, Source

    async def _count(stmt) -> int:
        return int((await session.execute(stmt)).scalar_one())

    claims = await _count(select(func.count()).select_from(Claim).where(Claim.run_id == run_id))
    evidence = await _count(select(func.count()).select_from(Evidence).where(Evidence.created_by_run_id == run_id))
    findings = await _count(select(func.count()).select_from(Finding).where(Finding.run_id == run_id))
    sources = await _count(select(func.count()).select_from(Source).where(Source.created_by_run_id == run_id))
    documents = await _count(
        select(func.count()).select_from(Document).join(Source, Document.source_id == Source.id)
        .where(Source.created_by_run_id == run_id))
    chunks = await _count(
        select(func.count()).select_from(Chunk).join(Document, Chunk.document_id == Document.id)
        .join(Source, Document.source_id == Source.id).where(Source.created_by_run_id == run_id))
    return {"sources": sources, "documents": documents, "chunks": chunks,
            "claims": claims, "evidence": evidence, "findings": findings}


async def project_live_run(
    *,
    live_run_id: str,
    task_id: str,
    query: str,
    brief: dict,
    source_documents: list[dict] | None,
    created_by: str | None = None,
) -> dict:
    """Project one completed live-research run into the canonical store.

    Returns the projection report; NEVER raises. On total failure the
    transaction is rolled back (no partial canonical run is left behind)
    and the report carries status ``failed`` with the degradations that
    explain why. Partial losses (one document un-ingestable, one quote
    unlocatable) degrade the report but do not fail the projection.
    """
    report: dict[str, Any] = {"status": "failed", "canonical_run_id": None,
                              "counts": dict(_ZERO_COUNTS), "degradations": []}
    try:
        from sqlalchemy import select
        from sqlalchemy.exc import IntegrityError

        from intelx.core.enums import (
            ClaimOrigin,
            ClaimType,
            EvidenceSupportType,
            RunOutcome,
            RunStatus,
            SourceKind,
        )
        from intelx.db.models import Finding, ResearchRun
        from intelx.db.repos import ClaimRepo, EvidenceRepo, RunRepo
        from intelx.db.session import get_sessionmaker, get_write_lock
        from intelx.memory.normalize import ingest_and_normalize

        key = _idempotency_key(live_run_id)
        sessionmaker = get_sessionmaker()
        async with get_write_lock():
            async with sessionmaker() as session:
                existing = (
                    await session.execute(
                        select(ResearchRun).where(ResearchRun.idempotency_key == key)
                    )
                ).scalar_one_or_none()
                if existing is not None:
                    report["status"] = "already_projected"
                    report["canonical_run_id"] = existing.id
                    report["counts"] = await _run_counts(session, existing.id)
                    return report

                run = await RunRepo.create_run(
                    session,
                    objective=str(query)[:4000],
                    scope_json={
                        "origin": "live_research_projection",
                        "live_run_id": live_run_id,
                        "task_id": task_id,
                        "answer_kind": brief.get("answer_kind"),
                        "synthesis_status": brief.get("synthesis_status"),
                    },
                    created_by=created_by,
                    idempotency_key=key,
                )
                run.started_at = run.created_at

                # Ingest the brief's source documents through the existing
                # machinery (content-hash dedupe; spans are computed over
                # the same text the quotes were aligned to). Each ingest
                # runs in a savepoint so one bad document cannot poison
                # the transaction for the rest (the SEN-003 pattern).
                doc_by_sid: dict[str, tuple] = {}
                for sdoc in source_documents or []:
                    sid = str(sdoc.get("source_id") or "")
                    url = str(sdoc.get("url") or "")
                    text = str(sdoc.get("text") or "")
                    if not sid or not url or not text:
                        continue
                    try:
                        async with session.begin_nested():
                            source, document, chunks, _created = await ingest_and_normalize(
                                session,
                                raw_bytes=text.encode("utf-8"),
                                location=url,
                                kind=SourceKind.WEB,
                                content_type="text/plain",
                                title=(str(sdoc.get("title") or "")[:512] or None),
                                domain=urlsplit(url).hostname,
                                created_by_run_id=run.id,
                            )
                    except Exception as exc:
                        report["degradations"].append(
                            {"kind": "document_ingest_failed", "source_url": url,
                             "error": type(exc).__name__})
                        continue
                    doc_by_sid[sid] = (source, document, chunks)
                    report["counts"]["sources"] += 1
                    report["counts"]["documents"] += 1
                    report["counts"]["chunks"] += len(chunks)

                # Claims (span-enforced by ClaimRepo) + one supporting
                # Evidence row per claim, each pair in its own savepoint.
                claim_ids: list[str] = []
                findings_in = brief.get("findings") or []
                for finding in findings_in:
                    if not isinstance(finding, dict):
                        continue
                    citations = finding.get("citations") or []
                    citation = citations[0] if citations and isinstance(citations[0], dict) else {}
                    sid = str(citation.get("source_id") or "")
                    entry = doc_by_sid.get(sid)
                    if entry is None:
                        report["degradations"].append(
                            {"kind": "claim_source_not_ingested",
                             "source_url": str(citation.get("source_url") or "")})
                        continue
                    source, document, chunks = entry
                    span = _locate_span(document.text, str(finding.get("quote") or ""))
                    if span is None:
                        report["degradations"].append(
                            {"kind": "quote_not_span_locatable",
                             "source_url": str(citation.get("source_url") or "")})
                        continue
                    start, end = span
                    quote = document.text[start:end]
                    chunk = _chunk_for_span(chunks, start, end)
                    if chunk is None:
                        report["degradations"].append(
                            {"kind": "document_has_no_chunks",
                             "source_url": str(citation.get("source_url") or "")})
                        continue
                    origin = (ClaimOrigin.EXTRACTED
                              if finding.get("status") == "source_excerpt"
                              else ClaimOrigin.INFERRED)
                    try:
                        async with session.begin_nested():
                            claim = await ClaimRepo.create_claim(
                                session,
                                run_id=run.id,
                                source_id=source.id,
                                document_id=document.id,
                                chunk_id=chunk.id,
                                text_content=str(finding.get("statement") or quote),
                                quote=quote,
                                span_start=start,
                                span_end=end,
                                claim_type=ClaimType.FACT,
                                confidence=(EXTRACTIVE_CONFIDENCE if origin is ClaimOrigin.EXTRACTED
                                            else INFERRED_CONFIDENCE),
                                confidence_method=CONFIDENCE_METHOD,
                                origin=origin,
                                created_by_agent=PROJECTION_AGENT,
                            )
                            await EvidenceRepo.create_evidence(
                                session,
                                claim_id=claim.id,
                                source_id=source.id,
                                document_id=document.id,
                                chunk_id=chunk.id,
                                span_start=start,
                                span_end=end,
                                quote=quote,
                                support_type=EvidenceSupportType.SUPPORTS,
                                created_by_run_id=run.id,
                                created_by_agent=PROJECTION_AGENT,
                            )
                    except Exception as exc:
                        report["degradations"].append(
                            {"kind": "claim_write_failed",
                             "source_url": str(citation.get("source_url") or ""),
                             "error": type(exc).__name__})
                        continue
                    claim_ids.append(claim.id)
                    report["counts"]["claims"] += 1
                    report["counts"]["evidence"] += 1

                if findings_in and not claim_ids:
                    # The brief carried findings but not one could be
                    # span-verified into the store: the projection failed
                    # its purpose. Roll everything back rather than leave
                    # a hollow run behind.
                    await session.rollback()
                    report["degradations"].append(
                        {"kind": "projection_failed",
                         "error": "no_span_valid_claims"})
                    return report

                if claim_ids:
                    gaps: list[str] = []
                    downgraded = brief.get("downgraded_findings") or []
                    if downgraded:
                        gaps.append(
                            f"{len(downgraded)} draft finding(s) downgraded at live "
                            "re-verification; not projected")
                    synthesis_error = brief.get("synthesis_error") or {}
                    if isinstance(synthesis_error, dict) and synthesis_error.get("reason"):
                        gaps.append(f"synthesis failed: {synthesis_error['reason']}")
                    session.add(Finding(
                        run_id=run.id,
                        conclusion=(str(brief.get("summary") or "")[:4000]
                                    or "Live research run projected from the synchronous live route."),
                        confidence=FINDING_CONFIDENCE,
                        confidence_method=CONFIDENCE_METHOD,
                        claim_ids_json=claim_ids,
                        gaps_json=gaps,
                        contradictions_json=[],
                        unverified_json=["not_independently_verified"],
                    ))
                    await session.flush()
                    report["counts"]["findings"] = 1

                if not claim_ids:
                    outcome = (RunOutcome.NO_EVIDENCE_FOUND if not brief.get("sources")
                               else RunOutcome.INSUFFICIENT_EVIDENCE)
                elif brief.get("status") == "SUCCESS":
                    outcome = RunOutcome.ANSWERED
                else:
                    outcome = RunOutcome.INSUFFICIENT_EVIDENCE
                await RunRepo.set_status(session, run.id, RunStatus.COMPLETED, outcome=outcome)
                try:
                    await session.commit()
                except IntegrityError:
                    # A concurrent projection of the same live run won the
                    # idempotency-key race; report the existing run.
                    await session.rollback()
                    existing = (
                        await session.execute(
                            select(ResearchRun).where(ResearchRun.idempotency_key == key)
                        )
                    ).scalar_one_or_none()
                    if existing is not None:
                        report["status"] = "already_projected"
                        report["canonical_run_id"] = existing.id
                        report["counts"] = await _run_counts(session, existing.id)
                        return report
                    raise
                report["status"] = "projected"
                report["canonical_run_id"] = run.id
                return report
    except Exception as exc:  # projection must never break the live answer
        logger.warning("canonical projection failed for live run %s (%s)",
                       live_run_id, type(exc).__name__)
        report["status"] = "failed"
        report["canonical_run_id"] = None
        report["counts"] = dict(_ZERO_COUNTS)
        report["degradations"].append(
            {"kind": "projection_failed", "error": type(exc).__name__})
        return report


async def project_and_annotate(
    envelope: dict,
    *,
    live_run_id: str,
    task_id: str,
    query: str,
    source_documents: list[dict] | None,
    created_by: str | None = None,
) -> dict:
    """Project a persisted live run and stamp the outcome on its envelope.

    The stamp is the full report on ``result.canonical_projection``, the
    status (and canonical run id, when one exists) in the receipt's
    verification evidence, and any degradations appended to a top-level
    ``degradations`` list. NEVER raises: the live answer is already
    complete and durable in ``live_research_runs`` before this runs.
    """
    result = envelope.get("result") if isinstance(envelope.get("result"), dict) else {}
    if "findings" not in result:
        # Timeout / invalid-pipeline envelopes carry no completed brief;
        # there is nothing truthful to project.
        projection = {"status": "skipped", "canonical_run_id": None,
                      "counts": dict(_ZERO_COUNTS), "degradations": [],
                      "reason": "no_completed_brief"}
    else:
        projection = await project_live_run(
            live_run_id=live_run_id, task_id=task_id, query=query,
            brief=result, source_documents=source_documents,
            created_by=created_by)
    try:
        if isinstance(envelope.get("result"), dict):
            envelope["result"]["canonical_projection"] = projection
        receipt = envelope.get("receipt")
        if isinstance(receipt, dict):
            evidence = receipt.get("verification_evidence")
            if isinstance(evidence, dict):
                evidence["canonical_projection"] = projection["status"]
                if projection.get("canonical_run_id"):
                    evidence["canonical_run_id"] = projection["canonical_run_id"]
        if projection["degradations"]:
            existing = envelope.get("degradations")
            envelope["degradations"] = (
                existing if isinstance(existing, list) else []
            ) + projection["degradations"]
    except Exception:  # annotation must never break the live answer either
        logger.warning("canonical projection annotation failed for live run %s",
                       live_run_id, exc_info=True)
    return projection
