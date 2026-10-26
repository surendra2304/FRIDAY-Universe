"""
Inference Deep Layer 12 — Real Agentic Deep Research Engine

Real repository integration:
    LearningCircuit/local-deep-research
    Upstream: https://github.com/LearningCircuit/local-deep-research

Local Deep Research (LDR) wraps an LLM in an agentic search loop: decompose a
query, fan it out across several search engines, accumulate findings with
citations, analyse what is still unknown, and iterate until coverage stops
improving. This module ports that *control flow and scoring* into the Inference
agent with stdlib-only computation:

* ``SearchEngineRegistry``       — LDR's engine catalogue (SearXNG, arXiv,
  PubMed, Semantic Scholar, Wikipedia, local documents, ...).
* ``QueryDecomposer``            — intent-aware sub-query generation.
* ``BM25SearchProvider``         — a deterministic local corpus backend so the
  loop can be exercised end-to-end without network access.
* ``ContextCompressor``          — token-budgeted, MMR-diversified context.
* ``SourceBasedSearchStrategy``  — engine-per-question fan-out (LDR "source based").
* ``FocusedIterativeStrategy``   — search -> findings -> new questions loop (LDR
  "focused iteration"), with coverage-based early stopping.
* ``ParallelSearchStrategy``     — one broad pass over every sub-query at once.
* ``DeepResearchEngine``         — runs a strategy, tracks cost, emits a report.
* ``CitationRegistry`` / ``CitationValidator`` — numbered citations plus
  unsupported-claim detection.
* ``ReportGenerator``            — markdown report with a source table.

Everything is deterministic: no network, no randomness, no stubs.
"""

from __future__ import annotations

import hashlib
import math
import re
import statistics
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from typing import Any, Callable, Iterable

_WORD_RE = re.compile(r"[a-z0-9][a-z0-9\-']+")
_STOPWORDS = frozenset(
    """a an and are as at be by for from how in is it of on or that the this to was were what when where which who why
    will with you your about into over under more most other some such than then there these those can could should
    would may might must does did do doing have has had having not no nor but if because until while""".split()
)


def tokenize(text: str) -> list[str]:
    return [t for t in _WORD_RE.findall((text or "").lower()) if t not in _STOPWORDS and len(t) > 1]


def clamp01(value: float) -> float:
    return 0.0 if value < 0.0 else (1.0 if value > 1.0 else value)


def safe_div(numerator: float, denominator: float, default: float = 0.0) -> float:
    return numerator / denominator if denominator else default


def estimate_tokens(text: str) -> int:
    """Rough tokenizer: ~4 characters per token, floored at one token per word group."""
    if not text:
        return 0
    return max(1, int(round(len(text) / 4.0)))


# ─────────────────────────────────────────────────────────────────────────────
# Search engines
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class SearchEngineSpec:
    """One search backend available to the research loop."""

    name: str
    kind: str  # web | academic | encyclopedic | code | local | news
    base_url: str = ""
    quality: float = 0.7          # 0-1 expected source quality
    latency_ms: int = 600
    max_results: int = 8
    supports_date_filter: bool = False
    supports_full_text: bool = False
    cost_per_query: float = 0.0

    @property
    def cost_per_result(self) -> float:
        return safe_div(self.cost_per_query, self.max_results)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "kind": self.kind,
            "base_url": self.base_url,
            "quality": self.quality,
            "latency_ms": self.latency_ms,
            "max_results": self.max_results,
            "supports_date_filter": self.supports_date_filter,
            "cost_per_query": self.cost_per_query,
        }


