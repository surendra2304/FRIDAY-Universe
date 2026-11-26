"""TASK-FRD-058 — RSVP speed-reading aid (rapid serial visual presentation).

Source: friday package F-17 (item DcmUG0vNBEK) — an RSVP speed-reading
aid; FRIDAY's baseline has no such aid (verified by code search on main
bf41a6c4: no rsvp module, no reader surface — see checkpoint 1).

The flow:
1. The owner pastes text or gives an article URL (chat, voice, or the
   ``/static/rsvp.html`` reading surface).
2. ``create_session`` splits the text into words, clamps the rate to
   60–1200 wpm, and saves the session as JSON under ``SESSION_DIR``
   (``FRIDAY/.data/rsvp/``). A URL is fetched and its article text
   extracted with ``extract_article_text`` (stdlib HTML parser: prefers
   ``<article>``, falls back to ``<main>``/``<body>``, drops scripts and
   styles — no reader-mode service, no paid API).
3. ``control_session`` pauses, resumes, changes the rate, or jumps to a
   position. ``session_progress`` / ``current_word`` report where the
   reader is. The reading surface polls these while it presents one word
   at a time at the session's rate.
4. The agent tools (``friday.tools.builtin.rsvp_tools``) and the API
   routes (``POST /api/rsvp/start``, ``POST /api/rsvp/control``,
   ``GET /api/rsvp/status/{session_id}`` in ``friday.api.server``) are
   thin wrappers over these functions.

Hard rules, by design:
- NOTHING is sent or submitted anywhere. Sessions are local JSON files;
  a URL fetch is a read-only GET of a public article.
- A failure is returned honestly with the reason — an empty text, a
  failed fetch, or an unknown session never yields a fabricated
  session or word.
- The live leg (one real article read through the RSVP surface on
  production FRIDAY at two different rates) is NOT done here: it needs
  production access and is a gated follow-up (see checkpoint 2). This
  module is the repo leg only.

Prior attempt: Muse TP9's PR #1850 (superseded by WATCH129) failed CI
because its test file expected ``SESSION_DIR`` and
``extract_article_text`` on this module and the module never defined
them (13 failures, all AttributeError — job log 45664458992). This
module defines exactly that API surface, and the tests in
``tests/test_ig_frd_058_rsvp.py`` exercise it. Nothing is taken from
PR #1850's branch; this implementation is written fresh.
"""

from __future__ import annotations

import json
import logging
import os
import re
import uuid
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Callable
from urllib.request import Request, urlopen

logger = logging.getLogger(__name__)

#: Default reading rate (words per minute).
DEFAULT_WPM = 300
#: Slowest rate the surface offers.
MIN_WPM = 60
#: Fastest rate the surface offers.
MAX_WPM = 1200
#: Longest pasted text accepted in one session (chars).
MAX_TEXT_CHARS = 200000

#: Session store. Tests monkeypatch this to a tmp dir; the functions
#: below read the module global at call time, so the patch takes effect.
#: Resolution mirrors ``book_translation._data_dir``: FRIDAY/.data/rsvp
#: when run from the FRIDAY dir, else src/.data/rsvp next to the package.
def _resolve_default_dir() -> Path:
    cwd = os.getcwd()
    if os.path.basename(cwd) == "FRIDAY" or os.path.isdir(os.path.join(cwd, ".data")):
        return Path(os.path.abspath(os.path.join(cwd, ".data", "rsvp")))
    here = os.path.dirname(__file__)  # .../friday/workflows
    return Path(os.path.abspath(os.path.join(here, "..", "..", ".data", "rsvp")))


SESSION_DIR = _resolve_default_dir()


def _session_dir(explicit: str | Path | None = None) -> Path:
    """Session store for this call: explicit dir, else the module global."""
    path = Path(explicit) if explicit is not None else SESSION_DIR
    path.mkdir(parents=True, exist_ok=True)
    return path


def _clamp_wpm(wpm: Any) -> int:
    try:
        value = int(wpm)
    except (TypeError, ValueError):
        return DEFAULT_WPM
    return max(MIN_WPM, min(MAX_WPM, value))


def _session_path(session_id: str, *, session_dir: str | Path | None = None) -> Path:
    return _session_dir(session_dir) / f"{session_id}.json"


