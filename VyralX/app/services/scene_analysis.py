"""Frame analysis for the viral repurposing pipeline.

The commentary must describe what the clip actually shows. Text-only generation
cannot do that: given only a source title, the model invents a plot and the
voice-over ends up narrating something that never happens on screen.

Two passes live here:

* :func:`describe_scene` — the original free-text pass (three frames, three
  numbered lines). Kept for callers that only need prose.
* :func:`analyze_scene` — the structured vision record the quality gates
  consume (TASK-VYR-014): three frames, one per beat (the provider caps a
  request at 3 images), returned as strict JSON
  with per-beat setting, time of day, subjects (hair, clothing, posture,
  action, emotion, eyes), objects and a summary, plus the clip's event arc.
  Unlike the free-text pass it is NOT best-effort: it returns ``None`` on any
  failure and the autopilot skips the candidate, because copy written
  without ground truth is exactly what the owner ordered deleted.
"""
from __future__ import annotations

import base64
import json
import logging
import math
import subprocess
import tempfile
import time
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any

import httpx

from app.config import get_settings

log = logging.getLogger("vyralx.scene_analysis")

# Positions through the clip: the setup, the middle beat and the payoff.
_FRAME_POSITIONS = (0.15, 0.5, 0.85)
# TASK-VYR-026 (fix 3): frames were 640px on the long edge; 512px keeps
# the record's subjects/objects legible while cutting the per-call
# image tokens an estimated 25-40% — the vision model's free-tier
# token limits (8k/min, 200k/day) are what cycles 6/7 starved on.
_MAX_EDGE = 512

_PROMPT = (
    "These frames are sampled from one short vertical comedy clip, in order: "
    "frame 1 is the start, frame 2 the middle, frame 3 the end. "
    "For each frame describe exactly what is visible: the subject, what they are "
    "doing, and how the situation changes. Use only what you can see - never guess "
    "a joke, a line of dialogue or a detail that is not in the frames. "
    "Reply with exactly three numbered lines, one per frame, in this exact format "
    "and nothing else:\n"
    "1) <what is on screen in frame 1>\n"
    "2) <what is on screen in frame 2>\n"
    "3) <what is on screen in frame 3>\n"
    "Each line one short sentence, present tense. No preamble, no conclusion, no "
    "extra lines."
)


def _extract_frame(source: Path, seconds: float, destination: Path) -> bool:
    settings = get_settings()
    cmd = [
        settings.ffmpeg_bin, "-hide_banner", "-loglevel", "error", "-y",
        "-ss", f"{max(0.0, seconds):.2f}", "-i", str(source),
        "-frames:v", "1",
        "-vf", f"scale={_MAX_EDGE}:-2",
        "-q:v", "4",
        str(destination),
    ]
    try:
        subprocess.run(cmd, capture_output=True, timeout=60, check=True)
    except (subprocess.SubprocessError, OSError) as exc:
        log.warning("Frame extraction failed at %.1fs: %s", seconds, exc)
        return False
    return destination.is_file() and destination.stat().st_size > 1_000


def _data_url(path: Path) -> str:
    return "data:image/jpeg;base64," + base64.b64encode(path.read_bytes()).decode("ascii")


# --------------------------------------------------------------------------- #
# Vision transport: rate-limit instrumentation, bounded 429 retry, pacing
# (TASK-VYR-026).
#
# Diagnosis (2026-11-19, ~/workspace/vyralx-vision-429/DIAGNOSIS.md):
# supervised cycles 6 and 7 lost 14/24 and 22/24 attempts to
# vision_unavailable. Every failure was this module's single Groq call
# returning HTTP 429 — the free plan for the vision model allows
# 8,000 tokens/min and 200,000 tokens/day per organization, and one
# scene call costs an estimated 3,000-5,500 tokens. The old code made
# exactly one attempt, discarded the 429 body and rate-limit headers
# (so nobody could tell WHICH limit bound), and converted any failure
# to None. The helpers below are the fixes 0-2 client half:
#
# * every non-200 response is logged with its status, truncated body
#   and the x-ratelimit-* / retry-after headers before it fails;
# * HTTP 429 — and only 429 — is retried, honouring Retry-After with
#   a 30/60/120s fallback ladder and a bounded total wait;
# * each logical call records an outcome (see last_vision_outcome)
#   so the viral loop can pace calls, budget the day's estimated
#   token spend, and stop cleanly when the day is drained.
# --------------------------------------------------------------------------- #