class SearchEngineRegistry:
    """Catalogue of search engines (mirrors LDR's ``search_engines`` package)."""

    ENGINES: tuple[SearchEngineSpec, ...] = (
        SearchEngineSpec("searxng", "web", "http://localhost:8080", quality=0.72, latency_ms=700, max_results=10, supports_date_filter=True),
        SearchEngineSpec("duckduckgo", "web", "https://duckduckgo.com", quality=0.66, latency_ms=900, max_results=8),
        SearchEngineSpec("brave", "web", "https://search.brave.com", quality=0.71, latency_ms=650, max_results=10, cost_per_query=0.003),
        SearchEngineSpec("arxiv", "academic", "https://arxiv.org", quality=0.93, latency_ms=1200, max_results=6, supports_full_text=True),
        SearchEngineSpec("pubmed", "academic", "https://pubmed.ncbi.nlm.nih.gov", quality=0.95, latency_ms=1400, max_results=6, supports_full_text=True),
        SearchEngineSpec("semantic_scholar", "academic", "https://api.semanticscholar.org", quality=0.90, latency_ms=1100, max_results=8),
        SearchEngineSpec("crossref", "academic", "https://api.crossref.org", quality=0.88, latency_ms=1000, max_results=6),
        SearchEngineSpec("wikipedia", "encyclopedic", "https://en.wikipedia.org", quality=0.80, latency_ms=500, max_results=5, supports_full_text=True),
        SearchEngineSpec("local_docs", "local", "file://", quality=0.85, latency_ms=60, max_results=12, supports_full_text=True),
        SearchEngineSpec("news_api", "news", "https://newsapi.org", quality=0.68, latency_ms=800, max_results=10, supports_date_filter=True, cost_per_query=0.002),
        SearchEngineSpec("github", "code", "https://api.github.com", quality=0.83, latency_ms=900, max_results=6),
    )

    def __init__(self, enabled: Iterable[str] | None = None):
        wanted = set(enabled) if enabled else None
        self._engines = {e.name: e for e in self.ENGINES if wanted is None or e.name in wanted}

    def get(self, name: str) -> SearchEngineSpec:
        if name not in self._engines:
            raise KeyError(f"unknown search engine: {name}")
        return self._engines[name]

    def names(self) -> list[str]:
        return sorted(self._engines)

    def by_kind(self, kind: str) -> list[SearchEngineSpec]:
        return [e for e in self._engines.values() if e.kind == kind]

    def all(self) -> list[SearchEngineSpec]:
        return [self._engines[n] for n in self.names()]

    def enable(self, name: str) -> SearchEngineSpec:
        for spec in self.ENGINES:
            if spec.name == name:
                self._engines[name] = spec
                return spec
        raise KeyError(f"unknown search engine: {name}")

    def disable(self, name: str) -> None:
        self._engines.pop(name, None)


# ─────────────────────────────────────────────────────────────────────────────
# Query understanding
# ─────────────────────────────────────────────────────────────────────────────

_INTENT_PATTERNS: list[tuple[str, str]] = [
    ("academic", r"\b(study|studies|paper|research|evidence|meta[- ]analysis|peer[- ]reviewed|trial|systematic|journal|arxiv|pubmed)\b"),
    ("code", r"\b(api|library|package|github|sdk|function|implementation|repository|code|pypi|npm)\b"),
    ("news", r"\b(latest|today|breaking|announced|launch|news|this week|2024|2025|2026)\b"),
    ("comparison", r"\b(vs\.?|versus|compare|comparison|difference between|better than|alternative)\b"),
    ("quantitative", r"\b(how many|how much|percentage|rate|statistics|growth|forecast|number of)\b"),
    ("definitional", r"^(what is|what are|who is|who was|define|meaning of)\b"),
    ("procedural", r"^(how to|how do|how can|steps to|guide to)\b"),
]

_INTENT_ENGINES: dict[str, tuple[str, ...]] = {
    "academic": ("arxiv", "pubmed", "semantic_scholar", "crossref", "wikipedia"),
    "code": ("github", "searxng", "duckduckgo"),
    "news": ("news_api", "searxng", "brave"),
    "comparison": ("searxng", "brave", "wikipedia", "semantic_scholar"),
    "quantitative": ("searxng", "wikipedia", "semantic_scholar", "crossref"),
    "definitional": ("wikipedia", "searxng", "duckduckgo"),
    "procedural": ("searxng", "duckduckgo", "github", "wikipedia"),
    "general": ("searxng", "wikipedia", "brave", "duckduckgo"),
}

_SUBQUERY_TEMPLATES: dict[str, tuple[str, ...]] = {
    "academic": (
        "{q} peer reviewed evidence",
        "{q} systematic review findings",
        "{q} limitations and criticism",
        "{q} effect size statistics",
    ),
    "code": (
        "{q} official documentation",
        "{q} github reference implementation",
        "{q} performance benchmark",
    ),
    "news": (
        "{q} latest developments",
        "{q} primary source announcement",
        "{q} expert reaction",
    ),
    "comparison": (
        "{q} head to head comparison",
        "{q} advantages",
        "{q} disadvantages",
    ),
    "quantitative": (
        "{q} measured statistics",
        "{q} historical trend",
        "{q} methodology and data source",
    ),
    "definitional": (
        "{q} definition",
        "{q} examples",
        "{q} common misconceptions",
    ),
    "procedural": (
        "{q} step by step",
        "{q} prerequisites",
        "{q} common mistakes",
    ),
    "general": (
        "{q} overview",
        "{q} key facts",
        "{q} counterarguments",
        "{q} expert commentary",
    ),
}


@dataclass
class ResearchQuery:
    """The original question plus its decomposition."""

    text: str
    intent: str = "general"
    entities: tuple[str, ...] = ()
    subqueries: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "text": self.text,
            "intent": self.intent,
            "entities": list(self.entities),
            "subqueries": self.subqueries,
        }


