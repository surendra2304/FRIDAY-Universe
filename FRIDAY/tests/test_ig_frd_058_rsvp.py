"""TASK-FRD-058 — RSVP speed-reading aid.

Hermetic tests: sessions live in a monkeypatched tmp SESSION_DIR, the
article fetcher is injected, so no network, no server and no provider
key is needed. Covers the exact API surface PR #1850's test file
expected but its workflow module never defined (``SESSION_DIR`` and
``extract_article_text`` — 13 AttributeError failures, job log
45664458992): this module defines both, and these tests pin them.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

pytestmark = [pytest.mark.unit]

REPO = Path(__file__).resolve().parent.parent.parent  # friday-universe root
for _p in (str(REPO / "FRIDAY" / "src"), str(REPO / "FRIDAY" / "apps" / "core" / "src"), str(REPO)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from friday.tools.builtin import RsvpControlTool, RsvpStartTool, RsvpStatusTool  # noqa: E402
from friday.tools.builtin.rsvp_tools import (  # noqa: E402
    RsvpControlTool as _RsvpControlToolDirect,
)
from friday.workflows import rsvp  # noqa: E402

TEXT = "The quick brown fox jumps over the lazy dog"
ARTICLE_HTML = """<html><head><title>Test</title><script>var secret = 'evil script words';</script></head>
<body><nav>Nav words here</nav>
<article><h1>Headline</h1><p>Alpha beta gamma delta.</p></article>
<footer>Footer words here</footer></body></html>"""


@pytest.fixture(autouse=True)
def _tmp_sessions(tmp_path, monkeypatch):
    monkeypatch.setattr(rsvp, "SESSION_DIR", tmp_path / "rsvp")
    return tmp_path


# ----------------------------------------------------------------------
# Session creation
# ----------------------------------------------------------------------

def test_create_session_defaults():
    result = rsvp.create_session(TEXT)
    assert result["ok"] is True
    assert result["total_words"] == 9
    assert result["wpm"] == rsvp.DEFAULT_WPM == 300
    assert result["position"] == 0
    assert result["paused"] is False
    assert result["percent"] == 0.0
    assert result["remaining_words"] == 9
    assert result["session_id"]
    assert (rsvp.SESSION_DIR / f"{result['session_id']}.json").exists()


def test_create_session_wpm_clamped():
    assert rsvp.create_session(TEXT, wpm=5000)["wpm"] == rsvp.MAX_WPM
    assert rsvp.create_session(TEXT, wpm=10)["wpm"] == rsvp.MIN_WPM
    assert rsvp.create_session(TEXT, wpm="not-a-number")["wpm"] == rsvp.DEFAULT_WPM


def test_create_session_empty_text_is_honest_error():
    assert rsvp.create_session("   ")["ok"] is False
    assert "Nothing to read" in rsvp.create_session("")["error"]


def test_create_session_url_honest_on_fetch_failure():
    def _boom(url):
        raise RuntimeError("DNS down")

    result = rsvp.create_session(url="https://example.com/nope", fetcher=_boom)
    assert result["ok"] is False
    assert "Could not fetch" in result["error"]


def test_create_session_url_uses_extractor():
    result = rsvp.create_session(url="https://example.com/a", fetcher=lambda url: ARTICLE_HTML)
    assert result["ok"] is True
    # Article only: headline + 4 article words; nav/footer/script excluded.
    assert result["total_words"] == 5
    assert result["source"] == "url"
    assert result["url"] == "https://example.com/a"


def test_create_session_url_with_no_visible_text_is_honest_error():
    result = rsvp.create_session(
        url="https://example.com/empty",
        fetcher=lambda url: "<html><head></head><body><script>var x = 1;</script></body></html>",
    )
    assert result["ok"] is False
    assert "no visible text" in result["error"]


# ----------------------------------------------------------------------
# Article extraction
# ----------------------------------------------------------------------

def test_extract_text_prefers_article():
    html = (
        "<html><body><nav>Nav text</nav>"
        "<article><p>Article text here</p></article>"
        "<footer>Footer text</footer></body></html>"
    )
    assert rsvp.extract_article_text(html) == "Article text here"


def test_extract_text_falls_back_to_main_then_body():
    assert rsvp.extract_article_text("<html><body><main>Main text</main></body></html>") == "Main text"
    assert rsvp.extract_article_text("<html><body><p>Body text</p></body></html>") == "Body text"


def test_extract_text_drops_scripts_and_styles():
    html = "<html><body><script>var x = 1;</script><style>.a{}</style><p>Visible</p></body></html>"
    assert rsvp.extract_article_text(html) == "Visible"
    assert rsvp.extract_article_text("") == ""


# ----------------------------------------------------------------------
# Control
# ----------------------------------------------------------------------

def _session():
    return rsvp.create_session(TEXT)


def test_control_pause_resume_rate_and_jump():
    sid = _session()["session_id"]
    paused = rsvp.control_session(sid, action="pause")
    assert paused["ok"] is True and paused["paused"] is True
    resumed = rsvp.control_session(sid, action="resume")
    assert resumed["paused"] is False
    rated = rsvp.control_session(sid, action="set_rate", wpm=450)
    assert rated["wpm"] == 450
    jumped = rsvp.control_session(sid, action="jump", position=4)
    assert jumped["position"] == 4
    assert jumped["percent"] == round(100.0 * 4 / 9, 1)


def test_control_clamps_rate_and_position():
    sid = _session()["session_id"]
    assert rsvp.control_session(sid, action="set_rate", wpm=99999)["wpm"] == rsvp.MAX_WPM
    assert rsvp.control_session(sid, action="jump", position=999)["position"] == 8
    assert rsvp.control_session(sid, action="jump", position=-5)["position"] == 0


def test_control_unknown_session_is_honest_error():
    result = rsvp.control_session("nope123", action="pause")
    assert result["ok"] is False
    assert "unknown session" in result["error"]


def test_control_unknown_action_is_honest_error():
    sid = _session()["session_id"]
    result = rsvp.control_session(sid, action="rewind")
    assert result["ok"] is False
    assert "Unknown RSVP action" in result["error"]


def test_control_missing_value_is_honest_error():
    sid = _session()["session_id"]
    assert rsvp.control_session(sid, action="set_rate")["ok"] is False
    assert rsvp.control_session(sid, action="jump")["ok"] is False


# ----------------------------------------------------------------------
# Progress + current word
# ----------------------------------------------------------------------

def test_session_progress():
    sid = _session()["session_id"]
    rsvp.control_session(sid, action="jump", position=2)
    progress = rsvp.session_progress(sid)
    assert progress["ok"] is True
    assert progress["position"] == 2
    assert progress["total_words"] == 9
    assert progress["percent"] == round(100.0 * 2 / 9, 1)
    assert progress["remaining_words"] == 7


def test_progress_unknown_session_is_honest_error():
    result = rsvp.session_progress("nope123")
    assert result["ok"] is False
    assert "unknown session" in result["error"]


def test_current_word():
    sid = _session()["session_id"]
    assert rsvp.current_word(sid)["word"] == "The"
    rsvp.control_session(sid, action="jump", position=3)
    assert rsvp.current_word(sid)["word"] == "jumps"


def test_current_word_at_end_is_honest_error():
    created = _session()
    sid = created["session_id"]
    path = rsvp.SESSION_DIR / f"{sid}.json"
    state = json.loads(path.read_text())
    state["position"] = len(state["words"])  # past the last word
    path.write_text(json.dumps(state))
    result = rsvp.current_word(sid)
    assert result["ok"] is False
    assert "End of text" in result["error"]


def test_get_session_returns_words():
    created = _session()
    full = rsvp.get_session(created["session_id"])
    assert full["ok"] is True
    assert full["words"] == TEXT.split()
    assert rsvp.get_session("nope123")["ok"] is False


# ----------------------------------------------------------------------
# Tools (real workflow path, tmp SESSION_DIR)
# ----------------------------------------------------------------------

def test_tools_create_and_control():
    start = RsvpStartTool()
    result = start.execute(text=TEXT, wpm=250)
    assert result.is_error is False
    assert result.metadata["total_words"] == 9
    assert result.metadata["wpm"] == 250
    sid = result.metadata["session_id"]

    control = RsvpControlTool()
    paused = control.execute(session_id=sid, action="pause")
    assert paused.is_error is False
    assert paused.metadata["paused"] is True
    assert "paused" in paused.content

    status = RsvpStatusTool()
    report = status.execute(session_id=sid)
    assert report.is_error is False
    assert "The" in report.content
    assert report.metadata["current_word"] == "The"


def test_tools_error_honestly():
    assert RsvpStartTool().execute(text="").is_error is True
    assert RsvpStartTool().execute().is_error is True
    assert RsvpControlTool().execute(session_id="nope123", action="pause").is_error is True
    assert RsvpStatusTool().execute(session_id="nope123").is_error is True
    assert RsvpStatusTool().execute(session_id="").is_error is True


def test_tools_are_exported_from_builtin():
    # The classes resolve through the package export, not just the module.
    assert _RsvpControlToolDirect is RsvpControlTool
    from friday.tools.builtin import RsvpStartTool as _Start, RsvpStatusTool as _Status

    assert _Start is RsvpStartTool
    assert _Status is RsvpStatusTool


# ----------------------------------------------------------------------
# Live-registry wiring (AUDIT-2 lesson: export-only is not implemented)
# ----------------------------------------------------------------------

def test_rsvp_tools_registered_in_live_registry():
    # Source-level assertion: building the production registry needs the
    # full agent import chain, which the tier-1 venv does not guarantee;
    # the production-registry test (test_ig_tool_registry_wiring.py)
    # covers the build path. Here we pin the exact register lines so a
    # future edit cannot silently drop the wiring again.
    mixin = REPO / "FRIDAY" / "src" / "friday" / "agent" / "mixins" / "tools.py"
    source = mixin.read_text(encoding="utf-8")
    for cls in ("RsvpStartTool", "RsvpControlTool", "RsvpStatusTool"):
        assert f"registry.register({cls}())" in source, f"{cls} missing from _create_default_registry"
        assert cls in source.split("from friday.tools.builtin import")[1].split(")")[0], (
            f"{cls} missing from the mixin builtin import block"
        )
