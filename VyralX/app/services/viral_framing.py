"""Framed production for voiced sources (TASK-VYR-019).

The owner's audio rule (locked 2026-11-18): a source WITH voice keeps
its own voice — VyralX never talks over it. Her narration only frames
the clip:

* a **hook** line before the moment (source audio ducked under it),
* the source's own speech at full level in between, carried by
  timing-true Whisper subtitles (the :class:`SpeechReport` cues —
  measured timings, never invented ones),
* a **payoff** line after it (source ducked again),
* a real BGM bed under everything, ducked under her lines.

A source WITHOUT voice never reaches this module — the loop routes it
to the commentary path in :mod:`app.services.viral_remix`, whose whole
design is a full voice-over. The two modes share the quality gates'
grounding discipline: the framing lines are claim-checked against the
same structured vision record the commentary path uses, the hook obeys
the same 18-word cap (and the same deterministic repair), and a line
that cannot be grounded or cannot fit its window skips the candidate
instead of shipping.

Short excerpts only (owner decision 2A): a source up to
``viral_max_source_seconds`` is used whole; a longer source contributes
one window around its event-arc peak, never the whole thing.

TASK-VYR-022 (the coordinator's full watch of cycle 2's renders):
her framing captions render in their own top band so they never stack
over the source's captions; hook/payoff/title are grounding-checked
against the source transcript and the vision record (invented objects
and title-promised actions the camera never showed are rejected, with
a claim-free generic fallback for lines); an excerpt that ends on a
disconnected still/reaction insert is trimmed where the insert
begins.
"""
from __future__ import annotations

import json
import logging
import re
import subprocess
import uuid
from pathlib import Path
from typing import Any

import httpx
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import Asset, PublishJob, RenderJob, Source, VideoProject, utcnow
from app.services import viral_quality as vq
from app.services import viral_remix as vr
from app.services.scene_analysis import analyze_scene, record_visual_defects, scene_text
from app.services.viral_series import normalise_label

log = logging.getLogger("vyralx.viral_framing")

# Spoken rate the production gates calibrate against (words per second).
_WORDS_PER_SECOND = 2.45
_HOOK_WORD_CAP = 18

# Render-fit profile (TASK-VYR-021). The first supervised loop cycle
# (2026-11-18) lost both framed renders to the 2,400s production
# timeout: at the old profile (1080x1920, libx264 veryfast/crf20) a
# 40s framed render costs 70.5 CPU-seconds on one core (1.76 per
# output second) with a 378MB peak RSS — on the shared ~956MB S2 host
# that working set invites swap pressure and the encode starves.
# Profiled stage split: the x264 encode is ~66% of the CPU, decode +
# filters ~23%, the audio chain ~7%; the caption burn-in is only
# ~3 CPU-s, so the captions stay exactly as they are.
#
# This profile measures 30.4 CPU-s for the same 40s render (0.76 per
# output second, 2.3x cheaper), 39.2 CPU-s for the longest possible
# 58s excerpt, and a 243MB peak RSS; a 60fps source gets 3.9x cheaper
# because the fps cap halves its frames before scaling. Quality:
# SSIM 0.965 against the old profile on a grain-heavy fixture, and a
# dark-gradient banding probe is indistinguishable (0.9993) from a
# superfast/crf21 encode. The output is still a 9:16 Short with the
# same burned captions (the ASS PlayRes is unchanged — libass scales
# proportionally), the same ducking and the same loudnorm target.
# Pinned by tests/test_viral_framing.py — do not retune casually.
_RENDER_WIDTH = 720
_RENDER_HEIGHT = 1280
_RENDER_MAX_FPS = 30
_X264_PRESET = "ultrafast"
_X264_CRF = "23"
_X264_THREADS = "2"

# Excerpt-fit profile (TASK-VYR-023). Supervised cycle 2 (2026-11-18/19)
# lost 3 of 12 attempts to TimeoutExpired on the EXCERPT cut — the one
# encode the render-fit profile above did not touch: it still cut at
# full source resolution (up to 1080x1920) at 60fps with
# veryfast/crf18 under the 600s _run default. That cost is pure waste:
# the excerpt file is an ANALYSIS-ONLY intermediate. It never reaches
# the final composition (render_framed trims from the original source),
# and its only consumers are
#   * viral_quality.measure_event_arc — frames at 96x170 grayscale,
#   * scene_analysis.analyze_scene / describe_scene — frames extracted
#     at scale=640:-2 (a 720-wide excerpt yields the identical
#     640x1138 vision frames a 1080-wide one does; verified locally).
# So the excerpt is capped to the render fit itself (720x1280 box,
# fps 30, ultrafast/crf23, threads 2), aspect preserved, never
# upscaled, never cropped — the vision record must see the whole
# frame, only smaller. Measured locally on a 1080x1920@60, ~10Mbps
# fixture, 24s cut (the shortest cycle-2 failure was 23.64s):
# OLD 52.3 CPU-s / 72.0s wall / 373MB RSS / 33.4MB out ->
# NEW 18.1 CPU-s / 31.6s wall / 135MB RSS / 18.6MB out (720x1280@30),
# SSIM 0.981 vs the old excerpt. The 600s excerpt timeout is NOT
# raised — the encode is made to fit inside it, exactly as #1026
# treated the 2,400s composition timeout. Pinned by
# tests/test_viral_framing.py — do not retune casually.
_EXCERPT_WIDTH = 720
_EXCERPT_HEIGHT = 1280
_EXCERPT_MAX_FPS = 30
_EXCERPT_PRESET = "ultrafast"
_EXCERPT_CRF = "23"
_EXCERPT_THREADS = "2"


def _excerpt_video_filter() -> str:
    """The excerpt-fit scale chain: cap to the 720x1280 box at 30fps.

    ``min(W,iw)``/``min(H,ih)`` in the scale target plus
    ``force_original_aspect_ratio=decrease`` means a smaller source
    passes through at its own size (never upscaled), a landscape
    source keeps its aspect (720x406 for 16:9 — no crop, no
    distortion), and a portrait source lands on 720x1280.
    """
    return (
        f"fps={_EXCERPT_MAX_FPS},"
        f"scale='min({_EXCERPT_WIDTH},iw)':'min({_EXCERPT_HEIGHT},ih)':"
        "force_original_aspect_ratio=decrease:force_divisible_by=2"
    )


def _excerpt_command(
    ffmpeg_bin: str, source_path: Path, destination: Path, start: float, seconds: float
) -> list[str]:
    """The full excerpt ffmpeg command at the excerpt-fit profile."""
    return [
        ffmpeg_bin, "-hide_banner", "-nostdin", "-y",
        "-ss", f"{start:.3f}", "-i", str(source_path),
        "-t", f"{seconds:.3f}",
        "-vf", _excerpt_video_filter(),
        "-c:v", "libx264", "-preset", _EXCERPT_PRESET, "-crf", _EXCERPT_CRF,
        "-threads", _EXCERPT_THREADS,
        "-an", str(destination),
    ]


def excerpt_window(
    duration: float,
    peak_position: float | None,
    *,
    full_seconds: float = 58.0,
    window_seconds: float = 40.0,
) -> tuple[float, float]:
    """The (start, end) excerpt for a source of ``duration`` seconds.

    Short sources are used whole. Longer ones contribute one
    ``window_seconds`` window centred on the event-arc peak (or on the
    middle when no arc could be measured), clamped to the source.
    """
    total = max(0.0, float(duration or 0.0))
    if total <= full_seconds:
        return 0.0, total
    window = min(window_seconds, total)
    peak = total / 2.0 if peak_position is None else float(peak_position) * total
    start = min(max(0.0, peak - window / 2.0), total - window)
    return round(start, 3), round(start + window, 3)


def hook_window_seconds(excerpt_seconds: float) -> float:
    """How long her hook may run before the source takes over."""
    return min(7.0, max(1.5, excerpt_seconds * 0.30))


def payoff_window_seconds(excerpt_seconds: float) -> float:
    """How long her payoff may run at the end of the excerpt."""
    return min(9.0, max(1.5, excerpt_seconds * 0.35))


