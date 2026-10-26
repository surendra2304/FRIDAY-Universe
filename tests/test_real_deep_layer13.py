"""
Real Deep Layer 13 Tests — LearningCircuit/local-deep-research → Inference.

Functional tests for Inference/app/agents/real_deep_research.py:
engine registry, intent-aware query decomposition, BM25 corpus backend,
context compression with MMR de-duplication, the findings ledger, citation
registry/validator, the three search strategies (source-based, focused
iterative, parallel), and report generation.
"""

import importlib.util
import os
import sys

import pytest

MODULE_PATH = os.path.join(
    os.path.dirname(__file__), "..", "Inference", "app", "agents", "real_deep_research.py")

spec = importlib.util.spec_from_file_location("real_deep_research", MODULE_PATH)
dr = importlib.util.module_from_spec(spec)
sys.modules["real_deep_research"] = dr
spec.loader.exec_module(dr)


DOCS = [
    dr.Document(url="https://a.example/vec", title="Vector databases for RAG",
                body="Vector databases store embeddings and serve approximate nearest neighbour "
                     "queries. pgvector adds vector search to Postgres with HNSW indexes. "
                     "Query latency stays under 20 ms at one million vectors. "
                     "Recall at 10 neighbours was 94 percent with M=16.",
                published_year=2025),
    dr.Document(url="https://b.example/hnsw", title="HNSW tuning tradeoffs",
                body="HNSW builds a multi-layer proximity graph. ef_search controls recall and "
                     "latency. Raising ef_search from 40 to 200 improved recall to 98 percent "
                     "but doubled p99 latency to 41 ms.",
                published_year=2024),
    dr.Document(url="https://c.example/pg", title="pgvector in production",
                body="pgvector lets teams keep embeddings next to relational data. Operating "
                     "cost drops 60 percent. Index build time for five million vectors was "
                     "18 minutes.",
                published_year=2025),
    dr.Document(url="https://d.example/bread", title="Sourdough baking",
                body="Sourdough needs a starter, flour, water and salt. Fermentation takes "
                     "12 hours at room temperature.",
                published_year=2023),
]


@pytest.fixture()
def provider():
    return dr.BM25SearchProvider(documents=DOCS)


@pytest.fixture()
def engine(provider):
    return dr.DeepResearchEngine(provider=provider)


# ── engine registry ──────────────────────────────────────────────────────────

def test_registry_lists_engines_and_kinds():
    registry = dr.SearchEngineRegistry()
    names = registry.names()
    assert "searxng" in names and "arxiv" in names
    academic = [e.name for e in registry.by_kind("academic")]
    assert set(academic) == {"arxiv", "pubmed", "semantic_scholar", "crossref"}
    assert len(registry.all()) == len(names)


def test_registry_enable_disable_and_unknown():
    registry = dr.SearchEngineRegistry()
    registry.disable("brave")
    assert "brave" not in registry.names()
    registry.enable("brave")
    assert "brave" in registry.names()
    with pytest.raises(KeyError):
        registry.get("nope")


def test_engine_spec_cost_per_result():
    arxiv = dr.SearchEngineRegistry().get("arxiv")
    assert arxiv.cost_per_result == pytest.approx(arxiv.cost_per_query / arxiv.max_results)
    assert arxiv.to_dict()["kind"] == "academic"


# ── query decomposition ──────────────────────────────────────────────────────

def test_detect_intent_precedence():
    decomposer = dr.QueryDecomposer()
    assert decomposer.detect_intent("What is a vector index?") == "definitional"
    assert decomposer.detect_intent("How to deploy pgvector on Kubernetes") == "procedural"
    assert decomposer.detect_intent("Published studies on retrieval latency") == "academic"
    assert decomposer.detect_intent("Best SDK for embedding search") == "code"
    assert decomposer.detect_intent("How many requests per second can it serve?") == "quantitative"
    assert decomposer.detect_intent("Something entirely unclassifiable") == "general"


def test_decompose_builds_subqueries_and_entities():
    decomposer = dr.QueryDecomposer(max_subqueries=5)
    query = decomposer.decompose("Compare pgvector versus Qdrant for RAG", extra_aspects=("cost",))
    assert query.intent == "comparison"
    assert "RAG" in query.entities or "Qdrant" in query.entities
    assert len(query.subqueries) <= 5
    assert any("cost" in s for s in query.subqueries)
    assert query.to_dict()["intent"] == "comparison"


