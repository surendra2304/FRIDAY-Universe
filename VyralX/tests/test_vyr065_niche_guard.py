"""TASK-VYR-065: offline pins for the hard niche avoid-list guardrail.

Covers ``VyralX/app/services/niche_guard.py`` (the single rule set shared
by both discovery entry points) and its wiring into the two supervised-
cycle scripts and the app-level discovery service.

What is pinned:

* Each of the nine researched ban-list niches is rejected by rule, and the
  rejection reason names the niche.
* Banned-niche queries are rejected outright (no search is issued).
* Proven-good discovery material passes: the six flat-script QUERIES, the
  four non-flat QUERIES, and the merged VYR-055 refresh-3 pool titles.
* Near-misses pass: bare ``cricket`` (the insect), bare ``highlights``,
  bare ``exam`` — the rules are phrases, not single ambiguous words.
* Matching is case- and punctuation-insensitive.
* ``filter_candidates`` keeps order, stamps ``rejection_reason`` on
  copies only, never mutates its input, and drops ``None`` entries.
* Wiring: the flat script's ``run_query`` drops a banned-niche row from
  the pool and records the rejection; the app service
  (``app/services/discovery.py``) imports the guard and calls it — pinned
  by file content, since the service needs the app stack to import.

Stdlib + pytest only, fully offline: the flat script is driven by a stub
yt-dlp executable printing canned flat JSON lines, so no network and no
YouTube account are needed.

The live leg — a real discovery run on VyralX-Server showing banned-niche
rejections in the live log — is NOT claimed here: the owner stop order is
in force (watch058, hub 7144369853). It is the verifier's re-test when
the gate lifts.
"""

from __future__ import annotations

import importlib.util
import stat
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]  # VyralX/
GUARD = ROOT / "app" / "services" / "niche_guard.py"
FLAT_SCRIPT = ROOT / "scripts" / "find_viral_candidates_flat.py"
DISCOVERY = ROOT / "app" / "services" / "discovery.py"


def _load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def guard():
    return _load(GUARD, "vyr065_niche_guard")


@pytest.fixture(scope="module")
def flat():
    return _load(FLAT_SCRIPT, "vyr065_find_viral_candidates_flat")


# --- the nine banned niches ------------------------------------------------

# (candidate title, niche label fragment expected in the reason)
BANNED_CASES = [
    ("Top 10 Anime Moments of 2025", "anime compilations"),
    ("Best Anime Fights Compilation", "anime compilations"),
    ("Cricket Highlights: India vs Australia", "cricket/sports highlights"),
    ("Football Highlights | Best Goals 2025", "cricket/sports highlights"),
    ("Best Bollywood Songs Mashup", "Bollywood edits"),
    ("Bollywood Edits | SRK Scenes", "Bollywood edits"),
    ("Best Movie Scenes Compilation", "movie/TV scene compilations"),
    ("TV Show Scenes That Broke The Internet", "movie/TV scene compilations"),
    ("Celebrity Edits | Taylor Swift Moments", "celebrity edits"),
    ("Viral Clips Compilation - Funniest Moments", "unlicensed viral-clip compilations"),
    ("Best Viral Clips of the Week", "unlicensed viral-clip compilations"),
    ("Insane PUBG Gameplay Highlights", "borrowed gameplay"),
    ("Minecraft Gameplay | Building a Castle", "borrowed gameplay"),
    ("NEET Lecture | Biology Full Chapter", "borrowed exam lectures"),
    ("Board Exam Preparation | Class 10 Science", "borrowed exam lectures"),
    ("Best Stock Tips for Beginners", "automated finance advice"),
    ("Make Money Online | Passive Income 2025", "automated finance advice"),
    ("Crypto Signals Group | 100x Calls", "automated finance advice"),
]


@pytest.mark.parametrize("title,label", BANNED_CASES)
def test_each_banned_niche_is_rejected(guard, title, label):
    allowed, reason = guard.check_candidate({"title": title})
    assert allowed is False
    assert reason is not None
    assert label in reason
    assert "banned niche" in reason


def test_all_nine_niches_covered(guard):
    labels = {n["label"] for n in guard.BANNED_NICHES}
    assert labels == {
        "anime compilations",
        "cricket/sports highlights",
        "Bollywood edits",
        "movie/TV scene compilations",
        "celebrity edits",
        "unlicensed viral-clip compilations",
        "borrowed gameplay",
        "borrowed exam lectures",
        "automated finance advice",
    }


def test_rejection_reason_names_matched_phrase(guard):
    _, reason = guard.check_candidate({"title": "Cricket Highlights Daily"})
    assert reason == "banned niche: cricket/sports highlights (matched 'cricket highlights')"


def test_match_uses_description_and_channel_too(guard):
    # Title is clean; the banned niche is in the description / channel.
    assert guard.check_candidate(
        {"title": "Oddly satisfying soap carving", "description": "Best anime moments"}
    )[0] is False
    assert guard.check_candidate(
        {"title": "Soap carving ASMR", "channel": "Bollywood Edits Daily"}
    )[0] is False


# --- queries ----------------------------------------------------------------

@pytest.mark.parametrize(
    "query",
    [
        "anime compilations best moments",
        "cricket highlights 2025",
        "bollywood edits new",
        "best stock tips today",
    ],
)
def test_banned_query_is_rejected(guard, query):
    allowed, reason = guard.check_query(query)
    assert allowed is False
    assert "banned niche" in reason


