"""TASK-IG-VYR-10: channel strategy references (IG corpus strategy cluster).

Behaviour pinned here:

* the strategy JSON parses, covers exactly the owner's three
  lanes, and every lane entry carries IG sources;
* the Silk Road series seed is present, in the history lane, with
  chapter topics shaped for series_automation (validated by the
  IG-VYR-04 validator's contract — lane + topic list — without
  importing the sibling module: the shape is checked directly);
* the honesty rule is structural, not decorative: the JSON note
  and the doc both state the corpus claims are unverified, and
  the creator-tools reference is marked reference-only;
* the doc exists and names the publish gate (nothing here is
  permission to publish).

On clean main every test fails: the data file and doc do not
exist.
"""
from __future__ import annotations

import json
from pathlib import Path

_DATA = (Path(__file__).resolve().parent.parent / "app" / "data"
         / "channel_strategy.json")
_DOC = (Path(__file__).resolve().parent.parent / "docs"
        / "CHANNEL_STRATEGY.md")


def _load():
    return json.loads(_DATA.read_text(encoding="utf-8"))


def test_strategy_covers_exactly_the_owner_lanes():
    data = _load()
    assert {e["lane"] for e in data["lanes"]} == {
        "space_science", "history", "tech_ai"}
    for entry in data["lanes"]:
        assert entry["ig_sources"], entry["lane"]
        assert entry["pillars"] and entry["positioning"]
        assert entry["selection_criteria_met"]


def test_silk_road_seed_shape_fits_series_automation():
    data = _load()
    seeds = data["series_seeds"]
    assert len(seeds) == 1
    seed = seeds[0]
    assert seed["lane"] == "history"
    assert seed["ig_source"] == "DZP1ifcpIof"
    assert "Silk Road" in seed["title"]
    assert len(seed["topics"]) >= 5
    assert seed["cadence_days"] >= 1
    # series_automation spec shape: lane + title + topics list.
    spec = {"lane": seed["lane"], "title": seed["title"],
            "topics": seed["topics"]}
    assert spec["lane"] in {"space_science", "history", "tech_ai"}
    assert all(isinstance(t, str) and t for t in spec["topics"])


def test_honesty_markers_are_present():
    data = _load()
    assert "unverified" in data["note"].casefold()
    assert data["creator_tools_reference"]["status"] == \
        "reference_only_unverified"
    doc = _DOC.read_text(encoding="utf-8")
    assert "unverified creator claims" in doc
    assert "Not permission to publish" in doc
    assert "Silk Road" in doc
