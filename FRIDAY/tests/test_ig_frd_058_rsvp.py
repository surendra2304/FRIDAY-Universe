"""TASK-FRD-058 — RSVP speed-reading aid tests (hermetic, no network).

Covers tokenisation, article extraction, session create/control/progress,
rate clamping, honest failures, and the two agent tools. The session store
is pointed at a scratch dir per test, so nothing touches the real data dir.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

pytestmark = [pytest.mark.unit]

REPO = Path(__file__).resolve().parent.parent.parent  # friday-universe root
for _p in (str(REPO / "FRIDAY" / "src"), str(REPO / "FRIDAY" / "apps" / "core" / "src"), str(REPO)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from friday.tools.builtin.rsvp_tools import ControlRSVPSessionTool, CreateRSVPSessionTool  # noqa: E402
from friday.workflows import rsvp  # noqa: E402


def _fresh(monkeypatch, tmp_path, name):
    """Point the session store at a scratch dir for one test."""
    store = tmp_path / name
    monkeypatch.setattr(rsvp, "SESSION_DIR", store)
    return store


def test_tokenize_keeps_words_and_punctuation():
    words = rsvp.tokenize("Hello, world!  One   two.")
    assert words == ["Hello,", "world!", "One", "two."]


def test_tokenize_empty_is_empty():
    assert rsvp.tokenize("") == []
    assert rsvp.tokenize("   \n\t  ") == []


def test_create_session_defaults(monkeypatch, tmp_path):
    _fresh(monkeypatch, tmp_path, "t1")
    result = rsvp.create_session("The quick brown fox jumps over the lazy dog.")
    assert result["ok"] is True
    assert result["word_count"] == 9
    assert result["wpm"] == 250
    assert result["paused"] is False
    assert result["position"] == 0
    assert result["url"] == f"/static/rsvp.html?session={result['session_id']}"
    assert result["id"]
    # The session file exists and round-trips.
    session = rsvp.get_session(result["session_id"])
    assert session is not None
    assert session["words"] == ["The", "quick", "brown", "fox", "jumps", "over", "the", "lazy", "dog."]
    assert session["title"]


def test_create_session_wpm_clamped(monkeypatch, tmp_path):
    _fresh(monkeypatch, tmp_path, "t2")
    too_fast = rsvp.create_session("one two three", wpm=5000)
    assert too_fast["wpm"] == 1000
    too_slow = rsvp.create_session("one two three", wpm=5)
    assert too_slow["wpm"] == 50


def test_create_session_empty_text_is_honest_error(monkeypatch, tmp_path):
    _fresh(monkeypatch, tmp_path, "t3")
    result = rsvp.create_session("   ")
    assert result["ok"] is False
    assert "empty" in result["error"].lower()


def test_create_session_url_honest_on_fetch_failure(monkeypatch, tmp_path):
    _fresh(monkeypatch, tmp_path, "t4")

    def boom(url, timeout=10):
        raise ConnectionError("no network in tests")

    monkeypatch.setattr(rsvp, "_fetch_url", boom)
    result = rsvp.create_session("https://example.com/some-article")
    assert result["ok"] is False
    assert "could not fetch" in result["error"].lower()


def test_create_session_url_uses_extractor(monkeypatch, tmp_path):
    _fresh(monkeypatch, tmp_path, "t5")
    html = (
        "<html><head><title>Test Piece</title></head><body>"
        "<header>Nav junk</header>"
        "<article><h1>Test Piece</h1><p>First sentence here.</p><p>Second one too.</p></article>"
        "<footer>Footer junk</footer></body></html>"
    )
    monkeypatch.setattr(rsvp, "_fetch_url", lambda url, timeout=10: html)
    result = rsvp.create_session("https://example.com/test-piece", title="Ignored")
    assert result["ok"] is True
    assert result["word_count"] == 8  # Test Piece + First sentence here. + Second one too.
    session = rsvp.get_session(result["session_id"])
    assert session["title"] == "Test Piece"
    assert "Nav junk" not in " ".join(session["words"])
    assert "Footer junk" not in " ".join(session["words"])


def test_extract_text_prefers_article():
    html = (
        "<html><body><nav>menu</nav>"
        "<main><p>Main body words.</p></main>"
        "<aside>sidebar</aside></body></html>"
    )
    text = rsvp.extract_article_text(html)
    assert text == "Main body words."
    assert "menu" not in text and "sidebar" not in text


def test_control_pause_resume_rate_and_jump(monkeypatch, tmp_path):
    _fresh(monkeypatch, tmp_path, "t6")
    created = rsvp.create_session("a b c d e f g h i j")
    sid = created["session_id"]

    paused = rsvp.control_session(sid, paused=True)
    assert paused["ok"] is True and paused["paused"] is True

    faster = rsvp.control_session(sid, wpm=600)
    assert faster["wpm"] == 600 and faster["paused"] is True  # rate change keeps pause

    jumped = rsvp.control_session(sid, position=5)
    assert jumped["position"] == 5 and jumped["percent"] == 50.0

    resumed = rsvp.control_session(sid, paused=False)
    assert resumed["paused"] is False and resumed["wpm"] == 600 and resumed["position"] == 5


def test_control_clamps_rate_and_position(monkeypatch, tmp_path):
    _fresh(monkeypatch, tmp_path, "t7")
    created = rsvp.create_session("a b c")
    sid = created["session_id"]
    result = rsvp.control_session(sid, wpm=1, position=99)
    assert result["wpm"] == 50
    assert result["position"] == 2  # last word


def test_control_unknown_session_is_honest_error(monkeypatch, tmp_path):
    _fresh(monkeypatch, tmp_path, "t8")
    result = rsvp.control_session("no-such-session", paused=True)
    assert result["ok"] is False
    assert "no rsvp session" in result["error"].lower()


def test_session_progress(monkeypatch, tmp_path):
    _fresh(monkeypatch, tmp_path, "t9")
    created = rsvp.create_session("one two three four")
    progress = rsvp.session_progress(created["session_id"])
    assert progress["ok"] is True
    assert progress["word_count"] == 4
    assert progress["position"] == 0
    assert progress["percent"] == 0.0
    rsvp.control_session(created["session_id"], position=2)
    progress = rsvp.session_progress(created["session_id"])
    assert progress["percent"] == 50.0


def test_progress_unknown_session_is_honest_error(monkeypatch, tmp_path):
    _fresh(monkeypatch, tmp_path, "t10")
    progress = rsvp.session_progress("missing")
    assert progress["ok"] is False


def test_current_word(monkeypatch, tmp_path):
    _fresh(monkeypatch, tmp_path, "t11")
    created = rsvp.create_session("alpha beta gamma")
    assert rsvp.current_word(created["session_id"]) == "alpha"
    rsvp.control_session(created["session_id"], position=2)
    assert rsvp.current_word(created["session_id"]) == "gamma"
    assert rsvp.current_word("missing") is None


def test_tools_create_and_control(monkeypatch, tmp_path):
    _fresh(monkeypatch, tmp_path, "t12")

    created = CreateRSVPSessionTool().execute(text="The quick brown fox.", wpm=300)
    assert created.is_error is False
    assert created.metadata["word_count"] == 4
    assert created.metadata["wpm"] == 300
    assert created.metadata["url"].startswith("/static/rsvp.html?session=")

    sid = created.metadata["session_id"]
    controlled = ControlRSVPSessionTool().execute(session_id=sid, paused=True, wpm=400)
    assert controlled.is_error is False
    assert controlled.metadata["paused"] is True
    assert controlled.metadata["wpm"] == 400

    empty = CreateRSVPSessionTool().execute(text="   ")
    assert empty.is_error is True

    missing = ControlRSVPSessionTool().execute(session_id="nope", paused=True)
    assert missing.is_error is True
