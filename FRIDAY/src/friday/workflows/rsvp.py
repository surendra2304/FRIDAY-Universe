"""TASK-FRD-058 — RSVP speed-reading aid.

Source: friday package F-17 (item DcmUG0vNBEK) — a rapid serial visual
presentation aid. No such aid exists in FRIDAY's baseline.

The flow:
1. The owner pastes text or an article URL (chat, voice, or the API).
   ``create_session`` resolves it — a URL is fetched and its readable
   text extracted; raw text is used as-is — tokenises it into words and
   saves a session under ``FRIDAY/.data/rsvp/sessions/<id>.json``.
2. The reading surface is ``FRIDAY/src/friday/api/rsvp.html`` (served
   at ``/static/rsvp.html`` — the API server mounts its own directory
   as /static). It shows one word at a time at the session's WPM, with
   the optimal-recognition-point letter highlighted, plus pause/resume
   and rate controls. It polls the session state so a pause or rate
   change made by voice or chat takes effect live.
3. Voice/chat control goes through ``control_session`` (and the
   ``/api/rsvp/session/<id>/control`` endpoint + the RSVP tools): set
   the WPM, pause/resume, or jump to a position. The page and the
   voice/chat side share the same session record, so they stay in sync.

Hard rules, by design:
- Sessions are local files only. Nothing is sent anywhere.
- A session that cannot be built (empty text, unfetchable URL, no
  readable text in the article) returns an honest error — never an
  invented word list.
- WPM is clamped to 50–1000; position is clamped to the word list.
"""

from __future__ import annotations

import html as html_lib
import json
import logging
import os
import re
import urllib.request
import uuid
from datetime import datetime, timezone
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)

#: Standard RSVP starting rate; the owner adjusts from here.
DEFAULT_WPM = 250
MIN_WPM = 50
MAX_WPM = 1000

FetcherFn = Callable[[str], str]


def _data_dir() -> str:
    """File-backed state root: FRIDAY/.data/rsvp/."""
    cwd = os.getcwd()
    if os.path.basename(cwd) == "FRIDAY" or os.path.isdir(os.path.join(cwd, ".data")):
        base = os.path.abspath(os.path.join(cwd, ".data", "rsvp"))
    else:
        here = os.path.dirname(__file__)  # .../friday/workflows
        base = os.path.abspath(os.path.join(here, "..", "..", ".data", "rsvp"))
    os.makedirs(base, exist_ok=True)
    return base


def _sessions_dir(*, data_dir: str | None = None) -> str:
    path = os.path.join(data_dir or _data_dir(), "sessions")
    os.makedirs(path, exist_ok=True)
    return path


def tokenize(text: str) -> list[str]:
    """Split text into RSVP words (whitespace split, punctuation kept)."""
    return [w for w in (text or "").split() if w]


def _clamp_wpm(wpm: Any) -> int:
    try:
        value = int(wpm)
    except (TypeError, ValueError):
        return DEFAULT_WPM
    return max(MIN_WPM, min(MAX_WPM, value))


def _extract_article_text(html_text: str) -> str:
    """Best-effort readable text from an article page.

    Drops script/style/nav/header/footer/aside blocks and their content,
    strips the remaining tags, unescapes entities, collapses whitespace.
    A heuristic — the session records the word count and opening words
    so the owner can see what was actually loaded.
    """
    text = html_text or ""
    for tag in ("script", "style", "nav", "header", "footer", "aside", "noscript"):
        text = re.sub(rf"<{tag}\b[^>]*>.*?</{tag}>", " ", text, flags=re.IGNORECASE | re.DOTALL)
    text = re.sub(r"<[^>]+>", " ", text)
    text = html_lib.unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def _default_fetcher(url: str) -> str:
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "FRIDAY-RSVP/1.0 (+https://friday-universe.duckdns.org)"},
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        raw = resp.read(2_000_000)
    return raw.decode("utf-8", errors="replace")


def _is_url(source: str) -> bool:
    return source.startswith("http://") or source.startswith("https://")


