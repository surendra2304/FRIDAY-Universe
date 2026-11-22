"""TASK-VYR-037: offline pins for the discovery helpers.

Covers the pure helpers of ``VyralX/scripts/find_viral_candidates.py``
(the discovery script fixed in this task: venv yt-dlp resolution,
cookie jar, ytsearch10 + Python-side 15-60s filter). Stdlib-only and
fully offline: yt-dlp is replaced by a stub executable that prints
canned JSON lines, so no network and no YouTube account are needed.

These pins fail if the Shorts-length gate, the yt-dlp resolution
order, the cookie flag, or the result parsing regress.
"""
from __future__ import annotations

import importlib.util
import json
import os
import stat
import subprocess
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parent.parent
_SCRIPT = _ROOT / "scripts" / "find_viral_candidates.py"


def _load_module():
    spec = importlib.util.spec_from_file_location(
        "vyr037_find_viral_candidates", _SCRIPT
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
        (23.5, True),
        (14, False),
        (61, False),
        (0, False),
        (-5, False),
        (249, False),
        (29866, False),
        (None, False),
        ("30", False),
        (True, False),  # bool is an int subclass; not a duration
    ],
)
def test_is_shorts_length_boundaries(mod, duration, expected):
    assert mod.is_shorts_length(duration) is expected


def test_queries_are_four_nonempty_strings(mod):
    assert len(mod.QUERIES) == 4
    assert all(isinstance(q, str) and q.strip() for q in mod.QUERIES)


# --- find_ytdlp: PATH first, then repo venv, else SystemExit ------------

def test_find_ytdlp_prefers_path(mod, monkeypatch, tmp_path):
    fake = tmp_path / "yt-dlp"
    fake.write_text("#!/bin/sh\nexit 0\n")
    fake.chmod(fake.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    monkeypatch.setenv("PATH", str(tmp_path) + os.pathsep + os.environ.get("PATH", ""))
    assert mod.find_ytdlp() == str(fake)


def test_find_ytdlp_falls_back_to_repo_venv(mod, monkeypatch):
    monkeypatch.setattr(mod.shutil, "which", lambda name: None)
    monkeypatch.setattr(Path, "is_file", lambda self: True)
    assert mod.find_ytdlp() == str(mod.ROOT.parent / "venv" / "bin" / "yt-dlp")


def test_find_ytdlp_exits_when_nowhere(mod, monkeypatch):
    monkeypatch.setattr(mod.shutil, "which", lambda name: None)
    monkeypatch.setattr(Path, "is_file", lambda self: False)
    with pytest.raises(SystemExit):
        mod.find_ytdlp()


# --- search: parses yt-dlp --dump-json lines, passes --cookies ----------

_STUB = """#!/usr/bin/env python3
import json, sys
open({argv_log!r}, "w").write(json.dumps(sys.argv))
rows = [
    {{"id": "CpQGaTtppnU", "title": "Mw2 TrickShot", "view_count": 1310,
      "duration": 23, "uploader": "x", "upload_date": "20111001"}},
    {{"id": "longform1", "title": "Compilation", "view_count": 99,
      "duration": 249, "uploader": "y", "upload_date": "20200101"}},
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


def test_search_parses_rows_and_skips_malformed(mod, stub_ytdlp):
    stub, _ = stub_ytdlp
    results = mod.search("insane human precision trickshot silent", str(stub), None)
    assert len(results) == 2
    short, longform = results
    assert short["id"] == "CpQGaTtppnU"
    assert short["title"] == "Mw2 TrickShot"
    assert short["views"] == 1310
    assert short["duration"] == 23
    assert short["url"] == "https://youtube.com/shorts/CpQGaTtppnU"
    assert short["uploader"] == "x"
    assert short["upload_date"] == "20111001"
    # search() returns every parsed row; the 15-60s filter lives in main()
    assert longform["id"] == "longform1"
    assert longform["duration"] == 249
    assert mod.is_shorts_length(short["duration"]) is True
    assert mod.is_shorts_length(longform["duration"]) is False


def test_search_passes_cookies_when_present(mod, stub_ytdlp, tmp_path):
    stub, argv_log = stub_ytdlp
    cookies = tmp_path / "youtube_cookies.txt"
    cookies.write_text("# Netscape HTTP Cookie File\n")
    mod.search("q", str(stub), cookies)
    argv = json.loads(argv_log.read_text())
    assert "--cookies" in argv
    assert str(cookies) in argv
    assert "--skip-download" in argv
    assert argv[-1] == "ytsearch10:q"


def test_search_omits_cookies_when_absent(mod, stub_ytdlp):
    stub, argv_log = stub_ytdlp
    mod.search("q", str(stub), None)
    argv = json.loads(argv_log.read_text())
    assert "--cookies" not in argv
    assert "--skip-download" in argv


def test_search_empty_output_is_empty(mod, tmp_path):
    stub = tmp_path / "yt-dlp"
    stub.write_text("#!/usr/bin/env python3\n")
    stub.chmod(stub.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    assert mod.search("q", str(stub), None) == []
