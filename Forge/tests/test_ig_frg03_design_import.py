"""TASK-IG-FRG-03: design-tool-to-agent pipeline (design spec -> build).

Corpus source: DcbDzR8yxCm (Stitch -> agent via MCP -> live site).
Pinned properties: a valid export becomes a deterministic brief +
manifest + goal; an invalid export is rejected whole with every
problem named; an unconfigured live source fails closed instead of
fabricating a design.
"""
from __future__ import annotations

import pytest

from app.integrations.design_import import (
    DesignSourceUnavailable,
    McpDesignSource,
    parse_design_spec,
    slugify,
)

SPEC = {
    "name": "Useless Website",
    "screens": [
        {
            "name": "Home",
            "route": "/",
            "components": [
                {"type": "hero", "name": "Hero"},
                {"type": "button", "name": "Big Red Button"},
            ],
        },
        {
            "name": "About Us",
            "route": "/about",
            "components": [{"type": "text", "name": "Story"}],
        },
    ],
    "tokens": {
        "colors": {"primary": "#ff0044", "background": "#101010"},
        "fonts": {"display": "Outfit, sans-serif"},
    },
}


def test_parse_valid_spec():
    brief = parse_design_spec(SPEC, source_tool="stitch", source_ref="file-123")
    assert brief.name == "Useless Website"
    assert brief.source_tool == "stitch"
    assert [s.name for s in brief.screens] == ["Home", "About Us"]
    assert brief.unique_components() == ["Hero", "Big Red Button", "Story"]


def test_manifest_is_explicit_and_deterministic():
    brief = parse_design_spec(SPEC)
    manifest = brief.to_manifest()
    paths = [e.path for e in manifest]
    assert paths[0] == "index.html"  # root screen
    assert "about-us.html" in paths
    assert "components/hero.html" in paths
    assert "components/big-red-button.html" in paths
    assert "assets/tokens.css" in paths
    assert "assets/design-brief.json" in paths
    assert brief.to_manifest() == manifest  # deterministic


def test_goal_names_every_manifest_file():
    brief = parse_design_spec(SPEC)
    goal = brief.to_goal()
    for entry in brief.to_manifest():
        assert entry.path in goal
    assert "Home" in goal and "About Us" in goal


def test_tokens_css_uses_design_tokens():
    brief = parse_design_spec(SPEC)
    css = brief.tokens_css()
    assert "--color-primary: #ff0044;" in css
    assert "--font-display: Outfit, sans-serif;" in css


def test_provenance_records_source():
    brief = parse_design_spec(SPEC, source_tool="figma", source_ref="abc")
    prov = brief.provenance()
    assert prov["source_tool"] == "figma"
    assert prov["source_ref"] == "abc"
    assert prov["screens"] == ["Home", "About Us"]


def test_invalid_spec_names_every_problem():
    bad = {"screens": [{"components": [{"name": "NoType"}]}]}
    with pytest.raises(ValueError) as exc:
        parse_design_spec(bad)
    message = str(exc.value)
    assert "spec.name" in message
    assert "screens[0].name" in message
    assert "components[0].type" in message


def test_empty_screens_rejected():
    with pytest.raises(ValueError):
        parse_design_spec({"name": "X", "screens": []})


def test_non_dict_spec_rejected():
    with pytest.raises(ValueError):
        parse_design_spec(["not", "a", "spec"])


def test_mcp_source_unconfigured_fails_closed():
    source = McpDesignSource()
    with pytest.raises(DesignSourceUnavailable):
        source.fetch_design("some-ref")


def test_mcp_source_with_fetcher_parses():
    source = McpDesignSource(fetcher=lambda ref: SPEC, tool_name="stitch")
    brief = source.fetch_design("file-9")
    assert brief.source_tool == "stitch"
    assert brief.source_ref == "file-9"
    assert brief.name == "Useless Website"


def test_mcp_source_fetcher_garbage_fails_closed():
    source = McpDesignSource(fetcher=lambda ref: {"bogus": True})
    with pytest.raises(ValueError):
        source.fetch_design("file-9")


def test_slugify():
    assert slugify("About Us!") == "about-us"
    assert slugify("  ") == "unnamed"
    assert slugify("Big Red Button") == "big-red-button"