class QueryDecomposer:
    """Turn a user question into intent-tagged, engine-ready sub-queries."""

    def __init__(self, max_subqueries: int = 12):
        self.max_subqueries = max_subqueries

    def detect_intent(self, text: str) -> str:
        lowered = (text or "").lower()
        for intent, pattern in _INTENT_PATTERNS:
            if re.search(pattern, lowered):
                return intent
        return "general"

    def extract_entities(self, text: str) -> tuple[str, ...]:
        """Capitalized multi-word phrases plus domain tokens (acronyms, versions)."""
        entities: list[str] = []
        for match in re.finditer(r"\b([A-Z][a-zA-Z0-9\-\.]+(?:\s+[A-Z][a-zA-Z0-9\-\.]+){0,3})\b", text or ""):
            candidate = match.group(1).strip()
            if candidate.lower() in _STOPWORDS:
                continue
            entities.append(candidate)
        for match in re.finditer(r"\b([A-Z]{2,6})\b", text or ""):
            if match.group(1) not in entities:
                entities.append(match.group(1))
        return tuple(dict.fromkeys(entities))[:8]

    def decompose(self, text: str, extra_aspects: Iterable[str] = ()) -> ResearchQuery:
        intent = self.detect_intent(text)
        entities = self.extract_entities(text)
        templates = _SUBQUERY_TEMPLATES.get(intent, _SUBQUERY_TEMPLATES["general"])
        subqueries = [t.format(q=text.strip()) for t in templates]
        for aspect in extra_aspects:
            subqueries.append(f"{text.strip()} {aspect}".strip())
        return ResearchQuery(text=text, intent=intent, entities=entities, subqueries=subqueries[: self.max_subqueries])

    def engines_for(self, query: ResearchQuery, registry: SearchEngineRegistry) -> list[SearchEngineSpec]:
        wanted = _INTENT_ENGINES.get(query.intent, _INTENT_ENGINES["general"])
        specs: list[SearchEngineSpec] = []
        for name in wanted:
            try:
                specs.append(registry.get(name))
            except KeyError:
                continue
        return specs or registry.all()


# ─────────────────────────────────────────────────────────────────────────────
# Results, corpus backend, compression
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class SearchResult:
    """One hit from one engine."""

    url: str
    title: str = ""
    snippet: str = ""
    engine: str = "searxng"
    score: float = 0.0
    published_year: int = 0
    full_text: str = ""

    @property
    def doc_id(self) -> str:
        return hashlib.sha1(self.url.encode("utf-8")).hexdigest()[:12]

    @property
    def tokens(self) -> int:
        return estimate_tokens(self.snippet)

    @property
    def text(self) -> str:
        return self.full_text or self.snippet

    def to_dict(self) -> dict[str, Any]:
        return {
            "url": self.url,
            "title": self.title,
            "snippet": self.snippet[:240],
            "engine": self.engine,
            "score": round(self.score, 4),
            "published_year": self.published_year,
            "doc_id": self.doc_id,
        }


@dataclass
class Document:
    """A local/private document in the searchable corpus."""

    url: str
    title: str = ""
    body: str = ""
    published_year: int = 0
    source_kind: str = "local_docs"

    @property
    def tokens(self) -> int:
        return estimate_tokens(self.body)


class BM25SearchProvider:
    """Deterministic offline search backend (Okapi BM25 over an in-memory corpus).

    LDR talks to real engines; the agent keeps this implementation so the whole
    research loop can run (and be tested) with zero network access.
    """

    def __init__(self, documents: Iterable[Document] | None = None, k1: float = 1.5, b: float = 0.75):
        self.k1 = k1
        self.b = b
        self.documents: list[Document] = list(documents or [])
        self._tokens: list[list[str]] = []
        self._tf: list[Counter[str]] = []
        self._df: Counter[str] = Counter()
        self._avg_len = 0.0
        self.queries_served = 0
        self.reindex()

    def add(self, document: Document) -> None:
        self.documents.append(document)
        self.reindex()

    def reindex(self) -> None:
        self._tokens = [tokenize(d.body + " " + d.title) for d in self.documents]
        self._tf = [Counter(toks) for toks in self._tokens]
        self._df = Counter()
        for toks in self._tokens:
            self._df.update(set(toks))
        total = sum(len(t) for t in self._tokens)
        self._avg_len = safe_div(total, len(self._tokens))

    def __call__(self, query: str, engine: str = "local_docs", max_results: int = 8) -> list[SearchResult]:
        """Protocol hook: strategies call the provider as a plain callable."""
        return self.search(query, engine, max_results)

    def _idf(self, term: str) -> float:
        n = len(self.documents)
        df = self._df.get(term, 0)
        return math.log(1.0 + safe_div(n - df + 0.5, df + 0.5))

    def score(self, query: str, index: int) -> float:
        terms = tokenize(query)
        if not terms or index >= len(self._tf):
            return 0.0
        tf = self._tf[index]
        length = len(self._tokens[index]) or 1
        total = 0.0
        matched = 0
        for term in terms:
            freq = tf.get(term, 0)
            if not freq:
                continue
            matched += 1
            denom = freq + self.k1 * (1 - self.b + self.b * length / max(1.0, self._avg_len))
            total += self._idf(term) * safe_div(freq * (self.k1 + 1), denom)
        coverage = safe_div(matched, len(set(terms)))
        return total * (0.4 + 0.6 * coverage)

    def search(self, query: str, engine: str = "local_docs", max_results: int = 8) -> list[SearchResult]:
        self.queries_served += 1
        scored: list[tuple[float, int]] = []
        for idx, doc in enumerate(self.documents):
            value = self.score(query, idx)
            if value > 0:
                scored.append((value, idx))
        scored.sort(key=lambda pair: (-pair[0], pair[1]))
        results: list[SearchResult] = []
        for value, idx in scored[:max_results]:
            doc = self.documents[idx]
            snippet = self._snippet(doc.body, query)
            results.append(
                SearchResult(
                    url=doc.url,
                    title=doc.title,
                    snippet=snippet,
                    engine=engine,
                    score=round(value, 4),
                    published_year=doc.published_year,
                    full_text=doc.body,
                )
            )
        return results

    def _snippet(self, body: str, query: str, window: int = 60) -> str:
        words = body.split()
        if len(words) <= window:
            return body
        terms = set(tokenize(query))
        best_idx, best_hits = 0, -1
        for start in range(0, max(1, len(words) - window), 10):
            chunk = set(tokenize(" ".join(words[start : start + window])))
            hits = len(chunk & terms)
            if hits > best_hits:
                best_idx, best_hits = start, hits
        return " ".join(words[best_idx : best_idx + window])