def generate_framing(
    category: str,
    source_title: str,
    channel: str,
    transcript: str,
    scene: str = "",
    taken_titles: set[str] | None = None,
    feedback: list[str] | None = None,
) -> dict[str, str]:
    """Write title, hook, payoff and description for a framed edit.

    Same transport and reply discipline as
    :func:`app.services.viral_remix.generate_editorial` — one JSON
    object, no reasoning in the reply. Returns ``{}`` when the model
    gives nothing usable; the caller treats that as a transient
    editorial failure and skips the candidate (no template framing is
    invented in its place).
    """
    settings = get_settings()
    taken = {title.casefold().strip() for title in (taken_titles or set())}
    prompt = (
        "You write for a viral Shorts channel that re-cuts other creators' clips "
        "WITHOUT talking over them: the source keeps its own voice, and your two "
        "short lines frame it — a hook before the moment and a payoff after it.\n\n"
        f"Source clip title: \"{source_title[:160]}\"\n"
        f"Source channel: {channel[:80]}\n"
        f"Category: {category}\n"
        f"What the clip actually shows (frame analysis - the only source of truth "
        f"for the action): \"{(scene or 'not available')[:700]}\"\n"
        f"What the source's own voice says (transcript): \"{(transcript or '')[:600]}\"\n\n"
        "Reply with the JSON object only - no reasoning, no markdown. "
        "Keys: title, hook, payoff, description.\n"
        "title: 5-11 words in the channel's style, 1-2 emojis, then ' #Shorts'. It must "
        "name the specific thing that happens in this clip and be totally new.\n"
        "hook: ONE sentence, at most 18 words, spoken over the opening seconds while "
        "the source audio is ducked. It teases the moment that is coming, using only "
        "what the frame analysis and transcript prove. Never invent characters, "
        "objects, dialogue or events. No 'you won't believe', no rhetorical filler.\n"
        "payoff: ONE sentence, at most 22 words, spoken over the closing seconds. It "
        "lands the moment — the reaction, the twist, the result — again only from the "
        "frame analysis and transcript. Never close with 'like and subscribe' or any "
        "engagement filler.\n"
        "Never state a colour, item of clothing, time of day, posture, emotion or "
        "eye state that the frame analysis does not record. Never describe a person's "
        "race or skin. If the frame analysis does not record it, do not say it.\n"
        "description: two short sentences about the moment, then a blank line, then a "
        "one-line question starting with an emoji and ending with 'Drop your answer "
        "below!', then a blank line, then ten hashtags starting with #Shorts. The "
        "question must name a concrete object, person or action from the frame "
        "analysis — a question naming anything else is rejected by the footage "
        "checker."
    )
    if taken:
        prompt += (
            "\n\nThese titles are already on the channel and must NOT be reused, echoed "
            "or paraphrased closely:\n"
            + "\n".join(f"- {title}" for title in sorted(taken)[:60])
        )
    if feedback:
        prompt += (
            "\n\nYour previous draft was REJECTED by the footage checker. Fix each of "
            "these problems:\n"
            + "\n".join(f"- {item}" for item in feedback[:10])
            + "\nNever state a colour, item of clothing, time of day, posture, emotion "
            "or eye state that the frame analysis does not record."
        )
    try:
        url = settings.inference_url.rstrip("/") + settings.inference_generation_path
        model = (settings.inference_model or "").strip()
        if not model or model.lower() == "auto":
            model = "llama-3.3-70b-versatile"
        body = {
            "model": model,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are a short-form video editor. Output one compact JSON "
                        "object with the keys title, hook, payoff and description. "
                        "Output ONLY the JSON object."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.9,
            "max_tokens": 1200,
            "response_format": {"type": "json_object"},
            "stream": False,
            "reasoning_effort": "none",
            "chat_template_kwargs": {"enable_thinking": False},
        }
        response = httpx.post(
            url,
            headers={
                "Authorization": f"Bearer {settings.inference_api_key}",
                "X-API-Key": settings.inference_api_key,
                "Content-Type": "application/json",
            },
            json=body,
            timeout=120,
        )
        response.raise_for_status()
        raw = vr._editorial_text(response.json())
        for payload in reversed(vr._json_objects(str(raw))):
            title = " ".join(str(payload.get("title") or "").split())
            hook = vr._trim_to_sentence(str(payload.get("hook") or ""))
            payoff = vr._trim_to_sentence(str(payload.get("payoff") or ""))
            if not title or title.casefold() in taken or len(title.split()) < 4:
                continue
            if not hook or not payoff:
                continue
            return {
                "title": title,
                "hook": hook,
                "payoff": payoff,
                "description": str(payload.get("description") or "").strip(),
            }
        log.warning("Framing reply had no usable package: %s", str(raw)[:500])
    except Exception as exc:
        log.info("Framing generation unavailable (%s: %s)", type(exc).__name__, str(exc)[:200])
    return {}


def framing_violations(
    *,
    hook: str,
    payoff: str,
    title: str,
    description: str,
    record: dict[str, Any] | None,
    excerpt_seconds: float,
    transcript: str = "",
    scene: str = "",
) -> list[vq.Violation]:
    """Gate suite for a framing package.

    Consistency is the production claim-check, unchanged. The
    structural half is framing-shaped (a hook and a payoff are two
    lines, not a 3-7 sentence commentary), but it enforces the same
    disciplines: the 18-word hook cap, no missing half, and an
    estimated-length fit against each line's duck window at the
    production spoken rate. On top of those, TASK-VYR-022 adds the
    transcript/record grounding gate and the engagement-bait closer
    check (see :func:`framing_grounding_violations`); the grounding
    half runs only when the caller supplies evidence (the production
    caller always passes the source transcript and scene text).
    """
    violations: list[vq.Violation] = []
    if record is not None:
        violations += vq.check_consistency(
            commentary=f"{hook} {payoff}".strip(),
            title=title,
            description=description,
            record=record,
        )
    if _ENGAGEMENT_BAIT.search(payoff or ""):
        violations.append(vq.Violation(
            "payoff_engagement_bait", "payoff",
            "the payoff closes with engagement bait instead of landing "
            "the moment (the editorial prompt forbids like/subscribe closers)",
        ))
    if transcript or scene or record is not None:
        violations += framing_grounding_violations(
            hook=hook,
            payoff=payoff,
            title=title,
            transcript=transcript,
            scene=scene,
            record=record,
        )
    if not hook:
        violations.append(vq.Violation(
            "hook_missing", "commentary", "the framing hook is empty",
        ))
    elif len(hook.split()) > _HOOK_WORD_CAP:
        violations.append(vq.Violation(
            "hook_too_long", "commentary",
            f"hook has {len(hook.split())} words; the cap is {_HOOK_WORD_CAP}",
        ))
    if not payoff:
        violations.append(vq.Violation(
            "payoff_missing", "commentary", "the framing payoff is empty",
        ))
    sentences = vq.split_sentences(f"{hook} {payoff}".strip())
    if len(sentences) > 3:
        violations.append(vq.Violation(
            "too_many_sentences", "commentary",
            f"framing has {len(sentences)} sentences; a hook and a payoff only",
        ))
    hook_estimate = len(hook.split()) / _WORDS_PER_SECOND if hook else 0.0
    if hook_estimate > hook_window_seconds(excerpt_seconds) + 0.35:
        violations.append(vq.Violation(
            "hook_overruns_window", "commentary",
            f"hook needs ~{hook_estimate:.1f}s at {_WORDS_PER_SECOND} wps; "
            f"its duck window is {hook_window_seconds(excerpt_seconds):.1f}s",
        ))
    payoff_estimate = len(payoff.split()) / _WORDS_PER_SECOND if payoff else 0.0
    if payoff_estimate > payoff_window_seconds(excerpt_seconds) + 0.35:
        violations.append(vq.Violation(
            "payoff_overruns_window", "commentary",
            f"payoff needs ~{payoff_estimate:.1f}s at {_WORDS_PER_SECOND} wps; "
            f"its duck window is {payoff_window_seconds(excerpt_seconds):.1f}s",
        ))
    return violations


# --------------------------------------------------------------------------- #
# grounding (TASK-VYR-022) — her lines may only claim what the evidence
# holds. The cycle-2 watch caught job 804's payoff inventing a "safety
# sign" and a "folder" that exist nowhere in the footage, and job 803's
# title promising a journal-strip tear the excerpt never shows. Root
# cause: vq.check_consistency claim-checks only the closed classes
# (colours, garments, postures, emotions, eyes, time of day) — the
# concrete nouns and actions in a framing line were never compared
# with anything. This gate compares them with the two evidence sources
# the production already holds: the source's verified transcript and
# the vision record (the "verified description"). A line carrying two
# or more significant words that appear in NEITHER is rejected as
# ungrounded; the retry loop then re-asks with the words named, and if
# a package's only remaining sins are ungrounded hook/payoff lines,
# produce_framed_short substitutes the claim-free generic lines below
# (and logs it) instead of shipping invented specifics.
# --------------------------------------------------------------------------- #
_ENGAGEMENT_BAIT = re.compile(
    r"\b(leave a like|like and subscribe|drop a like|smash (the|that) like|"
    r"like this video|hit subscribe|subscribe for more|follow for more|"
    r"please subscribe)\b",
    re.I,
)

