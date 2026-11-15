"""TASK-INT-004: pre-synthesis source-diversity check.

Covers the pure module (domain keys, near-duplicate clustering, collapse,
per-finding independent-source annotation) and the pipeline wiring in
collect_live_brief: two outlets republishing the same wire copy must reach
the synthesizer as ONE document, and every finding must carry its
independent-source count and single-source flag on the result.
"""
import hashlib
from types import SimpleNamespace

import pytest

from intelx.api.source_diversity import (
    annotate_findings,
    build_diversity_report,
    cluster_documents,
    collapse_documents,
    source_domain,
    text_similarity,
)
from intelx.api.live_research_task import collect_live_brief


WIRE_TEXT = (
    "Researchers at the national laboratory announced a quantum sensor "
    "breakthrough on Tuesday after years of careful measurement work. "
    "The new device detects magnetic fields with unprecedented precision "
    "using cooled atoms trapped inside a small glass chamber. "
    "Independent engineers described the result as a significant step for "
    "navigation systems that cannot rely on satellite signals."
)
WIRE_TEXT_VARIANT = WIRE_TEXT.replace("on Tuesday", "this week").replace(
    "small glass chamber", "compact glass chamber")
DISTINCT_TEXT = (
    "A field team in Bengaluru has begun testing a portable quantum sensor "
    "aboard survey trucks that crisscross remote mining districts. "
    "The prototype quantum sensor rides in a padded crate and logs gravity "
    "changes while drivers pause at marked waypoints along dirt roads. "
    "Investors backing the venture say rugged packaging matters more than "
    "laboratory records when prospectors hunt underground ore bodies."
)


def _doc(sid, url, text):
    return {"source_id": sid, "title": url, "url": url, "text": text}


# ── module units ─────────────────────────────────────────────────────────

def test_source_domain_strips_www_and_case():
    assert source_domain("https://www.Reuters.com/article/1") == "reuters.com"
    assert source_domain("https://apnews.com/x") == "apnews.com"
    assert source_domain("") == ""


def test_text_similarity_identical_and_disjoint():
    assert text_similarity(WIRE_TEXT, WIRE_TEXT) == 1.0
    assert text_similarity(WIRE_TEXT, DISTINCT_TEXT) < 0.5
    assert text_similarity("", WIRE_TEXT) == 0.0


def test_cluster_collapses_wire_copy_across_domains():
    docs = [_doc("a", "https://www.reuters.com/1", WIRE_TEXT),
            _doc("b", "https://news.yahoo.com/2", WIRE_TEXT_VARIANT),
            _doc("c", "https://example.net/3", DISTINCT_TEXT)]
    cluster_of, groups = cluster_documents(docs)
    assert cluster_of["a"] == cluster_of["b"]
    assert cluster_of["c"] != cluster_of["a"]
    (group,) = groups
    assert sorted(group["domains"]) == ["news.yahoo.com", "reuters.com"]
    collapsed = collapse_documents(docs, cluster_of)
    assert [d["source_id"] for d in collapsed] == ["a", "c"]


def test_annotate_counts_clusters_not_citations():
    docs = [_doc("a", "https://www.reuters.com/1", WIRE_TEXT),
            _doc("b", "https://news.yahoo.com/2", WIRE_TEXT_VARIANT),
            _doc("c", "https://example.net/3", DISTINCT_TEXT)]
    cluster_of, _ = cluster_documents(docs)
    findings = [
        {"statement": "wire claim", "citations": [{"source_id": "a"}, {"source_id": "b"}]},
        {"statement": "corroborated claim", "citations": [{"source_id": "a"}, {"source_id": "c"}]},
        {"statement": "lone claim", "citations": [{"source_id": "c"}]},
    ]
    annotated = annotate_findings(findings, docs, cluster_of)
    # Two citations into one wire-copy cluster = ONE independent source.
    assert annotated[0]["independent_source_count"] == 1
    assert annotated[0]["diversity_flag"] == "single_source"
    assert annotated[1]["independent_source_count"] == 2
    assert annotated[1]["diversity_flag"] == "multi_source"
    assert annotated[2]["independent_source_count"] == 1
    assert annotated[2]["diversity_flag"] == "single_source"


