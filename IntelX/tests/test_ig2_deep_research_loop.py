"""Tests for TASK-IG2-INT-02: iterative deep-research loop for IntelX.

The LearningCircuit loop (search -> grade -> follow-up queries -> cited
synthesis) is exercised against a fake search provider: no network, no LLM.
"""

import pytest

from intelx.agents.deep_research_loop import IterativeDeepResearcher
from intelx.connectors.search import SearchResult

ITEM_A = "solid state battery dendrite suppression evidence"
ITEM_B = "sulfide electrolyte cycling stability data"

JUNK = SearchResult(
    url="https://pinterest.com/pin/1",
    title="cute phone cases",
    snippet="shop cute cases now",
)


def _a_results():
    return [
        SearchResult(
            url="https://arxiv.org/abs/1234.5678",
            title="Solid state battery dendrite suppression study",
            snippet="solid state battery dendrite suppression evidence from cycling experiments",
        ),
        SearchResult(
            url="https://www.nature.com/articles/s41586-001",
            title="Dendrite suppression in solid state battery cells",
            snippet="battery dendrite suppression measurements and evidence",
        ),
        JUNK,
    ]


def _b_results():
    return [
        SearchResult(
            url="https://arxiv.org/abs/9999.0001",
            title="Sulfide electrolyte cycling stability",
            snippet="sulfide electrolyte cycling stability data for solid state cells",
        ),
        SearchResult(
            url="https://www.energy.gov/eere/sulfide-report",
            title="Sulfide electrolyte stability report",
            snippet="electrolyte cycling stability data summary",
        ),
        JUNK,
    ]


class FakeSearch:
    """Connector-shaped fake: records queries, answers by topic keyword."""

    def __init__(self, latest_extra=None):
        self.queries: list[str] = []
        self._latest_extra = latest_extra

    async def fetch(self, target, **kwargs):
        self.queries.append(target)
        if "latest" in target and self._latest_extra is not None:
            return self._latest_extra
        if "dendrite" in target:
            return _a_results()
        if "sulfide" in target:
            return _b_results()
        return []


async def test_loop_reaches_coverage_and_synthesises_citations():
    search = FakeSearch()
    researcher = IterativeDeepResearcher(search, min_sources_per_item=2, max_rounds=3)
    result = await researcher.research("battery research", plan_items=[ITEM_A, ITEM_B])

    assert result.stop_reason == "coverage_complete"
    assert result.coverage_ratio == 1.0
    assert result.missing_items == []
    assert len(result.rounds) == 1
    assert len(result.sources) == 4
    assert {s.citation_index for s in result.sources} == {1, 2, 3, 4}
    assert "[1]" in result.synthesis_markdown
    assert "## Sources" in result.synthesis_markdown
    assert all("pinterest" not in s.url for s in result.sources)


async def test_loop_rejects_low_quality_sources():
    search = FakeSearch()
    researcher = IterativeDeepResearcher(search, min_sources_per_item=2, max_rounds=1)
    result = await researcher.research("battery research", plan_items=[ITEM_A])
    assert result.rounds[0].rejected_low_quality >= 1
    assert result.rounds[0].sources_kept == 2


async def test_loop_follows_up_with_new_angles_for_gaps():
    extra = [
        SearchResult(
            url="https://arxiv.org/abs/5555.0001",
            title="More dendrite suppression evidence",
            snippet="solid state battery dendrite suppression evidence update",
        )
    ]
    class OneShotSearch(FakeSearch):
        async def fetch(self, target, **kwargs):
            self.queries.append(target)
            if "latest" in target:
                return extra
            if "dendrite" in target:
                return _a_results()[:1]  # only one good source in round 0
            return []

    researcher = IterativeDeepResearcher(OneShotSearch(), min_sources_per_item=2, max_rounds=3)
    result = await researcher.research("battery research", plan_items=[ITEM_A])

    assert result.stop_reason == "coverage_complete"
    assert len(result.rounds) == 2
    assert any("latest" in q for q in result.rounds[1].queries)
    assert result.rounds[0].queries != result.rounds[1].queries


async def test_loop_stops_on_diminishing_returns():
    search = FakeSearch()
    researcher = IterativeDeepResearcher(search, min_sources_per_item=5, max_rounds=4)
    result = await researcher.research("battery research", plan_items=[ITEM_A])
    # Round 0 keeps the 2 good sources; later rounds only re-see duplicates.
    assert result.stop_reason == "diminishing_returns"
    assert result.rounds[-1].sources_kept == 0
    assert result.rounds[-1].duplicates_skipped >= 1


async def test_loop_respects_source_budget():
    search = FakeSearch()
    researcher = IterativeDeepResearcher(
        search, min_sources_per_item=5, max_rounds=3, max_sources=2
    )
    result = await researcher.research("battery research", plan_items=[ITEM_A, ITEM_B])
    assert result.stop_reason == "source_budget"
    assert len(result.sources) == 2


async def test_loop_accepts_plain_async_callable_search():
    async def search_fn(query, **kwargs):
        return _a_results() if "dendrite" in query else []

    researcher = IterativeDeepResearcher(search_fn, min_sources_per_item=2, max_rounds=2)
    result = await researcher.research("battery research", plan_items=[ITEM_A])
    assert result.stop_reason == "coverage_complete"
    assert len(result.sources) == 2


async def test_loop_reports_missing_items_honestly():
    search = FakeSearch()
    researcher = IterativeDeepResearcher(search, min_sources_per_item=2, max_rounds=2)
    result = await researcher.research(
        "battery research", plan_items=[ITEM_A, "unobtainium fusion reactor blueprint"]
    )
    assert "unobtainium fusion reactor blueprint" in result.missing_items
    assert "No source met the quality bar" in result.synthesis_markdown


async def test_to_source_candidates_shape():
    search = FakeSearch()
    researcher = IterativeDeepResearcher(search, min_sources_per_item=2, max_rounds=1)
    result = await researcher.research("battery research", plan_items=[ITEM_A])
    candidates = result.to_source_candidates()
    assert len(candidates) == len(result.sources)
    assert candidates[0].location == result.sources[0].url
    assert "deep-research loop" in candidates[0].reason


def test_invalid_budgets_raise():
    with pytest.raises(ValueError):
        IterativeDeepResearcher(FakeSearch(), max_rounds=0)
    with pytest.raises(ValueError):
        IterativeDeepResearcher(FakeSearch(), min_quality=1.5)
