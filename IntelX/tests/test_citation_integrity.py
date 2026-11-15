"""TASK-INT-008: mechanical citation-integrity checks and the pipeline fix.

Covers the three verification levels — citation (a) exists, (b) was actually
retrieved, (c) supports the claim's wording — plus the synthesizer partition
behaviour: findings without a mechanically verified claim must be labelled
as inference, never presented as fact.
"""

from intelx.core.citation_integrity import (
    audit_finding,
    check_claim,
    check_claims,
    label_unbacked_findings,
)
from intelx.core.report import filter_and_ground_findings

QUOTE = "Acme Corp reported revenue of 250 million dollars in 2024"
DOC_TEXT = QUOTE + ", up from 200 million in 2023. The board approved a dividend."


def make_corpus():
    source = {"id": "src-1", "retrieved_at": "2026-11-15T00:00:00Z", "title": "Acme filing"}
    document = {"id": "doc-1", "source_id": "src-1", "text": DOC_TEXT}
    chunk = {
        "id": "chk-1",
        "document_id": "doc-1",
        "start_char": 0,
        "end_char": len(QUOTE),
        "text": QUOTE,
    }
    claim = {
        "id": "clm-1",
        "source_id": "src-1",
        "document_id": "doc-1",
        "chunk_id": "chk-1",
        "text": QUOTE,
        "quote": QUOTE,
        "span_start": 0,
        "span_end": len(QUOTE),
        "origin": "EXTRACTED",
        "status": "ACTIVE",
    }
    return claim, source, document, chunk


def corpus_maps(claim, source, document, chunk):
    return (
        {claim["id"]: claim},
        {source["id"]: source},
        {document["id"]: document},
        {chunk["id"]: chunk},
    )


# --- (a)/(b)/(c): the claim-level checks ------------------------------------


def test_clean_claim_is_grounding_ok():
    claim, source, document, chunk = make_corpus()
    result = check_claim(claim, source, document, chunk)
    assert result.exists and result.retrieved and result.span_verified
    assert result.wording_supported and not result.is_inference and result.status_ok
    assert result.grounding_ok and result.failures == ()


def test_missing_source_fails_exists():
    claim, source, document, chunk = make_corpus()
    result = check_claim(claim, None, document, chunk)
    assert not result.exists and not result.grounding_ok


def test_source_without_retrieval_timestamp_fails_retrieved():
    claim, source, document, chunk = make_corpus()
    source = {**source, "retrieved_at": None}
    result = check_claim(claim, source, document, chunk)
    assert not result.retrieved and not result.grounding_ok


def test_unfaithful_chunk_fails_retrieved():
    claim, source, document, chunk = make_corpus()
    chunk = {**chunk, "text": "tampered chunk text"}
    result = check_claim(claim, source, document, chunk)
    assert not result.retrieved and not result.grounding_ok


def test_quote_not_matching_span_fails_span():
    claim, source, document, chunk = make_corpus()
    claim = {**claim, "quote": "Acme Corp reported revenue of 999 million dollars in 2024"}
    result = check_claim(claim, source, document, chunk)
    assert not result.span_verified and not result.grounding_ok


def test_number_absent_from_quote_fails_wording():
    claim, source, document, chunk = make_corpus()
    claim = {**claim, "text": "Acme Corp reported revenue of 500 million dollars in 2024"}
    result = check_claim(claim, source, document, chunk)
    assert result.span_verified  # the quote itself is genuine
    assert not result.wording_supported and not result.grounding_ok


def test_drifted_wording_fails_wording():
    claim, source, document, chunk = make_corpus()
    claim = {**claim, "text": "The company faces imminent bankruptcy amid collapsing demand"}
    result = check_claim(claim, source, document, chunk)
    assert not result.wording_supported and not result.grounding_ok


def test_inferred_origin_never_grounds():
    claim, source, document, chunk = make_corpus()
    claim = {**claim, "origin": "INFERRED"}
    result = check_claim(claim, source, document, chunk)
    assert result.is_inference and result.span_verified
    assert not result.grounding_ok


def test_disputed_status_never_grounds():
    claim, source, document, chunk = make_corpus()
    claim = {**claim, "status": "DISPUTED"}
    result = check_claim(claim, source, document, chunk)
    assert not result.status_ok and not result.grounding_ok


def test_document_from_another_source_fails_exists():
    claim, source, document, chunk = make_corpus()
    document = {**document, "source_id": "src-other"}
    result = check_claim(claim, source, document, chunk)
    assert not result.exists and not result.grounding_ok


