"""VyralX packaging generator + research scorer (TASK-VYR-008).

TASK-VYR-005 built the packaging *rules* (``packaging.py``: lane lints,
hook framework, pre-publish checklist) from its autopsy of the 29
unlisted autopilot shorts. This module is the companion *generator*: given
a finished video's facts, it proposes exactly three packaging variants —
title + thumbnail text + first-frame hook — and scores each one against
the public packaging research summarised in
``docs/PACKAGING_RESEARCH.md``.

Division of labour (no duplication):

* ``packaging.py`` (VYR-005) owns the hard gates: what is *allowed*.
* This module owns generation and *ranking*: which allowed variant the
  research says to try first. Its hard-gate checks mirror the VYR-005
  caps so the module stands alone; when ``packaging`` is importable its
  lints are run as well and merged into the gate report.

Honesty rules, same as the rest of VyralX post-REL-020:

* Scores are *priors from published studies*, not measured CTR. The
  channel has no performance data at all (VYR-005 autopsy: VIDEO_METRICS
  held 0 rows for 46 videos), so nothing here claims a predicted view
  count. Every score component names the research rule it comes from.
* Pure and deterministic: no network, no randomness, no LLM call. The
  same input always yields the same three variants in the same order.

Nothing here uploads, schedules, or talks to YouTube.
"""
from __future__ import annotations

import re
from typing import Any

# ---------------------------------------------------------------------------
# Research rules. Each scoring component cites one of these ids; the full
# finding + source for every id lives in docs/PACKAGING_RESEARCH.md.
# ---------------------------------------------------------------------------

RESEARCH_RULES: dict[str, dict[str, str]] = {
    "R1_TITLE_LENGTH": {
        "finding": "Top Shorts titles average ~49 chars; low performers run ~30% longer; the feed truncates around 60.",
        "source": "SubSub title study, 120,703 videos (70,191 Shorts)",
    },
    "R2_TITLE_EMOJI": {
        "finding": "57% of top-performing Shorts titles carry 1-2 emoji vs 17% of low performers; more reads as clickbait.",
        "source": "SubSub title study, 120,703 videos",
    },
    "R3_FRONTLOAD": {
        "finding": "Front-load the subject/search phrase: only ~40-60 chars display in the feed, and Shorts are found via search long after posting.",
        "source": "Webeyez Shorts CTR guide; Viibeo faceless Shorts guide (search compounding)",
    },
    "R4_ANCHOR": {
        "finding": "A concrete anchor (number, year, named subject) beats interchangeable mood titles — the exact defect the VYR-005 autopsy found in all 46 autopilot videos.",
        "source": "TASK-VYR-005 autopsy; miraflow curiosity-gap guidance",
    },
    "R5_QUESTION_TITLES": {
        "finding": "Question-form titles underperform for Shorts specifically (they work in hooks, not titles). Small penalty, flagged not banned.",
        "source": "SubSub title study (Shorts formula: avoid questions)",
    },
    "R6_PAYABLE_PROMISE": {
        "finding": "A superlative with no concrete anchor is clickbait risk: if the first 2 seconds don't pay the promise, retention dies and distribution is punished.",
        "source": "x20 Shorts thumbnail network analysis (18,000 Shorts); YouTube reused/inauthentic policy context in PACKAGING_RESEARCH.md",
    },
    "R7_THUMB_WORDS": {
        "finding": "Thumbnail text: 3 words maximum wins on a 6-inch screen; high contrast (yellow/white on dark) won the most tests.",
        "source": "x20 Shorts thumbnail network analysis (18,000 Shorts, Q1 2026)",
    },
    "R8_HOOK_LENGTH": {
        "finding": "The hook must land inside ~2-3 seconds: ~50-60% of all drop-off happens in the first 3 seconds; viewers decide in ~1 second.",
        "source": "vidIQ retention research via Virvid; YouTube Blog Shorts deep dive (Hoyos/Sherman, Jan 2025)",
    },
    "R9_HOOK_TYPE": {
        "finding": "Controlled 50-video test, 3-second retention: in-media-res 85%, result-first 78%, problem-statement 74%, no hook 62%. VVSA 70-90% is the strong-distribution band.",
        "source": "AllIn1Panel 180-day storytelling study; Paddy Galloway 3.3B-Shorts study via Virvid",
    },
    "R10_PROMISE_ALIGNMENT": {
        "finding": "Title/thumbnail must match the first 2 seconds of the video; a mismatch kills retention and the algorithm punishes it.",
        "source": "x20 network analysis; Kompozy Shorts optimisation guide (curiosity loop must be paid off)",
    },
}

