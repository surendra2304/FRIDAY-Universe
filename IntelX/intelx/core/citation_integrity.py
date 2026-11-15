"""Mechanical citation-integrity verification for INTELX claims and findings.

TASK-INT-008. The pre-existing machinery verified fragments of the citation
chain in isolation: ``ClaimRepo`` enforces ``quote == document[span]`` when a
claim is created through the repository, ``ClaimVerifier`` checks evidence
spans during analysis, and ``CitationValidator`` checks that ``[S:id]`` /
``[C:id]`` tokens in a rendered report resolve to known IDs. None of that
gates what the synthesizer presents as fact: grounding only required a claim
row to exist with ACTIVE status, so a stored claim whose quote no longer
matches its document, whose source was never actually retrieved, whose
wording outruns its quote, or whose origin is INFERRED could still ground a
"Key Finding" presented as verified fact.

This module is the missing output-side check. For every claim it verifies,
mechanically and deterministically (no model calls):

  (a) EXISTS    — the claim's source, document and chunk rows all resolve,
                  and the document/chunk linkage is consistent;
  (b) RETRIEVED — the source was actually retrieved: it carries a retrieval
                  timestamp, a stored document with non-empty text exists,
                  and the claim's chunk is a faithful slice of that document
                  (``chunk.text == document.text[chunk.start:end]``);
  (c) SUPPORTS  — the claim's verbatim quote is exactly the document slice at
                  ``[span_start:span_end]``, and the claim's own wording is
                  supported by that quote: every number appearing in the
                  claim text must appear in the quote, and the claim's
                  content words must be contained in the quote at or above
                  ``WORDING_MIN_CONTAINMENT``. A figure computed from the
                  quote (rather than stated in it) fails this check on
                  purpose: a derived figure is an inference, not a citation.

Claims with origin INFERRED are inference-grade by construction and can
never ground a finding presented as fact, however clean their spans are.

A claim is ``grounding_ok`` only when every check passes, its origin is
EXTRACTED and its status is ACTIVE or VERIFIED. The synthesizer uses this to
partition findings: anything without at least one ``grounding_ok`` claim is
labelled as inference instead of being presented as fact. The corpus audit
in ``scripts/audit_citation_integrity.py`` runs the same checks over stored
research to measure the failure rate.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

# Fraction of a claim's content words that must appear in its quote for the
# claim's wording to count as supported by the quote.
WORDING_MIN_CONTAINMENT = 0.5

_GROUNDING_STATUSES = {"ACTIVE", "VERIFIED"}

_STOPWORDS = frozenset(
    """
    a an the and or but if then else of at by for with about into through
    during before after above below to from up down in out on off over under
    again further once here there when where why how all any both each few
    more most other some such no nor not only own same so than too very can
    will just is are was were be been being have has had having do does did
    doing would should could ought i you he she it we they them his her its
    our their this that these those am as was were per via etc also one two
    """.split()
)

_NUMBER_RE = re.compile(r"\d[\d,]*(?:\.\d+)?")
_WORD_RE = re.compile(r"[a-z][a-z0-9'-]*")


def _get(obj: Any, field_name: str, default: Any = None) -> Any:
    """Safely extract a field from an ORM object or a dict."""
    if obj is None:
        return default
    if isinstance(obj, dict):
        val = obj.get(field_name, default)
    else:
        val = getattr(obj, field_name, default)
    return val if val is not None else default


def _enum_str(value: Any) -> str:
    return str(getattr(value, "value", value) or "").upper()


def _resolve(target: str, ids: set[str]) -> str | None:
    """Resolve an exact ID or a unique prefix against a set of IDs."""
    if target in ids:
        return target
    matches = [i for i in ids if i.startswith(target)]
    return matches[0] if len(matches) == 1 else None


def _numbers(text: str) -> set[str]:
    """Normalised numeric tokens in *text* (commas and trailing zeros removed)."""
    out: set[str] = set()
    for raw in _NUMBER_RE.findall(text or ""):
        token = raw.replace(",", "")
        if "." in token:
            token = token.rstrip("0").rstrip(".")
        else:
            token = token.lstrip("0") or "0"
        out.add(token)
    return out


def _content_words(text: str) -> set[str]:
    """Lowercased content words (stopwords removed, possessives stripped)."""
    words: set[str] = set()
    for w in _WORD_RE.findall((text or "").lower()):
        w = w.strip("'-")
        if w.endswith("'s"):
            w = w[:-2]
        if len(w) >= 3 and w not in _STOPWORDS:
            words.add(w)
    return words


def _word_supported(word: str, quote_words: set[str]) -> bool:
    if word in quote_words:
        return True
    # Light singular/plural tolerance.
    if word.endswith("s") and len(word) > 3 and word[:-1] in quote_words:
        return True
    if word + "s" in quote_words:
        return True
    return False


@dataclass(frozen=True, slots=True)
class ClaimIntegrity:
    """Mechanical verification outcome for a single stored claim."""

    claim_id: str
    exists: bool
    retrieved: bool
    span_verified: bool
    wording_supported: bool
    is_inference: bool
    status_ok: bool
    grounding_ok: bool
    failures: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class FindingSupport:
    """Whether a finding's cited claims mechanically support it as fact."""

    verdict: str  # "grounded" | "inference_only" | "unsupported"
    grounding_claim_ids: tuple[str, ...] = ()
    reasons: tuple[str, ...] = ()


