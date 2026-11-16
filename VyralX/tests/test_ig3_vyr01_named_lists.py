"""TASK-IG3-VYR-01: the corpus's named lists, recorded in the strategy data.

The full re-watch diff (clusters B129/B132/B136; package entries
V-04/V-06/V-07) found that wave-1/wave-2 stored the channel-strategy
*patterns* but never the named lists themselves: the seven teaching
channels, the Photopea browser toolkit, the five-generator shortlist
and the free-for-paid tool swaps existed nowhere in VyralX data.

Behaviour pinned here:

* every named list is present in channel_strategy.json with exactly
  the names the corpus recorded — no additions, no silent drops;
* every section is marked reference-only / pattern-notes with IG
  sources, so no name can be mistaken for an adopted tool or niche;
* the faceless-idea examples carry an explicit NOT-adopted marker
  (several conflict with the owner's lanes or the compliance gate);
* the pre-existing VYR-10 invariants still hold (three lanes, the
  Silk Road seed, the creator-tools pointer untouched).

On clean main every test fails: the sections do not exist.
"""
from __future__ import annotations

import json
from pathlib import Path

_DATA = (Path(__file__).resolve().parent.parent / "app" / "data"
         / "channel_strategy.json")
_DOC = (Path(__file__).resolve().parent.parent / "docs"
        / "CHANNEL_STRATEGY.md")

_REFERENCE_STATUSES = {"reference_only_unverified", "pattern_notes_only"}


def _load():
    return json.loads(_DATA.read_text(encoding="utf-8"))


def _assert_reference(section: dict) -> None:
    assert section["status"] in _REFERENCE_STATUSES
    assert section["ig_sources"], "section must carry its IG sources"
    assert "unverified" in section["note"].casefold() or \
        "creator" in section["note"].casefold() or \
        "pattern notes" in section["note"].casefold()


def test_teaching_channel_watchlist_names_all_seven():
    data = _load()
    section = data["teaching_channel_watchlist"]
    _assert_reference(section)
    assert section["channels"] == [
        "Make Money Matt", "Dave Nick", "James Jernigan", "AI Guy",
        "Varun Mayya", "Sandeep Swadia", "Film Booth"]
    assert section["ig_sources"] == ["Dd7wM1giLJ1"]


def test_browser_toolkit_names_the_three_tools():
    data = _load()
    section = data["browser_toolkit_reference"]
    _assert_reference(section)
    assert [t["name"] for t in section["tools"]] == [
        "Photopea", "Remove.bg", "Cleanup.pictures"]
    assert all(t["role"] for t in section["tools"])
    assert section["ig_sources"] == ["DZ7MtMhjAZI"]


def test_free_generator_shortlist_names_all_five():
    data = _load()
    section = data["free_generator_shortlist"]
    _assert_reference(section)
    assert section["tools"] == ["YesChat", "Vidnoz", "Clipfly",
                                 "Canva", "VEED.IO"]
    assert section["ig_sources"] == ["Dee1ZxUybxd"]
    # The corpus comparison scores are deliberately NOT recorded.
    assert "scores are not" in section["note"]


def test_faceless_idea_examples_recorded_but_not_adopted():
    data = _load()
    section = data["faceless_idea_examples"]
    _assert_reference(section)
    assert section["ideas_named"] == [
        "Classic Cars", "Courtroom Cases", "Finance Tips",
        "AI Tutorials", "Conspiracy Theories", "Plane Crashes",
        "Women's Fashion", "YouTuber Drama"]
    assert "NOT adopted" in section["adoption"]
    assert section["claimed_rpm_usd"] == [3, 15]
    assert section["ig_sources"] == ["DeUpDUwDID-"]


def test_free_route_alternatives_record_all_six_swaps():
    data = _load()
    section = data["free_route_alternatives"]
    _assert_reference(section)
    swaps = {(s["free_route"], s["paid_counterpart"])
             for s in section["swaps"]}
    assert swaps == {
        ("Sora 2", "Google Veo 3"), ("MiniMax", "ElevenLabs"),
        ("NanoBanana", "Seedream 4"), ("Wan 2.6", "RunwayML"),
        ("SadTalker", "HeyGen"), ("Gamma AI", "Plus AI")}
    assert "disputed" in section["note"]
    # The generated-footage gate is named as unchanged: this section
    # must never read as admission of generated media.
    assert "gate is unchanged" in section["note"]


def test_listicle_tool_patterns_are_notes_only():
    data = _load()
    section = data["listicle_tool_patterns"]
    assert section["status"] == "pattern_notes_only"
    assert section["tools"] == ["Wireflo", "ZSKY AI", "D-ID Studio",
                                 "Steve AI", "Pictory"]
    assert set(section["ig_sources"]) == {"DdePxRHk3mB", "DeMoCfwCHE8"}


def test_vyr10_invariants_untouched():
    data = _load()
    assert {e["lane"] for e in data["lanes"]} == {
        "space_science", "history", "tech_ai"}
    assert data["creator_tools_reference"]["status"] == \
        "reference_only_unverified"
    assert "ig_source" not in data["creator_tools_reference"] or \
        data["creator_tools_reference"]["ig_source"] == "DeKGOHHE0Rh"
    assert len(data["series_seeds"]) == 1


def test_doc_names_the_recorded_lists():
    doc = _DOC.read_text(encoding="utf-8")
    assert "TASK-IG3-VYR-01" in doc
    for marker in ("teaching_channel_watchlist", "browser_toolkit_reference",
                   "free_generator_shortlist", "faceless_idea_examples",
                   "free_route_alternatives", "listicle_tool_patterns"):
        assert marker in doc


# --- Production wiring (AUDIT-2: the data must be reachable from
# --- the app path, not only from tests) ---------------------------

_MAIN = (Path(__file__).resolve().parent.parent / "app" / "main.py")


def test_loader_serves_every_reference_section():
    from app.services import channel_strategy as cs

    data = cs.load_strategy()
    sections = cs.reference_sections(data)
    assert set(sections) == {
        "creator_tools_reference", "teaching_channel_watchlist",
        "browser_toolkit_reference", "free_generator_shortlist",
        "faceless_idea_examples", "free_route_alternatives",
        "listicle_tool_patterns"}
    # Serving a name never upgrades its recorded status.
    for section in sections.values():
        assert section["status"] in _REFERENCE_STATUSES
    with __import__("pytest").raises(KeyError):
        cs.get_reference(data, "no_such_section")


def test_strategy_routes_answer_and_404():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from app.services import channel_strategy as cs

    app = FastAPI()
    app.include_router(cs.router, prefix="/api/v1")
    client = TestClient(app)

    res = client.get("/api/v1/strategy/references")
    assert res.status_code == 200
    body = res.json()
    assert "unverified" in body["honesty_note"].casefold()
    assert body["sections"]["teaching_channel_watchlist"]["channels"][0] \
        == "Make Money Matt"

    res = client.get("/api/v1/strategy/references/free_generator_shortlist")
    assert res.status_code == 200
    assert res.json()["section"]["tools"][-1] == "VEED.IO"

    res = client.get("/api/v1/strategy/lanes")
    assert res.status_code == 200
    assert {e["lane"] for e in res.json()["lanes"]} == {
        "space_science", "history", "tech_ai"}

    res = client.get("/api/v1/strategy/references/nope")
    assert res.status_code == 404


def test_main_mounts_the_strategy_router():
    main_src = _MAIN.read_text(encoding="utf-8")
    assert "from app.services.channel_strategy import router as " \
        "channel_strategy_router" in main_src
    assert "app.include_router(channel_strategy_router" in main_src