# ---------------------------------------------------------------------------
# Gates (mirror the TASK-VYR-005 caps so this module stands alone; when
# packaging.py is present its lints are merged in — see _gate_report).
# ---------------------------------------------------------------------------

TITLE_MAX_CHARS = 60
TITLE_MAX_EMOJI = 2
THUMB_MAX_WORDS = 4
THUMB_MAX_CHARS = 24
HOOK_MAX_WORDS = 12

GLOBAL_BANNED_TERMS = ["repurposed", "subscribe now", "watch till end"]
LANE_BANNED_TERMS: dict[str, list[str]] = {
    "tech_ai": ["100x", "destroyed", "kills", "dead"],
    "money_stories": [
        "buy now", "sell now", "guaranteed", "will make you rich",
        "get rich", "hot tip", "signal", "invest in", "double your money",
    ],
}

LANES = ("space_science", "history_dyk", "tech_ai", "money_stories")
STRATEGIES = ("fact_first", "curiosity_gap", "scale_or_story")

_EMOJI_RE = re.compile("[\U0001F300-\U0001FAFF\u2600-\u27BF\U0001F000-\U0001F0FF]")
_LANE_EMOJI = {
    "space_science": "\U0001F92F",   # 🤯
    "history_dyk": "\U0001F62E",     # 😮
    "tech_ai": "\u26A1",             # ⚡
    "money_stories": "\U0001F4B8",   # 💸
}
_CURIOSITY_WORDS = {
    "never", "nobody", "no one", "secret", "hidden", "impossible",
    "first", "biggest", "largest", "oldest", "why", "how", "lost",
    "fooled", "banned", "buried", "forgotten",
}
_RESULT_MARKERS = {
    "just", "filmed", "captured", "lost", "fooled", "changed", "meet",
    "looking at", "took", "won", "fell", "crashed", "vanished",
}
_PROBLEM_MARKERS = {"problem", "wrong", "failing", "broken", "mistake", "risk"}


def _emoji_count(text: str) -> int:
    return len(_EMOJI_RE.findall(text))


def _words(text: str) -> list[str]:
    return [w.strip("!?.,:;\"'").lower() for w in str(text or "").split()]


def _has_anchor(text: str) -> bool:
    if any(ch.isdigit() for ch in text) or "?" in text:
        return True
    raw = str(text or "").split()
    return any(w[:1].isupper() and i > 0 for i, w in enumerate(raw) if w)


# ---------------------------------------------------------------------------
# Scoring. Every component returns points plus the rule ids behind them.
# Totals: title 40 + thumbnail 25 + hook 35 = 100.
# ---------------------------------------------------------------------------

def score_title(title: str, subject: str = "") -> dict[str, Any]:
    text = " ".join(str(title or "").split())
    comp: dict[str, int] = {}
    rules: set[str] = set()

    n = len(text)
    comp["length"] = 10 if 35 <= n <= 60 else 5 if 25 <= n < 35 or 60 < n <= 70 else 2
    rules.add("R1_TITLE_LENGTH")

    e = _emoji_count(text)
    comp["emoji"] = 6 if 1 <= e <= TITLE_MAX_EMOJI else 2 if e == 0 else 0
    rules.add("R2_TITLE_EMOJI")

    subj = " ".join(str(subject or "").split())
    if subj and subj.lower() in text.lower():
        pos = text.lower().find(subj.lower())
        comp["frontload"] = 8 if pos <= 25 else 4
    elif subj and subj.split()[0].lower() in text.lower():
        comp["frontload"] = 4
    else:
        comp["frontload"] = 0
    rules.add("R3_FRONTLOAD")

    comp["anchor"] = 8 if _has_anchor(text) else 0
    rules.add("R4_ANCHOR")

    comp["curiosity"] = 4 if (set(_words(text)) & _CURIOSITY_WORDS or "?" in text) else 0
    if text.rstrip().endswith("?"):
        comp["question_form"] = -3
        rules.add("R5_QUESTION_TITLES")

    alpha = [c for c in text if c.isalpha()]
    if alpha and sum(c.isupper() for c in alpha) / len(alpha) > 0.4:
        comp["caps_abuse"] = -4
    if re.search(r"\b(biggest|largest|greatest|best|worst|first ever)\b", text, re.I) \
            and not any(ch.isdigit() for ch in text):
        comp["unanchored_superlative"] = -4
        rules.add("R6_PAYABLE_PROMISE")

    return {"score": max(0, min(40, sum(comp.values()))), "max": 40,
            "components": comp, "rules": sorted(rules)}