# Fallback waits before retries 1/2/3 when the provider sends no
# Retry-After. Their sum (210s) stays under the default total cap.
_RETRY_FALLBACK_WAITS = (30.0, 60.0, 120.0)

# The headers that name WHICH limit bound; logged on every failure.
_RATE_LIMIT_HEADERS = (
    "x-ratelimit-limit-tokens",
    "x-ratelimit-remaining-tokens",
    "x-ratelimit-reset-tokens",
    "x-ratelimit-limit-requests",
    "x-ratelimit-remaining-requests",
    "retry-after",
)

# Token estimator constants. The provider charges admission as
# prompt + max_tokens and accounts images per tile; exact accounting
# is the provider's, so the budget only needs a stable, slightly
# conservative estimate: JSON-dense prompts tokenise at roughly
# 3 chars/token (prose is ~4), and one 512px JPEG frame lands in the
# same few-hundred-to-~1k range across providers — 1,000 flat keeps
# the estimate at the top of the diagnosed 3,000-5,500/call range.
_TEXT_CHARS_PER_TOKEN = 3
_IMAGE_TOKEN_ESTIMATE = 1000

# Outcome of the most recent logical vision call, and the monotonic
# timestamp of the most recent HTTP request (pacing). Module-level
# because the call sites are plain functions; the viral loop reads
# the outcome after each production attempt.
_VISION_OUTCOME: dict[str, Any] = {
    "seq": 0,
    "status": None,
    "rate_limit_exhausted": False,
    "attempts": 0,
    "estimated_tokens": 0,
    "called_at": None,
}
_LAST_VISION_REQUEST_MONO: float | None = None


def estimate_vision_tokens(body: dict[str, Any]) -> int:
    """Estimated provider tokens for one vision request.

    estimate = text chars / 3 + 1,000 per image + max_tokens.
    Deterministic and dependency-free by design — it feeds the
    loop's daily budget bookkeeping, never a billing decision.
    """
    text_chars = 0
    images = 0
    for message in body.get("messages") or []:
        if not isinstance(message, dict):
            continue
        content = message.get("content")
        if isinstance(content, str):
            text_chars += len(content)
        elif isinstance(content, list):
            for part in content:
                if not isinstance(part, dict):
                    continue
                if part.get("type") == "text":
                    text_chars += len(str(part.get("text") or ""))
                elif part.get("type") == "image_url":
                    images += 1
    return (
        math.ceil(text_chars / _TEXT_CHARS_PER_TOKEN)
        + images * _IMAGE_TOKEN_ESTIMATE
        + int(body.get("max_tokens") or 0)
    )


def _retry_after_seconds(response: httpx.Response) -> float | None:
    """Parse a Retry-After header (seconds or HTTP-date), or None."""
    raw = str(response.headers.get("retry-after") or "").strip()
    if not raw:
        return None
    try:
        return max(0.0, float(raw))
    except ValueError:
        pass
    try:
        moment = parsedate_to_datetime(raw)
    except (TypeError, ValueError):
        return None
    if moment is None:
        return None
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    return max(0.0, (moment - datetime.now(timezone.utc)).total_seconds())


