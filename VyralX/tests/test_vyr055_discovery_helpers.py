"""TASK-VYR-055: offline pins for the flat-playlist discovery helpers.

Covers the pure helpers of ``VyralX/scripts/find_viral_candidates_flat.py``
(the flat-search discovery script added in this task: ``--flat-playlist``
bypasses the broken per-video extraction, same 15-60s gate, same
exclusions, most-popular ranking by view_count). Stdlib-only and fully
offline: yt-dlp is replaced by a stub executable that prints canned
flat JSON lines, so no network and no YouTube account are needed.

These pins fail if the Shorts-length gate, the flat-entry parsing, the
known-id exclusion, the most-popular ranking, or the ``--flat-playlist``
/ ``--cookies`` argv regress.
"""
from __future__ import annotations

import importlib.util
import json
import os
import stat
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parent.parent
_SCRIPT = _ROOT / "scripts" / "find_viral_candidates_flat.py"


def _load_module():
    spec = importlib.util.spec_from_file_location(
        "vyr055_find_viral_candidates_flat", _SCRIPT
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def mod():
    return _load_module()


# --- is_shorts_length: the 15-60s Shorts gate ---------------------------

@pytest.mark.parametrize(
    "duration,expected",
    [
        (15, True),
        (60, True),
        (23, True),
        (49, True),
        (23.5, True),
        (14, False),
        (61, False),
        (0, False),
        (-5, False),
        (112, False),
        (1300, False),
        (None, False),
        ("30", False),
        (True, False),  # bool is an int subclass; not a duration
    ],
)
def test_is_shorts_length_boundaries(mod, duration, expected):
    assert mod.is_shorts_length(duration) is expected


def test_queries_are_six_new_angles(mod):
    assert len(mod.QUERIES) == 6
    assert all(isinstance(q, str) and q.strip() for q in mod.QUERIES)
    # None repeats a VYR-037 / VYR-040 query angle.
    assert "amazing domino art chain reaction short" in mod.QUERIES
    assert "epic basketball trick shot short" in mod.QUERIES


# --- parse_flat_entry ----------------------------------------------------

def test_parse_flat_entry_keeps_pool_fields(mod):
    row = {"id": "JxAMNzlUFFE", "title": "Domino Effect V10",
           "duration": 49, "view_count": 116695080,
           "uploader": "Idan David Animations",
           "channel": "Idan David Animations"}
    entry = mod.parse_flat_entry(row)
    assert entry["id"] == "JxAMNzlUFFE"
    assert entry["title"] == "Domino Effect V10"
    assert entry["duration"] == 49
    assert entry["views"] == 116695080
    assert entry["uploader"] == "Idan David Animations"
    assert entry["channel"] == "Idan David Animations"
    assert entry["url"] == "https://youtube.com/shorts/JxAMNzlUFFE"


def test_parse_flat_entry_missing_id_is_none(mod):
    assert mod.parse_flat_entry({"title": "no id", "duration": 30}) is None
    assert mod.parse_flat_entry({"id": "", "duration": 30}) is None
    assert mod.parse_flat_entry({}) is None


def test_parse_flat_entry_tolerates_missing_optional_fields(mod):
    entry = mod.parse_flat_entry({"id": "abc123"})
    assert entry["duration"] is None
    assert entry["views"] is None
    assert entry["url"] == "https://youtube.com/shorts/abc123"


# --- rank_fresh: filter + exclude + most-popular ranking ---------------

def _entry(vid, duration, views):
    return {"id": vid, "title": vid, "duration": duration, "views": views,
            "uploader": "u", "channel": "c",
            "url": "https://youtube.com/shorts/" + vid}


def test_rank_fresh_sorts_by_views_desc(mod):
    entries = [_entry("low", 30, 636), _entry("top", 49, 116695080),
               _entry("mid", 15, 74048)]
    ranked = mod.rank_fresh(entries, set())
    assert [e["id"] for e in ranked] == ["top", "mid", "low"]


def test_rank_fresh_drops_long_form_and_excluded(mod):
    entries = [_entry("long", 112, 99999999), _entry("known", 29, 5000),
               _entry("fresh", 31, 1752), _entry("fresh", 31, 1752)]
    ranked = mod.rank_fresh(entries, {"known"})
    assert [e["id"] for e in ranked] == ["fresh"]


def test_rank_fresh_keeps_boundary_durations(mod):
    entries = [_entry("lo", 15, 10), _entry("hi", 60, 20),
               _entry("under", 14, 30), _entry("over", 61, 40)]
    ranked = mod.rank_fresh(entries, set())
    assert [e["id"] for e in ranked] == ["hi", "lo"]


def test_rank_fresh_none_views_count_as_zero(mod):
    entries = [_entry("noviews", 29, None), _entry("some", 29, 4)]
    ranked = mod.rank_fresh(entries, set())
    assert [e["id"] for e in ranked] == ["some", "noviews"]


def test_rank_fresh_ignores_none_entries(mod):
    assert mod.rank_fresh([None, _entry("ok", 30, 1)], set())[0]["id"] == "ok"


# --- load_exclusions ------------------------------------------------------

def test_load_exclusions_reads_all_three_sets(mod, tmp_path):
    (tmp_path / "rejected_sources.json").write_text(
        json.dumps(["rej1", "rej2"]))
    (tmp_path / "published_shorts_manifest.json").write_text(
        json.dumps([{"video_id": "pub1", "yt_id": "pub1yt"},
                    {"video_id": "pub2"}]))
    (tmp_path / "viral_loop_manifest.jsonl").write_text(
        json.dumps({"video_id": "held1"}) + "\nnot-json\n")
    ids = mod.load_exclusions(tmp_path, {"extra1"})
    assert ids == {"rej1", "rej2", "pub1", "pub1yt", "pub2", "held1", "extra1"}


def test_load_exclusions_missing_files_is_empty(mod, tmp_path):
    assert mod.load_exclusions(tmp_path) == set()


# --- search_flat: parses flat --dump-json lines, passes flags -----------

_STUB = """#!/usr/bin/env python3
import json, sys
open({argv_log!r}, "w").write(json.dumps(sys.argv))
rows = [
    {{"id": "JxAMNzlUFFE", "title": "Domino Effect V10", "duration": 49,
      "view_count": 116695080, "uploader": "Idan David Animations",
      "channel": "Idan David Animations"}},
    {{"id": "longform1", "title": "Compilation", "duration": 112,
      "view_count": 22027536, "uploader": "Alexa Real",
      "channel": "Alexa Real"}},
]
for row in rows:
    print(json.dumps(row))
print("not-json {{{{")
"""


@pytest.fixture
def stub_ytdlp(tmp_path):
    argv_log = tmp_path / "argv.json"
    stub = tmp_path / "yt-dlp"
    stub.write_text(_STUB.format(argv_log=str(argv_log)))
    stub.chmod(stub.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return stub, argv_log


def test_search_flat_parses_rows_and_skips_malformed(mod, stub_ytdlp):
    stub, _ = stub_ytdlp
    results = mod.search_flat("amazing domino art chain reaction short",
                              str(stub), None)
    assert len(results) == 2
    assert results[0]["id"] == "JxAMNzlUFFE"
    assert results[0]["views"] == 116695080
    assert results[1]["id"] == "longform1"
    assert results[1]["duration"] == 112


def test_search_flat_passes_flat_playlist_and_cookies(mod, stub_ytdlp, tmp_path):
    stub, argv_log = stub_ytdlp
    cookies = tmp_path / "youtube_cookies.txt"
    cookies.write_text("# Netscape HTTP Cookie File\n")
    mod.search_flat("q", str(stub), cookies)
    argv = json.loads(argv_log.read_text())
    assert "--flat-playlist" in argv
    assert "--cookies" in argv
    assert str(cookies) in argv
    assert "--skip-download" in argv
    assert argv[-1] == "ytsearch10:q"


def test_search_flat_omits_cookies_when_absent(mod, stub_ytdlp):
    stub, argv_log = stub_ytdlp
    mod.search_flat("q", str(stub), None)
    argv = json.loads(argv_log.read_text())
    assert "--flat-playlist" in argv
    assert "--cookies" not in argv


def test_search_flat_empty_output_is_empty(mod, tmp_path):
    stub = tmp_path / "yt-dlp"
    stub.write_text("#!/usr/bin/env python3\n")
    stub.chmod(stub.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    assert mod.search_flat("q", str(stub), None) == []


# --- run_query: end-to-end shape over a stub ------------------------------

def test_run_query_shape(mod, stub_ytdlp):
    stub, _ = stub_ytdlp
    out = mod.run_query("amazing domino art chain reaction short",
                        str(stub), None, {"known"})
    assert out["query"] == "amazing domino art chain reaction short"
    assert out["returned"] == 2
    assert out["shorts_len"] == 1
    assert out["excluded_known"] == 1
    assert [e["id"] for e in out["fresh"]] == ["JxAMNzlUFFE"]