def score_thumbnail_text(thumb: str, title: str = "") -> dict[str, Any]:
    t = " ".join(str(thumb or "").split())
    comp: dict[str, int] = {}
    rules: set[str] = set()
    w = t.split()
    comp["words"] = 10 if 1 <= len(w) <= 3 else 7 if len(w) == 4 else 0
    rules.add("R7_THUMB_WORDS")
    comp["chars"] = 5 if 0 < len(t) <= THUMB_MAX_CHARS else 0
    comp["not_title_repeat"] = 5
    if title:
        tw = _words(t)
        titlew = _words(title)
        if len(tw) >= 2 and titlew[: len(tw)] == tw:
            comp["not_title_repeat"] = 0
    comp["curiosity"] = 5 if (set(_words(t)) & _CURIOSITY_WORDS
                              or any(ch.isdigit() for ch in t)) else 0
    return {"score": sum(comp.values()), "max": 25,
            "components": comp, "rules": sorted(rules),
            "pairing_note": "Render in yellow or white bold sans on a dark, "
                            "high-contrast frame (R7); face/object in the top two-thirds."}


def classify_hook(hook: str) -> str:
    text = " ".join(str(hook or "").split())
    low = text.lower()
    if "?" in text:
        return "question_gap"
    if set(_words(text)) & _PROBLEM_MARKERS:
        return "problem_statement"
    if set(_words(text)) & _RESULT_MARKERS or any(ch.isdigit() for ch in text):
        return "in_media_res"
    return "plain_statement"


def score_hook(hook: str, title: str = "") -> dict[str, Any]:
    text = " ".join(str(hook or "").split())
    comp: dict[str, int] = {}
    rules: set[str] = {"R8_HOOK_LENGTH", "R9_HOOK_TYPE"}
    wc = len(text.split())
    comp["length"] = 8 if 0 < wc <= HOOK_MAX_WORDS else 4 if wc <= 16 else 0
    htype = classify_hook(text)
    comp["type"] = {"in_media_res": 12, "question_gap": 8,
                    "problem_statement": 9, "plain_statement": 3}[htype]
    devices = []
    if any(ch.isdigit() for ch in text):
        devices.append("number")
    if "?" in text:
        devices.append("question")
    if re.search(r"\b(never|nobody|no one|didn't|don't|not|secret|hid|buried)\b", text, re.I):
        devices.append("negation_or_secret")
    if re.search(r"\byou('re| are)?\b", text, re.I):
        devices.append("second_person")
    comp["curiosity_device"] = 7 if devices else 0
    comp["promise_alignment"] = 0
    if title:
        shared = (set(_words(text)) & set(_words(title))) - {
            "the", "a", "an", "this", "that", "it", "is", "of", "to", "in", "on"}
        comp["promise_alignment"] = 8 if shared else 0
        rules.add("R10_PROMISE_ALIGNMENT")
    return {"score": sum(comp.values()), "max": 35, "components": comp,
            "rules": sorted(rules), "hook_type": htype, "devices": devices}


# ---------------------------------------------------------------------------
# Hard gates (mirror of the VYR-005 caps + optional live VYR-005 lints).
# ---------------------------------------------------------------------------

def _gate_report(lane: str, title: str, thumb: str, hook: str) -> dict[str, Any]:
    issues: list[str] = []
    text = " ".join(str(title or "").split())
    if not text:
        issues.append("title is empty")
    if len(text) > TITLE_MAX_CHARS:
        issues.append(f"title is {len(text)} chars; max {TITLE_MAX_CHARS}")
    if _emoji_count(text) > TITLE_MAX_EMOJI:
        issues.append(f"{_emoji_count(text)} emoji; max {TITLE_MAX_EMOJI}")
    low = text.lower()
    for term in GLOBAL_BANNED_TERMS + LANE_BANNED_TERMS.get(lane, []):
        if term in low:
            issues.append(f"banned term: {term!r}")
    if text and not _has_anchor(text):
        issues.append("title has no concrete anchor")
    t = " ".join(str(thumb or "").split())
    if not t:
        issues.append("thumbnail text is empty")
    if len(t.split()) > THUMB_MAX_WORDS:
        issues.append(f"thumbnail text {len(t.split())} words; max {THUMB_MAX_WORDS}")
    if len(t) > THUMB_MAX_CHARS:
        issues.append(f"thumbnail text {len(t)} chars; max {THUMB_MAX_CHARS}")
    h = " ".join(str(hook or "").split())
    if not h:
        issues.append("hook line is empty")
    elif len(h.split()) > HOOK_MAX_WORDS:
        issues.append(f"hook {len(h.split())} words; max {HOOK_MAX_WORDS}")

    merged = {"mirror_lints_applied": True, "vyr005_lints_applied": False}
    try:  # Compose, don't duplicate: run the real VYR-005 lints if present.
        from . import packaging as _pkg  # type: ignore
        lt = _pkg.lint_title(title, lane)
        lth = _pkg.lint_thumbnail_text(thumb, title)
        sh = _pkg.score_hook(hook)
        issues += [i for i in lt["issues"] + lth["issues"] + sh["issues"]
                   if i not in issues]
        merged["vyr005_lints_applied"] = True
    except Exception:
        pass
    return {"ok": not issues, "issues": issues, **merged}


