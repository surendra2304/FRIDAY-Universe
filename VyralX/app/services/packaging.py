"""VyralX packaging system for the remix era (TASK-VYR-005).

Packaging = everything that decides whether a finished remix gets clicked
and kept: the title, the thumbnail text, and the first-two-seconds hook.
This module is the single source of truth for those rules. It exists
because the autopilot era it replaces (see docs/AUTOPSY_29_UNLISTED.md)
packaged 46 videos with one interchangeable formula — a sensational
scene description + emoji + "#Shorts" — with no lane, no hook framework,
and no gate between a render and an upload.

Contents:

* ``LANES`` — the researched content lanes (owner-confirmed top 3 plus
  the guarded money-stories lane), each with title templates, hook
  archetypes, and lane-specific hard rules.
* ``lint_title`` / ``lint_thumbnail_text`` / ``score_hook`` — pure,
  deterministic checks a producer (human or autopilot) can run before
  upload. No network, no randomness, no invented metrics: a lint either
  passes a stated rule or reports the exact rule it broke.
* ``prepublish_checklist`` — the gate list an upload must clear. It
  composes this module's packaging lints with the TASK-VYR-003 sync
  gates (per-beat retiming + Whisper-aligned captions) and the
  TASK-VYR-004 provenance/compliance gates (per-source licence record;
  original commentary mandatory). A candidate that fails any gate is
  not publishable, and the failing gate says why.

Nothing here uploads, schedules, or talks to YouTube.
"""
from __future__ import annotations

import re
from typing import Any

# ---------------------------------------------------------------------------
# Lanes
#
# Ranking and RPM evidence: the 2026-11-15 niche research (YouTube policy
# pages + AIR/vidIQ/upGrowth data), owner-confirmed lanes 1-3.
# Lane 4 (money stories) is a near-miss kept behind extra rules: stories
# about money are allowed, advice is not — YouTube bars financial-advice
# content from AI personas and SEBI bars unregistered advice in India.
# ---------------------------------------------------------------------------

ALLOWED_LICENSES = {
    "public domain",
    "pd",
    "cc0",
    "cc by",
    "cc by-sa",
    "creative commons attribution",
    "owner-owned",
    "nasa",
    "noaa",
    "wikimedia commons",
}

LANES: dict[str, dict[str, Any]] = {
    "space_science": {
        "label": "Space & science facts",
        "sources": "Public-domain footage only (NASA / NOAA / ESA public domain, Wikimedia Commons).",
        "title_templates": [
            "This {object} Is Bigger Than {comparison}",
            "NASA Filmed {phenomenon} — Here's What It Means",
            "{number} Facts About {object} in {seconds} Seconds",
            "You're Looking at {object}. It Took {duration} to Get This Shot",
        ],
        "hook_archetypes": {
            "scale_shock": "Meet {object} — {scale_fact}.",
            "you_are_looking_at": "You're looking at {object}. {twist}.",
            "the_shot": "This shot took {duration} to capture. Watch the {moment}.",
        },
        "banned_title_terms": [],
    },
    "history_dyk": {
        "label": "History / did-you-know",
        "sources": "Archive and Wikimedia public-domain material; Indian history and GK included.",
        "title_templates": [
            "The {event} Nobody Taught You in School",
            "On This Day: {event} Changed {place}",
            "Why {figure} Did {surprising_act}",
            "{number} Seconds of {era} You've Never Seen",
        ],
        "hook_archetypes": {
            "buried_fact": "They didn't teach you this: {fact}.",
            "on_this_day": "On this day in {year}, {event}.",
            "the_photo": "This photo hid a secret for {duration}.",
        },
        "banned_title_terms": [],
    },
    "tech_ai": {
        "label": "Tech & AI explainers",
        "sources": "Own screen recordings first; review clips only with a provenance record.",
        "title_templates": [
            "This AI Just Did {capability}",
            "I Tested {tool} So You Don't Have To",
            "{tool} vs {rival}: The {metric} Test",
            "Nobody Is Talking About {feature}",
        ],
        "hook_archetypes": {
            "just_happened": "This AI just {capability}. Watch.",
            "the_test": "I gave {tool} one job: {job}.",
            "nobody_talking": "Nobody is talking about {feature} — yet.",
        },
        # No fabricated benchmarks or capability claims the video doesn't show.
        "banned_title_terms": ["100x", "destroyed", "kills", "dead"],
    },
    "money_stories": {
        "label": "Money stories (rise / fall / scams) — stories only, never advice",
        "sources": "PD/CC business and archive footage; charts drawn by VyralX itself.",
        "title_templates": [
            "He Lost {amount} in {duration}. Here's the Story",
            "The {scam} That Fooled {victims}",
            "From {start} to {end}: The {name} Story",
        ],
        "hook_archetypes": {
            "the_fall": "He had {amount}. Then {event}.",
            "the_scam": "This scam fooled {victims}. Here's how it worked.",
            "the_turn": "Everyone laughed at {name}. Then {turn}.",
        },
        # Advice language is a hard fail in this lane (title, hook, script).
        "banned_title_terms": [
            "buy now", "sell now", "guaranteed", "will make you rich",
            "get rich", "hot tip", "signal", "invest in", "double your money",
        ],
    },
}

