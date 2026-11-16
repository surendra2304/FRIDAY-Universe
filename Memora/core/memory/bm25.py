"""
BM25 keyword ranking for Memora (TASK-IG2-MEM-01, agentmemory ADAPT).

The agentmemory pattern's first recall rule is *keyless BM25 first*:
lexical relevance that needs no API key, no embedding model and no
vector store, with semantic search layered on top when available.
Memora's retrieval config has always NAMED its keyword method "bm25"
(see ``core/memory/retrieval_config.py``), but the implementation in
``SearchService.hybrid_search`` was substring token-overlap counting —
a record mentioning a rare query term once scored exactly like a record
stuffed with common words, and term frequency / document length played
no part. This module is the real thing: Okapi BM25 over the bounded
candidate set the search service already materialises, pure stdlib
(``re`` + ``math``), no new dependency, negligible memory at fleet
scale (the candidate window is capped at 500–5000 short records).

Scores are raw BM25 (unbounded, >= 0). Callers that need a 0–1 signal
use :func:`squash` (score / (1 + score)), the same squash the graph leg
adopted in TASK-REL-024.
"""

from __future__ import annotations

import math
import re
from collections import Counter
from typing import Dict, Iterable, List, Tuple

_TOKEN_RE = re.compile(r"[a-z0-9]+")


def tokenize(text: str) -> List[str]:
    """Lowercase alphanumeric tokens.

    Single-character tokens are dropped (they are almost never content
    terms and were the LIKE-wildcard hazard the search service already
    guards against), except single digits, which can be meaningful
    (versions, counts).
    """
    return [tok for tok in _TOKEN_RE.findall((text or "").lower()) if len(tok) > 1 or tok.isdigit()]


def squash(score: float) -> float:
    """Map a raw BM25 score into (0, 1) — monotonic, rank-preserving."""
    if score <= 0:
        return 0.0
    return score / (1.0 + score)


class BM25Index:
    """A small in-memory BM25 index over a bounded document set.

    Built per query over the search service's candidate window — the
    corpus statistics (idf, average length) are therefore the
    candidates' own, which is the right comparison set for ranking
    them against each other.
    """

    def __init__(self, k1: float = 1.5, b: float = 0.75) -> None:
        self.k1 = float(k1)
        self.b = float(b)
        self._doc_tokens: Dict[str, List[str]] = {}
        self._doc_freq: Counter = Counter()
        self._total_length = 0

    def add_document(self, doc_id: str, text: str) -> None:
        tokens = tokenize(text)
        if doc_id in self._doc_tokens:  # re-adding replaces, never double-counts
            old = self._doc_tokens[doc_id]
            for term in set(old):
                self._doc_freq[term] -= 1
            self._total_length -= len(old)
        self._doc_tokens[doc_id] = tokens
        self._total_length += len(tokens)
        for term in set(tokens):
            self._doc_freq[term] += 1

    def build(self, documents: Iterable[Tuple[str, str]]) -> "BM25Index":
        for doc_id, text in documents:
            self.add_document(doc_id, text)
        return self

    @property
    def document_count(self) -> int:
        return len(self._doc_tokens)

    def _idf(self, term: str) -> float:
        n = len(self._doc_tokens)
        df = self._doc_freq.get(term, 0)
        # Robertson/Walker idf with the standard +0.5 smoothing, floored
        # at a small positive value so a term present in every candidate
        # still contributes a little rather than going negative.
        return max(0.05, math.log(1.0 + (n - df + 0.5) / (df + 0.5)))

    def score(self, query: str) -> Dict[str, float]:
        """Raw BM25 score per document id (only positive scores returned)."""
        if not self._doc_tokens:
            return {}
        query_terms = [term for term in dict.fromkeys(tokenize(query))]
        if not query_terms:
            return {}
        avg_len = self._total_length / max(1, len(self._doc_tokens)) or 1.0
        scores: Dict[str, float] = {}
        for doc_id, tokens in self._doc_tokens.items():
            if not tokens:
                continue
            counts = Counter(tokens)
            doc_len = len(tokens)
            total = 0.0
            for term in query_terms:
                tf = counts.get(term, 0)
                if not tf:
                    continue
                denom = tf + self.k1 * (1.0 - self.b + self.b * doc_len / avg_len)
                total += self._idf(term) * (tf * (self.k1 + 1.0)) / denom
            if total > 0:
                scores[doc_id] = total
        return scores

    def rank(self, query: str) -> List[Tuple[str, float]]:
        """(doc_id, raw score) pairs, best first; ties broken by doc_id
        so the order is deterministic for a given candidate set."""
        return sorted(self.score(query).items(), key=lambda kv: (-kv[1], kv[0]))