# ---------------------------------------------------------------------------
# Generation. Input ``video`` keys:
#   lane        one of LANES (required)
#   subject     the named thing the video is about (required)
#   fact_title  the payoff fact, phrased for a title (required)
#   hook_fact   the payoff fact as a spoken line, <= 12 words (required)
#   thumb_shout 2-3 word thumbnail shout for the fact-first variant
#   question    the open mystery, as a question (curiosity-gap variant)
#   gap_hook    spoken gap hook, <= 12 words (curiosity-gap variant)
#   thumb_gap   thumbnail shout for the gap variant
#   scale_fact  comparison/scale phrase (scale_or_story variant)
#   story_title title-shaped story framing (scale_or_story variant)
#   story_hook  spoken story hook, <= 12 words
#   thumb_story thumbnail shout for the story variant
# Missing optional slots degrade that variant's score honestly — the
# generator never invents a fact the caller did not supply.
# ---------------------------------------------------------------------------

def generate_variants(video: dict[str, Any]) -> dict[str, Any]:
    lane = str(video.get("lane", ""))
    if lane not in LANES:
        return {"ok": False, "issues": [f"unknown lane: {lane!r} (expected one of {LANES})"],
                "variants": []}
    subject = str(video.get("subject", "")).strip()
    if not subject or not str(video.get("fact_title", "")).strip() \
            or not str(video.get("hook_fact", "")).strip():
        return {"ok": False,
                "issues": ["subject, fact_title and hook_fact are required — "
                           "the generator does not invent facts"],
                "variants": []}
    emoji = _LANE_EMOJI.get(lane, "")

    raw = [
        ("fact_first",
         f"{video['fact_title'].strip()} {emoji}".strip(),
         str(video.get("thumb_shout", "")).strip(),
         str(video["hook_fact"]).strip()),
        ("curiosity_gap",
         str(video.get("question", "")).strip(),
         str(video.get("thumb_gap", "")).strip(),
         str(video.get("gap_hook", "")).strip()),
        ("scale_or_story",
         str(video.get("story_title", "")).strip(),
         str(video.get("thumb_story", "")).strip(),
         str(video.get("story_hook", "")).strip()),
    ]
    variants = []
    for strategy, title, thumb, hook in raw:
        if not title:
            variants.append({"strategy": strategy, "title": "", "thumbnail_text": thumb,
                             "hook_line": hook, "score": 0, "publishable_packaging": False,
                             "notes": ["variant not generated: required slot missing "
                                       "(question/story_title) — supplied by the producer, "
                                       "never invented here"]})
            continue
        st = score_title(title, subject)
        sth = score_thumbnail_text(thumb, title)
        sh = score_hook(hook, title)
        gates = _gate_report(lane, title, thumb, hook)
        variants.append({
            "strategy": strategy,
            "title": title,
            "thumbnail_text": thumb,
            "hook_line": hook,
            "score": st["score"] + sth["score"] + sh["score"],
            "breakdown": {"title": st, "thumbnail_text": sth, "hook": sh},
            "gates": gates,
            "publishable_packaging": gates["ok"],
            "notes": ([] if gates["ok"] else ["fails a hard gate — fix before use"])
                     + ([] if sh["devices"] else ["hook carries no curiosity device"]),
        })
    order = {s: i for i, s in enumerate(STRATEGIES)}
    variants.sort(key=lambda v: (-v["score"], order[v["strategy"]]))
    return {"ok": True, "lane": lane, "subject": subject,
            "score_basis": "research priors (see docs/PACKAGING_RESEARCH.md); "
                           "not measured CTR — the channel has no metrics yet",
            "variants": variants,
            "recommended": variants[0]["strategy"] if variants else None}