@dataclass
class CompressedContext:
    """Token-budgeted, de-duplicated, diversity-selected context."""

    results: list[SearchResult] = field(default_factory=list)
    tokens: int = 0
    dropped_duplicates: int = 0
    dropped_budget: int = 0
    dropped_redundant: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "kept": len(self.results),
            "tokens": self.tokens,
            "dropped_duplicates": self.dropped_duplicates,
            "dropped_budget": self.dropped_budget,
            "dropped_redundant": self.dropped_redundant,
            "urls": [r.url for r in self.results],
        }


class ContextCompressor:
    """Keep the highest-value, least-redundant evidence inside a token budget."""

    def __init__(self, max_tokens: int = 6000, similarity_threshold: float = 0.72, lambda_mmr: float = 0.65):
        self.max_tokens = max_tokens
        self.similarity_threshold = similarity_threshold
        self.lambda_mmr = lambda_mmr

    @staticmethod
    def jaccard(a: SearchResult, b: SearchResult) -> float:
        ta, tb = set(tokenize(a.text)), set(tokenize(b.text))
        if not ta or not tb:
            return 0.0
        return safe_div(len(ta & tb), len(ta | tb))

    @staticmethod
    def normalize_key(result: SearchResult) -> str:
        canonical = re.sub(r"[^a-z0-9]+", " ", result.url.lower()).strip()
        return hashlib.sha1((canonical + "|" + result.snippet[:80].lower()).encode()).hexdigest()

    def compress(self, results: list[SearchResult]) -> CompressedContext:
        seen: set[str] = set()
        unique: list[SearchResult] = []
        duplicates = 0
        for result in sorted(results, key=lambda r: r.score, reverse=True):
            key = self.normalize_key(result)
            if key in seen:
                duplicates += 1
                continue
            seen.add(key)
            unique.append(result)

        selected: list[SearchResult] = []
        tokens = 0
        dropped_budget = 0
        dropped_redundant = 0
        for result in unique:
            if tokens + result.tokens > self.max_tokens:
                dropped_budget += 1
                continue
            if any(self.jaccard(result, kept) > self.similarity_threshold for kept in selected):
                dropped_redundant += 1
                continue
            selected.append(result)
            tokens += result.tokens

        return CompressedContext(selected, tokens, duplicates, dropped_budget, dropped_redundant)

    def rank_by_mmr(self, results: list[SearchResult], query: str, limit: int = 8) -> list[SearchResult]:
        """Maximal marginal relevance: relevance minus redundancy against the query."""
        if not results:
            return []
        query_terms = set(tokenize(query))
        pool = list(results)
        selected: list[SearchResult] = []

        def relevance(result: SearchResult) -> float:
            terms = set(tokenize(result.text))
            return safe_div(len(terms & query_terms), max(1, len(query_terms))) * 0.6 + clamp01(result.score / 12.0) * 0.4

        while pool and len(selected) < limit:
            best, best_value = None, -1e9
            for candidate in pool:
                redundancy = max((self.jaccard(candidate, kept) for kept in selected), default=0.0)
                value = self.lambda_mmr * relevance(candidate) - (1 - self.lambda_mmr) * redundancy
                if value > best_value:
                    best, best_value = candidate, value
            assert best is not None
            selected.append(best)
            pool.remove(best)
        return selected


# ─────────────────────────────────────────────────────────────────────────────
# Findings + citations
# ─────────────────────────────────────────────────────────────────────────────

