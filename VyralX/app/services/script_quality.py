"""VyralX script-quality system: rubric briefs + pre-production script scoring.

TASK-VYR-007. The library (lanes, hook formulas, format structures,
escalation/payoff patterns, rubric weights) lives in
``script_quality_data.json`` beside this module so it can be retuned
without code changes.

Two jobs:

1. ``build_script_brief`` tells VyralX's scriptwriter (``content.py``,
   which prompts Inference) exactly what a good script looks like for a
   lane: the assigned hook formula (rotated least-recently-used so
   consecutive videos never share a template), the format structure,
   the spoken-word budgets and the banned framings.

2. ``score_script`` grades a generated script BEFORE production:
   hook strength, escalation, payoff, format/duration fit, lane fit
   and originality (structural fingerprint + word 4-gram overlap
   against recent scripts). Hard gates (banned content, an opening
   hook that cannot fit in 3 seconds, a blown duration ceiling, a
   near-duplicate of a recent script) force REJECT regardless of the
   numeric score, because those are the failures that made the old
   autopilot output unwatchable and risk YouTube's inauthentic-content
   policy.

Everything here is deterministic and standard-library only: the same
script always gets the same grade, and the module adds no dependency
to VyralX's small production hosts.
"""
from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

_DATA_PATH = Path(__file__).with_name("script_quality_data.json")

_WORD_RE = re.compile(r"[a-z0-9']+")
_SENTENCE_RE = re.compile(r"(?<=[.!?])\s+")
_NUMBER_WORDS = {
    "one", "two", "three", "four", "five", "six", "seven", "eight",
    "nine", "ten", "eleven", "twelve", "twenty", "thirty", "forty",
    "fifty", "sixty", "seventy", "eighty", "ninety", "hundred",
    "thousand", "million", "billion", "trillion",
}
_STOPWORDS = {
    "the", "a", "an", "and", "or", "but", "of", "to", "in", "on", "is",
    "it", "its", "that", "this", "was", "are", "were", "be", "been",
    "with", "for", "as", "by", "at", "from", "has", "have", "had",
    "not", "no", "so", "if", "then", "than", "you", "your", "we",
    "they", "he", "she", "his", "her", "their", "our", "i", "me",
}
_RANK_MARKERS = [
    ("five", "5"), ("four", "4"), ("three", "3"), ("two", "2"), ("one", "1"),
]


@lru_cache(maxsize=1)
def load_library() -> dict[str, Any]:
    """Load the rubric/hook library (cached; data file ships with the code)."""
    return json.loads(_DATA_PATH.read_text(encoding="utf-8"))


def list_lanes() -> list[str]:
    return sorted(load_library()["lanes"])


def list_formats() -> list[str]:
    return sorted(load_library()["formats"])


def _lane(lane: str) -> dict[str, Any]:
    lanes = load_library()["lanes"]
    if lane not in lanes:
        raise ValueError(f"unknown lane {lane!r}; known lanes: {sorted(lanes)}")
    return lanes[lane]


def _format(fmt: str) -> dict[str, Any]:
    formats = load_library()["formats"]
    if fmt not in formats:
        raise ValueError(f"unknown format {fmt!r}; known formats: {sorted(formats)}")
    return formats[fmt]


def hook_formulas(lane: str | None = None, fmt: str | None = None) -> list[dict[str, Any]]:
    """Hook formulas, optionally filtered to one format. Examples are per-lane."""
    formulas = load_library()["hook_formulas"]
    if fmt is not None:
        _format(fmt)
        formulas = [f for f in formulas if fmt in f["formats"]]
    if lane is not None:
        _lane(lane)
    return formulas


# ---------------------------------------------------------------------------
# Text helpers
# ---------------------------------------------------------------------------

def _words(text: str) -> list[str]:
    return _WORD_RE.findall(str(text).lower())


def _content_words(text: str) -> set[str]:
    return {w for w in _words(text) if w not in _STOPWORDS and len(w) > 2}


def split_beats(text: str) -> list[str]:
    """Split narration text into beats: one beat per line, else per sentence."""
    raw = str(text or "").strip()
    if not raw:
        return []
    lines = [ln.strip() for ln in raw.splitlines() if ln.strip()]
    if len(lines) > 1:
        return lines
    parts = [p.strip() for p in _SENTENCE_RE.split(raw) if p.strip()]
    return parts or [raw]