def _log_vision_failure(context: str, response: httpx.Response) -> None:
    """Fix 0: make every vision failure say WHICH limit bound."""
    headers = {
        name: response.headers.get(name)
        for name in _RATE_LIMIT_HEADERS
        if response.headers.get(name) is not None
    }
    try:
        body_text = response.text[:300]
    except Exception:  # noqa: BLE001 - logging must never raise
        body_text = "<unreadable>"
    log.warning(
        "Vision request failed (%s): HTTP %s rate-limit headers=%s body=%s",
        context, response.status_code, headers, body_text,
    )


def _record_vision_outcome(
    *, status: int | None, attempts: int, estimated_tokens: int,
    called_at: float | None, rate_limit_exhausted: bool,
) -> None:
    global _VISION_OUTCOME
    _VISION_OUTCOME = {
        "seq": int(_VISION_OUTCOME.get("seq") or 0) + 1,
        "status": status,
        "rate_limit_exhausted": rate_limit_exhausted,
        "attempts": attempts,
        "estimated_tokens": estimated_tokens,
        "called_at": called_at,
    }


def vision_call_seq() -> int:
    """Sequence number of the most recent logical vision call."""
    return int(_VISION_OUTCOME.get("seq") or 0)


def last_vision_outcome() -> dict[str, Any]:
    """Outcome of the most recent logical vision call (a copy).

    ``rate_limit_exhausted`` is True only when the call's final
    response was HTTP 429 after the bounded retries — the signal the
    viral loop's clean-stop counts. ``estimated_tokens`` charges the
    per-request estimate once per HTTP attempt, retries included.
    """
    return dict(_VISION_OUTCOME)


def seed_vision_clock(epoch: float | None) -> None:
    """Seed the pacing clock from a persisted last-call epoch.

    Supervised cycles run as separate processes; the loop persists
    the last call's epoch and seeds it back here so the minimum
    interval is honoured across process boundaries too.
    """
    global _LAST_VISION_REQUEST_MONO
    if not epoch:
        return
    age = max(0.0, time.time() - float(epoch))
    _LAST_VISION_REQUEST_MONO = time.monotonic() - age


def wait_for_vision_pacing(min_interval_seconds: float) -> float:
    """Sleep until the last vision request is >= the interval old.

    Returns the seconds waited (0.0 when no wait was needed — first
    call ever, or the interval already elapsed).
    """
    if _LAST_VISION_REQUEST_MONO is None or min_interval_seconds <= 0:
        return 0.0
    remaining = (_LAST_VISION_REQUEST_MONO + float(min_interval_seconds)) - time.monotonic()
    if remaining <= 0:
        return 0.0
    time.sleep(remaining)
    return remaining