# Global title rules, learned from the autopsy: the old formula's defect
# was interchangeability — the same shape regardless of content — plus
# carry-overs of the source creator's framing ("Repurposed: ...").
GLOBAL_BANNED_TITLE_TERMS = ["repurposed", "subscribe now", "watch till end"]
TITLE_MAX_CHARS = 60          # beyond this the Shorts feed truncates
TITLE_MAX_EMOJI = 2
THUMB_MAX_WORDS = 4
THUMB_MAX_CHARS = 24
HOOK_MAX_WORDS = 12           # must be speakable inside the first ~2-3 seconds

_EMOJI_RE = re.compile(
    "[\U0001F300-\U0001FAFF☀-➿\U0001F000-\U0001F0FF]"
)


def _emoji_count(text: str) -> int:
    return len(_EMOJI_RE.findall(text))


def _has_anchor(title: str) -> bool:
    """A title needs a concrete anchor: a number, a question, or a name.

    Interchangeable mood titles ("His Reaction Says Everything") were the
    autopsy era's norm; an anchor is the cheapest specificity check.
    """
    if any(ch.isdigit() for ch in title) or "?" in title:
        return True
    words = re.findall(r"[A-Za-z][a-z]+|[A-Z][A-Za-z]+", title)
    # A capitalised word that is not sentence-initial counts as a name anchor.
    raw = title.split()
    return any(w[:1].isupper() and i > 0 for i, w in enumerate(raw) if w)


def lint_title(title: str, lane: str) -> dict[str, Any]:
    """Lint a candidate title for ``lane``. Returns {ok, issues}."""
    if lane not in LANES:
        return {"ok": False, "issues": [f"unknown lane: {lane}"]}
    text = " ".join(str(title or "").split())
    issues: list[str] = []
    if not text:
        issues.append("title is empty")
        return {"ok": False, "issues": issues}
    if len(text) > TITLE_MAX_CHARS:
        issues.append(f"title is {len(text)} chars; max {TITLE_MAX_CHARS} (feed truncates)")
    if _emoji_count(text) > TITLE_MAX_EMOJI:
        issues.append(f"{_emoji_count(text)} emoji; max {TITLE_MAX_EMOJI}")
    low = text.lower()
    for term in GLOBAL_BANNED_TITLE_TERMS:
        if term in low:
            issues.append(f"banned term: {term!r}")
    for term in LANES[lane]["banned_title_terms"]:
        if term in low:
            issues.append(f"banned in lane {lane}: {term!r}")
    if not _has_anchor(text):
        issues.append("no concrete anchor (number, question, or named subject)")
    return {"ok": not issues, "issues": issues}


def render_title(lane: str, template_index: int = 0, **slots: str) -> str:
    """Render one of the lane's title templates with ``slots`` filled."""
    template = LANES[lane]["title_templates"][template_index]
    return template.format(**slots)