@pytest.mark.parametrize(
    "query",
    [
        "most satisfying video ever short",
        "incredible street magic revealed short",
        "satisfying hydraulic press crushing short",
        "amazing domino art chain reaction short",
        "oddly satisfying soap carving short",
        "epic basketball trick shot short",
        "oddly satisfying visual craft silent",
        "insane human precision trickshot silent",
        "mesmerizing soap cutting satisfying asmr",
        "satisfying industrial loop machine silent",
    ],
)
def test_proven_discovery_queries_pass(guard, query):
    assert guard.check_query(query) == (True, None)


# --- allowed material passes -----------------------------------------------

ALLOWED_TITLES = [
    "Domino Effect V10",
    "NASA Webb Telescope: Deep Field in 60 seconds",
    "Oddly Satisfying Soap Carving ASMR",
    "Hydraulic Press vs Bowling Ball",
    "Street Magic Revealed: Card Trick Tutorial",
    "James Webb Space Telescope Images Explained",
    "Satisfying Kinetic Sand Cutting",
    "How Black Holes Bend Light",
]


@pytest.mark.parametrize("title", ALLOWED_TITLES)
def test_allowed_titles_pass(guard, title):
    assert guard.check_candidate({"title": title}) == (True, None)


# --- near-misses pass (phrases, not bare ambiguous words) -------------------

def test_near_misses_pass(guard):
    assert guard.check_candidate({"title": "Cricket sounds for sleep 8 hours"}) == (True, None)
    assert guard.check_candidate({"title": "NASA highlights of the week"}) == (True, None)
    assert guard.check_candidate({"title": "Exam season: how to stay calm"}) == (True, None)
    assert guard.check_candidate({"title": "Football training drills for kids"}) == (True, None)


def test_matching_is_case_and_punctuation_insensitive(guard):
    allowed, reason = guard.check_candidate({"title": "ANIME: Best-Fights Compilation!"})
    assert allowed is False
    assert "anime compilations" in reason


# --- filter_candidates -------------------------------------------------------

def test_filter_keeps_order_and_stamps_reason_without_mutating(guard):
    clean = {"id": "ok1", "title": "Domino Effect V10", "duration": 49}
    banned = {"id": "bad1", "title": "Cricket Highlights Daily", "duration": 30}
    kept, rejected = guard.filter_candidates([clean, banned, None, clean], log=False)
    assert [c["id"] for c in kept] == ["ok1", "ok1"]
    assert len(rejected) == 1
    assert rejected[0]["id"] == "bad1"
    assert rejected[0]["rejection_reason"] == (
        "banned niche: cricket/sports highlights (matched 'cricket highlights')"
    )
    # Inputs untouched: no stamp leaked into the caller's dicts.
    assert "rejection_reason" not in banned
    assert "rejection_reason" not in clean


def test_filter_empty_and_none_inputs(guard):
    assert guard.filter_candidates([], log=False) == ([], [])
    assert guard.filter_candidates(None, log=False) == ([], [])


def test_missing_and_non_string_fields_do_not_crash(guard):
    assert guard.check_candidate({}) == (True, None)
    assert guard.check_candidate({"title": None, "description": 42}) == (True, None)
    assert guard.check_candidate("not a dict") == (True, None)
    assert guard.check_query("") == (True, None)
    assert guard.check_query(None) == (True, None)


# --- flat-script wiring (stub yt-dlp) ---------------------------------------

_STUB = """#!/usr/bin/env python3
import json
rows = [
    {"id": "clean1", "title": "Domino Effect V10", "duration": 49,
      "view_count": 116695080, "uploader": "Idan David Animations",
      "channel": "Idan David Animations"},
    {"id": "banned1", "title": "Cricket Highlights Daily", "duration": 30,
      "view_count": 99999999, "uploader": "Highlights Hub",
      "channel": "Highlights Hub"},
    {"id": "longform1", "title": "Compilation", "duration": 112,
      "view_count": 22027536, "uploader": "Alexa Real",
      "channel": "Alexa Real"},
]
for row in rows:
    print(json.dumps(row))
"""


@pytest.fixture
def stub_ytdlp(tmp_path):
    stub = tmp_path / "yt-dlp"
    stub.write_text(_STUB)
    stub.chmod(stub.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return str(stub)


def test_flat_run_query_drops_banned_niche_and_records_reason(flat, stub_ytdlp):
    out = flat.run_query("amazing domino art chain reaction short",
                         stub_ytdlp, None, set())
    assert [e["id"] for e in out["fresh"]] == ["clean1"]
    assert out["rejected_niche"] == 1
    assert out["rejected_niche_reasons"] == [
        {"id": "banned1",
         "rejection_reason": "banned niche: cricket/sports highlights (matched 'cricket highlights')"}
    ]
    # The banned row never reaches the pool, however many views it has.
    assert out["returned"] == 3
    assert out["shorts_len"] == 2


def test_flat_run_query_rejects_banned_query_without_search(flat, stub_ytdlp):
    out = flat.run_query("cricket highlights 2025", stub_ytdlp, None, set())
    assert out["fresh"] == []
    assert out["returned"] == 0
    assert "banned niche" in out["rejected_query"]


# --- app-service wiring (static pin) -----------------------------------------

def test_discovery_service_wires_the_guard():
    text = DISCOVERY.read_text()
    assert "from app.services.niche_guard import check_query, filter_candidates" in text
    assert "check_query(query)" in text
    assert "filter_candidates(candidates)" in text
    assert "TASK-VYR-065" in text


def test_guard_module_is_stdlib_only():
    text = GUARD.read_text()
    assert "import httpx" not in text
    assert "app.config" not in text
    assert "import logging" in text
    assert "import re" in text