def _vision_request(body: dict[str, Any], *, context: str) -> httpx.Response:
    """POST one vision chat-completion with bounded 429 retry.

    Returns the final response — callers keep their existing
    raise_for_status flow, so non-429 failures behave exactly as
    before. Transport errors propagate (and are recorded). Only
    HTTP 429 is retried: up to ``vision_max_retries`` retries,
    waiting Retry-After when present (the fallback ladder
    otherwise), with the total wait capped at
    ``vision_retry_wait_cap_seconds`` per logical call.
    """
    global _LAST_VISION_REQUEST_MONO
    settings = get_settings()
    key = str(getattr(settings, "vision_api_key", "") or "").strip()
    url = settings.vision_base_url.rstrip("/") + "/chat/completions"
    headers = {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "User-Agent": "VyralX/1.0",
    }
    timeout = float(getattr(settings, "vision_timeout_seconds", 90))
    max_retries = max(0, int(getattr(settings, "vision_max_retries", 3)))
    wait_cap = max(0.0, float(getattr(settings, "vision_retry_wait_cap_seconds", 240)))
    estimated = estimate_vision_tokens(body)
    attempts = 0
    waited = 0.0
    while True:
        attempts += 1
        _LAST_VISION_REQUEST_MONO = time.monotonic()
        called_at = time.time()
        try:
            response = httpx.post(url, headers=headers, json=body, timeout=timeout)
        except Exception:
            _record_vision_outcome(
                status=None, attempts=attempts,
                estimated_tokens=estimated * attempts,
                called_at=called_at, rate_limit_exhausted=False,
            )
            raise
        if response.status_code == 200:
            _record_vision_outcome(
                status=200, attempts=attempts,
                estimated_tokens=estimated * attempts,
                called_at=called_at, rate_limit_exhausted=False,
            )
            return response
        _log_vision_failure(context, response)
        exhausted = response.status_code == 429 and attempts > max_retries
        if response.status_code != 429 or exhausted:
            _record_vision_outcome(
                status=response.status_code, attempts=attempts,
                estimated_tokens=estimated * attempts,
                called_at=called_at,
                rate_limit_exhausted=response.status_code == 429,
            )
            return response
        wait = _retry_after_seconds(response)
        if wait is None:
            wait = _RETRY_FALLBACK_WAITS[min(attempts - 1, len(_RETRY_FALLBACK_WAITS) - 1)]
        if waited + wait > wait_cap:
            log.warning(
                "Vision %s: 429 retry wait %.0fs would exceed the %.0fs "
                "per-call cap (already waited %.0fs); giving up",
                context, wait, wait_cap, waited,
            )
            _record_vision_outcome(
                status=429, attempts=attempts,
                estimated_tokens=estimated * attempts,
                called_at=called_at, rate_limit_exhausted=True,
            )
            return response
        log.info(
            "Vision %s rate-limited (429); retry %d/%d in %.0fs",
            context, attempts, max_retries, wait,
        )
        time.sleep(wait)
        waited += wait


def describe_scene(source_path: Path | str, duration: float) -> str:
    """Return a grounded description of the clip, or "" when vision is unavailable."""
    settings = get_settings()
    key = str(getattr(settings, "vision_api_key", "") or "").strip()
    if not key:
        return ""

    source = Path(source_path)
    if not source.is_file():
        return ""
    length = float(duration or 0.0)
    if length <= 0:
        return ""

    with tempfile.TemporaryDirectory(prefix="vyralx_frames_") as tmp:
        frames: list[Path] = []
        for index, position in enumerate(_FRAME_POSITIONS):
            destination = Path(tmp) / f"frame_{index}.jpg"
            if _extract_frame(source, length * position, destination):
                frames.append(destination)
        if not frames:
            return ""

        content: list[dict] = [{"type": "text", "text": _PROMPT}]
        for frame in frames:
            content.append({"type": "image_url", "image_url": {"url": _data_url(frame)}})

        body = {
            "model": settings.vision_model,
            "messages": [{"role": "user", "content": content}],
            "temperature": 0.2,
            "max_tokens": 300,
        }
        try:
            response = _vision_request(body, context="describe_scene")
            response.raise_for_status()
            payload = response.json()
            text = str(payload["choices"][0]["message"]["content"] or "").strip()
        except Exception as exc:  # noqa: BLE001 - vision must never block an upload
            log.warning("Scene analysis unavailable (%s: %s)", type(exc).__name__, str(exc)[:160])
            return ""

    text = "\n".join(line.strip() for line in text.splitlines() if line.strip())
    if text:
        log.info("Scene analysis: %s", text.replace("\\n", " | "))
    return text


# --------------------------------------------------------------------------- #
# structured vision record (TASK-VYR-014)
#
# The free-text pass above cannot be checked: a checker cannot verify
# "pink-haired" against a prose paragraph reliably, and when the pass failed
# the pipeline invented copy from the source title. The record below is the
# single source of truth the editorial writes from and the quality gates
# verify against. Race/skin identity is deliberately never recorded — hair
# and clothing are the visible, checkable attributes.
# --------------------------------------------------------------------------- #

