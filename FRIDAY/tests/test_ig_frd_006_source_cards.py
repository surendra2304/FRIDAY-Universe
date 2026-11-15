"""TASK-IG-FRD-006 — source-card extraction and attachment tests."""

from __future__ import annotations

from types import SimpleNamespace

from friday.cognition.source_cards import (
    attach_source_cards,
    extract_source_cards,
)
from friday.core.types import AgentResponse, ToolResult


def _result(content="", metadata=None, name="web_search"):
    return ToolResult(name=name, content=content, metadata=metadata or {})


def test_extract_from_structured_dicts():
    results = [
        _result(metadata={"sources": [
            {"title": "NASA release", "url": "https://nasa.gov/a", "snippet": "Water found"},
            {"title": "Paper", "url": "https://arxiv.org/abs/1"},
        ]})
    ]
    cards = extract_source_cards(results)
    assert [c.url for c in cards] == ["https://nasa.gov/a", "https://arxiv.org/abs/1"]
    assert cards[0].title == "NASA release"
    assert cards[0].publisher == "nasa.gov"
    assert cards[0].claim == "Water found"
    assert cards[0].via == "web_search"


def test_extract_bare_urls_from_text_and_dedupe():
    results = [
        _result(content="See https://example.com/x and https://example.com/x again, plus https://other.org/y."),
    ]
    cards = extract_source_cards(results)
    assert [c.url for c in cards] == ["https://example.com/x", "https://other.org/y"]
    assert cards[0].title == "example.com"  # honest fallback: the domain


def test_no_sources_no_cards():
    assert extract_source_cards([_result(content="no links here")]) == []
    assert extract_source_cards([]) == []
    assert extract_source_cards(None) == []


def test_attach_sets_metadata_and_appends_section():
    response = AgentResponse(
        content="Water was found on the Moon.",
        tool_results=[_result(metadata={"sources": [{"title": "NASA", "url": "https://nasa.gov/a"}]})],
    )
    out = attach_source_cards(response)
    assert out.metadata["source_cards"][0]["url"] == "https://nasa.gov/a"
    assert "Sources:" in out.content
    assert "https://nasa.gov/a" in out.content
    # Original object is not mutated (model_copy).
    assert "Sources:" not in response.content


def test_attach_is_idempotent_for_section():
    response = AgentResponse(
        content="Answer.",
        tool_results=[_result(content="ref https://example.com/x")],
    )
    once = attach_source_cards(response)
    twice = attach_source_cards(once)
    assert twice.content.count("Sources:") == 1


def test_attach_untouched_without_sources():
    response = AgentResponse(content="Plain answer.", tool_results=[_result(content="nothing")])
    out = attach_source_cards(response)
    assert out.content == "Plain answer."
    assert "source_cards" not in out.metadata


def test_attach_untouched_without_tool_results():
    response = AgentResponse(content="Hi.")
    assert attach_source_cards(response) is response
    stub = SimpleNamespace(content="x", tool_results=None, metadata={})
    assert attach_source_cards(stub) is stub


def test_cap_at_eight():
    many = [{"title": f"S{i}", "url": f"https://s{i}.example.com/"} for i in range(20)]
    cards = extract_source_cards([_result(metadata={"sources": many})])
    assert len(cards) == 8