_CLAIM_CUES = (
    "shows", "found", "according", "because", "results", "significant", "reduces", "increases",
    "causes", "improve", "higher", "lower", "study", "report", "measured", "evidence", "demonstrates",
)


@dataclass
class Finding:
    """One sentence of evidence extracted from a search result."""

    finding_id: str
    query: str
    iteration: int
    sentence: str
    url: str
    engine: str
    relevance: float = 0.0
    source_quality: float = 0.0

    @property
    def confidence(self) -> float:
        """Relevance x source quality, boosted when the sentence carries a claim cue."""
        cue_bonus = 0.12 if any(cue in self.sentence.lower() for cue in _CLAIM_CUES) else 0.0
        return round(clamp01(0.55 * clamp01(self.relevance) + 0.45 * clamp01(self.source_quality) + cue_bonus), 4)

    @property
    def has_numeric_claim(self) -> bool:
        return bool(re.search(r"\b\d+(?:\.\d+)?\s?(?:%|percent|x|times|fold|points)(?![a-z0-9])", self.sentence.lower()))

    def to_dict(self) -> dict[str, Any]:
        return {
            "finding_id": self.finding_id,
            "query": self.query,
            "iteration": self.iteration,
            "sentence": self.sentence,
            "url": self.url,
            "engine": self.engine,
            "relevance": round(self.relevance, 4),
            "source_quality": round(self.source_quality, 4),
            "confidence": self.confidence,
        }


class FindingsLedger:
    """Accumulates findings, tracks coverage of the question space."""

    def __init__(self):
        self.findings: list[Finding] = []
        self.seen_sentences: set[str] = set()
        self.queried: list[str] = []
        self.covered: set[str] = set()

    def _key(self, sentence: str) -> str:
        return hashlib.sha1(re.sub(r"\s+", " ", sentence.lower()).strip().encode()).hexdigest()

    def add(self, finding: Finding) -> bool:
        key = self._key(finding.sentence)
        if key in self.seen_sentences:
            return False
        self.seen_sentences.add(key)
        self.findings.append(finding)
        return True

    def record_query(self, query: str, produced: bool) -> None:
        """Record a sub-query once; later re-runs only upgrade it to covered."""
        if query not in self.queried:
            self.queried.append(query)
        if produced:
            self.covered.add(query)

    def coverage(self) -> float:
        return round(safe_div(len(self.covered), len(self.queried)), 4)

    def by_confidence(self, limit: int = 10) -> list[Finding]:
        return sorted(self.findings, key=lambda f: f.confidence, reverse=True)[:limit]

    def urls(self) -> list[str]:
        return list(dict.fromkeys(f.url for f in self.findings))

    def stats(self) -> dict[str, Any]:
        confidences = [f.confidence for f in self.findings]
        return {
            "findings": len(self.findings),
            "queries_run": len(self.queried),
            "coverage": self.coverage(),
            "unique_sources": len(self.urls()),
            "mean_confidence": round(statistics.mean(confidences), 4) if confidences else 0.0,
            "numeric_claims": sum(1 for f in self.findings if f.has_numeric_claim),
            "engine_mix": dict(Counter(f.engine for f in self.findings)),
        }


class CitationRegistry:
    """Numbered citation registry: [1] -> url, used by the report writer."""

    def __init__(self):
        self._ids: dict[str, str] = {}
        self._order: list[str] = []

    def register(self, url: str) -> str:
        if url not in self._ids:
            self._ids[url] = f"[{len(self._order) + 1}]"
            self._order.append(url)
        return self._ids[url]

    def marker(self, url: str) -> str:
        return self.register(url)

    def url_for(self, marker: str) -> str | None:
        digits = marker.strip("[]")
        if not digits.isdigit():
            return None
        idx = int(digits) - 1
        return self._order[idx] if 0 <= idx < len(self._order) else None

    @property
    def sources(self) -> list[dict[str, str]]:
        return [{"marker": f"[{i + 1}]", "url": url} for i, url in enumerate(self._order)]

    def __len__(self) -> int:
        return len(self._order)


class CitationValidator:
    """Detect report sentences that make numeric/strong claims without a citation."""

    STRONG_CLAIM = re.compile(
        r"(?:\b\d+(?:\.\d+)?\s?(?:%|percent|x|times)(?![a-z0-9])|\balways\b|\bnever\b|\bproves?\b|\bguaranteed\b|\bsignificantly\b|\bconclusively\b)",
        re.IGNORECASE,
    )
    MARKER = re.compile(r"\[\d+\]")

    def validate(self, report: str, registry: CitationRegistry) -> dict[str, Any]:
        unsupported: list[str] = []
        supported = 0
        strong = 0
        for line in report.splitlines():
            sentence = line.strip()
            if not sentence or sentence.startswith(("#", "|", ">")):
                continue
            if self.STRONG_CLAIM.search(sentence):
                strong += 1
                if self.MARKER.search(sentence):
                    supported += 1
                else:
                    unsupported.append(sentence[:200])
        unknown = sorted({m for m in self.MARKER.findall(report) if registry.url_for(m) is None})
        total_strong = max(1, strong)
        return {
            "strong_claims": strong,
            "cited_strong_claims": supported,
            "unsupported_claims": unsupported,
            "citation_rate": round(safe_div(supported, total_strong), 4),
            "unknown_markers": unknown,
            "valid": not unsupported and not unknown,
        }