# One frame per beat, at the beat anchors (15% / 50% / 85% of the clip —
# the same anchors the scene-timed renderer narrates against). The vision
# provider's hard cap is 3 images per request (proven on the production
# host 2026-11-17: a six-frame request is rejected with HTTP 400 "Too many
# images provided. This model supports up to 3 images"), so the record
# pass sends exactly three. The event-arc measurement in viral_quality
# samples ten frames independently, so motion evidence does not depend on
# this pass.
_RECORD_POSITIONS = ((0.15,), (0.50,), (0.85,))

_RECORD_PROMPT = (
    "These three frames are sampled from one short vertical clip, in "
    "order. Frame 1 is the START beat, frame 2 the MIDDLE beat, frame 3 "
    "the END beat. Describe ONLY what is visible - never guess a joke, a "
    "line of dialogue, a motive, or any detail that is not in the frames. "
    "Never describe a person's race, ethnicity or skin colour; describe "
    "their hair and clothing instead. Reply with ONE JSON object and "
    "nothing else, in exactly this shape:\n"
    '{"beats": [{"setting": "where this beat happens, a few words", '
    '"time_of_day": "day|night|indoor|unknown", '
    '"subjects": [{"hair": "hair colour and style, or unknown", '
    '"clothing": "clothing with colours, or unknown", '
    '"posture": "sitting|standing|lying|kneeling|crouching|leaning|unknown", '
    '"action": "what the subject is doing, a few words", '
    '"emotion": "visible emotion, or unknown", '
    '"eyes": "open|closed|unknown"}], '
    '"objects": ["visible object", "..."], '
    '"captions_present": false, '
    '"summary": "one short present-tense sentence: what happens in this beat"}], '
    '"event_arc": "one sentence: what changes from the start beat to the end beat", '
    '"static": false, '
    '"watermark_text": "a watermark, username (for example @name) or channel '
    'name stamped onto the footage by the clip\'s creator as an overlay, '
    'copied exactly as it appears, or an empty string when there is none. '
    'Text that is part of the scene being filmed (a TV broadcast shown in '
    'the clip, signs, screens, printed words) is NOT a watermark", '
    '"caption_overlap": false}\n'
    "Exactly three beats. Set \"static\" to true only if essentially nothing "
    "changes across all three frames. Set a field to \"unknown\" whenever the "
    "frames do not show it clearly - an honest unknown is far better than a "
    "guess, because every word of the narration will be checked against "
    "this record. Set \"caption_overlap\" to true when in any frame two or "
    "more burned-in text overlays or captions overlap each other so that "
    "any line cannot be read. Set a beat's \"captions_present\" to true "
    "when that beat's frame carries burned-in caption or subtitle text "
    "that transcribes spoken words - typically a word-by-word caption "
    "line in the lower or middle third that changes as people speak. "
    "Text that is part of the scene being filmed (signs, jerseys, score "
    "bugs, screens, printed words) is NOT captions, and neither is a "
    "one-off title or name card that does not transcribe speech."
)

_TIME_VALUES = {"day", "night", "indoor", "unknown"}
_EYES_VALUES = {"open", "closed", "unknown"}


def _balanced_json_object(text: str) -> dict[str, Any] | None:
    """First balanced {...} object in a possibly noisy model reply."""
    depth = 0
    start = -1
    in_string = False
    escaped = False
    for index, char in enumerate(text):
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
        elif char == "{":
            if depth == 0:
                start = index
            depth += 1
        elif char == "}" and depth:
            depth -= 1
            if depth == 0 and start >= 0:
                try:
                    parsed = json.loads(text[start:index + 1], strict=False)
                except json.JSONDecodeError:
                    return None
                return parsed if isinstance(parsed, dict) else None
    return None


def _clean_field(value: Any, limit: int = 200) -> str:
    return " ".join(str(value or "").split())[:limit]