def estimate_seconds(word_count: int) -> float:
    wps = float(load_library()["speech"]["words_per_second"])
    return round(word_count / wps, 1)


def _has_number(text: str) -> bool:
    lowered = str(text).lower()
    return bool(re.search(r"\d", lowered)) or any(
        w in _NUMBER_WORDS for w in _words(lowered)
    )


def _cue_present(cue: str, hook: str) -> bool:
    text = str(hook).lower()
    words = _words(text)
    if cue == "number":
        return _has_number(text)
    if cue == "question":
        return "?" in text or (words and words[0] in {"why", "how", "what", "when", "where", "who"})
    if cue == "negation":
        return any(w in words for w in ("not", "never", "no", "isn't", "don't", "wasn't"))
    if cue == "contrast":
        return any(m in text for m in (" but ", " opposite", " instead", " yet ", " while ", "whereas", "never"))
    if cue == "second_person":
        return any(w in words for w in ("you", "your", "yours"))
    if cue == "countdown":
        return ("number one" in text or "number 1" in text) and _has_number(text)
    if cue == "anchor":
        return bool(re.search(r"\b(1[0-9]{3}|20[0-9]{2})\b", text)) or bool(
            re.search(r"\b\d{1,4}\s*(bc|ad)\b", text))
    if cue == "scale_compare":
        return "if " in text and ("would" in text or " were " in text)
    if cue == "turn":
        return any(w in words for w in ("then", "but", "until", "suddenly"))
    if cue == "comparison":
        return any(m in text for m in (" than ", " more ", " bigger", " larger", " faster")) or _has_number(text)
    return False


# ---------------------------------------------------------------------------
# Rotation + brief (the scriptwriter's side)
# ---------------------------------------------------------------------------

def _lru_pick(options: list[str], recent_ids: list[str], canonical: list[str]) -> str:
    """Pick the option whose most recent use is oldest (never used wins)."""
    def last_index(opt: str) -> float:
        try:
            return float(recent_ids.index(opt))
        except ValueError:
            return float("inf")
    # recent_ids is most-recent-first: a LARGER index = used longer ago.
    return max(options, key=lambda o: (last_index(o), -canonical.index(o)))


def choose_rotation(lane: str, recent: list[dict[str, Any]] | None = None) -> dict[str, str]:
    """Choose the next (format, hook formula) for a lane, least-recently-used.

    ``recent`` is the lane's recent production history, most recent first,
    as dicts with ``format`` and ``hook_formula`` keys (exactly what
    ``score_script`` returns in its result, so callers can feed results
    straight back in). Rotation is what keeps the channel from becoming
    template-identical output.
    """
    _lane(lane)
    recent = [r for r in (recent or []) if isinstance(r, dict)]
    recent_formats = [str(r.get("format")) for r in recent]
    recent_formulas = [str(r.get("hook_formula")) for r in recent]
    canonical_formats = list(load_library()["formats"])
    fmt = _lru_pick(canonical_formats, recent_formats, canonical_formats)
    compatible = [f["id"] for f in hook_formulas(fmt=fmt)]
    formula = _lru_pick(compatible, recent_formulas, [f["id"] for f in load_library()["hook_formulas"]])
    return {"format": fmt, "hook_formula": formula}