# ─────────────────────────────────────────────────────────────────────────────
# Search strategies
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class ResearchBudget:
    """Hard limits for a research run."""

    max_iterations: int = 3
    max_queries: int = 24
    max_results_per_query: int = 6
    context_tokens: int = 6000
    min_iteration_gain: float = 0.05

    def to_dict(self) -> dict[str, Any]:
        return {
            "max_iterations": self.max_iterations,
            "max_queries": self.max_queries,
            "max_results_per_query": self.max_results_per_query,
            "context_tokens": self.context_tokens,
            "min_iteration_gain": self.min_iteration_gain,
        }


@dataclass
class ResearchState:
    """Mutable state threaded through the loop (LangGraph-style, but plain data)."""

    query: ResearchQuery
    iteration: int = 0
    queries_run: int = 0
    results_seen: int = 0
    findings: FindingsLedger = field(default_factory=FindingsLedger)
    context: CompressedContext = field(default_factory=CompressedContext)
    coverage_history: list[float] = field(default_factory=list)
    follow_up_questions: list[str] = field(default_factory=list)
    stopped_reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "query": self.query.to_dict(),
            "iteration": self.iteration,
            "queries_run": self.queries_run,
            "results_seen": self.results_seen,
            "coverage_history": self.coverage_history,
            "follow_up_questions": self.follow_up_questions,
            "stopped_reason": self.stopped_reason,
            "findings": self.findings.stats(),
        }


SearchProvider = Callable[[str, str, int], list[SearchResult]]


class ResearchStrategy:
    """Base class for the three LDR search strategies."""

    name = "base"

    def __init__(
        self,
        registry: SearchEngineRegistry,
        provider: SearchProvider,
        budget: ResearchBudget | None = None,
        compressor: ContextCompressor | None = None,
    ):
        self.registry = registry
        self.provider = provider
        self.budget = budget or ResearchBudget()
        self.compressor = compressor or ContextCompressor(max_tokens=self.budget.context_tokens)
        self.engine_calls: Counter[str] = Counter()

    # -- hooks -------------------------------------------------------------
    def plan_queries(self, state: ResearchState) -> list[tuple[str, SearchEngineSpec]]:
        raise NotImplementedError

    # -- shared helpers ----------------------------------------------------
    def _search(self, query: str, engine: SearchEngineSpec) -> list[SearchResult]:
        self.engine_calls[engine.name] += 1
        return self.provider(query, engine.name, self.budget.max_results_per_query)

    def _extract_findings(
        self,
        state: ResearchState,
        query: str,
        results: list[SearchResult],
        engine_quality: dict[str, float],
    ) -> int:
        added = 0
        query_terms = set(tokenize(query))
        for result in results:
            for sentence in self._sentences(result.text):
                terms = set(tokenize(sentence))
                if len(terms) < 5:
                    continue
                overlap = safe_div(len(terms & query_terms), max(1, len(query_terms)))
                retrieval = clamp01(result.score / 5.0)
                relevance = clamp01(0.5 * overlap + 0.5 * retrieval)
                if relevance <= 0:
                    continue
                quality = engine_quality.get(result.engine, 0.7)
                finding = Finding(
                    finding_id=f"f{len(state.findings.findings) + 1:04d}",
                    query=query,
                    iteration=state.iteration,
                    sentence=sentence,
                    url=result.url,
                    engine=result.engine,
                    relevance=round(clamp01(relevance), 4),
                    source_quality=quality,
                )
                if state.findings.add(finding):
                    added += 1
        state.findings.record_query(query, added > 0)
        return added

    @staticmethod
    def _sentences(text: str) -> list[str]:
        parts = re.split(r"(?<=[.!?])\s+", (text or "").replace("\n", " ").strip())
        return [p.strip() for p in parts if len(p.split()) >= 6]

    def _note_coverage(self, state: ResearchState) -> None:
        state.coverage_history.append(state.findings.coverage())

    def _should_continue(self, state: ResearchState) -> bool:
        if state.iteration >= self.budget.max_iterations:
            state.stopped_reason = "max_iterations"
            return False
        if state.queries_run >= self.budget.max_queries:
            state.stopped_reason = "max_queries"
            return False
        if len(state.coverage_history) >= 2:
            gain = state.coverage_history[-1] - state.coverage_history[-2]
            if gain < self.budget.min_iteration_gain:
                state.stopped_reason = "diminishing_coverage"
                return False
        return True

    def run(self, query: ResearchQuery) -> ResearchState:
        raise NotImplementedError