def _load_session(session_id: str, *, session_dir: str | Path | None = None) -> dict[str, Any] | None:
    try:
        with open(_session_path(session_id, session_dir=session_dir), "r", encoding="utf-8") as f:
            state = json.load(f)
        if isinstance(state, dict) and isinstance(state.get("words"), list):
            return state
    except Exception:
        pass
    return None


def _save_session(state: dict[str, Any], *, session_dir: str | Path | None = None) -> None:
    path = _session_path(state["session_id"], session_dir=session_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def _public_state(state: dict[str, Any]) -> dict[str, Any]:
    """The session as the surface and tools see it (words stay on disk)."""
    total = len(state["words"])
    position = int(state.get("position") or 0)
    return {
        "ok": True,
        "session_id": state["session_id"],
        "title": state.get("title", "Untitled"),
        "source": state.get("source", "text"),
        "url": state.get("url", ""),
        "total_words": total,
        "position": position,
        "wpm": int(state.get("wpm") or DEFAULT_WPM),
        "paused": bool(state.get("paused", False)),
        "percent": round(100.0 * position / total, 1) if total else 0.0,
        "remaining_words": max(0, total - position),
    }


# ----------------------------------------------------------------------
# Article extraction — stdlib HTML parser, no reader-mode service
# ----------------------------------------------------------------------

class _ArticleParser(HTMLParser):
    """Collect visible text, preferring <article>, then <main>, then <body>."""

    _SKIP = {"script", "style", "noscript", "template", "svg"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._article: list[str] = []
        self._main: list[str] = []
        self._body: list[str] = []
        self._stack: list[str] = []
        self._skip_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self._stack.append(tag)
        if tag in self._SKIP:
            self._skip_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if self._stack and self._stack[-1] == tag:
            self._stack.pop()
        elif tag in self._stack:
            self._stack.remove(tag)
        if tag in self._SKIP and self._skip_depth:
            self._skip_depth -= 1

    def handle_data(self, data: str) -> None:
        if self._skip_depth:
            return
        text = data.strip()
        if not text:
            return
        if "article" in self._stack:
            self._article.append(text)
        elif "main" in self._stack:
            self._main.append(text)
        elif "body" in self._stack or not self._stack:
            self._body.append(text)

    def text(self) -> str:
        for parts in (self._article, self._main, self._body):
            joined = " ".join(parts)
            collapsed = re.sub(r"\s+", " ", joined).strip()
            if collapsed:
                return collapsed
        return ""


def extract_article_text(html: str) -> str:
    """Best visible text from an article page's HTML.

    Prefers ``<article>`` content, falls back to ``<main>``, then to the
    whole ``<body>``. Scripts, styles and other non-visible elements are
    dropped. Returns "" when the page has no visible text.
    """
    if not (html or "").strip():
        return ""
    parser = _ArticleParser()
    try:
        parser.feed(html)
    except Exception as exc:
        logger.warning("[RSVP] article extraction failed: %s", exc)
        return ""
    return parser.text()


# ----------------------------------------------------------------------
# Sessions
# ----------------------------------------------------------------------

def _default_fetcher(url: str) -> str:
    """Read-only GET of a public article URL (15 s timeout, browser UA)."""
    request = Request(url, headers={"User-Agent": "FRIDAY-RSVP/1.0"})
    with urlopen(request, timeout=15) as resp:
        raw = resp.read()
    charset = "utf-8"
    try:
        content_type = resp.headers.get_content_charset()
        if content_type:
            charset = content_type
    except Exception:
        pass
    return raw.decode(charset, errors="replace")


def create_session(
    text: str | None = None,
    *,
    url: str | None = None,
    wpm: Any = DEFAULT_WPM,
    title: str | None = None,
    session_dir: str | Path | None = None,
    fetcher: Callable[[str], str] | None = None,
) -> dict[str, Any]:
    """Start an RSVP session from pasted text or an article URL.

    Returns ok/session_id/total_words/wpm/position, or ok False with an
    honest error. ``fetcher`` is injectable for tests; otherwise the URL
    is fetched with a plain read-only GET.
    """
    source = "url" if (url or "").strip() else "text"
    article_url = (url or "").strip()
    if source == "url":
        try:
            fetch = fetcher or _default_fetcher
            html = fetch(article_url)
        except Exception as exc:
            return {"ok": False, "error": f"Could not fetch {article_url}: {exc}"}
        text = extract_article_text(html)
        if not text:
            return {
                "ok": False,
                "error": f"Could not read article text from {article_url}: no visible text found.",
            }
    raw = (text or "")
    if len(raw) > MAX_TEXT_CHARS:
        raw = raw[:MAX_TEXT_CHARS]
    words = raw.split()
    if not words:
        return {"ok": False, "error": "Nothing to read: the text was empty."}
    session_id = uuid.uuid4().hex[:12]
    state = {
        "session_id": session_id,
        "title": (title or "").strip() or "Untitled",
        "source": source,
        "url": article_url,
        "words": words,
        "wpm": _clamp_wpm(wpm),
        "position": 0,
        "paused": False,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    try:
        _save_session(state, session_dir=session_dir)
    except Exception as exc:
        return {"ok": False, "error": f"Could not save RSVP session: {exc}"}
    return _public_state(state)


def control_session(
    session_id: str,
    *,
    action: str,
    wpm: Any = None,
    position: Any = None,
    session_dir: str | Path | None = None,
) -> dict[str, Any]:
    """Pause, resume, change rate, or jump within a session.

    Actions: ``pause``, ``resume``, ``set_rate`` (needs ``wpm``),
    ``jump`` (needs ``position``). Rate and position are clamped; an
    unknown session or action is an honest error, never a silent no-op.
    """
    state = _load_session(session_id, session_dir=session_dir)
    if state is None:
        return {"ok": False, "error": f"No RSVP session {session_id}: unknown session id."}
    total = len(state["words"])
    action = (action or "").strip().lower()
    if action == "pause":
        state["paused"] = True
    elif action == "resume":
        state["paused"] = False
    elif action == "set_rate":
        if wpm is None:
            return {"ok": False, "error": "set_rate needs a wpm value."}
        state["wpm"] = _clamp_wpm(wpm)
    elif action == "jump":
        if position is None:
            return {"ok": False, "error": "jump needs a position value."}
        try:
            target = int(position)
        except (TypeError, ValueError):
            return {"ok": False, "error": f"jump needs a numeric position, got {position!r}."}
        state["position"] = max(0, min(max(total - 1, 0), target))
    else:
        return {"ok": False, "error": f"Unknown RSVP action {action!r}: use pause, resume, set_rate, or jump."}
    try:
        _save_session(state, session_dir=session_dir)
    except Exception as exc:
        return {"ok": False, "error": f"Could not save RSVP session: {exc}"}
    return _public_state(state)


def session_progress(
    session_id: str, *, session_dir: str | Path | None = None
) -> dict[str, Any]:
    """Where a session is: position, total, percent, rate, paused."""
    state = _load_session(session_id, session_dir=session_dir)
    if state is None:
        return {"ok": False, "error": f"No RSVP session {session_id}: unknown session id."}
    return _public_state(state)


def get_session(
    session_id: str, *, session_dir: str | Path | None = None
) -> dict[str, Any]:
    """Full session record, words included, for the reading surface.

    The surface fetches this once after starting a session and runs its
    own display timer from the word list; control calls keep the saved
    state in sync so voice/chat can pause, resume, or change the rate.
    """
    state = _load_session(session_id, session_dir=session_dir)
    if state is None:
        return {"ok": False, "error": f"No RSVP session {session_id}: unknown session id."}
    result = _public_state(state)
    result["words"] = list(state["words"])
    return result


def current_word(
    session_id: str, *, session_dir: str | Path | None = None
) -> dict[str, Any]:
    """The word at the session's current position (or end-of-text)."""
    state = _load_session(session_id, session_dir=session_dir)
    if state is None:
        return {"ok": False, "error": f"No RSVP session {session_id}: unknown session id."}
    total = len(state["words"])
    position = int(state.get("position") or 0)
    if position >= total:
        result = _public_state(state)
        result["ok"] = False
        result["error"] = "End of text reached: the session is finished."
        return result
    result = _public_state(state)
    result["word"] = state["words"][position]
    return result


__all__ = [
    "DEFAULT_WPM",
    "MAX_WPM",
    "MIN_WPM",
    "SESSION_DIR",
    "control_session",
    "create_session",
    "current_word",
    "extract_article_text",
    "get_session",
    "session_progress",
]