def check_claim(claim: Any, source: Any, document: Any, chunk: Any) -> ClaimIntegrity:
    """Run checks (a) exists, (b) retrieved, (c) supports for one claim.

    ``source``/``document``/``chunk`` are the rows the claim references (or
    ``None`` when the referenced row does not exist).
    """
    claim_id = str(_get(claim, "id", ""))
    failures: list[str] = []

    source_id = str(_get(claim, "source_id", "") or "")
    document_id = str(_get(claim, "document_id", "") or "")
    chunk_id = str(_get(claim, "chunk_id", "") or "")

    # (a) EXISTS — every referenced row resolves and linkage is consistent.
    exists = True
    if source is None:
        exists = False
        failures.append(f"source {source_id or '?'} not found")
    if document is None:
        exists = False
        failures.append(f"document {document_id or '?'} not found")
    if chunk is None:
        exists = False
        failures.append(f"chunk {chunk_id or '?'} not found")
    if document is not None and str(_get(document, "source_id", "")) != source_id:
        exists = False
        failures.append("document belongs to a different source than the claim")
    if (
        document is not None
        and chunk is not None
        and str(_get(chunk, "document_id", "")) != str(_get(document, "id", ""))
    ):
        exists = False
        failures.append("chunk does not belong to the claim's document")

    # (b) RETRIEVED — a real fetch stands behind the source/document/chunk.
    retrieved = True
    doc_text = _get(document, "text", "") if document is not None else ""
    if source is not None and _get(source, "retrieved_at") is None:
        retrieved = False
        failures.append("source has no retrieval timestamp")
    if document is not None and not str(doc_text or "").strip():
        retrieved = False
        failures.append("stored document text is empty — nothing was retrieved")
    if document is not None and chunk is not None:
        c_start = _get(chunk, "start_char")
        c_end = _get(chunk, "end_char")
        if (
            isinstance(c_start, int)
            and isinstance(c_end, int)
            and 0 <= c_start <= c_end <= len(str(doc_text))
            and str(doc_text)[c_start:c_end] != str(_get(chunk, "text", ""))
        ):
            retrieved = False
            failures.append("chunk text is not a faithful slice of the document")
    # Missing rows already failed (a); retrieval cannot be established without them.
    retrieved = retrieved and source is not None and document is not None and chunk is not None

    # (c1) SUPPORTS — the verbatim quote is exactly the document slice.
    span_verified = False
    quote = str(_get(claim, "quote", "") or "")
    span_start = _get(claim, "span_start")
    span_end = _get(claim, "span_end")
    if document is None:
        failures.append("span cannot be verified: document missing")
    elif not quote:
        failures.append("claim carries no verbatim quote")
    elif not (
        isinstance(span_start, int)
        and isinstance(span_end, int)
        and 0 <= span_start <= span_end <= len(str(doc_text))
    ):
        failures.append(f"span [{span_start}:{span_end}] is out of bounds for the document")
    elif str(doc_text)[span_start:span_end] != quote:
        failures.append("quote does not match the document text at the claimed span")
    else:
        span_verified = True

    # (c2) SUPPORTS — the claim's own wording is supported by its quote.
    wording_supported = False
    claim_text = str(_get(claim, "text", "") or "")
    if not claim_text.strip():
        failures.append("claim text is empty")
    elif not quote:
        failures.append("claim wording cannot be checked: no quote")
    else:
        claim_numbers = _numbers(claim_text)
        quote_numbers = _numbers(quote)
        missing_numbers = claim_numbers - quote_numbers
        claim_words = _content_words(claim_text)
        quote_words = _content_words(quote)
        if missing_numbers:
            failures.append(
                "claim wording states number(s) absent from its quote: "
                + ", ".join(sorted(missing_numbers))
            )
        if not claim_words:
            failures.append("claim text has no checkable content words")
            containment = 0.0
        else:
            supported = sum(1 for w in claim_words if _word_supported(w, quote_words))
            containment = supported / len(claim_words)
            if containment < WORDING_MIN_CONTAINMENT:
                failures.append(
                    f"claim wording is not supported by its quote "
                    f"(content-word containment {containment:.2f} < {WORDING_MIN_CONTAINMENT})"
                )
        wording_supported = not missing_numbers and containment >= WORDING_MIN_CONTAINMENT

    is_inference = _enum_str(_get(claim, "origin", "EXTRACTED")) == "INFERRED"
    status_ok = _enum_str(_get(claim, "status", "ACTIVE")) in _GROUNDING_STATUSES

    grounding_ok = (
        exists
        and retrieved
        and span_verified
        and wording_supported
        and not is_inference
        and status_ok
    )
    return ClaimIntegrity(
        claim_id=claim_id,
        exists=exists,
        retrieved=retrieved,
        span_verified=span_verified,
        wording_supported=wording_supported,
        is_inference=is_inference,
        status_ok=status_ok,
        grounding_ok=grounding_ok,
        failures=tuple(failures),
    )