# --- finding-level audit -----------------------------------------------------


def test_audit_finding_grounded_by_verified_claim():
    claim, source, document, chunk = make_corpus()
    claims_by_id, sources, documents, chunks = corpus_maps(claim, source, document, chunk)
    integrity = check_claims([claim], sources, documents, chunks)
    support = audit_finding({"claim_ids": ["clm-1"]}, claims_by_id, integrity)
    assert support.verdict == "grounded"


def test_audit_finding_inference_only():
    claim, source, document, chunk = make_corpus()
    claim = {**claim, "origin": "INFERRED"}
    claims_by_id, sources, documents, chunks = corpus_maps(claim, source, document, chunk)
    integrity = check_claims([claim], sources, documents, chunks)
    support = audit_finding({"claim_ids": ["clm-1"]}, claims_by_id, integrity)
    assert support.verdict == "inference_only"


def test_audit_finding_unsupported_without_claims():
    support = audit_finding({"claim_ids": []}, {}, {})
    assert support.verdict == "unsupported"


# --- the pipeline fix: integrity-aware partition -----------------------------


def test_partition_moves_span_broken_finding_to_unverified():
    claim, source, document, chunk = make_corpus()
    claim = {**claim, "quote": "fabricated quote text"}
    claims_by_id, sources, documents, chunks = corpus_maps(claim, source, document, chunk)
    integrity = check_claims([claim], sources, documents, chunks)
    findings = [{"statement": "Acme revenue was 250 million.", "claim_ids": ["clm-1"]}]
    grounded, unverified = filter_and_ground_findings(
        findings, claims_by_id, integrity_by_claim=integrity
    )
    assert grounded == []
    assert len(unverified) == 1
    assert "Citation integrity check failed" in unverified[0]["unverified_reason"]


def test_partition_moves_inference_only_finding_to_unverified():
    claim, source, document, chunk = make_corpus()
    claim = {**claim, "origin": "INFERRED"}
    claims_by_id, sources, documents, chunks = corpus_maps(claim, source, document, chunk)
    integrity = check_claims([claim], sources, documents, chunks)
    findings = [{"statement": "Acme revenue was 250 million.", "claim_ids": ["clm-1"]}]
    grounded, unverified = filter_and_ground_findings(
        findings, claims_by_id, integrity_by_claim=integrity
    )
    assert grounded == []
    assert "inferred" in unverified[0]["unverified_reason"]


def test_partition_keeps_finding_with_one_verified_claim():
    claim, source, document, chunk = make_corpus()
    bad = {**claim, "id": "clm-2", "quote": "fabricated"}
    claims = [claim, bad]
    claims_by_id = {c["id"]: c for c in claims}
    integrity = check_claims(claims, {source["id"]: source}, {document["id"]: document}, {chunk["id"]: chunk})
    findings = [{"statement": "Acme revenue was 250 million.", "claim_ids": ["clm-2", "clm-1"]}]
    grounded, unverified = filter_and_ground_findings(
        findings, claims_by_id, integrity_by_claim=integrity
    )
    assert len(grounded) == 1 and unverified == []


def test_partition_legacy_behaviour_without_integrity_map():
    claim, source, document, chunk = make_corpus()
    claims_by_id, *_ = corpus_maps(claim, source, document, chunk)
    findings = [{"statement": "Acme revenue was 250 million.", "claim_ids": ["clm-1"]}]
    grounded, unverified = filter_and_ground_findings(findings, claims_by_id)
    assert len(grounded) == 1 and unverified == []


# --- the post-render labelling safety net ------------------------------------

REPORT = """# Research Report: Acme

## Key Findings
- Acme revenue was 250 million dollars in 2024 [Confidence: High] [C:clm-1] [S:src-1]
- Acme will surely double revenue next year [Confidence: High]
- [Inference] Acme might expand abroad [Confidence: Low]
- No verifiable key findings established within the given scope.

## Evidence Map
- A bullet outside the findings section without citations
"""


def test_label_unbacked_findings():
    labelled = label_unbacked_findings(REPORT)
    assert "- [Inference] Acme will surely double revenue next year" in labelled
    # Cited, already-labelled, placeholder and other-section lines untouched.
    assert "- Acme revenue was 250 million dollars in 2024 [Confidence: High] [C:clm-1]" in labelled
    assert "- [Inference] Acme might expand abroad" in labelled
    assert "- No verifiable key findings established" in labelled
    assert "- A bullet outside the findings section without citations" in labelled
    assert labelled.count("[Inference]") == 2