# Discourse and relational words: they frame or locate the moment but
# make no checkable claim about what the footage contains.
_FRAMING_GENERIC_WORDS = {
    "watch", "wait", "happen", "happens", "happened", "happening",
    "comes", "coming", "keep", "keeps", "kept", "stay", "stays", "stayed",
    "resume", "resumes", "resumed", "continue", "continues", "continued",
    "ends", "screen", "camera", "starts", "stops", "again", "back",
    "beside", "behind", "near", "under", "above", "below", "around",
    "between", "against", "toward", "towards", "along", "across",
    "front", "whole", "every", "never", "always", "really", "actually",
    "together",
}

# A handful of high-frequency paraphrase pairs: the claim word counts
# as grounded when its synonym is what the evidence happens to say.
# Deliberately tiny — this absorbs ordinary rewording (the record
# says "walking", her hook says "stroll"), it is not a thesaurus.
_WORD_SYNONYMS = {
    "stroll": "walk", "strolls": "walk", "strolling": "walk",
    "jog": "run", "jogs": "run", "jogging": "run",
    "sprint": "run", "sprints": "run", "dash": "run",
    "leap": "jump", "leaps": "jump", "leaping": "jump",
}

# Judgement/teaser adjectives: they colour a claim without adding a
# checkable object or action (the consistency gates police the factual
# adjectives — colours — separately).
_DESCRIPTIVE_WORDS = {
    "tiny", "little", "small", "big", "huge", "large", "weird", "funny",
    "sudden", "unexpected", "bold", "quick", "crazy", "wild", "mystery",
    "secret", "hidden", "simple", "easy", "perfect", "amazing",
    "incredible", "unbelievable", "hilarious", "adorable", "clever",
}

# Action verbs a Shorts title commonly promises. A title naming one of
# these must find it in the vision record's own account of the action —
# the transcript alone does not prove the camera showed it (job 803's
# source TALKS about tearing strips; the footage never tears one).
# The list is CLOSED by construction: an off-list verb escapes this
# record-only rule and is judged by the general union rule alone —
# a recorded residual (see framing_grounding_violations). "shatter"
# and its kin were added after review C2 on PR #1053 demonstrated
# "He Shatters the Journal Strip" evading the rule against job 803's
# evidence; the list grows as evasions are observed, it is never
# complete.
_TITLE_ACTION_WORDS = {
    "tear", "rip", "flip", "break", "smash", "catch", "drop", "throw",
    "build", "open", "close", "pour", "cut", "hit", "kick", "jump",
    "fall", "crash", "spill", "poke", "crack", "scribble", "press",
    "push", "pull", "shake", "spin", "slide", "climb", "chase", "bite",
    "steal", "hide", "reveal", "unbox", "paint", "draw", "cook",
    "drive", "ride", "swim", "dive", "rescue", "escape", "transform",
    "shatter", "crush", "squash", "melt", "burn", "freeze", "burst",
    "pop", "snap", "bend", "twist", "fold", "toss", "grab", "lift",
    "drag", "roll", "bounce", "dig", "wrap", "stack",
}

# Tangible-object nouns that are classic editorial inventions. One of
# these, ungrounded, flags a line on its own: if the object were
# really in the footage, the transcript or the vision record would
# name it (a real folder in frame is recorded as a folder). Ordinary
# paraphrase drift ("stroll" for the record's "walking") is NOT in
# this class and needs the two-word threshold below. Listed objects
# are grounded ONLY by their own spellings appearing verbatim in the
# evidence (see _is_grounded): the stem/prefix fuzzy routes that
# absorb paraphrase for other words are closed for this class,
# because they let morphological cousins ("posted", "folding",
# "signing") vouch for objects that were never there.
_UNGROUNDED_OBJECT_WORDS = {
    "folder", "sign", "trophy", "envelope", "ladder", "balloon",
    "candle", "suitcase", "umbrella", "bicycle", "guitar", "piano",
    "sword", "banner", "poster", "bucket", "basket", "microphone",
    "phone", "laptop", "notebook", "backpack", "wallet",
}

# Claim-free fallbacks (see produce_framed_short): each line's
# significant words are all generic, so both pass this gate by
# construction — they promise nothing about the footage at all.
_GENERIC_HOOK = "Watch what happens in this clip."
_GENERIC_PAYOFF = "And that is how it ends."
_GROUNDING_KINDS = {"framing_ungrounded", "title_ungrounded", "title_action_ungrounded"}


def _ungrounded_is_violation(missing: list[str]) -> bool:
    """The rejection rule: two or more ungrounded specifics, or one
    invented tangible object (see _UNGROUNDED_OBJECT_WORDS)."""
    return len(missing) >= 2 or any(
        _object_base(word) is not None for word in missing
    )


def _object_base(word: str) -> str | None:
    """The listed tangible object a claim word names, if any.

    Matches the word itself or its singular ("folders" -> "folder",
    "trophies" -> "trophy"): the single-object invariant is about
    the object, not about which spelling the line happened to use.
    """
    if word in _UNGROUNDED_OBJECT_WORDS:
        return word
    singulars: set[str] = set()
    if word.endswith("ies") and len(word) > 4:
        singulars.add(word[:-3] + "y")
    if word.endswith("es") and len(word) > 4:
        singulars.add(word[:-2])
    if word.endswith("s") and len(word) > 3:
        singulars.add(word[:-1])
    for singular in singulars:
        if singular in _UNGROUNDED_OBJECT_WORDS:
            return singular
    return None


def _object_family(word: str) -> set[str]:
    """Inflectional spellings of an object noun: the word itself, its
    singular, and their plurals — nothing else.

    Deliberately NOT :func:`_word_forms`. That family's derivational
    stem guesses jump lexemes: "signing" stems down to "sign" and
    "folding" spawns the non-word stem "folde", so a stem-intersection
    (or a prefix match against such a stem) lets a morphological
    cousin vouch for an object that was never in the footage. An
    object is vouched for only by the object word's own spellings
    appearing verbatim in the evidence.
    """
    family = {word}
    if word.endswith("ies") and len(word) > 4:
        family.add(word[:-3] + "y")
    if word.endswith("es") and len(word) > 4:
        family.add(word[:-2])
    if word.endswith("s") and len(word) > 3:
        family.add(word[:-1])
    for form in list(family):
        family.add(form + "s")
        if form.endswith("y") and len(form) > 1 and form[-2] not in "aeiou":
            family.add(form[:-1] + "ies")
        if form.endswith(("s", "x", "z", "ch", "sh")):
            family.add(form + "es")
    return family


def _word_forms(word: str) -> set[str]:
    """Crude morphological family of a word (tear/tears/tearing).

    Deliberately simple suffix rules, applied to BOTH the claim and
    the evidence side (plus the narrow prefix backstop in
    :func:`_is_grounded`). It exists so a line is not rejected for
    using the record's own word in another tense.
    """
    forms = {word}
    if word.endswith("ies") and len(word) > 4:
        forms.add(word[:-3] + "y")
    if word.endswith("ing") and len(word) > 5:
        stem = word[:-3]
        forms.add(stem)
        forms.add(stem + "e")
        if len(stem) > 1 and stem[-1] == stem[-2]:
            forms.add(stem[:-1])
    if word.endswith("ed") and len(word) > 4:
        stem = word[:-2]
        forms.add(stem)
        forms.add(stem + "e")
        if len(stem) > 1 and stem[-1] == stem[-2]:
            forms.add(stem[:-1])
    if word.endswith("es") and len(word) > 4:
        forms.add(word[:-2])
    if word.endswith("s") and len(word) > 3:
        forms.add(word[:-1])
    return forms


def _evidence_tokens(texts: list[str]) -> set[str]:
    """Raw evidence tokens, exactly as written (no stemming).

    This is the only evidence view the tangible-object check may
    use: an object counts as vouched for when the evidence names
    the object itself, not a stemmed or prefixed relative of it.
    """
    tokens: set[str] = set()
    for text in texts:
        tokens.update(re.findall(r"[a-z]{4,}", str(text or "").lower()))
    return tokens


def _evidence_forms(texts: list[str]) -> set[str]:
    forms: set[str] = set()
    for token in _evidence_tokens(texts):
        forms |= _word_forms(token)
    return forms


def _common_prefix(a: str, b: str) -> int:
    count = 0
    for left, right in zip(a, b):
        if left != right:
            break
        count += 1
    return count


def _is_grounded(
    word: str, evidence_forms: set[str], evidence_tokens: set[str]
) -> bool:
    if _object_base(word) is not None:
        # Tangible objects take the strict route only (review C1 on
        # PR #1053): the evidence must name the object itself or its
        # plural, verbatim. Both fuzzy routes below are closed for
        # this class — stem-form intersection let "signing" vouch
        # for an invented "sign", and the prefix backstop let
        # "posted" vouch for an invented "poster" and the generated
        # stem "folde" (from "folding") for an invented "folder".
        return bool(_object_family(word) & evidence_tokens)
    forms = _word_forms(word)
    if forms & evidence_forms:
        return True
    synonym = _WORD_SYNONYMS.get(word)
    if synonym and _word_forms(synonym) & evidence_forms:
        return True
    # Prefix kinship as a narrow backstop (waterfall/water). The
    # floor is a 5-char common prefix: "sign"/"side" share 2 and
    # "sign"/"signal" share 4 — neither may ground the other, because
    # a sign is not a signal and neither is a safe side.
    return any(
        _common_prefix(form, evidence) >= 5
        for form in forms
        for evidence in evidence_forms
    )