def _coerce_record(payload: Any) -> dict[str, Any] | None:
    """Validate/coerce a vision reply into the record schema, or None."""
    if not isinstance(payload, dict):
        return None
    raw_beats = payload.get("beats")
    if not isinstance(raw_beats, list) or not raw_beats:
        return None
    beats: list[dict[str, Any]] = []
    for raw in raw_beats[:3]:
        if not isinstance(raw, dict):
            return None
        time_value = _clean_field(raw.get("time_of_day"), 20).lower()
        if time_value not in _TIME_VALUES:
            time_value = "unknown"
        subjects: list[dict[str, str]] = []
        for raw_subject in raw.get("subjects") or []:
            if not isinstance(raw_subject, dict):
                continue
            eyes = _clean_field(raw_subject.get("eyes"), 20).lower()
            if eyes not in _EYES_VALUES:
                eyes = "unknown"
            subjects.append({
                "hair": _clean_field(raw_subject.get("hair"), 120),
                "clothing": _clean_field(raw_subject.get("clothing"), 160),
                "posture": _clean_field(raw_subject.get("posture"), 60),
                "action": _clean_field(raw_subject.get("action"), 160),
                "emotion": _clean_field(raw_subject.get("emotion"), 60),
                "eyes": eyes,
            })
        summary = _clean_field(raw.get("summary"), 300)
        if not summary:
            return None
        beats.append({
            "setting": _clean_field(raw.get("setting"), 120),
            "time_of_day": time_value,
            "subjects": subjects,
            "objects": [_clean_field(item, 80) for item in (raw.get("objects") or [])][:8],
            "captions_present": bool(raw.get("captions_present")),
            "summary": summary,
        })
    while len(beats) < 3:
        beats.append(dict(beats[-1]))
    caption_beats = sum(1 for beat in beats if beat["captions_present"])
    return {
        "beats": beats,
        "event_arc": _clean_field(payload.get("event_arc"), 300),
        "static": bool(payload.get("static")),
        # Visible-text defects (TASK-VYR-024): the record is the only
        # pre-render look at the source's pixels, so it is where a
        # creator watermark or an unreadable burned-in caption pile-up
        # must be reported — after the render, both are baked in.
        # Replies that omit the fields (older prompts) coerce to the
        # clean defaults. The caption-track fields (TASK-VYR-025)
        # default the same way: no per-beat flags, no track.
        "watermark_text": _clean_field(payload.get("watermark_text"), 80),
        "caption_overlap": bool(payload.get("caption_overlap")),
        # Already-captioned sources (TASK-VYR-025): the per-beat
        # captions_present flags collapse to one record-level verdict —
        # a full burned-in caption track is present in a strict majority
        # of the sampled beats. A single flagged beat (a transient
        # title or one captioned moment) is not a track.
        "caption_beats": caption_beats,
        "source_caption_track": source_caption_track(caption_beats, len(beats)),
    }


def source_caption_track(caption_beats: int, total_beats: int) -> bool:
    """Majority rule for the already-captioned verdict (TASK-VYR-025).

    The vision pass samples three beats; a source counts as carrying a
    full burned-in caption track only when captions transcribing speech
    appear in a strict majority of them (2 of 3). Anything weaker — one
    beat with a title card, one captioned moment — must not condemn the
    candidate, because the skip is final for that cycle.
    """
    return total_beats > 0 and caption_beats * 2 > total_beats


