#!/usr/bin/env python3
"""Corpus-wide citation-integrity audit over stored INTELX research.

TASK-INT-008. READ-ONLY: this script issues SELECT statements only and never
commits. It loads every stored claim with the source/document/chunk rows it
references, runs the mechanical checks from
``intelx.core.citation_integrity`` (citation exists / source actually
retrieved / quote matches the document span / claim wording supported by the
quote / origin not INFERRED), and then audits every stored finding twice:

* BEFORE — the presentation the pipeline actually shipped: findings stored
  without an unverified marker were presented as fact. A shipped finding
  counts as a failure when none of its cited claims is mechanically
  verified.
* AFTER — the same stored findings re-partitioned through the fixed
  ``filter_and_ground_findings`` with the integrity map applied. A finding
  counts as a failure when it still lands in the grounded partition without
  a mechanically verified claim.

Usage:
    python3 scripts/audit_citation_integrity.py [--json-out PATH]

With no arguments it uses the configured INTELX database (Oracle in
production). For a local test database set INTELX_ENV=test and pass
``--db-url sqlite+aiosqlite:////path/to.db``.
"""

from __future__ import annotations

import argparse
import asyncio
import json
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from intelx.core.citation_integrity import audit_corpus, audit_finding, check_claims
from intelx.core.report import filter_and_ground_findings
from intelx.db.engine import dispose_engine, get_async_engine
from intelx.db.models import Chunk, Claim, Document, Finding, Source


async def run_audit(db_url: str | None) -> dict[str, Any]:
    engine = get_async_engine(db_url)
    maker = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
    async with maker() as session:
        claims = list((await session.execute(select(Claim))).scalars().all())
        source_ids = {c.source_id for c in claims if c.source_id}
        document_ids = {c.document_id for c in claims if c.document_id}
        chunk_ids = {c.chunk_id for c in claims if c.chunk_id}
        sources = (
            list(
                (await session.execute(select(Source).where(Source.id.in_(source_ids))))
                .scalars()
                .all()
            )
            if source_ids
            else []
        )
        documents = (
            list(
                (
                    await session.execute(
                        select(Document).where(Document.id.in_(document_ids))
                    )
                )
                .scalars()
                .all()
            )
            if document_ids
            else []
        )
        chunks = (
            list(
                (await session.execute(select(Chunk).where(Chunk.id.in_(chunk_ids))))
                .scalars()
                .all()
            )
            if chunk_ids
            else []
        )
        findings = list((await session.execute(select(Finding))).scalars().all())

    sources_by_id = {str(s.id): s for s in sources}
    documents_by_id = {str(d.id): d for d in documents}
    chunks_by_id = {str(c.id): c for c in chunks}
    claims_by_id = {str(c.id): c for c in claims}

    integrity = check_claims(claims, sources_by_id, documents_by_id, chunks_by_id)
    corpus = audit_corpus(claims, sources_by_id, documents_by_id, chunks_by_id)

    # BEFORE: what the shipped pipeline presented as fact.
    presented_as_fact = [f for f in findings if not (f.unverified_json or [])]
    before_failures = []
    for f in presented_as_fact:
        support = audit_finding(
            {"claim_ids": list(f.claim_ids_json or [])}, claims_by_id, integrity
        )
        if support.verdict != "grounded":
            before_failures.append(
                {
                    "finding_id": str(f.id),
                    "run_id": str(f.run_id),
                    "verdict": support.verdict,
                    "reasons": list(support.reasons),
                }
            )

    # AFTER: re-partition every stored finding through the fixed pipeline code.
    # Each rebuilt finding carries its corpus index so partition membership can
    # be traced back to the stored row exactly.
    shipped_idx = {i for i, f in enumerate(findings) if not (f.unverified_json or [])}
    rebuilt = [
        {"statement": f.conclusion, "claim_ids": list(f.claim_ids_json or []), "_idx": i}
        for i, f in enumerate(findings)
    ]
    try:
        grounded_after, unverified_after = filter_and_ground_findings(
            rebuilt, claims_by_id, integrity_by_claim=integrity
        )
        after_source = "fixed filter_and_ground_findings (integrity-aware)"
    except TypeError:
        # Running against a tree that predates the fix: partition by the
        # audit verdicts instead (a finding is grounded iff at least one
        # cited claim is grounding_ok — the same predicate the fixed
        # filter applies) and disclose the substitution in the output.
        after_source = "verdict equivalence (tree predates the fixed filter)"
        grounded_after, unverified_after = [], []
        for f in rebuilt:
            support = audit_finding(f, claims_by_id, integrity)
            (grounded_after if support.verdict == "grounded" else unverified_after).append(f)
    after_failures = []
    for f in grounded_after:
        support = audit_finding(f, claims_by_id, integrity)
        if support.verdict != "grounded":
            after_failures.append(
                {"statement": f.get("statement", "")[:80], "verdict": support.verdict}
            )
    relabelled_count = sum(1 for f in unverified_after if f.get("_idx") in shipped_idx)

    example_claim_failures = [
        {"claim_id": cid, "failures": list(r.failures)}
        for cid, r in list(integrity.items())
        if not r.grounding_ok
    ][:10]

    summary: dict[str, Any] = {
        "claims": {
            "total": corpus.total_claims,
            "failing_any_check": corpus.claims_failing_any,
            "failure_rate": round(corpus.claim_failure_rate, 4),
            "exists_failures": corpus.exists_failures,
            "retrieved_failures": corpus.retrieved_failures,
            "span_failures": corpus.span_failures,
            "wording_failures": corpus.wording_failures,
            "inference_origin_claims": corpus.inference_claims,
            "status_failures": corpus.status_failures,
        },
        "findings": {
            "total": len(findings),
            "presented_as_fact_before": len(presented_as_fact),
            "before_failures": len(before_failures),
            "before_failure_rate": round(
                len(before_failures) / len(presented_as_fact), 4
            )
            if presented_as_fact
            else 0.0,
            "after_partition_source": after_source,
            "grounded_after": len(grounded_after),
            "unverified_after": len(unverified_after),
            "after_failures": len(after_failures),
            "after_failure_rate": round(
                len(after_failures) / len(grounded_after), 4
            )
            if grounded_after
            else 0.0,
            "shipped_as_fact_now_relabelled_inference": relabelled_count,
        },
        "example_claim_failures": example_claim_failures,
        "example_finding_failures_before": before_failures[:10],
    }
    await dispose_engine()
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db-url", default=None, help="Explicit DB URL (test suite only)")
    parser.add_argument("--json-out", default=None, help="Also write the JSON summary here")
    args = parser.parse_args()
    summary = asyncio.run(run_audit(args.db_url))
    text = json.dumps(summary, indent=2, default=str)
    print(text)
    if args.json_out:
        with open(args.json_out, "w") as fh:
            fh.write(text + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