def _session_path(session_id: str, *, data_dir: str | None = None) -> str:
    return os.path.join(_sessions_dir(data_dir=data_dir), f"{session_id}.json")


def _save_session(session: dict[str, Any], *, data_dir: str | None = None) -> None:
    with open(_session_path(session["id"], data_dir=data_dir), "w", encoding="utf-8") as f:
        json.dump(session, f, ensure_ascii=False)


def get_session(session_id: str, *, data_dir: str | None = None) -> Optional[dict[str, Any]]:
    """Load a session, or None (honestly) when it does not exist."""
    try:
        with open(_session_path(session_id, data_dir=data_dir), "r", encoding="utf-8") as f:
            session = json.load(f)
        return session if isinstance(session, dict) else None
    except Exception:
        return None


def _summary(session: dict[str, Any]) -> dict[str, Any]:
    words = session.get("words") or []
    position = int(session.get("position") or 0)
    return {
        "id": session["id"],
        "title": session.get("title", ""),
        "word_count": len(words),
        "wpm": int(session.get("wpm") or DEFAULT_WPM),
        "paused": bool(session.get("paused", False)),
        "position": position,
        "percent": round(100.0 * position / max(1, len(words)), 1),
        "created_at": session.get("created_at", ""),
    }


def create_session(
    source: str,
    *,
    wpm: int = DEFAULT_WPM,
    title: str | None = None,
    fetcher: FetcherFn | None = None,
    data_dir: str | None = None,
) -> dict[str, Any]:
    """Build an RSVP session from pasted text or an article URL.

    Returns ok/session_id/title/word_count/wpm/url, or ok False with the
    reason. The reading URL is the static page with the session id.
    """
    raw = (source or "").strip()
    if not raw:
        return {"ok": False, "error": "Nothing to read: the text was empty."}
    if _is_url(raw):
        fetch = fetcher or _default_fetcher
        try:
            page = fetch(raw)
        except Exception as exc:
            return {"ok": False, "error": f"Could not fetch the article {raw}: {exc}"}
        text = _extract_article_text(page)
        if not text:
            return {"ok": False, "error": f"Could not extract readable text from {raw}."}
    else:
        text = raw
    words = tokenize(text)
    if not words:
        return {"ok": False, "error": "Nothing to read: no words in the text."}
    session_id = uuid.uuid4().hex[:12]
    session = {
        "id": session_id,
        "title": (title or "").strip() or " ".join(words[:8]),
        "words": words,
        "wpm": _clamp_wpm(wpm),
        "paused": False,
        "position": 0,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    _save_session(session, data_dir=data_dir)
    return {
        "ok": True,
        "session_id": session_id,
        "title": session["title"],
        "word_count": len(words),
        "wpm": session["wpm"],
        "url": f"/static/rsvp.html?session={session_id}",
    }


def control_session(
    session_id: str,
    *,
    wpm: Any = None,
    paused: Any = None,
    position: Any = None,
    data_dir: str | None = None,
) -> dict[str, Any]:
    """Pause/resume, change the rate, or jump to a position.

    Only the fields given are changed. Returns the updated summary, or
    ok False when the session does not exist.
    """
    session = get_session(session_id, data_dir=data_dir)
    if session is None:
        return {"ok": False, "error": f"No RSVP session {session_id}."}
    if wpm is not None:
        session["wpm"] = _clamp_wpm(wpm)
    if paused is not None:
        session["paused"] = bool(paused)
    if position is not None:
        try:
            pos = int(position)
        except (TypeError, ValueError):
            pos = int(session.get("position") or 0)
        words = session.get("words") or []
        session["position"] = max(0, min(max(0, len(words) - 1), pos))
    _save_session(session, data_dir=data_dir)
    summary = _summary(session)
    summary["ok"] = True
    return summary


def session_progress(session_id: str, *, data_dir: str | None = None) -> dict[str, Any]:
    """Where a session stands (position / percent / rate / paused)."""
    session = get_session(session_id, data_dir=data_dir)
    if session is None:
        return {"ok": False, "error": f"No RSVP session {session_id}."}
    progress = _summary(session)
    progress["ok"] = True
    return progress