def check_claims(
    claims: list[Any],
    sources_by_id: dict[str, Any],
    documents_by_id: dict[str, Any],
    chunks_by_id: dict[str, Any],
) -> dict[str, ClaimIntegrity]:
    """Run :func:`check_claim` over a corpus, keyed by claim ID."""
    results: dict[str, ClaimIntegrity] = {}
    for claim in claims:
        cid = str(_get(claim, "id", "") or "")
        if not cid:
            continue
        results[cid] = check_claim(
            claim,
            sources_by_id.get(str(_get(claim, "source_id", "") or "")),
            documents_by_id.get(str(_get(claim, "document_id", "") or "")),
            chunks_by_id.get(str(_get(claim, "chunk_id", "") or "")),
        )
    return results


def audit_finding(
    finding: Any,
    claims_by_id: dict[str, Any],
    integrity_by_claim: dict[str, ClaimIntegrity],
) -> FindingSupport:
    """Decide whether a finding may be presented as fact.

    A finding is ``grounded`` only when at least one of its cited claims is
    mechanically verified (``grounding_ok``). It is ``inference_only`` when
    every resolvable claim is inference-grade or fails verification, and
    ``unsupported`` when it cites no resolvable claim at all.
    """
    raw_ids = _get(finding, "claim_ids") or _get(finding, "claim_ids_json") or []
    claim_ids = [str(c) for c in raw_ids if c]
    if not claim_ids:
        return FindingSupport(verdict="unsupported", reasons=("finding cites no claims",))

    known_ids = set(claims_by_id.keys())
    grounding: list[str] = []
    saw_resolvable = False
    saw_inference = False
    first_failures: tuple[str, ...] = ()
    for token in claim_ids:
        resolved = _resolve(token, known_ids)
        if resolved is None:
            continue
        saw_resolvable = True
        integrity = integrity_by_claim.get(resolved)
        if integrity is None:
            continue
        if integrity.grounding_ok:
            grounding.append(resolved)
        elif integrity.is_inference and integrity.exists and integrity.span_verified:
            saw_inference = True
        elif not first_failures and integrity.failures:
            first_failures = integrity.failures

    if grounding:
        return FindingSupport(verdict="grounded", grounding_claim_ids=tuple(grounding))
    if not saw_resolvable:
        return FindingSupport(
            verdict="unsupported",
            reasons=("none of the finding's cited claims resolve to stored claims",),
        )
    if saw_inference and not first_failures:
        return FindingSupport(
            verdict="inference_only",
            reasons=("supported only by inferred claims — no retrieved evidence",),
        )
    reasons = first_failures or ("no cited claim passed citation-integrity verification",)
    return FindingSupport(verdict="inference_only", reasons=reasons)


