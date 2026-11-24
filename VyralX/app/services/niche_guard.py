"""TASK-VYR-065: hard niche avoid-list exclusion guardrail for discovery.

Discovery must reject the researched ban-list niches *by rule* — a
candidate whose title / description / channel text names a banned niche is
dropped before it can enter a pool, and the rejection reason is logged.

Source of the rule set: WORK_BOARD.yaml TASK-VYR-065 acceptance, filed by
Muse (coordinator) 2026-11-24 under the owner's implementation-push order
(19:38 IST); GAP-LIST.md section 2, TASK-VYR-AVOID-GUARD, research note
``vyralx-niche-research-20261115``. The nine banned niches are:

    anime compilations, cricket/sports highlights, Bollywood edits,
    movie/TV scene compilations, celebrity edits, unlicensed viral-clip
    compilations, borrowed gameplay, borrowed exam lectures, automated
    finance advice.

Design notes:

* Stdlib only (``re`` + ``logging``) so both discovery entry points can
  share this one rule set without the service stack: the app-level
  ``app.services.discovery.discover_youtube_videos`` imports it directly,
  and the standalone supervised-cycle scripts
  (``scripts/find_viral_candidates_flat.py`` and
  ``scripts/find_viral_candidates.py``) load this file by path.
* Matching is phrase-based on text normalised to ``[a-z0-9 ]`` so
  punctuation and case cannot dodge a rule (``"Anime: Best-Fights!"``
  normalises to ``"anime best fights"``). Single words are used only
  where the word itself names the niche (``anime``, ``bollywood``,
  ``celebrity``, ``gameplay``); ambiguous words are matched as phrases
  only — bare ``cricket`` does not match (a cricket-sounds sleep video
  is legitimate), ``exam`` does not match on its own, and bare
  ``highlights`` does not match (only sport + highlights phrases do).
  This is a rule layer, not a classifier: a banned video whose title
  never names its niche will pass, and that residual risk is a live
  re-test item, not something this module claims to close.
* This is a *hard* rule in discovery. It is separate from the
  operator-configured ``channel_avoid_topics`` setting (``app/config.py``),
  which is soft editorial guidance for *generation* in
  ``app/services/content.py``. It is also separate from the id-based
  ``data/rejected_sources.json`` ledger (``viral_loop.py``), which
  rejects known video ids; this module rejects *niches*, including ids
  never seen before.
* ``filter_candidates`` never mutates its input: rejected entries are
  returned as shallow copies carrying ``rejection_reason``.
"""

from __future__ import annotations

import logging
import re

logger = logging.getLogger("vyralx.niche_guard")

# Each rule: stable id, human label (used in the rejection reason), and the
# phrases that trigger it. First matching phrase wins; order inside a rule
# is longest-first so the reason names the most specific phrase.
BANNED_NICHES = (
    {
        "id": "anime_compilations",
        "label": "anime compilations",
        "phrases": (
            "anime compilations",
            "anime compilation",
            "anime moments",
            "anime fights",
            "anime edits",
            "anime",
        ),
    },
    {
        "id": "cricket_sports_highlights",
        "label": "cricket/sports highlights",
        "phrases": (
            "cricket highlights",
            "sports highlights",
            "football highlights",
            "soccer highlights",
            "basketball highlights",
            "match highlights",
            "ipl highlights",
            "nfl highlights",
            "nba highlights",
            "fifa highlights",
            "cricket match",
            "cricket funny",
            "best goals",
            "best wickets",
        ),
    },
    {
        "id": "bollywood_edits",
        "label": "Bollywood edits",
        "phrases": (
            "bollywood edits",
            "bollywood songs",
            "bollywood",
        ),
    },
    {
        "id": "movie_tv_scene_compilations",
        "label": "movie/TV scene compilations",
        "phrases": (
            "movie compilations",
            "movie compilation",
            "movie scenes",
            "movie clips",
            "movie moments",
            "tv show scenes",
            "tv scenes",
            "web series scenes",
            "film scenes",
            "serial scenes",
            "scene compilation",
        ),
    },
    {
        "id": "celebrity_edits",
        "label": "celebrity edits",
        "phrases": (
            "celebrity edits",
            "celebrity moments",
            "celebrity",
        ),
    },
    {
        "id": "unlicensed_viral_clip_compilations",
        "label": "unlicensed viral-clip compilations",
        "phrases": (
            "viral clips compilation",
            "viral video compilation",
            "viral moments compilation",
            "funny clips compilation",
            "best viral clips",
            "viral compilation",
            "viral clips",
        ),
    },
    {
        "id": "borrowed_gameplay",
        "label": "borrowed gameplay",
        "phrases": (
            "minecraft gameplay",
            "gameplay",
            "gaming moments",
            "game highlights",
            "pubg",
            "free fire",
        ),
    },
    {
        "id": "borrowed_exam_lectures",
        "label": "borrowed exam lectures",
        "phrases": (
            "board exam preparation",
            "exam preparation",
            "exam lectures",
            "exam lecture",
            "board exam",
            "neet lecture",
            "jee lecture",
            "coaching classes",
            "exam tips",
        ),
    },
    {
        "id": "automated_finance_advice",
        "label": "automated finance advice",
        "phrases": (
            "financial advice",
            "finance advice",
            "investment advice",
            "stock market tips",
            "stock tips",
            "trading signals",
            "crypto signals",
            "make money online",
            "passive income",
        ),
    },
)