class SourceBasedSearchStrategy(ResearchStrategy):
    """LDR 'source based': each sub-query is answered by the best engine(s) for it."""

    name = "source_based"

    def plan_queries(self, state: ResearchState) -> list[tuple[str, SearchEngineSpec]]:
        engines = QueryDecomposer().engines_for(state.query, self.registry)
        plan: list[tuple[str, SearchEngineSpec]] = []
        for i, sub in enumerate(state.query.subqueries):
            engine = engines[i % len(engines)] if engines else self.registry.all()[0]
            plan.append((sub, engine))
        return plan

    def run(self, query: ResearchQuery) -> ResearchState:
        state = ResearchState(query=query)
        quality = {e.name: e.quality for e in self.registry.all()}
        while self._should_continue(state):
            state.iteration += 1
            plan = self.plan_queries(state)
            for sub, engine in plan:
                if state.queries_run >= self.budget.max_queries:
                    break
                results = self._search(sub, engine)
                state.results_seen += len(results)
                state.queries_run += 1
                self._extract_findings(state, sub, results, quality)
            self._note_coverage(state)
            state.context = self.compressor.compress(self._as_results(state))
            state.follow_up_questions = self._follow_ups(state)
        if not state.stopped_reason:
            state.stopped_reason = "plan_exhausted"
        return state

    def _as_results(self, state: ResearchState) -> list[SearchResult]:
        seen: dict[str, SearchResult] = {}
        for finding in state.findings.findings:
            if finding.url in seen:
                seen[finding.url].snippet += " " + finding.sentence
            else:
                seen[finding.url] = SearchResult(
                    url=finding.url,
                    title=finding.url.rsplit("/", 1)[-1][:60],
                    snippet=finding.sentence,
                    engine=finding.engine,
                    score=finding.confidence * 10.0,
                    full_text=finding.sentence,
                )
        return list(seen.values())

    @staticmethod
    def _follow_ups(state: ResearchState) -> list[str]:
        covered = state.findings.coverage()
        if covered >= 0.85:
            return []
        uncovered = [q for q in state.findings.queried if q not in state.findings.covered]
        return [f"Verify with another source: {q}" for q in uncovered[:3]]


class FocusedIterativeStrategy(SourceBasedSearchStrategy):
    """LDR 'focused iteration': search -> assess gaps -> narrower follow-ups."""

    name = "focused_iterative"

    def plan_queries(self, state: ResearchState) -> list[tuple[str, SearchEngineSpec]]:
        engines = QueryDecomposer().engines_for(state.query, self.registry)
        if state.iteration <= 1:
            return [(sub, engines[i % len(engines)]) for i, sub in enumerate(state.query.subqueries[: max(3, len(engines))])]
        # Later iterations target the weakest-covered aspects only.
        pending = [q for q in state.findings.queried if q not in state.findings.covered]
        if not pending:
            return []
        return [(f"{q} {state.query.entities[0] if state.query.entities else 'specifics'}", engines[state.iteration % len(engines)]) for q in pending[:4]]


class ParallelSearchStrategy(SourceBasedSearchStrategy):
    """LDR 'parallel': every sub-query hits every selected engine in one pass."""

    name = "parallel"

    def plan_queries(self, state: ResearchState) -> list[tuple[str, SearchEngineSpec]]:
        engines = QueryDecomposer().engines_for(state.query, self.registry)[:3]
        plan: list[tuple[str, SearchEngineSpec]] = []
        for sub in state.query.subqueries:
            for engine in engines:
                plan.append((sub, engine))
        return plan

    def run(self, query: ResearchQuery) -> ResearchState:
        state = ResearchState(query=query)
        quality = {e.name: e.quality for e in self.registry.all()}
        state.iteration = 1
        plan = self.plan_queries(state)
        for sub, engine in plan:
            if state.queries_run >= self.budget.max_queries:
                break
            results = self._search(sub, engine)
            state.results_seen += len(results)
            state.queries_run += 1
            self._extract_findings(state, sub, results, quality)
        self._note_coverage(state)
        state.context = self.compressor.compress(self._as_results(state))
        state.stopped_reason = "single_parallel_pass"
        return state


# ─────────────────────────────────────────────────────────────────────────────
# Engine + report
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class ResearchReport:
    """The rendered output of a research run."""

    query: str
    intent: str
    strategy: str
    markdown: str
    sections: dict[str, str]
    sources: list[dict[str, str]]
    metrics: dict[str, Any]
    citations: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "query": self.query,
            "intent": self.intent,
            "strategy": self.strategy,
            "sections": list(self.sections),
            "sources": self.sources,
            "metrics": self.metrics,
            "citations": self.citations,
            "markdown_chars": len(self.markdown),
        }