def build_script_brief(
    lane: str,
    fmt: str | None = None,
    recent: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Build the rubric brief the scriptwriter prompt must follow for one video."""
    lib = load_library()
    lane_cfg = _lane(lane)
    rotation = choose_rotation(lane, recent)
    fmt = fmt or rotation["format"]
    fmt_cfg = _format(fmt)
    formula_id = rotation["hook_formula"] if fmt == rotation["format"] else _lru_pick(
        [f["id"] for f in hook_formulas(fmt=fmt)],
        [str(r.get("hook_formula")) for r in (recent or []) if isinstance(r, dict)],
        [f["id"] for f in lib["hook_formulas"]],
    )
    formula = next(f for f in lib["hook_formulas"] if f["id"] == formula_id)
    speech = lib["speech"]
    lo_words = int(speech["duration_target_seconds"][0] * speech["words_per_second"])
    hi_words = int(speech["duration_target_seconds"][1] * speech["words_per_second"])
    example = formula["examples"].get(lane, "")
    lines = [
        "SCRIPT QUALITY BRIEF - VyralX rubric v1 (follow exactly; the finished script is machine-graded against this brief before production):",
        f"Lane: {lane_cfg['label']} - {lane_cfg['promise']}",
        f"Format: {fmt_cfg['label']} ({fmt_cfg['beats'][0]}-{fmt_cfg['beats'][1]} beats). Structure: "
        + " -> ".join(fmt_cfg["structure"]) + ".",
        *[f"Format rule: {rule}" for rule in fmt_cfg["rules"]],
        f"Hook formula (assigned by rotation - use THIS one): {formula['name']}: \"{formula['template']}\""
        + (f" Lane example: \"{example}\"" if example else ""),
        f"Hook budget: {speech['hook_ideal_words'][0]}-{speech['hook_ideal_words'][1]} words, spoken inside "
        f"{3} seconds, no greeting, no channel intro, no 'in this video'.",
        "Escalation: every beat must raise the stakes - a bigger number, a comparison, or a turn "
        "(but / then / until / suddenly). Never restate the previous beat in other words.",
        "Payoff: finish with one of - " + "; ".join(p["name"] for p in lib["payoffs"])
        + ". The final beat must keep the promise the hook made.",
        f"Length: {speech['duration_target_seconds'][0]}-{speech['duration_target_seconds'][1]} seconds of "
        f"speech = {lo_words}-{hi_words} words total.",
        "Never use: financial advice or guarantees, 'they don't want you to know' framing, or invented "
        "statistics. Lane-specific bans: " + "; ".join(lane_cfg["banned_terms"]) + ".",
    ]
    return {
        "lane": lane,
        "format": fmt,
        "hook_formula": formula_id,
        "brief_text": "\n".join(lines),
    }


# ---------------------------------------------------------------------------
# Scorer
# ---------------------------------------------------------------------------

def _ngrams(words: list[str], n: int = 4) -> set[tuple[str, ...]]:
    return {tuple(words[i:i + n]) for i in range(len(words) - n + 1)} if len(words) >= n else set()


def _beat_shape(beat: str) -> tuple[str, int]:
    words = _words(beat)
    if not words:
        return ("empty", 0)
    first = words[0]
    if _has_number(first):
        kind = "number"
    elif first in {"why", "how", "what", "when", "where", "who"}:
        kind = "question"
    elif first in {"you", "your", "we", "i", "it", "they", "he", "she"}:
        kind = "pronoun"
    elif str(beat)[:1].isupper() and not str(beat).split()[0].isdigit():
        kind = "name"
    else:
        kind = "other"
    return (kind, min(len(words) // 5, 6))


def fingerprint(beats: list[str]) -> dict[str, Any]:
    """Structural fingerprint: the sequence of beat shapes (kind, length bucket)."""
    return {"shapes": [list(_beat_shape(b)) for b in beats], "beats": len(beats)}


def _fingerprint_similarity(a: list, b: list) -> float:
    if not a or not b:
        return 0.0
    same = sum(1 for x, y in zip(a, b) if list(x) == list(y))
    return same / max(len(a), len(b))


def _extract(script: Any) -> tuple[str, list[str], str]:
    """Normalise any script input to (hook, beats, full_text)."""
    if isinstance(script, dict):
        hook = str(script.get("hook") or "").strip()
        beats: list[str] = []
        raw_beats = script.get("beats")
        if isinstance(raw_beats, list) and raw_beats:
            for b in raw_beats:
                if isinstance(b, dict):
                    beats.append(str(b.get("text") or b.get("voiceover") or b.get("narration") or ""))
                else:
                    beats.append(str(b))
            beats = [b.strip() for b in beats if b.strip()]
        if not beats:
            body = str(script.get("voiceover") or script.get("script") or "")
            beats = split_beats(body)
        if not hook and beats:
            hook = beats[0]
        full = "\n".join(beats) if beats else hook
        return hook, beats, full
    text = str(script or "")
    beats = split_beats(text)
    return (beats[0] if beats else ""), beats, text


def _infer_format(beats: list[str]) -> str:
    joined = " ".join(beats).lower()
    ranks = sum(1 for word, _ in _RANK_MARKERS if f"number {word}" in joined or f"number {_}" in joined)
    if ranks >= 4:
        return "top5"
    return "one_fact"


def score_script(
    script: Any,
    *,
    lane: str,
    fmt: str | None = None,
    hook_formula: str | None = None,
    recent: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Grade a script against the rubric. See module docstring for the contract.

    ``recent`` entries may be prior ``score_script`` results or plain dicts
    with ``script``/``voiceover`` text plus ``format``/``hook_formula`` keys;
    they drive the anti-template (originality) dimension and are how the
    inauthentic-content risk is kept down.
    """
    lib = load_library()
    lane_cfg = _lane(lane)
    rubric = lib["rubric"]
    weights = rubric["weights"]
    speech = lib["speech"]
    hook, beats, full_text = _extract(script)
    fmt = fmt or _infer_format(beats)
    fmt_cfg = _format(fmt)
    gates: list[str] = []
    dims: dict[str, dict[str, Any]] = {}

    def dim(name: str, score: float, notes: list[str]) -> None:
        dims[name] = {"score": round(max(0.0, min(score, float(weights[name]))), 1),
                      "max": weights[name], "notes": notes}

    if not beats or not full_text.strip():
        return {
            "lane": lane, "format": fmt, "hook_formula": hook_formula,
            "score": 0.0, "grade": "F", "verdict": "REJECT",
            "gates_failed": ["empty_script"], "dimensions": {},
            "metrics": {"beats": 0, "words": 0, "duration_seconds_est": 0.0,
                        "hook_words": 0, "hook_seconds_est": 0.0},
            "fingerprint": fingerprint(beats),
        }

    lowered = full_text.lower()
    hook_words = len(_words(hook))
    total_words = len(_words(full_text))
    duration = estimate_seconds(total_words)

    # --- hard gates: banned content -------------------------------------
    banned_hits = []
    for group in ("advice_terms", "deception_terms"):
        for term in lib["banned_global"][group]:
            if term in lowered:
                banned_hits.append(term)
    for term in lane_cfg["banned_terms"]:
        if term in lowered:
            banned_hits.append(term)
    if banned_hits:
        gates.append("banned_content:" + ",".join(sorted(set(banned_hits))[:3]))

    # --- hook (25) -------------------------------------------------------
    notes: list[str] = []
    ideal_lo, ideal_hi = speech["hook_ideal_words"]
    if hook_words > speech["hook_hard_max_words"]:
        gates.append(f"hook_too_long:{hook_words}w")
        hook_score = 4.0
        notes.append(f"hook is {hook_words} words - cannot land inside 3 seconds")
    elif ideal_lo <= hook_words <= ideal_hi:
        hook_score = 11.0
    elif hook_words <= speech["hook_soft_max_words"]:
        hook_score = 8.0
        notes.append(f"hook is {hook_words} words - slightly over the 3-second budget")
    elif hook_words < ideal_lo:
        hook_score = 7.0
        notes.append(f"hook is only {hook_words} words - thin for a 3-second promise")
    else:
        hook_score = 5.0
        notes.append(f"hook is {hook_words} words - over the 3-second budget")
    formula = next((f for f in lib["hook_formulas"] if f["id"] == hook_formula), None)
    cue_targets = formula["cues"] if formula else ["number", "question", "negation", "second_person"]
    cue_hits = [c for c in cue_targets if _cue_present(c, hook)]
    hook_score += 9.0 * (len(cue_hits) / max(1, len(cue_targets)))
    if formula and len(cue_hits) < len(cue_targets):
        notes.append(f"hook misses formula cues: {sorted(set(cue_targets) - set(cue_hits))}")
    opener = lowered.strip()
    throat = [t for t in lib["banned_global"]["throat_clearing_openers"] if opener.startswith(t)]
    if throat:
        hook_score -= 6.0
        notes.append(f"throat-clearing opener '{throat[0]}' - the hook must be the first thing spoken")
    proper_noun = any(w[:1].isupper() for w in str(hook).split()[1:])
    if _content_words(hook) & set(lane_cfg["signal_words"]):
        hook_score += 5.0
    elif _has_number(hook) or proper_noun:
        hook_score += 2.0
        notes.append("hook has a number or name but no lane-specific anchor")
    else:
        notes.append("hook has no concrete anchor (number, name or lane keyword)")
    dim("hook", hook_score, notes)

    # --- escalation (20) --------------------------------------------------
    notes = []
    esc = lib["escalation"]
    esc_score = 0.0
    if len(beats) >= 4:
        esc_score += 6.0
    elif len(beats) >= 3:
        esc_score += 3.0
        notes.append("only 3 beats - little room to escalate")
    else:
        notes.append("fewer than 3 beats - no escalation is possible")
    turns = sum(1 for b in beats for m in esc["turn_markers"] if f" {m} " in f" {b.lower()} ")
    # A countdown escalates by construction (each entry must outrank the
    # last), so top5 is not required to also carry turn markers.
    need_turns = 2 if fmt == "story" else 1 if fmt == "one_fact" else 0
    if turns >= need_turns and (need_turns > 0 or len(beats) >= 5):
        esc_score += 5.0
    elif need_turns > 0:
        notes.append(f"only {turns} turn marker(s) - the script reads as a flat list")
    def magnitude(text: str) -> int:
        low = text.lower()
        return sum(1 for m in esc["magnitude_markers"] if m in low) + (1 if _has_number(low) else 0)
    third = max(1, len(beats) // 3)
    first_mag = sum(magnitude(b) for b in beats[:third])
    last_mag = sum(magnitude(b) for b in beats[-third:])
    if last_mag >= first_mag and last_mag > 0:
        esc_score += 5.0
    else:
        notes.append("stakes do not rise: the final third is not bigger than the first")
    padded = False
    for a, b in zip(beats, beats[1:]):
        wa, wb = _content_words(a), _content_words(b)
        if wa and wb and len(wa & wb) / max(1, min(len(wa), len(wb))) > 0.6:
            padded = True
    if not padded:
        esc_score += 4.0
    else:
        notes.append("adjacent beats repeat each other - padding, not escalation")
    dim("escalation", esc_score, notes)

    # --- payoff (15) -------------------------------------------------------
    notes = []
    last = beats[-1]
    pay_score = 0.0
    hook_content = _content_words(hook)
    if hook_content & _content_words(last):
        pay_score += 5.0  # callback / loop close family
    if magnitude(last) > 0 and magnitude(last) >= max(magnitude(b) for b in beats[:-1] or [""]):
        pay_score += 4.0  # scale landing
    if any(m in last.lower() for m in lib["payoff_implication_markers"]):
        pay_score += 4.0  # implication
    if len(_words(last)) <= 8 and fmt == "story":
        pay_score += 2.0  # verdict line
    final_third = " ".join(beats[-third:])
    if hook_content & _content_words(final_third):
        pay_score += 2.0
    else:
        notes.append("the hook's promise never returns in the final third - payoff missing")
    if last.strip().endswith("?") and pay_score < 5.0:
        pay_score = max(0.0, pay_score - 3.0)
        notes.append("script ends on an unanswered question instead of a payoff")
    if pay_score == 0.0:
        notes.append("no payoff pattern detected in the final beat")
    dim("payoff", pay_score, notes)

    # --- format fit (15) ---------------------------------------------------
    notes = []
    fit = 0.0
    lo_b, hi_b = fmt_cfg["beats"]
    if lo_b <= len(beats) <= hi_b:
        fit += 5.0
    else:
        notes.append(f"{len(beats)} beats is outside the {fmt} range {lo_b}-{hi_b}")
        fit += 2.0
    t_lo, t_hi = speech["duration_target_seconds"]
    if t_lo <= duration <= t_hi:
        fit += 6.0
    elif duration <= speech["duration_soft_max_seconds"]:
        fit += 3.0
        notes.append(f"estimated {duration}s is outside the {t_lo}-{t_hi}s target")
    else:
        notes.append(f"estimated {duration}s far outside the {t_lo}-{t_hi}s target")
    if duration > speech["duration_hard_max_seconds"]:
        gates.append(f"duration_too_long:{duration}s")
    if fmt == "top5":
        found = [w for w, digit in _RANK_MARKERS
                 if f"number {w}" in lowered or f"number {digit}" in lowered]
        if len(set(found)) >= 5:
            fit += 4.0
        else:
            notes.append(f"countdown incomplete: only {len(set(found))} of 5 entries marked")
            fit += 4.0 * len(set(found)) / 5.0
    elif fmt == "story":
        if any(_cue_present("anchor", b) for b in beats[:2]):
            fit += 2.0
        else:
            notes.append("story has no time/place anchor in its first two beats")
        if turns >= 2:
            fit += 2.0
    else:  # one_fact
        claims = sum(1 for b in beats if magnitude(b) >= 2)
        if claims <= 3:
            fit += 4.0
        else:
            notes.append("one_fact drifts into a list - too many competing claims")
            fit += 1.0
    dim("format_fit", fit, notes)

    # --- lane fit (10) ------------------------------------------------------
    notes = []
    signals = set(lane_cfg["signal_words"])
    hits = signals & set(_words(full_text)) | {s for s in signals if " " in s and s in lowered}
    lane_score = min(10.0, 3.0 + 1.75 * len(hits))
    if len(hits) < 2:
        notes.append(f"only {len(hits)} lane signal(s) - the script could belong to any channel")
        lane_score = min(lane_score, 4.0)
    other_hits = {}
    for other, cfg in lib["lanes"].items():
        if other == lane:
            continue
        o = set(cfg["signal_words"]) & set(_words(full_text))
        if len(o) > len(hits):
            other_hits[other] = len(o)
    if other_hits:
        lane_score -= 3.0
        notes.append(f"stronger signals for another lane: {other_hits}")
    dim("lane_fit", lane_score, notes)

    # --- originality / anti-template (15) -----------------------------------
    notes = []
    orig = 0.0
    my_fp = fingerprint(beats)
    my_grams = _ngrams(_words(full_text))
    history = []
    for r in recent or []:
        if not isinstance(r, dict):
            continue
        if "fingerprint" in r and isinstance(r["fingerprint"], dict):
            history.append(r)
        elif r.get("script") or r.get("voiceover") or r.get("beats"):
            _, r_beats, r_full = _extract(r)
            history.append({"fingerprint": fingerprint(r_beats), "_text": r_full,
                            "format": r.get("format"), "hook_formula": r.get("hook_formula")})
        else:
            history.append(r)
    if not history:
        orig = 9.0
        notes.append("no recent-script history supplied - originality graded on rotation only")
    else:
        max_gram = 0.0
        max_shape = 0.0
        for h in history:
            h_text = h.get("_text") or ""
            if not h_text and h.get("script"):
                h_text = str(h["script"])
            if h_text:
                hg = _ngrams(_words(h_text))
                if my_grams and hg:
                    max_gram = max(max_gram, len(my_grams & hg) / max(1, min(len(my_grams), len(hg))))
            h_shapes = (h.get("fingerprint") or {}).get("shapes") or []
            if h_shapes:
                max_shape = max(max_shape, _fingerprint_similarity(my_fp["shapes"], h_shapes))
        if max_gram >= rubric["template_ngram_gate"]:
            gates.append(f"template_repeat:ngram={round(max_gram, 2)}")
            notes.append(f"word 4-gram overlap {round(max_gram, 2)} with a recent script - near-duplicate")
        elif max_gram < rubric["template_ngram_full_marks_below"]:
            orig += 9.0
        else:
            orig += 4.0
            notes.append(f"word 4-gram overlap {round(max_gram, 2)} with a recent script - too close for comfort")
        if max_shape < 0.8:
            orig += 4.0
        else:
            notes.append(f"beat-shape fingerprint similarity {round(max_shape, 2)} - same skeleton as a recent script")
        last_same_lane = next((h for h in history if h.get("lane", lane) == lane), None)
        if last_same_lane and last_same_lane.get("format") == fmt and hook_formula \
                and last_same_lane.get("hook_formula") == hook_formula:
            orig -= 4.0
            notes.append("same format + hook formula as the previous script in this lane - rotation broken")
        else:
            orig += 2.0
    dim("originality", orig, notes)

    total = round(sum(d["score"] for d in dims.values()), 1)
    if gates:
        verdict = "REJECT"
    elif total >= rubric["pass_score"]:
        verdict = "PASS"
    elif total >= rubric["revise_score"]:
        verdict = "REVISE"
    else:
        verdict = "REJECT"
    grade = ("S" if total >= 90 else "A" if total >= 80 else "B" if total >= 70
             else "C" if total >= 55 else "D" if total >= 40 else "F")
    return {
        "lane": lane,
        "format": fmt,
        "hook_formula": hook_formula,
        "score": total,
        "grade": grade,
        "verdict": verdict,
        "gates_failed": gates,
        "dimensions": dims,
        "metrics": {
            "beats": len(beats),
            "words": total_words,
            "duration_seconds_est": duration,
            "hook_words": hook_words,
            "hook_seconds_est": estimate_seconds(hook_words),
        },
        "fingerprint": my_fp,
    }


def score_content_pack(pack: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
    """Grade a content.py pack (hook + voiceover fields) before production."""
    return score_script(pack, **kwargs)