# Pre-compiled word-boundary matchers, one per (niche, phrase).
_COMPILED = tuple(
    (niche["id"], niche["label"], phrase, re.compile(r"\b" + re.escape(phrase) + r"\b"))
    for niche in BANNED_NICHES
    for phrase in niche["phrases"]
)

_TEXT_FIELDS = ("title", "description", "channel_title", "channel", "uploader")


def _normalize(text) -> str:
    """Lowercase and collapse every non-alphanumeric run to one space."""
    if not isinstance(text, str):
        return ""
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


def match_niche(text) -> tuple[str, str, str] | None:
    """Return ``(niche_id, label, phrase)`` for the first banned phrase in
    ``text``, or ``None`` when the text names no banned niche."""
    normalized = _normalize(text)
    if not normalized:
        return None
    for niche_id, label, phrase, pattern in _COMPILED:
        if pattern.search(normalized):
            return niche_id, label, phrase
    return None


def _reason(match: tuple[str, str, str]) -> str:
    _, label, phrase = match
    return f"banned niche: {label} (matched '{phrase}')"


def check_candidate(candidate: dict) -> tuple[bool, str | None]:
    """Check one discovery candidate record.

    Returns ``(True, None)`` when allowed, ``(False, reason)`` when the
    candidate's title / description / channel text names a banned niche.
    """
    if not isinstance(candidate, dict):
        return True, None
    text = " ".join(
        str(candidate.get(field) or "") for field in _TEXT_FIELDS
    )
    match = match_niche(text)
    if match is None:
        return True, None
    return False, _reason(match)


def check_query(query: str) -> tuple[bool, str | None]:
    """Check a discovery query string the same way.

    A query naming a banned niche is rejected outright — the search is
    never issued, so no banned-niche pool can be built from it.
    """
    match = match_niche(query)
    if match is None:
        return True, None
    return False, _reason(match)


def filter_candidates(candidates, *, log: bool = True):
    """Split discovery candidates into ``(kept, rejected)``.

    Rejected entries are shallow copies of the input carrying
    ``rejection_reason``; the input list and its dicts are not mutated.
    Each rejection is logged (``vyralx.niche_guard``, WARNING) with the
    video id when present and the reason, so the exclusion is auditable
    in the discovery run's own log. ``None`` entries are dropped.
    """
    kept: list = []
    rejected: list = []
    for candidate in candidates or []:
        if candidate is None:
            continue
        allowed, reason = check_candidate(candidate)
        if allowed:
            kept.append(candidate)
            continue
        rejected.append({**candidate, "rejection_reason": reason})
        if log:
            vid = candidate.get("id") or candidate.get("video_id") or "?"
            logger.warning("niche guard rejected %s: %s", vid, reason)
    return kept, rejected