def _claim_words(text: str) -> list[str]:
    """Significant words of a line that assert something checkable.

    Excludes stopwords (vq.content_words), framing/discourse words,
    judgement adjectives, and every class the consistency gates
    already police on their own (colours, emotions, postures, hair,
    identity labels) so a word is never double-flagged.
    """
    words: list[str] = []
    for token in vq.content_words(text):
        if token in _FRAMING_GENERIC_WORDS or token in _DESCRIPTIVE_WORDS:
            continue
        if token in vq._EMOTION_CANON or token in vq._POSTURE_CANON:
            continue
        if vq._canon_colour(token) in vq.COLOURS:
            continue
        if token in vq._HAIR_WORDS or token in vq._IDENTITY_WORDS:
            continue
        words.append(token)
    return words


def _ungrounded_words(
    text: str, evidence_forms: set[str], evidence_tokens: set[str]
) -> list[str]:
    return [
        word
        for word in _claim_words(text)
        if not _is_grounded(word, evidence_forms, evidence_tokens)
    ]


def framing_grounding_violations(
    *,
    hook: str,
    payoff: str,
    title: str,
    transcript: str = "",
    scene: str = "",
    record: dict[str, Any] | None = None,
) -> list[vq.Violation]:
    """Reject framing copy whose specifics the footage never vouches for.

    Hook, payoff and title are checked against the union evidence
    (source transcript + verified scene record) under
    :func:`_ungrounded_is_violation`: two or more ungrounded
    specifics, or a single invented tangible object. A single stray
    paraphrase word is deliberately tolerated — job 804's own good
    hook says "stroll" where the record says "walking", and a gate
    that rejects ordinary paraphrase would strangle the retry loop;
    job 804's bad payoff, by contrast, carried three invented
    specifics (a flipped "sign", a handed-over "folder"). The title
    additionally obeys the stricter record-only rule for action
    verbs — a title may only promise an action the vision record
    says the camera showed.

    Known residuals (deliberate, recorded — review C1/C2 on
    PR #1053):

    - A single invented tangible object that is NOT in
      _UNGROUNDED_OBJECT_WORDS, used with an otherwise grounded
      verb, still passes: "He walks the path with a ribbon." flags
      only 'ribbon', below the two-word threshold. Listed objects
      no longer enjoy any such slack — since the C1 fix they are
      grounded only by their own spellings in the evidence, never
      by the stem/prefix fuzzy routes — but the list itself is
      closed, so an unlisted object rides on the general threshold.
    - The title record-only rule likewise covers only the closed
      _TITLE_ACTION_WORDS list. A title promising an unshown action
      with an off-list verb is judged by the general union rule
      alone and can pass it when the rest of the title is grounded
      (before the list was extended, "He Shatters the Journal
      Strip" passed both title rules against job 803's evidence).
      The list is extended as evasions are observed, but it remains
      closed by construction; the coordinator's watch is the
      backstop for both residuals.
    """
    record_texts = vq._record_strings(record) if record is not None else []
    union_texts = [transcript or "", scene or "", *record_texts]
    union_forms = _evidence_forms(union_texts)
    union_tokens = _evidence_tokens(union_texts)
    violations: list[vq.Violation] = []
    for field_name, line in (("hook", hook), ("payoff", payoff)):
        if not line:
            continue
        missing = _ungrounded_words(line, union_forms, union_tokens)
        if _ungrounded_is_violation(missing):
            violations.append(vq.Violation(
                "framing_ungrounded", field_name,
                f"the {field_name} names {', '.join(repr(w) for w in missing)}, "
                "which appear nowhere in the source transcript or the "
                "verified scene record — describe only what the footage shows",
            ))
    if title:
        # Hashtags are channel metadata, not claims ("#Shorts" rides
        # every title by design); they are stripped before checking.
        title_text = re.sub(r"#\w+", "", title)
        missing = _ungrounded_words(title_text, union_forms, union_tokens)
        if _ungrounded_is_violation(missing):
            violations.append(vq.Violation(
                "title_ungrounded", "title",
                f"the title names {', '.join(repr(w) for w in missing)}, "
                "which appear nowhere in the source transcript or the "
                "verified scene record",
            ))
        record_forms = _evidence_forms(record_texts)
        record_tokens = _evidence_tokens(record_texts)
        if record is not None:
            for token in re.findall(r"[a-z]+", title_text.lower()):
                forms = _word_forms(token)
                if forms & _TITLE_ACTION_WORDS and not _is_grounded(
                    token, record_forms, record_tokens
                ):
                    violations.append(vq.Violation(
                        "title_action_ungrounded", "title",
                        f"the title promises the action '{token}', which the "
                        "vision record never shows happening — retitle from "
                        "what the excerpt actually shows",
                    ))
                    break
    return violations


def grounding_fallback_fields(violations: list[vq.Violation]) -> set[str] | None:
    """Which lines may be replaced by the claim-free generic lines.

    Substitution is allowed only when EVERY remaining violation is an
    ungrounded hook or payoff — a title problem, a consistency claim
    or a structural defect still skips the candidate, because a
    generic title would be its own false promise and the other gates
    protect facts, not phrasing. Returns the set of fields to replace
    (subset of {"hook", "payoff"}), or None when substitution is not
    permitted.
    """
    if not violations:
        return None
    fields: set[str] = set()
    for violation in violations:
        if violation.kind != "framing_ungrounded" or violation.field not in {"hook", "payoff"}:
            return None
        fields.add(violation.field)
    return fields or None


# --------------------------------------------------------------------------- #
# tail trim (TASK-VYR-022) — a disconnected still/reaction insert at the
# excerpt's tail is not the clip's ending. Job 802's excerpt closed on
# an unrelated black-and-white reaction still. Detection reuses the
# event arc's frame-difference machinery (vq.frame_change_metrics over
# the same greyscale samples vq.measure_event_arc extracts): a hard
# scene cut inside the tail window followed by near-zero change to the
# end is an inserted still. A merely quiet ending (no cut) is the main
# scene's own ending and is left alone, and an insert that leaves too
# little real clip when trimmed skips the candidate instead of
# shipping a video that is mostly a borrowed still.
# --------------------------------------------------------------------------- #
_TAIL_WINDOW_SECONDS = 8.0
_TAIL_SAMPLES = 12
_TAIL_CUT_MIN_CHANGE = 0.06    # a scene cut; the arc's "real event" floor is 0.02
_TAIL_MIN_STILL_SECONDS = 1.2
_MIN_EXCERPT_SECONDS = 8.0


def detect_tail_still(
    changes: Any,
    *,
    interval_seconds: float,
    cut_threshold: float = _TAIL_CUT_MIN_CHANGE,
    still_epsilon: float = vq._STATIC_EPSILON,
    min_still_seconds: float = _TAIL_MIN_STILL_SECONDS,
) -> float | None:
    """Offset where a still insert begins, or None.

    ``changes[i]`` is the frame change between evenly spaced samples
    i and i+1. Returns the offset (seconds from the first sample) of
    the first still frame — just after the LAST cut that is followed
    only by stillness lasting at least ``min_still_seconds`` — or
    None when the tail is the main scene's own ending: no cut at all,
    or motion resumes after the cut.
    """
    series = [float(change) for change in changes or ()]
    if interval_seconds <= 0 or len(series) < 2:
        return None
    last_cut: int | None = None
    for index, change in enumerate(series):
        if change >= cut_threshold:
            last_cut = index
    if last_cut is None:
        return None
    still_after = series[last_cut + 1:]
    if not still_after:
        return None
    if any(change >= still_epsilon for change in still_after):
        return None
    if len(still_after) * interval_seconds < min_still_seconds:
        return None
    return round((last_cut + 1) * interval_seconds, 3)