def test_engines_for_intent_are_real():
    decomposer = dr.QueryDecomposer()
    registry = dr.SearchEngineRegistry()
    academic = decomposer.decompose("a peer reviewed study of retrieval")
    assert [s.name for s in decomposer.engines_for(academic, registry)][0] == "arxiv"
    code = decomposer.decompose("a github library for embeddings")
    assert "github" in [s.name for s in decomposer.engines_for(code, registry)]


# ── BM25 backend ─────────────────────────────────────────────────────────────

def test_bm25_ranks_relevant_docs_first(provider):
    hits = provider.search("vector database latency recall", max_results=8)
    assert hits, "expected at least one hit"
    assert hits[0].url == "https://a.example/vec"
    assert hits[0].score >= hits[-1].score
    assert "sourdough" not in " ".join(h.url for h in hits)


def test_bm25_is_callable_and_counts_queries(provider):
    before = provider.queries_served
    hits = provider("ef_search recall latency", "local_docs", 3)
    assert len(hits) <= 3
    assert provider.queries_served == before + 1


def test_bm25_add_and_snippet(provider):
    provider.add(dr.Document(url="https://e.example/ivf", title="IVF indexes",
                             body="Inverted file indexes partition the vector space with k-means."))
    hits = provider.search("inverted file index k-means", max_results=2)
    assert any("ivf" in h.url for h in hits)
    assert hits[0].snippet


def test_document_and_result_token_estimates():
    doc = dr.Document(url="u", title="t", body="word " * 100)
    assert doc.tokens == dr.estimate_tokens(doc.body)
    result = dr.SearchResult(url="u", title="t", snippet="s", full_text="word " * 50)
    assert result.tokens > 0
    assert result.to_dict()["url"] == "u"


# ── compression ──────────────────────────────────────────────────────────────

def test_compressor_drops_duplicate_urls(provider):
    hits = provider.search("vector database", max_results=8)
    ctx = dr.ContextCompressor(max_tokens=5000).compress(hits)
    urls = [r.url for r in ctx.results]
    assert len(urls) == len(set(urls))
    assert ctx.tokens > 0


def test_compressor_respects_token_budget(provider):
    hits = provider.search("vector database latency recall pgvector", max_results=8)
    ctx = dr.ContextCompressor(max_tokens=60).compress(hits)
    assert ctx.tokens <= 60 + dr.estimate_tokens(next(iter([r.snippet for r in ctx.results]), ""))
    assert ctx.dropped_budget + len(ctx.results) <= len(hits)


def test_mmr_promotes_diversity(provider):
    hits = provider.search("vector database pgvector", max_results=8)
    ranked = dr.ContextCompressor().rank_by_mmr(hits, "vector database", limit=3)
    assert 1 <= len(ranked) <= 3
    urls = [r.url for r in ranked]
    assert len(urls) == len(set(urls)), "MMR must not return duplicate documents"


# ── findings ledger ──────────────────────────────────────────────────────────

def test_finding_confidence_and_dedupe():
    finding = dr.Finding(finding_id="f1", query="q", iteration=1,
                         sentence="Recall improved by 12 percent after tuning.",
                         url="https://a.example/vec", engine="local_docs",
                         relevance=0.8, source_quality=0.9)
    assert finding.has_numeric_claim is True
    assert finding.confidence == pytest.approx(0.55 * 0.8 + 0.45 * 0.9 + 0.12, rel=1e-3)

    plain = dr.Finding(finding_id="f2", query="q", iteration=1, sentence="Indexes are useful.",
                       url="https://b.example/hnsw", engine="local_docs",
                       relevance=0.5, source_quality=0.5)
    assert plain.has_numeric_claim is False
    assert plain.confidence < finding.confidence

    ledger = dr.FindingsLedger()
    assert ledger.add(finding) is True
    assert ledger.add(finding) is False, "duplicate sentences must be rejected"


def test_ledger_coverage_and_stats():
    ledger = dr.FindingsLedger()
    for i, url in enumerate(["https://a.example/vec", "https://b.example/hnsw"]):
        ledger.add(dr.Finding(finding_id=f"f{i}", query=f"q{i}", iteration=1,
                              sentence=f"Distinct evidence sentence number {i} about latency.",
                              url=url, engine="local_docs", relevance=0.6, source_quality=0.7))
    ledger.record_query("q0", True)
    ledger.record_query("q1", True)
    ledger.record_query("q2", False)
    stats = ledger.stats()
    assert stats["findings"] == 2
    assert stats["unique_sources"] == 2
    assert stats["coverage"] == pytest.approx(2 / 3, rel=1e-3)
    assert ledger.coverage() == pytest.approx(2 / 3, rel=1e-3)
    assert stats["engine_mix"] == {"local_docs": 2}
    assert len(ledger.by_confidence(limit=1)) == 1
    assert set(ledger.urls()) == {"https://a.example/vec", "https://b.example/hnsw"}