_KEY_FINDINGS_HEADING = "## Key Findings"
_INFERENCE_PREFIX = "[Inference] "


def label_unbacked_findings(report_markdown: str) -> str:
    """Prefix ``[Inference]`` to Key-Findings bullets that carry no citation.

    Safety net for the render/strip seam: citation validation strips
    unresolvable ``[C:]``/``[S:]`` tokens *after* rendering, which could
    otherwise leave a statement standing in Key Findings with neither a
    citation nor a label. Bullets already labelled, bullets with a surviving
    citation token, and the explicit "no verifiable findings" line are left
    untouched. Only the Key Findings section is modified.
    """
    lines = report_markdown.split("\n")
    in_section = False
    for i, line in enumerate(lines):
        if line.startswith("## "):
            in_section = line.strip() == _KEY_FINDINGS_HEADING
            continue
        if not in_section:
            continue
        if not line.startswith("- "):
            continue
        if "[C:" in line or "[S:" in line:
            continue
        if line.startswith("- " + _INFERENCE_PREFIX):
            continue
        if "No verifiable key findings" in line:
            continue
        lines[i] = "- " + _INFERENCE_PREFIX + line[2:]
    return "\n".join(lines)


@dataclass(frozen=True, slots=True)
class CorpusAudit:
    """Aggregate failure rates over a stored-research corpus."""

    total_claims: int = 0
    claims_failing_any: int = 0
    exists_failures: int = 0
    retrieved_failures: int = 0
    span_failures: int = 0
    wording_failures: int = 0
    inference_claims: int = 0
    status_failures: int = 0
    per_claim: dict[str, ClaimIntegrity] = field(default_factory=dict)

    @property
    def claim_failure_rate(self) -> float:
        return self.claims_failing_any / self.total_claims if self.total_claims else 0.0


def audit_corpus(
    claims: list[Any],
    sources_by_id: dict[str, Any],
    documents_by_id: dict[str, Any],
    chunks_by_id: dict[str, Any],
) -> CorpusAudit:
    """Aggregate :func:`check_claims` results into corpus failure rates."""
    per_claim = check_claims(claims, sources_by_id, documents_by_id, chunks_by_id)
    return CorpusAudit(
        total_claims=len(per_claim),
        claims_failing_any=sum(1 for r in per_claim.values() if not r.grounding_ok),
        exists_failures=sum(1 for r in per_claim.values() if not r.exists),
        retrieved_failures=sum(1 for r in per_claim.values() if not r.retrieved),
        span_failures=sum(1 for r in per_claim.values() if not r.span_verified),
        wording_failures=sum(1 for r in per_claim.values() if not r.wording_supported),
        inference_claims=sum(1 for r in per_claim.values() if r.is_inference),
        status_failures=sum(1 for r in per_claim.values() if not r.status_ok),
        per_claim=per_claim,
    )


__all__ = [
    "WORDING_MIN_CONTAINMENT",
    "ClaimIntegrity",
    "FindingSupport",
    "CorpusAudit",
    "check_claim",
    "check_claims",
    "audit_finding",
    "audit_corpus",
    "label_unbacked_findings",
]