def test_report_shape_and_share():
    docs = [_doc("a", "https://www.reuters.com/1", WIRE_TEXT),
            _doc("b", "https://news.yahoo.com/2", WIRE_TEXT_VARIANT)]
    cluster_of, groups = cluster_documents(docs)
    findings = [{"statement": "x", "citations": [{"source_id": "a"}]}]
    report = build_diversity_report(findings, docs, cluster_of, groups)
    assert report["documents_retrieved"] == 2
    assert report["distinct_domains"] == 2
    assert report["independent_sources"] == 1
    assert report["single_source_findings"] == 1
    assert report["single_source_share"] == 1.0


# ── pipeline integration ─────────────────────────────────────────────────

class _Search:
    def __init__(self, results):
        self._results = results

    async def fetch(self, query, max_results=10):
        return self._results


class _Fetch:
    def __init__(self, pages):
        self._pages = pages

    async def fetch(self, url, max_bytes=1_000_000):
        return SimpleNamespace(status_code=200, content_type="text/plain",
                               final_url=url, content=self._pages[url].encode())


def _candidate(url, title):
    return SimpleNamespace(url=url, title=title)


def _sid(url):
    return hashlib.sha256(url.encode()).hexdigest()[:16]


WIRE_A = "https://www.reuters.com/quantum-sensor"
WIRE_B = "https://news.yahoo.com/quantum-sensor"
DISTINCT = "https://example.net/gravimeter-startup"
QUERY = "quantum sensor breakthrough research"


@pytest.mark.asyncio
async def test_wire_copy_collapses_before_synthesis():
    pages = {WIRE_A: WIRE_TEXT, WIRE_B: WIRE_TEXT, DISTINCT: DISTINCT_TEXT}
    search = _Search([_candidate(WIRE_A, "Wire A"), _candidate(WIRE_B, "Wire B"),
                      _candidate(DISTINCT, "Distinct")])
    received = {}

    async def synthesize(query, documents):
        received["documents"] = documents
        return {"status": "SUCCESS", "answer_kind": "source_attributed_model_draft",
                "quotes_verified": True, "semantic_entailment_verified": False,
                "synthesis_provider": "test",
                "findings": [{"statement": "A quantum sensor breakthrough was announced.",
                              "quote": "quantum sensor breakthrough",
                              "status": "source_attributed_model_draft",
                              "citations": [{"source_id": _sid(WIRE_A),
                                             "source_title": "Wire A",
                                             "source_url": WIRE_A}]}]}

    result = await collect_live_brief(QUERY, search, _Fetch(pages), synthesize=synthesize)
    # The synthesizer saw two independent documents, not three.
    assert len(received["documents"]) == 2
    report = result["source_diversity"]
    assert report["documents_retrieved"] == 3
    assert report["distinct_domains"] == 3
    assert report["independent_sources"] == 2
    (group,) = report["collapsed_groups"]
    assert sorted(group["domains"]) == ["news.yahoo.com", "reuters.com"]
    (finding,) = result["findings"]
    assert finding["independent_source_count"] == 1
    assert finding["diversity_flag"] == "single_source"


@pytest.mark.asyncio
async def test_extractive_findings_are_flagged_too():
    pages = {WIRE_A: WIRE_TEXT, DISTINCT: DISTINCT_TEXT}
    search = _Search([_candidate(WIRE_A, "Wire A"), _candidate(DISTINCT, "Distinct")])
    result = await collect_live_brief(QUERY, search, _Fetch(pages))
    report = result["source_diversity"]
    assert report["documents_retrieved"] == 2
    assert report["independent_sources"] == 2
    assert result["findings"], "expected extractive findings"
    # Every extractive finding cites exactly one document, so the flag must
    # say so on every one — that is the audit's headline, surfaced not hidden.
    assert report["single_source_share"] == 1.0
    assert all(f["diversity_flag"] == "single_source" for f in result["findings"])