def lint_thumbnail_text(text: str, title: str = "") -> dict[str, Any]:
    """Thumbnail text is a shout, not a sentence: <= 4 words, <= 24 chars,
    and it must not merely repeat the title's opening words."""
    t = " ".join(str(text or "").split())
    issues: list[str] = []
    if not t:
        issues.append("thumbnail text is empty")
        return {"ok": False, "issues": issues}
    if len(t.split()) > THUMB_MAX_WORDS:
        issues.append(f"{len(t.split())} words; max {THUMB_MAX_WORDS}")
    if len(t) > THUMB_MAX_CHARS:
        issues.append(f"{len(t)} chars; max {THUMB_MAX_CHARS}")
    if title:
        thumb_words = [w.lower().strip("!?.,") for w in t.split()]
        title_words = [w.lower().strip("!?.,") for w in title.split()]
        if len(thumb_words) >= 2 and title_words[: len(thumb_words)] == thumb_words:
            issues.append("thumbnail text repeats the title's opening words")
    return {"ok": not issues, "issues": issues}


def build_hook(lane: str, archetype: str, **slots: str) -> str:
    """Render a hook line from the lane's framework."""
    return LANES[lane]["hook_archetypes"][archetype].format(**slots)


def score_hook(hook_line: str) -> dict[str, Any]:
    """Check a hook line against the framework: speakable in ~2 seconds
    (<= HOOK_MAX_WORDS words) and carrying a curiosity device — a number,
    a question, a negation, or a second-person address."""
    text = " ".join(str(hook_line or "").split())
    words = text.split()
    devices = []
    if any(ch.isdigit() for ch in text):
        devices.append("number")
    if "?" in text:
        devices.append("question")
    if re.search(r"\b(never|nobody|no one|didn't|don't|not|secret|hid|buried)\b", text, re.I):
        devices.append("negation_or_secret")
    if re.search(r"\byou('re| are)?\b", text, re.I):
        devices.append("second_person")
    ok = bool(text) and len(words) <= HOOK_MAX_WORDS and bool(devices)
    return {
        "ok": ok,
        "word_count": len(words),
        "devices": devices,
        "issues": ([] if ok else [
            *(["hook is empty"] if not text else []),
            *([f"{len(words)} words; max {HOOK_MAX_WORDS} for a 2-second hook"] if len(words) > HOOK_MAX_WORDS else []),
            *(["no curiosity device (number / question / negation / 'you')"] if not devices else []),
        ]),
    }


# ---------------------------------------------------------------------------
# Pre-publish checklist
#
# Gate thresholds for sync are the TASK-VYR-003 proven values with margin:
# the fixed pipeline measured per-beat error 0.00s, caption offset mean
# 0.025s / max 0.413s, and full narration coverage (the broken pipeline it
# replaced covered 73.6% of the runtime with one guessed TTS block).
# ---------------------------------------------------------------------------

SYNC_BEAT_MAX_ERROR_S = 0.25
SYNC_CAPTION_MEAN_MAX_S = 0.15
SYNC_CAPTION_MAX_S = 0.50
SYNC_MIN_NARRATION_COVERAGE = 0.98
MIN_COMMENTARY_WORDS = 40        # original commentary is the product
CLAIMED_MATERIAL_MAX_SECONDS = 60  # claimed Shorts over 60s get blocked