class ReportGenerator:
    """Turns a finished :class:`ResearchState` into a cited markdown report."""

    def __init__(self, max_findings: int = 12, max_sentence_chars: int = 320):
        self.max_findings = max_findings
        self.max_sentence_chars = max_sentence_chars

    def generate(self, state: ResearchState, strategy_name: str) -> ResearchReport:
        registry = CitationRegistry()
        findings = state.findings.by_confidence(self.max_findings)

        bullets: list[str] = []
        for finding in findings:
            marker = registry.register(finding.url)
            sentence = finding.sentence.strip()
            if len(sentence) > self.max_sentence_chars:
                sentence = sentence[: self.max_sentence_chars].rsplit(" ", 1)[0] + "..."
            bullets.append(f"- {sentence} {marker}")

        top = findings[:3]
        if top:
            summary_parts = []
            for finding in top:
                marker = registry.register(finding.url)
                summary_parts.append(f"{finding.sentence} {marker}")
            summary = " ".join(summary_parts)[:800]
        else:
            summary = "No evidence was retrieved for this query."
        sections = {
            "Summary": f"{summary}\n\nResearch question: *{state.query.text}*\n\n"
            f"Strategy: `{strategy_name}` — intent classified as `{state.query.intent}`.",
            "Key Findings": "\n".join(bullets) if bullets else "- No findings.",
            "Method": (
                f"- Sub-queries: {len(state.query.subqueries)}\n"
                f"- Searches executed: {len(state.findings.queried)}\n"
                f"- Results inspected: {state.results_seen}\n"
                f"- Unique sources cited: {len(registry)}\n"
                f"- Coverage of sub-queries: {state.findings.coverage():.0%} of {len(state.findings.queried)}\n"
                f"- Stopped because: {state.stopped_reason}"
            ),
            "Open Questions": "\n".join(f"- {q}" for q in state.follow_up_questions) or "- None remaining.",
        }

        source_rows = "\n".join(f"| {s['marker']} | {s['url']} |" for s in registry.sources) or "| - | - |"
        markdown = "\n\n".join(
            [f"# Research Report: {state.query.text}", *[f"## {name}\n{body}" for name, body in sections.items()],
             "## Sources\n\n| # | URL |\n| --- | --- |\n" + source_rows]
        )

        metrics = {
            **state.findings.stats(),
            "strategy": strategy_name,
            "iterations": state.iteration,
            "context_tokens": state.context.tokens,
            "coverage_history": [round(c, 4) for c in state.coverage_history],
        }
        # Validate only the claim-bearing prose (summary + findings), not the
        # metadata section where percentages are metrics rather than claims.
        claims_text = sections["Summary"] + "\n" + sections["Key Findings"]
        return ResearchReport(
            query=state.query.text,
            intent=state.query.intent,
            strategy=strategy_name,
            markdown=markdown,
            sections=sections,
            sources=registry.sources,
            metrics=metrics,
            citations=CitationValidator().validate(claims_text, registry),
        )


class DeepResearchEngine:
    """Top-level entry point: decompose -> search -> accumulate -> report."""

    STRATEGIES: dict[str, type[ResearchStrategy]] = {
        "source_based": SourceBasedSearchStrategy,
        "focused_iterative": FocusedIterativeStrategy,
        "parallel": ParallelSearchStrategy,
    }

    def __init__(
        self,
        provider: SearchProvider,
        registry: SearchEngineRegistry | None = None,
        budget: ResearchBudget | None = None,
        decomposer: QueryDecomposer | None = None,
    ):
        self.provider = provider
        self.registry = registry or SearchEngineRegistry()
        self.budget = budget or ResearchBudget()
        self.decomposer = decomposer or QueryDecomposer()
        self.history: list[ResearchReport] = []

    def strategy(self, name: str) -> ResearchStrategy:
        if name not in self.STRATEGIES:
            raise KeyError(f"unknown strategy: {name}")
        return self.STRATEGIES[name](self.registry, self.provider, self.budget)

    def research(self, question: str, strategy: str = "focused_iterative", aspects: Iterable[str] = ()) -> ResearchReport:
        query = self.decomposer.decompose(question, aspects)
        runner = self.strategy(strategy)
        state = runner.run(query)
        state.context = runner.compressor.compress(runner._as_results(state))
        report = ReportGenerator().generate(state, strategy)
        self.history.append(report)
        return report

    def compare_strategies(self, question: str) -> dict[str, dict[str, Any]]:
        """Run every strategy on the same question and return their metrics."""
        out: dict[str, dict[str, Any]] = {}
        for name in self.STRATEGIES:
            report = self.research(question, strategy=name)
            out[name] = {
                "findings": report.metrics["findings"],
                "coverage": report.metrics["coverage"],
                "mean_confidence": report.metrics["mean_confidence"],
                "sources": len(report.sources),
                "iterations": report.metrics["iterations"],
                "citation_rate": report.citations["citation_rate"],
            }
        return out