def measure_tail_trim(
    excerpt_path: Path,
    excerpt_seconds: float,
    *,
    ffmpeg_bin: str = "ffmpeg",
) -> tuple[float | None, str]:
    """(new_excerpt_seconds, reason) for a still-insert tail.

    Reasons: "trimmed" (new length returned), "no_still_tail" (the
    ending is the main scene's own), "still_dominates" (an insert
    exists but trimming it would leave less than the minimum viable
    excerpt — the caller skips), "not_measured" (too short to judge
    or frame extraction failed; production proceeds untrimmed, as
    before this gate existed).
    """
    length = float(excerpt_seconds or 0.0)
    source = Path(excerpt_path)
    if length < _MIN_EXCERPT_SECONDS + 2.0 or not source.is_file():
        return None, "not_measured"
    window = min(_TAIL_WINDOW_SECONDS, length * 0.4)
    interval = window / _TAIL_SAMPLES
    window_start = length - window
    frames: list[bytes] = []
    for index in range(_TAIL_SAMPLES):
        at = window_start + (index + 0.5) * interval
        cmd = [
            ffmpeg_bin, "-hide_banner", "-loglevel", "error", "-nostdin",
            "-ss", f"{at:.2f}", "-i", str(source),
            "-frames:v", "1",
            "-vf", (f"scale={vq._FRAME_WIDTH}:{vq._FRAME_HEIGHT}:"
                    "force_original_aspect_ratio=increase,"
                    f"crop={vq._FRAME_WIDTH}:{vq._FRAME_HEIGHT},format=gray"),
            "-f", "rawvideo", "-",
        ]
        try:
            proc = subprocess.run(cmd, capture_output=True, timeout=60)
        except (subprocess.SubprocessError, OSError) as exc:
            log.warning("Tail-trim frame extraction failed at %.1fs: %s", at, exc)
            return None, "not_measured"
        if proc.returncode == 0 and len(proc.stdout) == vq._FRAME_WIDTH * vq._FRAME_HEIGHT:
            frames.append(proc.stdout)
    if len(frames) < 6:
        log.warning("Tail-trim measurement got only %d usable frames", len(frames))
        return None, "not_measured"
    arc = vq.frame_change_metrics(frames)
    # Samples sit at (index + 0.5) * interval into the window; the
    # detected offset counts whole intervals from the window start, so
    # the trim lands up to half an interval BEFORE the first still
    # frame — the safe direction (it can only shave moving frames,
    # never leave still ones).
    cut_offset = detect_tail_still(arc.changes, interval_seconds=interval)
    if cut_offset is None:
        return None, "no_still_tail"
    new_seconds = round(window_start + cut_offset, 3)
    if new_seconds < _MIN_EXCERPT_SECONDS:
        return None, "still_dominates"
    if length - new_seconds < 1.0:
        return None, "no_still_tail"
    return new_seconds, "trimmed"


