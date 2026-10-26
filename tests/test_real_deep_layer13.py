"""Robin-inspired offline OSINT extraction, deduplication and URL policy."""
from __future__ import annotations

import pytest
import importlib.util
from pathlib import Path
import sys

# Load the standalone engine without IntelX's optional FastAPI application imports.
spec = importlib.util.spec_from_file_location(
    "real_onion_research", Path(__file__).resolve().parents[1] /
    "IntelX/intelx/services/real_onion_research.py")
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)
OnionResearchEngine = module.OnionResearchEngine
ResearchHit = module.ResearchHit


@pytest.mark.parametrize("url", ["https://abc.onion.evil/", "https://abc.onion@evil/",
    "https://evil@abc.onion/", "https://abc.onion\\@evil/", "https://abc.onion:bad/",
    "https://abc.onion/\n", "file:///abc.onion", "https:///missing", "https://.onion/"])
def test_reject_ambiguous_destinations(url):
    with pytest.raises(ValueError):
        OnionResearchEngine().validate(url)


def test_normalization_and_explicit_clearweb():
    engine = OnionResearchEngine()
    assert engine.validate("https://ABC.onion/a#fragment") == "https://abc.onion/a"
    assert engine.validate("https://example.com", allow_clearweb=True) == "https://example.com/"


def test_wrapper_preserves_target_query():
    target = OnionResearchEngine().extract_target(
        "/redirect?url=http%3A%2F%2Ftarget.onion%2Fa%3Fx%3D1%26y%3D2&ref=engine",
        "http://engine.onion")
    assert target == "http://target.onion/a?x=1&y=2"


def test_external_wrapper_is_not_unwrapped():
    assert OnionResearchEngine().extract_target(
        "https://evil.com/?url=http%3A%2F%2Ftarget.onion", "http://engine.onion") is None


def test_engine_navigation_is_not_a_result():
    assert OnionResearchEngine().extract_target("/about", "http://engine.onion") is None


def test_dedup_host_diversity_and_accounting():
    batch = OnionResearchEngine().process([
        ResearchHit("First title", "http://a.onion/p?id=1&utm_source=x"),
        ResearchHit("Duplicate", "http://a.onion/p?fbclid=y&id=1"),
        ResearchHit("Other content", "http://a.onion/p?id=2"),
        ResearchHit("Second host", "http://b.onion/"),
        ResearchHit("Clearweb", "https://example.com/"),
        ResearchHit("!!!", "http://c.onion/"),
    ], per_host_limit=1)
    assert len(batch.hits) == 2
    assert batch.distinct_hosts == 2
    assert (batch.rejected_count, batch.duplicate_count, batch.capped_count) == (2, 1, 1)
    assert batch.raw_count == len(batch.hits) + batch.rejected_count + batch.duplicate_count + batch.capped_count


def test_content_parameters_are_not_tracking():
    engine = OnionResearchEngine()
    assert engine.canonical_key("http://a.onion/?id=1") != engine.canonical_key("http://a.onion/?id=2")
    assert engine.canonical_key("http://a.onion/?b=2&a=1") == engine.canonical_key("http://a.onion/?a=1&b=2")


def test_title_sanitization_and_empty_batch():
    engine = OnionResearchEngine()
    result = engine.process([ResearchHit("Long\x00 title " * 40, "http://a.onion")])
    assert len(result.hits[0].title) == 200
    assert "\x00" not in result.hits[0].title
    assert engine.process([]).raw_count == 0
    with pytest.raises(ValueError):
        engine.process([], 0)