def prepublish_checklist(candidate: dict[str, Any]) -> dict[str, Any]:
    """Evaluate every pre-publish gate for one remix candidate.

    ``candidate`` keys: lane, title, thumbnail_text, hook_line,
    duration_s, claimed_material_possible (bool), sync {beat_max_error_s,
    caption_mean_abs_offset_s, caption_max_abs_offset_s,
    narration_coverage}, provenance {source_url, author, license,
    retrieved_on}, commentary {script, voiceover_present}.

    Returns {"publishable": bool, "gates": [{gate, ok, detail}, ...]}.
    A missing measurement is a failed gate, never a skipped one — that is
    the autopsy's central lesson (VIDEO_METRICS sat empty for 46 videos).
    """
    gates: list[dict[str, Any]] = []

    def gate(name: str, ok: bool, detail: str) -> None:
        gates.append({"gate": name, "ok": bool(ok), "detail": detail})

    lane = candidate.get("lane", "")
    # --- TASK-VYR-004 provenance / compliance gates ---------------------
    prov = candidate.get("provenance") or {}
    missing = [k for k in ("source_url", "author", "license", "retrieved_on") if not prov.get(k)]
    gate("provenance_record_complete", not missing,
         "missing: " + ", ".join(missing) if missing else "source, author, license, retrieval date recorded")
    lic = str(prov.get("license", "")).strip().lower()
    gate("license_allowed", any(a in lic for a in ALLOWED_LICENSES) if lic else False,
         f"license {prov.get('license')!r} is not a recognised PD/CC/owner-owned licence"
         if lic and not any(a in lic for a in ALLOWED_LICENSES) else
         ("recognised reusable licence" if lic else "no license recorded"))
    comm = candidate.get("commentary") or {}
    words = len(str(comm.get("script", "")).split())
    gate("original_commentary_present",
         words >= MIN_COMMENTARY_WORDS and bool(comm.get("voiceover_present")),
         f"script {words} words (min {MIN_COMMENTARY_WORDS}), voiceover_present={bool(comm.get('voiceover_present'))}")

    # --- TASK-VYR-003 sync gates ----------------------------------------
    sync = candidate.get("sync") or {}
    def _num(key: str) -> float | None:
        v = sync.get(key)
        return float(v) if isinstance(v, (int, float)) else None
    beat = _num("beat_max_error_s")
    gate("sync_beats_retimed", beat is not None and beat <= SYNC_BEAT_MAX_ERROR_S,
         "no beat measurement" if beat is None else f"max beat error {beat}s (max {SYNC_BEAT_MAX_ERROR_S}s)")
    cmean = _num("caption_mean_abs_offset_s")
    gate("sync_caption_mean", cmean is not None and cmean <= SYNC_CAPTION_MEAN_MAX_S,
         "no caption measurement" if cmean is None else f"mean |offset| {cmean}s (max {SYNC_CAPTION_MEAN_MAX_S}s)")
    cmax = _num("caption_max_abs_offset_s")
    gate("sync_caption_max", cmax is not None and cmax <= SYNC_CAPTION_MAX_S,
         "no caption measurement" if cmax is None else f"max |offset| {cmax}s (max {SYNC_CAPTION_MAX_S}s)")
    cov = _num("narration_coverage")
    gate("sync_narration_coverage", cov is not None and cov >= SYNC_MIN_NARRATION_COVERAGE,
         "no coverage measurement" if cov is None else f"coverage {cov} (min {SYNC_MIN_NARRATION_COVERAGE})")

    # --- Duration safety --------------------------------------------------
    dur = candidate.get("duration_s")
    if candidate.get("claimed_material_possible"):
        gate("duration_under_claim_block", isinstance(dur, (int, float)) and dur < CLAIMED_MATERIAL_MAX_SECONDS,
             f"duration {dur}s; claimed Shorts >= {CLAIMED_MATERIAL_MAX_SECONDS}s get blocked")
    else:
        gate("duration_under_claim_block", True, "material is PD/CC or owner-owned; claim-block rule not triggered")

    # --- Packaging gates (this module) ------------------------------------
    t = lint_title(candidate.get("title", ""), lane)
    gate("packaging_title", t["ok"], "; ".join(t["issues"]) or "title passes lane lint")
    th = lint_thumbnail_text(candidate.get("thumbnail_text", ""), candidate.get("title", ""))
    gate("packaging_thumbnail_text", th["ok"], "; ".join(th["issues"]) or "thumbnail text passes lint")
    h = score_hook(candidate.get("hook_line", ""))
    gate("packaging_hook", h["ok"], "; ".join(h["issues"]) or f"hook ok ({', '.join(h['devices'])})")

    return {"publishable": all(g["ok"] for g in gates), "gates": gates}