def _cue_tokens(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", str(text or "").lower()))


def _duplicates_framing_line(speech_text: str, framing_text: str) -> bool:
    """True when a source speech cue repeats her framing line's words.

    The cycle-2 watch (job 801) showed the source's final spoken line
    captioned twice at once — once as the Whisper speech cue and again
    inside her payoff, which had quoted it. When the words are the
    same, one caption carries them: hers, in her band, while the
    source audio is ducked under her voice anyway.
    """
    speech_tokens = _cue_tokens(speech_text)
    framing_tokens = _cue_tokens(framing_text)
    if len(speech_tokens) < 2 or not framing_tokens:
        return False
    if speech_tokens <= framing_tokens:
        return True
    union = speech_tokens | framing_tokens
    return bool(union) and len(speech_tokens & framing_tokens) / len(union) >= 0.5


# The only framing violations with a deterministic, fact-free repair:
# the description's question/CTA mechanics. Everything else a gate can
# raise is a factual claim about the footage and must fail, never be
# edited into compliance (viral_quality.repair_description_question's
# own contract).
_DESCRIPTION_QUESTION_KINDS = frozenset({"question_ungrounded", "cta_without_question"})


def repair_framing_description(
    framing: dict[str, str],
    violations: list[vq.Violation],
    *,
    hook: str,
    payoff: str,
    record: dict[str, Any],
    excerpt_seconds: float,
    transcript: str = "",
    scene: str = "",
) -> tuple[dict[str, str], list[vq.Violation], bool]:
    """Repair a framing package whose ONLY defect is its question.

    TASK-VYR-023 diagnosis: the commentary path has had this escape
    since TASK-VYR-014 — after its retries, a package whose remaining
    violations are all description-question kinds gets
    :func:`viral_quality.repair_description_question` and a full
    re-gate. The framed path never got the same step, even though it
    runs the identical description check (via check_consistency) on
    the identical mandated description format (a question ending in
    'Drop your answer below!'). The TASK-VYR-022 grounding fallback
    covers ungrounded hook/payoff LINES; nothing covered the
    description's question. A framed package whose hook, payoff and
    title were fully grounded therefore died as script_unverifiable
    over packaging mechanics the commentary path repairs
    deterministically — in supervised cycle 2 the question_ungrounded
    kind is the only violation kind documented more than once (2 of
    the commentary candidate's 3 rejected drafts), and the framed
    path had no way out of it at all.

    The repair is applied ONLY when every remaining violation is a
    description-question kind, and the repaired package must pass
    the FULL framing gate suite again (transcript/scene evidence
    included, exactly as the production caller gates) to be
    accepted — factual violations (colours, garments, posture,
    identity, time of day, grounding) are never repaired. Returns
    (framing, violations, repaired).
    """
    if not violations or any(
        violation.kind not in _DESCRIPTION_QUESTION_KINDS for violation in violations
    ):
        return framing, violations, False
    repaired_description = vq.repair_description_question(
        str(framing.get("description") or ""), record
    )
    if repaired_description == str(framing.get("description") or ""):
        return framing, violations, False
    repaired_framing = {**framing, "description": repaired_description}
    remaining = framing_violations(
        hook=hook,
        payoff=payoff,
        title=str(repaired_framing.get("title") or ""),
        description=repaired_description,
        record=record,
        excerpt_seconds=excerpt_seconds,
        transcript=transcript,
        scene=scene,
    )
    if remaining:
        return framing, violations, False
    return repaired_framing, [], True


def framed_cues(
    speech_cues: Any,
    *,
    excerpt_start: float,
    excerpt_seconds: float,
    hook: str,
    hook_seconds: float,
    payoff: str,
    payoff_seconds: float,
) -> list[dict[str, Any]]:
    """Caption cues for a framed edit, on the excerpt's timeline.

    The source's own speech keeps its measured Whisper timings
    (shifted into the excerpt and clipped to it — a cue that falls
    outside the excerpt is dropped, never stretched). Her hook and
    payoff cues sit at the two ends, where she actually speaks, and
    carry ``framing: True`` so the ASS writer puts them in their own
    top band (TASK-VYR-022) instead of the lower-third zone the
    source's captions occupy. A source speech cue that merely repeats
    her framing line inside that line's window is dropped — the words
    stay on screen exactly once. Subtitles are on the whole video,
    always.
    """
    framing_windows: list[tuple[float, float, str]] = []
    if hook and hook_seconds > 0:
        framing_windows.append((0.0, min(hook_seconds, excerpt_seconds), hook))
    if payoff and payoff_seconds > 0:
        framing_windows.append(
            (max(0.0, excerpt_seconds - payoff_seconds), excerpt_seconds, payoff)
        )
    cues: list[dict[str, Any]] = []
    for cue in speech_cues or ():
        start = float(cue.get("start") or 0.0) - excerpt_start
        end = float(cue.get("end") or 0.0) - excerpt_start
        if end <= 0.0 or start >= excerpt_seconds:
            continue
        text = str(cue.get("text") or "").strip()
        if not text:
            continue
        start = max(0.0, start)
        end = min(excerpt_seconds, end)
        if any(
            start < window_end and end > window_start
            and _duplicates_framing_line(text, window_text)
            for window_start, window_end, window_text in framing_windows
        ):
            log.info(
                "Dropping source speech cue duplicating a framing line: %r", text[:80]
            )
            continue
        cues.append({
            "start": round(start, 2),
            "end": round(end, 2),
            "text": text,
            "speech": True,
        })
    if hook and hook_seconds > 0:
        cues.append({
            "start": 0.0,
            "end": round(min(hook_seconds, excerpt_seconds), 2),
            "text": hook,
            "framing": True,
        })
    if payoff and payoff_seconds > 0:
        cues.append({
            "start": round(max(0.0, excerpt_seconds - payoff_seconds), 2),
            "end": round(excerpt_seconds, 2),
            "text": payoff,
            "framing": True,
        })
    cues.sort(key=lambda item: (item["start"], item["end"]))
    return vr._sanitize_cues(cues)


def render_framed(
    source_path: Path,
    output_path: Path,
    *,
    excerpt_start: float,
    excerpt_seconds: float,
    hook_audio: Path,
    hook_seconds: float,
    payoff_audio: Path,
    payoff_seconds: float,
    cues: list[dict[str, Any]],
    category: str,
    music_bed_path: Path | None = None,
) -> Path:
    """Assemble the framed edit.

    Video: the excerpt window, channel format + burned captions via
    the production filter, encoded at the render-fit profile above
    (720x1280, TASK-VYR-021 — the framed path runs on the fleet's
    smallest host; the commentary path keeps the 1080x1920 default).
    Audio: the source at full level except
    under her two lines (ducked to 0.22, the production duck level),
    her lines placed at the two ends, and the BGM bed at full level
    in the stretches where nobody speaks and ducked under her lines.
    The mix is loudnormed to the production target. The BGM bed is
    mandatory (TASK-VYR-032): a render with no bed, or a bed file that
    is empty or undecodable, raises instead of shipping silent.
    """
    settings = get_settings()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    bed_path = vr._require_music_bed(music_bed_path)
    ass_path = vr._write_ass(cues, output_path.with_suffix(".ass"))
    video_chain = vr._base_video_filter(
        cues,
        category,
        ass_path,
        width=_RENDER_WIDTH,
        height=_RENDER_HEIGHT,
        max_fps=_RENDER_MAX_FPS,
    )
    end = excerpt_start + excerpt_seconds
    duck_hook_end = min(excerpt_seconds, hook_seconds + 0.15)
    duck_payoff_start = max(0.0, excerpt_seconds - payoff_seconds - 0.15)
    payoff_delay_ms = int(max(0.0, excerpt_seconds - payoff_seconds) * 1000)

    filters = [
        f"[0:v]trim=start={excerpt_start:.3f}:end={end:.3f},"
        f"setpts=PTS-STARTPTS,{video_chain}[v]",
        f"[0:a]atrim=start={excerpt_start:.3f}:end={end:.3f},"
        "asetpts=PTS-STARTPTS,"
        f"volume=0.22:enable='between(t,0,{duck_hook_end:.3f})',"
        f"volume=0.22:enable='between(t,{duck_payoff_start:.3f},{excerpt_seconds:.3f})'"
        "[src]",
        f"[1:a]apad=whole_dur={excerpt_seconds:.3f}[hk]",
        f"[2:a]adelay={payoff_delay_ms}|{payoff_delay_ms}[po]",
        "[hk][po]amix=inputs=2:duration=first:dropout_transition=0[nar]",
    ]
    filters.append(
        "[3:a]volume=0.12,"
        f"volume=0.05:enable='between(t,0,{duck_hook_end:.3f})',"
        f"volume=0.05:enable='between(t,{duck_payoff_start:.3f},{excerpt_seconds:.3f})'"
        "[bed]"
    )
    filters.append(
        "[src][nar][bed]amix=inputs=3:duration=first:dropout_transition=2,"
        "loudnorm=I=-14:LRA=9:TP=-1.5[a]"
    )
    cmd = [
        settings.ffmpeg_bin, "-hide_banner", "-nostdin", "-y",
        "-i", str(source_path),
        "-i", str(hook_audio),
        "-i", str(payoff_audio),
        "-i", str(bed_path),
    ]
    cmd += [
        "-filter_complex", ";".join(filters),
        "-map", "[v]", "-map", "[a]",
        "-c:v", "libx264", "-preset", _X264_PRESET, "-crf", _X264_CRF,
        "-pix_fmt", "yuv420p",
        "-threads", _X264_THREADS,
        "-c:a", "aac", "-b:a", "192k",
        "-movflags", "+faststart",
        "-t", f"{excerpt_seconds:.2f}",
        str(output_path),
    ]
    vr._run(cmd, timeout=2400)
    return output_path


def _cut_excerpt(source_path: Path, destination: Path, start: float, seconds: float) -> Path:
    """Cut the excerpt window to its own file for vision analysis.

    Encoded at the excerpt-fit profile above (TASK-VYR-023): the file
    feeds only the event-arc measurement and the vision record, so it
    is capped to what those consumers — and the 720x1280 final
    render — can use. The final composition is unaffected: it trims
    from the original source at the render-fit profile.
    """
    settings = get_settings()
    destination.parent.mkdir(parents=True, exist_ok=True)
    vr._run(_excerpt_command(settings.ffmpeg_bin, source_path, destination, start, seconds))
    return destination


# --------------------------------------------------------------------------- #
# render binding (TASK-VYR-024) — a held job's title, series, source
# and render must never diverge. Production writes every one of those
# from the single candidate object, and the cycle-5 records prove the
# pipeline's own bindings held: publish_jobs, render_jobs, assets,
# sources, video_projects, the loop manifest and the physical files
# (names and probed durations) all agree for jobs 821-825. The pairing
# that crossed — job 823's title read against job 824's render file —
# was assembled OUTSIDE the pipeline, by pairing two separately
# enumerated lists by position. These checks give the pipeline's own
# record the means to prove the binding by key instead: the finished
# render is probed before anything is persisted, a mismatch fails the
# production closed (no publish job is created), and the probe result
# is stamped into the render job's options so any later enumeration
# can verify — by key, not by position — that the file on disk is the
# render this job produced.
# --------------------------------------------------------------------------- #
_RENDER_BINDING_DURATION_TOLERANCE = 1.0


def render_binding_violations(
    *,
    video_id: str,
    render_name: str,
    render_duration: float,
    excerpt_seconds: float,
) -> list[str]:
    """Ways a finished render fails to bind to the job that ordered it."""
    problems: list[str] = []
    if not str(render_name).startswith(f"framed-{video_id}-"):
        problems.append(
            f"render file {render_name!r} does not carry source id {video_id!r}"
        )
    if not render_duration or float(render_duration) <= 0:
        problems.append("render probe returned no duration")
    elif abs(float(render_duration) - float(excerpt_seconds)) > _RENDER_BINDING_DURATION_TOLERANCE:
        problems.append(
            f"render duration {float(render_duration):.2f}s does not match "
            f"the excerpt it was cut from ({float(excerpt_seconds):.2f}s)"
        )
    return problems


def produce_framed_short(
    candidate: Any,
    db: Session,
    *,
    publish: bool = True,
    hold_for_review: bool = False,
) -> dict[str, Any]:
    """Audition -> excerpt -> frame -> register -> publish-job for one
    voiced candidate. Mirrors :func:`app.services.viral_remix.produce_viral_short`'s
    persistence and result shape, with ``edit_mode="framed"``.

    ``hold_for_review`` has the same meaning as in the commentary
    path: the publish job is created ``pending_approval`` with no
    approval timestamp, so nothing can upload it before the owner
    reviews it.
    """
    settings = get_settings()
    category = normalise_label(str(getattr(candidate, "category", "") or "VIRAL"))
    settings.prepare_directories()
    settings.render_dir.mkdir(parents=True, exist_ok=True)
    settings.media_dir.mkdir(parents=True, exist_ok=True)

    # 1. Audition: this mode exists ONLY for voiced sources, and only
    # when the speech comes with timings we can subtitle. Anything
    # else is a mis-route or an unsubtitlable clip — fail closed.
    audio_dir = settings.media_dir / "viral_audio_probe"
    audio_path = vr.download_audio_only(candidate.video_id, audio_dir)
    if audio_path is None:
        return {"status": "SKIPPED", "reason": "audio_unavailable", "video_id": candidate.video_id}
    speech = vr.detect_speech(audio_path)
    if not speech.has_speech:
        return {"status": "SKIPPED", "reason": "source_has_no_narration", "video_id": candidate.video_id}
    if not speech.cues:
        return {"status": "SKIPPED", "reason": "no_transcript", "video_id": candidate.video_id}

    # 2. Full download, probe, excerpt window around the event peak.
    source_path = vr.download_source_video(candidate.video_id, settings.media_dir / "viral_sources")
    probe = vr.probe_media(source_path)
    duration = max(6.0, probe.duration or float(candidate.duration or 20.0))
    project_key = f"framed-{candidate.video_id}-{uuid.uuid4().hex[:6]}"

    gates_on = bool(getattr(settings, "viral_quality_gates_enabled", True))
    full_arc = None
    if gates_on:
        full_arc = vq.measure_event_arc(source_path, duration, ffmpeg_bin=settings.ffmpeg_bin)
    excerpt_start, excerpt_end = excerpt_window(
        duration,
        full_arc.peak_position if full_arc is not None else None,
        full_seconds=float(getattr(settings, "viral_max_source_seconds", 58.0)),
    )
    excerpt_seconds = round(excerpt_end - excerpt_start, 3)
    excerpt_path = _cut_excerpt(
        source_path,
        settings.media_dir / "viral_sources" / f"{project_key}-excerpt.mp4",
        excerpt_start,
        excerpt_seconds,
    )

    # 2b. Tail trim (TASK-VYR-022): if the excerpt ends on a
    # disconnected still/reaction insert, the excerpt ends where the
    # insert begins — before any analysis, so the vision record and
    # the editorial describe the clip that will actually ship. An
    # insert that dominates the excerpt skips the candidate.
    tail_trim_reason = ""
    if gates_on:
        trimmed_seconds, tail_trim_reason = measure_tail_trim(
            excerpt_path, excerpt_seconds, ffmpeg_bin=settings.ffmpeg_bin
        )
        if tail_trim_reason == "still_dominates":
            log.info(
                "Skipping %s: excerpt tail is a disconnected still insert "
                "with too little real clip before it",
                candidate.video_id,
            )
            return {
                "status": "SKIPPED", "reason": "tail_still_dominates",
                "video_id": candidate.video_id,
            }
        if trimmed_seconds is not None:
            log.info(
                "Trimming still-insert tail for %s: excerpt %.2fs -> %.2fs",
                candidate.video_id, excerpt_seconds, trimmed_seconds,
            )
            excerpt_seconds = trimmed_seconds
            excerpt_path = _cut_excerpt(
                source_path, excerpt_path, excerpt_start, excerpt_seconds
            )

    record: dict[str, Any] | None = None
    arc_info: dict[str, Any] | None = None
    if gates_on:
        arc = vq.measure_event_arc(excerpt_path, excerpt_seconds, ffmpeg_bin=settings.ffmpeg_bin)
        arc_ok, arc_reason = vq.arc_gate(arc)
        if arc is not None:
            arc_info = {
                "mean_change": arc.mean_change,
                "max_change": arc.max_change,
                "static_ratio": arc.static_ratio,
                "peak_position": arc.peak_position,
                "verdict": arc_reason,
            }
        if not arc_ok:
            log.info("Skipping %s: static scene (arc %s)", candidate.video_id, arc_info)
            return {
                "status": "SKIPPED", "reason": "static_scene",
                "video_id": candidate.video_id, "event_arc": arc_info,
            }
        record = analyze_scene(excerpt_path, excerpt_seconds)
        if record is None:
            return {"status": "SKIPPED", "reason": "vision_unavailable", "video_id": candidate.video_id}
        if record.get("static"):
            return {
                "status": "SKIPPED", "reason": "static_scene",
                "video_id": candidate.video_id, "event_arc": arc_info,
            }
        # Visible-text defects (TASK-VYR-024): a creator watermark
        # stamped on the footage or burned-in captions piled up
        # unreadably are defects of the source's pixels — no later
        # stage can remove them, so the candidate is rejected here,
        # at the only pre-render look at those pixels. Cycle 5 held
        # both (a "@WARPATROL" watermark throughout one render;
        # overlapping source captions in another) because the vision
        # record was never asked about on-screen text.
        defects = record_visual_defects(record)
        if defects:
            log.info(
                "Skipping %s: visible-text defect in source frames (%s)",
                candidate.video_id, ", ".join(defects),
            )
            return {
                "status": "SKIPPED", "reason": defects[0],
                "video_id": candidate.video_id,
                "visual_defects": defects,
                "watermark_text": str(record.get("watermark_text") or ""),
            }
        scene = scene_text(record)
    else:
        from app.services.scene_analysis import describe_scene

        scene = describe_scene(excerpt_path, excerpt_seconds)

    # 3. Framing editorial under the gate suite (same fail-closed
    # discipline as the commentary path: feedback retries, the
    # deterministic hook repair, then the candidate is skipped).
    taken_titles = vr.existing_upload_titles(db)
    hook = ""
    payoff = ""
    framing: dict[str, str] = {}
    violations: list[vq.Violation] = []
    gate_attempts = 0
    hook_repaired = False
    grounding_fallback_used = False
    feedback: list[str] | None = None
    attempts_allowed = 3 if (gates_on and record is not None) else 1
    for attempt in range(attempts_allowed):
        gate_attempts = attempt + 1
        framing = generate_framing(
            category,
            str(getattr(candidate, "title", "")),
            str(getattr(candidate, "channel", "")),
            speech.text,
            scene=scene,
            taken_titles=taken_titles,
            feedback=feedback,
        )
        if not framing:
            return {"status": "SKIPPED", "reason": "editorial_unavailable", "video_id": candidate.video_id}
        hook = vq.sanitize_spoken_text(framing.get("hook") or "")
        payoff = vq.sanitize_spoken_text(framing.get("payoff") or "")
        if not (gates_on and record is not None):
            break
        violations = framing_violations(
            hook=hook,
            payoff=payoff,
            title=str(framing.get("title") or ""),
            description=str(framing.get("description") or ""),
            record=record,
            excerpt_seconds=excerpt_seconds,
            transcript=speech.text,
            scene=scene,
        )
        if not violations:
            break
        if any(violation.kind == "hook_too_long" for violation in violations):
            repaired_hook = vq.repair_hook_length(hook)
            if repaired_hook != hook and not framing_violations(
                hook=repaired_hook,
                payoff=payoff,
                title=str(framing.get("title") or ""),
                description=str(framing.get("description") or ""),
                record=record,
                excerpt_seconds=excerpt_seconds,
                transcript=speech.text,
                scene=scene,
            ):
                hook = repaired_hook
                hook_repaired = True
                violations = []
                break
        feedback = [violation.detail for violation in violations]
    # Grounding fallback (TASK-VYR-022): when the ONLY remaining
    # defect is an ungrounded hook/payoff — the model kept inventing
    # specifics the footage never shows — the invented line is
    # replaced by a claim-free generic line and the rejection is
    # logged with the rejected text. The substituted package must
    # re-pass the whole gate suite; anything else still skips.
    if gates_on and record is not None and violations:
        fallback_fields = grounding_fallback_fields(violations)
        if fallback_fields:
            sub_hook = _GENERIC_HOOK if "hook" in fallback_fields else hook
            sub_payoff = _GENERIC_PAYOFF if "payoff" in fallback_fields else payoff
            if not framing_violations(
                hook=sub_hook,
                payoff=sub_payoff,
                title=str(framing.get("title") or ""),
                description=str(framing.get("description") or ""),
                record=record,
                excerpt_seconds=excerpt_seconds,
                transcript=speech.text,
                scene=scene,
            ):
                log.warning(
                    "Framing grounding fallback for %s: rejected ungrounded "
                    "%s (hook=%r, payoff=%r); substituted claim-free "
                    "generic line(s)",
                    candidate.video_id, sorted(fallback_fields), hook, payoff,
                )
                hook, payoff, violations = sub_hook, sub_payoff, []
                grounding_fallback_used = True
    if gates_on and record is not None and violations:
        # Same deterministic escape the commentary path has had since
        # TASK-VYR-014 (TASK-VYR-023): a package grounded in every
        # factual claim whose only remaining defect is the
        # description's question gets that question repaired and is
        # re-gated in full; anything else still skips, unrepaired.
        framing, violations, description_repaired = repair_framing_description(
            framing, violations,
            hook=hook, payoff=payoff, record=record,
            excerpt_seconds=excerpt_seconds,
            transcript=speech.text, scene=scene,
        )
        if description_repaired:
            log.info(
                "Description question repaired for %s", candidate.video_id,
            )
    if gates_on and record is not None and violations:
        return {
            "status": "SKIPPED", "reason": "script_unverifiable",
            "video_id": candidate.video_id,
            "violations": [violation.kind for violation in violations],
        }
    if not hook or not payoff:
        return {"status": "SKIPPED", "reason": "editorial_unavailable", "video_id": candidate.video_id}

    # 4. Her two lines, synthesised and MEASURED against their windows.
    voice = vr.VOICE_BY_CATEGORY.get(category, vr.DEFAULT_VOICE)
    voice_dir = settings.media_dir / "voiceovers"
    hook_audio, _hook_cues = vr.synthesize_commentary(
        hook, voice, voice_dir / f"{project_key}-hook.mp3"
    )
    payoff_audio, _payoff_cues = vr.synthesize_commentary(
        payoff, voice, voice_dir / f"{project_key}-payoff.mp3"
    )
    hook_seconds = float(vr.probe_media(hook_audio).duration or 0.0)
    payoff_seconds = float(vr.probe_media(payoff_audio).duration or 0.0)
    if (
        hook_seconds <= 0
        or payoff_seconds <= 0
        or hook_seconds > hook_window_seconds(excerpt_seconds) + 0.35
        or payoff_seconds > payoff_window_seconds(excerpt_seconds) + 0.35
    ):
        log.info(
            "Skipping %s: framing lines do not fit (hook %.2fs of %.2fs, payoff %.2fs of %.2fs)",
            candidate.video_id, hook_seconds, hook_window_seconds(excerpt_seconds),
            payoff_seconds, payoff_window_seconds(excerpt_seconds),
        )
        return {
            "status": "SKIPPED", "reason": "script_length_misfit",
            "video_id": candidate.video_id,
        }

    # 5. Captions (always), BGM bed (mandatory), render.
    cues = framed_cues(
        speech.cues,
        excerpt_start=excerpt_start,
        excerpt_seconds=excerpt_seconds,
        hook=hook,
        hook_seconds=hook_seconds,
        payoff=payoff,
        payoff_seconds=payoff_seconds,
    )
    if not cues:
        raise RuntimeError("caption generation produced no cues")
    bed_path: Path | None = None
    bgm_source = ""
    if bool(getattr(settings, "viral_music_bed_enabled", True)):
        from app.services.viral_bgm import is_real_track_label, prepare_music_bed

        bed_path, bgm_source = prepare_music_bed(
            voice_dir / f"{project_key}-bed.wav",
            excerpt_seconds,
            category=category,
        )
    render_path = settings.render_dir / f"{project_key}.mp4"
    render_framed(
        source_path,
        render_path,
        excerpt_start=excerpt_start,
        excerpt_seconds=excerpt_seconds,
        hook_audio=hook_audio,
        hook_seconds=hook_seconds,
        payoff_audio=payoff_audio,
        payoff_seconds=payoff_seconds,
        cues=cues,
        category=category,
        music_bed_path=bed_path,
    )

    # Render binding (TASK-VYR-024): probe the finished file and prove
    # it is the render THIS candidate ordered before anything is
    # persisted — on a mismatch the production fails closed and no
    # publish job is created. The probe is stamped into the render
    # job's options below, so the binding stays verifiable by key.
    render_probe = vr.probe_media(render_path)
    binding_problems = render_binding_violations(
        video_id=candidate.video_id,
        render_name=render_path.name,
        render_duration=float(render_probe.duration or 0.0),
        excerpt_seconds=excerpt_seconds,
    )
    if binding_problems:
        raise RuntimeError(
            f"render binding check failed for {candidate.video_id}: "
            + "; ".join(binding_problems)
        )

    thumbnail_path = settings.render_dir / f"{project_key}-thumb.jpg"
    try:
        from app.services.thumbnail_designer import generate_genre_thumbnail

        generate_genre_thumbnail(
            video_path=source_path,
            output_path=thumbnail_path,
            headline=str(candidate.hook or "WAIT FOR IT"),
            category=category,
        )
    except Exception as exc:  # thumbnail is a nice-to-have, never fatal
        log.warning("Thumbnail generation failed: %s", exc)
        thumbnail_path = Path("")

    editorial = {
        "title": str(framing.get("title") or ""),
        "description": str(framing.get("description") or ""),
        "commentary": f"{hook} {payoff}".strip(),
    }
    meta = vr.build_metadata(
        candidate, speech, hook, category, editorial, taken_titles, record=record
    )
    try:
        from app.services.monetization import monetization_footer

        _footer = monetization_footer()
        if _footer:
            meta["description"] = f"{meta['description']}\n\n{_footer}"[:4800]
    except Exception as exc:  # monetization must never break production
        log.warning("Monetization footer skipped: %s", exc)

    # 6. Persist rights record + render + publish job (mirrors the
    # commentary path's block, including its rights bookkeeping).
    reuse_licensed = bool(str(getattr(candidate, "license", "")).strip()) and (
        "creative commons" in str(candidate.license).casefold()
    )
    if reuse_licensed:
        platform = "youtube_creative_commons"
        license_name = str(candidate.license)[:190]
        permission_reference = (
            f"https://www.youtube.com/watch?v={candidate.video_id} - licence: {candidate.license}"
        )[:2000]
        notes = "Reuse licence verified from the source metadata."
    else:
        platform = "youtube_transformative"
        license_name = "Transformative commentary - original creator credited (operator policy)"
        permission_reference = (
            f"https://www.youtube.com/watch?v={candidate.video_id} - operator-attested "
            "transformative commentary: original audio retained or new commentary added, "
            "subtitles and attribution on every upload"
        )[:2000]
        notes = "Operator-selected transformative commentary policy; original creator credited in the description."
    source = Source(
        title=f"Source: {candidate.title[:240]}",
        source_url=f"https://www.youtube.com/watch?v={candidate.video_id}",
        platform=platform,
        creator=str(candidate.channel or "")[:280],
        license_name=license_name,
        permission_reference=permission_reference,
        repeat_use_allowed=True,
        repeat_use_reviewed_at=utcnow(),
        repeat_use_review_notes=(
            "Operator-attested transformative-commentary policy; no repeat-use "
            "review required."
        ),
        rights_verified=True,
        status="approved",
        notes=notes,
    )
    db.add(source)
    db.flush()
    asset = Asset(
        source_id=source.id,
        title=str(candidate.title)[:280],
        file_path=str(source_path),
        duration_seconds=float(duration),
        width=probe.width,
        height=probe.height,
        rights_verified=True,
    )
    db.add(asset)
    db.flush()

    project = VideoProject(
        project_key=project_key,
        topic=f"Framed: {str(candidate.title)[:120]}",
        video_format="shorts",
        target_seconds=int(round(excerpt_seconds)),
        audience="viral shorts audience",
        tone="framing commentary - source voice kept",
        scene_count=1,
        confirm_pexels_license=False,
        confirm_pexels_repeat_use=False,
        use_voiceover=True,
        status="completed",
        primary_asset_id=asset.id,
        asset_ids_json=json.dumps([asset.id]),
        thumbnail_path=str(thumbnail_path) if thumbnail_path else "",
        completed_at=utcnow(),
        attempts=1,
    )
    db.add(project)
    db.flush()

    render_job = RenderJob(
        asset_id=asset.id,
        preset="shorts",
        status="completed",
        output_path=str(render_path),
        attempts=1,
        project_id=None,
        options_json=json.dumps({
            "montage_asset_ids": [asset.id],
            "source_video_id": candidate.video_id,
            "source_views": int(getattr(candidate, "view_count", 0) or 0),
            "edit_mode": "framed",
            "event_arc": arc_info,
            "quality_gate_attempts": gate_attempts,
            "hook_repaired": hook_repaired,
            "grounding_fallback": grounding_fallback_used,
            "tail_trim": tail_trim_reason,
            "hold_for_review": hold_for_review,
            "bgm_source": bgm_source,
            # TASK-VYR-038: the per-job gate field — True only when the bed
            # is a real library track, so a supervised cycle can gate on
            # it without string-matching the label.
            "bgm_real_track": is_real_track_label(bgm_source),
            "excerpt": {"start": excerpt_start, "seconds": excerpt_seconds},
            "series": category,
            "render_duration_seconds": round(float(render_probe.duration or 0.0), 3),
            "render_bytes": render_path.stat().st_size if render_path.is_file() else 0,
        }),
        completed_at=utcnow(),
    )
    db.add(render_job)
    db.flush()
    project.render_job_id = render_job.id

    publish_job = None
    if publish:
        publish_job = PublishJob(
            asset_id=asset.id,
            render_job_id=render_job.id,
            title=meta["title"],
            description=meta["description"],
            tags_json=json.dumps(meta["tags"]),
            privacy_status=str(getattr(settings, "autonomous_publish_privacy", "unlisted")),
            status="pending_approval" if hold_for_review else "queued",
            approved_at=None if hold_for_review else utcnow(),
            thumbnail_path=str(thumbnail_path) if thumbnail_path else "",
            category_id=str(meta.get("category_id") or ""),
        )
        db.add(publish_job)
    db.commit()

    result = {
        "status": "QUEUED_FOR_PUBLISH" if publish else "RENDERED",
        "project_key": project_key,
        "project_id": project.id,
        "render_job_id": render_job.id,
        "publish_job_id": publish_job.id if publish_job else None,
        "edit_mode": "framed",
        "source_video_id": candidate.video_id,
        "source_views": int(getattr(candidate, "view_count", 0) or 0),
        "source_license": candidate.license,
        "title": meta["title"],
        "duration": round(excerpt_seconds, 1),
        "narration": f"{hook} {payoff}".strip()[:280],
        "render": str(render_path),
        "event_arc": arc_info,
        "quality_gate_attempts": gate_attempts,
        "hook_repaired": hook_repaired,
        "grounding_fallback": grounding_fallback_used,
        "tail_trim": tail_trim_reason,
        "hold_for_review": hold_for_review,
        "bgm_source": bgm_source,
        "bgm_real_track": is_real_track_label(bgm_source),
        "excerpt": {"start": excerpt_start, "seconds": excerpt_seconds},
        "series": category,
    }
    if publish and getattr(settings, "crosspost_export_enabled", True):
        try:
            from app.services.crosspost_export import write_crosspost_bundle

            bundle = write_crosspost_bundle(
                render_path,
                title=meta["title"],
                description=meta["description"],
                tags=meta["tags"],
                category=category,
                video_key=project_key,
            )
            result["crosspost_bundle"] = bundle["bundle"]
        except Exception as exc:  # packaging must never break production
            log.warning("Cross-post bundle skipped: %s", exc)
    log.info("Framed short ready: %s", result)
    return result