# ── citations ────────────────────────────────────────────────────────────────

def test_citation_registry_markers_are_stable():
    registry = dr.CitationRegistry()
    first = registry.register("https://a.example/vec")
    second = registry.register("https://b.example/hnsw")
    assert first != second
    assert registry.url_for(first) == "https://a.example/vec"
    assert registry.marker("https://a.example/vec") == first
    assert registry.url_for("[99]") is None
    assert len(registry) == 2
    assert {row["url"] for row in registry.sources} == {
        "https://a.example/vec", "https://b.example/hnsw"}


def test_citation_validator_flags_uncited_strong_claims():
    registry = dr.CitationRegistry()
    marker = registry.register("https://a.example/vec")
    good = f"Recall improved by 12 percent {marker}."
    bad = "This approach always halves the cost."
    report = "\n".join(["# Heading", good, bad, "> quoted line 50 percent"])
    result = dr.CitationValidator().validate(report, registry)
    assert result["strong_claims"] == 2
    assert result["citation_rate"] == pytest.approx(0.5, rel=1e-3)
    assert result["unsupported_claims"] == [bad]
    assert result["valid"] is False


def test_citation_validator_detects_unknown_markers():
    result = dr.CitationValidator().validate("Growth was 30 percent [9].", dr.CitationRegistry())
    assert result["unknown_markers"] == ["[9]"]
    assert result["valid"] is False


# ── strategies + reporting ───────────────────────────────────────────────────

def test_research_run_produces_a_cited_report(engine):
    report = engine.research("Compare vector database options for RAG and their latency tradeoffs",
                             strategy="focused_iterative")
    assert report.strategy == "focused_iterative"
    assert report.metrics["findings"] > 0
    assert report.sources
    assert set(report.sections) >= {"Summary", "Key Findings", "Method", "Open Questions"}
    assert report.citations["strong_claims"] >= 1
    assert report.citations["citation_rate"] == pytest.approx(1.0, rel=1e-6)
    assert report.citations["valid"] is True
    assert "Research Report" in report.markdown
    assert engine.history[-1] is report


def test_all_strategies_run_and_are_comparable(engine):
    comparison = engine.compare_strategies("How does pgvector compare with a dedicated vector database?")
    assert set(comparison) == {"source_based", "focused_iterative", "parallel"}
    for name, metrics in comparison.items():
        assert metrics["findings"] >= 0
        assert 0.0 <= metrics["coverage"] <= 1.0
        assert metrics["iterations"] >= 1
        assert metrics["citation_rate"] >= 0.0


def test_parallel_strategy_uses_one_iteration(engine):
    report = engine.research("vector database latency", strategy="parallel")
    assert report.metrics["iterations"] == 1
    assert report.metrics["queries_run"] >= 1


def test_unknown_strategy_raises(engine):
    with pytest.raises(KeyError):
        engine.strategy("magic")


def test_budget_limits_are_respected(provider):
    tight = dr.ResearchBudget(max_iterations=1, max_queries=2, max_results_per_query=2,
                              context_tokens=400, min_iteration_gain=0.9)
    engine = dr.DeepResearchEngine(provider=provider, budget=tight)
    report = engine.research("vector database latency", strategy="focused_iterative")
    assert report.metrics["queries_run"] <= 2
    assert report.metrics["iterations"] <= 1
    assert "Stopped because:" in report.markdown


def test_report_generator_handles_empty_state():
    state = dr.ResearchState(query=dr.ResearchQuery(text="nothing"), iteration=0,
                             findings=dr.FindingsLedger(), context=dr.CompressedContext(results=[]),
                             coverage_history=[], follow_up_questions=[], stopped_reason="no_results")
    report = dr.ReportGenerator().generate(state, "source_based")
    assert report.metrics["findings"] == 0
    assert "No findings" in report.markdown or "no findings" in report.markdown.lower()


# ── helpers ──────────────────────────────────────────────────────────────────

def test_tokenizer_and_helpers():
    assert dr.tokenize("The Latency Of Pgvector") == ["latency", "pgvector"]
    assert dr.clamp01(2.0) == 1.0
    assert dr.safe_div(4, 0, default=0.25) == 0.25
    assert dr.estimate_tokens("") >= 0