def record_visual_defects(record: dict[str, Any] | None) -> list[str]:
    """Visible-text defect kinds a scene record reports (TASK-VYR-024).

    Both kinds are defects of the SOURCE footage's pixels that no
    subtitle-track fix can repair after the fact:

    * ``watermark_visible`` — a third-party watermark, username or
      channel branding stamped on the footage (supervised cycle 5
      held a render carrying "@WARPATROL" centre-frame throughout;
      the record never reported it because the vision pass was never
      asked about on-screen text).
    * ``caption_overlap`` — two or more burned-in caption/text layers
      overlapping so a line is unreadable (cycle 5, job 822 ~12.8s:
      the source's own captions printed over each other; VyralX's
      framing captions were fine — the defect is in the pixels, not
      the cue track PR #1053 deduplicated).
    * ``source_captioned`` — the source already carries a full
      burned-in caption track (TASK-VYR-025; cycle 6, job 841: the
      mascot-race source's own word-by-word captions ran throughout,
      and the render added VyralX's caption track carrying the same
      narration out of sync — two tracks doubling for the whole
      video, the pattern the owner rejected in cycle-5 job 823).
      VyralX's subtitles are always on by the owner's rule, so an
      already-captioned source can only double them; there is no
      render-without-captions mode, so the candidate is skipped.

    Returns the kinds in a stable order; empty when the record is
    clean. A ``None`` record yields no defects — absence of ground
    truth is the caller's separate ``vision_unavailable`` case.
    """
    if not isinstance(record, dict):
        return []
    defects: list[str] = []
    if str(record.get("watermark_text") or "").strip():
        defects.append("watermark_visible")
    if bool(record.get("caption_overlap")):
        defects.append("caption_overlap")
    if bool(record.get("source_caption_track")):
        defects.append("source_captioned")
    return defects


def analyze_scene(source_path: Path | str, duration: float) -> dict[str, Any] | None:
    """Return the structured vision record for a clip, or None.

    None means *no ground truth* — missing key, unreachable model, or an
    unusable reply. The caller must treat None as "do not write copy about
    this clip", never as "write generic copy instead".
    """
    settings = get_settings()
    key = str(getattr(settings, "vision_api_key", "") or "").strip()
    if not key:
        log.warning("Scene record unavailable: no vision API key configured")
        return None
    source = Path(source_path)
    length = float(duration or 0.0)
    if not source.is_file() or length <= 0:
        return None

    with tempfile.TemporaryDirectory(prefix="vyralx_record_") as tmp:
        frames: list[tuple[int, Path]] = []
        for beat_index, positions in enumerate(_RECORD_POSITIONS):
            for frame_index, position in enumerate(positions):
                destination = Path(tmp) / f"beat{beat_index}_{frame_index}.jpg"
                if _extract_frame(source, length * position, destination):
                    frames.append((beat_index, destination))
        if len(frames) < 3:
            log.warning("Scene record unavailable: only %d frames extracted", len(frames))
            return None

        content: list[dict] = [{"type": "text", "text": _RECORD_PROMPT}]
        labels = ("START", "MIDDLE", "END")
        for beat_index, frame_path in frames:
            content.append({"type": "text", "text": f"{labels[beat_index]} beat frame:"})
            content.append({"type": "image_url", "image_url": {"url": _data_url(frame_path)}})

        body = {
            "model": settings.vision_model,
            "messages": [{"role": "user", "content": content}],
            "temperature": 0.1,
            "max_tokens": 1100,
        }
        try:
            response = _vision_request(body, context="analyze_scene")
            response.raise_for_status()
            payload = response.json()
            text = str(payload["choices"][0]["message"]["content"] or "").strip()
        except Exception as exc:  # noqa: BLE001 - None is the designed failure value
            log.warning("Scene record unavailable (%s: %s)", type(exc).__name__, str(exc)[:160])
            return None

    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        parsed = _balanced_json_object(text)
    record = _coerce_record(parsed)
    if record is None:
        log.warning("Scene record reply was not usable JSON: %s", text[:200])
    else:
        log.info("Scene record: %s", " | ".join(b["summary"] for b in record["beats"]))
    return record


def scene_text(record: dict[str, Any]) -> str:
    """Render the record as the numbered beat lines the editorial expects."""
    lines = []
    for index, beat in enumerate(record.get("beats") or [], start=1):
        if isinstance(beat, dict) and beat.get("summary"):
            lines.append(f"{index}) {beat['summary']}")
    return "\n".join(lines)
