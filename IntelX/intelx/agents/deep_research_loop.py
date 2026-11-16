"""INTELX Iterative Deep-Research Loop (local-deep-research pattern, TASK-IG2-INT-02).

Pattern adapted from LearningCircuit/local-deep-research (MIT License,
https://github.com/LearningCircuit/local-deep-research): research is not a
single search-and-summarise pass but a loop —

    search -> grade sources -> analyse coverage -> generate follow-up
    queries for the gaps -> search again -> ... -> synthesise a cited report

FRIDAY adaptation — the pattern, not the deployment. The upstream stack
(Ollama with a 20B+ local model, a self-hosted SearXNG instance, its own
web/DB app, SQLCipher library) cannot fit the fleet's ~956MB VMs, so the loop
is implemented against IntelX's existing providers instead:

* search rounds go through the injected search callable — in production the
  existing ``WebSearchConnector`` (Tavily / SearXNG / Google News / Wikipedia /
  DuckDuckGo routing already lives there);
* source grading reuses ``SourceQuality`` (authority / relevance / freshness /
  independence) with a relevance floor, instead of a new scoring stack;
* the coverage/stopping decision reuses the existing ``EvidenceFirstAgent``
  controller rather than a second, divergent stopping rule;
* follow-up queries come from the existing ``QueryPortfolioPlanner`` angle
  portfolio (direct -> latest -> official -> technical -> counterevidence ->
  historical), so later rounds attack a subquestion from angles earlier
  rounds have not tried;
* synthesis is a deterministic, extractive cited brief: every statement is a
  graded source's own snippet carrying its citation marker. An LLM
  synthesizer (``SynthesizerAgent``) can consume ``sources`` /
  ``evidence_by_item`` downstream, but the loop itself never fabricates
  prose, so its output is honest even with no model available.

The loop is bounded on every axis: rounds, total sources, queries per round,
and it stops early on full coverage or diminishing returns (a round that
keeps no new source ends the loop instead of burning the run budget).
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlsplit

from intelx.agents.query_planner import QueryPortfolioPlanner
from intelx.agents.research_agent import EvidenceFirstAgent
from intelx.connectors.search import SearchResult
from intelx.connectors.source_quality import SourceQuality

logger = logging.getLogger(__name__)


@dataclass
class GradedSource:
    """A search result that survived grading, bound to the subquestion it serves."""

    url: str
    title: str
    snippet: str
    plan_item_id: str
    query_text: str
    round_index: int
    quality_total: float
    quality_bucket: str
    authority: float
    relevance: float
    domain: str
    citation_index: int = 0  # assigned at synthesis, 1-based


@dataclass
class LoopRound:
    """Telemetry for one loop iteration."""

    index: int
    queries: list[str] = field(default_factory=list)
    results_seen: int = 0
    sources_kept: int = 0
    rejected_low_quality: int = 0
    duplicates_skipped: int = 0
    search_failures: int = 0


@dataclass
class DeepResearchResult:
    """Outcome of an iterative deep-research run."""

    question: str
    plan_items: list[str]
    sources: list[GradedSource]
    evidence_by_item: dict[str, list[GradedSource]]
    rounds: list[LoopRound]
    stop_reason: str
    coverage_ratio: float
    covered_items: list[str]
    missing_items: list[str]
    synthesis_markdown: str
    elapsed_s: float = 0.0

    def to_source_candidates(self) -> list[Any]:
        """Return kept sources as Scout ``SourceCandidate`` objects for retrieval.

        The import is deferred: ``intelx.agents.scout`` pulls in the DB layer,
        and this module must stay importable in connector-level contexts.
        """
        from intelx.agents.scout import SourceCandidate

        return [
            SourceCandidate(
                location=s.url,
                title=s.title,
                reason=(
                    f"deep-research loop round {s.round_index} via query "
                    f"{s.query_text!r}; quality {s.quality_total:.2f} ({s.quality_bucket})"
                ),
                expected_relevance=max(0.0, min(1.0, s.quality_total)),
                snippet=s.snippet or None,
            )
            for s in self.sources
        ]


@dataclass(frozen=True)
class _ClaimRef:
    """Minimal claim shape the EvidenceFirstAgent controller reads."""

    plan_item_id: str
    status: str = "ACTIVE"


class IterativeDeepResearcher:
    """LearningCircuit-style iterative search -> grade -> synthesise loop.

    ``search`` may be a ``WebSearchConnector`` (anything with an async
    ``fetch(query) -> list[SearchResult]``) or a plain async callable with
    the same return shape, which is how tests and other agents inject
    alternative providers.
    """

    def __init__(
        self,
        search: Any,
        quality: SourceQuality | None = None,
        controller: EvidenceFirstAgent | None = None,
        planner: QueryPortfolioPlanner | None = None,
        max_rounds: int = 3,
        max_sources: int = 25,
        min_quality: float = 0.60,
        min_sources_per_item: int = 2,
        max_queries_per_round: int = 8,
        results_per_query: int = 8,
    ) -> None:
        if max_rounds < 1 or max_sources < 1 or min_sources_per_item < 1:
            raise ValueError("loop budgets must be positive")
        if not 0.0 <= min_quality <= 1.0:
            raise ValueError("min_quality must be within [0, 1]")
        self._search = search
        self.quality = quality or SourceQuality()
        self.controller = controller or EvidenceFirstAgent()
        self.planner = planner or QueryPortfolioPlanner()
        self.max_rounds = max_rounds
        self.max_sources = max_sources
        self.min_quality = min_quality
        self.min_sources_per_item = min_sources_per_item
        self.max_queries_per_round = max_queries_per_round
        self.results_per_query = results_per_query

    async def _run_search(self, query: str) -> list[SearchResult]:
        fetch = getattr(self._search, "fetch", None)
        if callable(fetch):
            return await fetch(query, max_results=self.results_per_query)
        return await self._search(query)

    def _queries_for_round(
        self,
        round_index: int,
        uncovered: list[str],
        plan_items: list[str],
        issued: set[str],
    ) -> list[tuple[str, str]]:
        """Pick this round's (plan_item_id, query) pairs from untried angles.

        Round 0 leads with each item's direct query. Later rounds walk the
        portfolio angles in priority order, skipping any query text already
        issued in an earlier round, so every round asks something new.
        """
        pairs: list[tuple[str, str]] = []
        for item in uncovered:
            portfolio = sorted(
                self.planner.build(item, item), key=lambda q: q.priority, reverse=True
            )
            fresh = [q for q in portfolio if q.text not in issued]
            if not fresh:
                continue
            # Early rounds take the single best untried angle per item so all
            # gaps advance together; the final round sweeps two per item.
            take = 2 if round_index >= self.max_rounds - 1 else 1
            for query in fresh[:take]:
                pairs.append((item, query.text))
        pairs = pairs[: self.max_queries_per_round]
        if round_index == 0 and not pairs and plan_items:
            fallback = plan_items[0]
            if fallback not in issued:
                pairs = [(fallback, fallback)]
        return pairs

    async def research(
        self,
        question: str,
        plan_items: list[str] | None = None,
    ) -> DeepResearchResult:
        """Run the loop for ``question`` over ``plan_items`` subquestions."""
        started = time.monotonic()
        items = [str(i).strip() for i in (plan_items or [question]) if str(i).strip()]
        if not items:
            items = [question]

        sources: list[GradedSource] = []
        evidence_by_item: dict[str, list[GradedSource]] = {item: [] for item in items}
        seen_urls: set[str] = set()
        domain_counts: dict[str, int] = {}
        issued_queries: set[str] = set()
        rounds: list[LoopRound] = []
        stop_reason = "max_rounds"

        for round_index in range(self.max_rounds):
            uncovered = [
                item
                for item in items
                if len(evidence_by_item[item]) < self.min_sources_per_item
            ]
            if not uncovered:
                stop_reason = "coverage_complete"
                break
            if len(sources) >= self.max_sources:
                stop_reason = "source_budget"
                break

            pairs = self._queries_for_round(round_index, uncovered, items, issued_queries)
            if not pairs:
                stop_reason = "queries_exhausted"
                break
            record = LoopRound(index=round_index, queries=[q for _, q in pairs])
            rounds.append(record)

            for item, query_text in pairs:
                issued_queries.add(query_text)
                try:
                    results = await self._run_search(query_text)
                except Exception as exc:
                    record.search_failures += 1
                    logger.warning(
                        "deep-research search failed for %r (%s)", query_text, type(exc).__name__
                    )
                    continue
                record.results_seen += len(results)
                query_terms = set(self.planner.keywords(item))
                for result in results:
                    if len(sources) >= self.max_sources:
                        break
                    url = (result.url or "").strip()
                    if not url or url in seen_urls:
                        record.duplicates_skipped += 1
                        continue
                    seen_urls.add(url)
                    domain = (urlsplit(url).hostname or "").lower()
                    score = self.quality.score(
                        url,
                        result.title or "",
                        result.snippet or "",
                        query_terms,
                        duplicate_count=domain_counts.get(domain, 0),
                    )
                    if score.total < self.min_quality:
                        record.rejected_low_quality += 1
                        continue
                    graded = GradedSource(
                        url=url,
                        title=result.title or url,
                        snippet=result.snippet or "",
                        plan_item_id=item,
                        query_text=query_text,
                        round_index=round_index,
                        quality_total=score.total,
                        quality_bucket=self.quality.quality_bucket(score.total),
                        authority=score.authority,
                        relevance=score.relevance,
                        domain=domain,
                    )
                    sources.append(graded)
                    evidence_by_item[item].append(graded)
                    domain_counts[domain] = domain_counts.get(domain, 0) + 1
                    record.sources_kept += 1

            decision = self.controller.decide(
                plan_items=items,
                sources=sources,
                evidence=[s for s in sources if s.snippet],
                claims=[_ClaimRef(plan_item_id=s.plan_item_id) for s in sources],
                min_sources=min(2, self.max_sources),
                max_sources=self.max_sources,
                target_claims_per_item=self.min_sources_per_item,
            )
            if decision.plan_complete:
                stop_reason = "coverage_complete"
                break
            if len(sources) >= self.max_sources:
                stop_reason = "source_budget"
                break
            if record.sources_kept == 0 and round_index >= 1:
                stop_reason = "diminishing_returns"
                break

        ranked = sorted(sources, key=lambda s: (-s.quality_total, s.round_index, s.url))
        for idx, source in enumerate(ranked, start=1):
            source.citation_index = idx
        covered = [
            item for item in items if len(evidence_by_item[item]) >= self.min_sources_per_item
        ]
        missing = [item for item in items if item not in covered]
        coverage = len(covered) / len(items) if items else 1.0
        synthesis = self._synthesize(
            question, items, evidence_by_item, ranked, stop_reason, coverage
        )

        return DeepResearchResult(
            question=question,
            plan_items=items,
            sources=ranked,
            evidence_by_item=evidence_by_item,
            rounds=rounds,
            stop_reason=stop_reason,
            coverage_ratio=coverage,
            covered_items=covered,
            missing_items=missing,
            synthesis_markdown=synthesis,
            elapsed_s=round(time.monotonic() - started, 3),
        )

    @staticmethod
    def _synthesize(
        question: str,
        items: list[str],
        evidence_by_item: dict[str, list[GradedSource]],
        ranked: list[GradedSource],
        stop_reason: str,
        coverage: float,
    ) -> str:
        """Build the deterministic cited brief (extractive — no invented prose)."""
        lines = [
            f"# Deep research: {question}",
            "",
            f"Coverage: {coverage:.0%} of subquestions met the evidence bar; "
            f"loop stopped on {stop_reason}; {len(ranked)} graded sources.",
            "",
        ]
        for item in items:
            lines.append(f"## {item}")
            item_sources = sorted(
                evidence_by_item.get(item, []), key=lambda s: -s.quality_total
            )
            if not item_sources:
                lines.append("- No source met the quality bar for this subquestion.")
            for source in item_sources:
                snippet = " ".join((source.snippet or source.title).split())[:300]
                lines.append(f"- {snippet} [{source.citation_index}]")
            lines.append("")
        if ranked:
            lines.append("## Sources")
            for source in ranked:
                lines.append(
                    f"[{source.citation_index}] {source.title} — {source.url} "
                    f"(quality {source.quality_total:.2f}, {source.quality_bucket})"
                )
        return "\n".join(lines).strip() + "\n"


__all__ = [
    "DeepResearchResult",
    "GradedSource",
    "IterativeDeepResearcher",
    "LoopRound",
]
