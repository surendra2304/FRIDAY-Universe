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
#
# TASK-VYR-028 (fix 4): when the primary call exhausts its retries on
# HTTP 429, _vision_request makes exactly one attempt against the
# fail-over endpoint configured by the VISION_FAILOVER_* env seams
# (see _attempt_vision_failover) instead of returning the 429 — the
# cycle-8 TPD wall (Used ~198k of 200k) and the OTPM sizing fault
# (max_tokens 1100 vs the 1000 limit) are both primary-only limits,
# and the fail-over keeps the same request shape, the same record
# validation, and the same outcome accounting.
#
# TASK-VYR-029: the fail-over exposed a budget-accounting defect —
# the VYR-026 daily token budget counted estimated tokens per
# attempt regardless of provider, so cycle 9 stopped at 195,560
# estimated tokens after 10 attempts even though 7 of them spent
# their tokens on Gemini, which never touches Groq's TPD. The
# outcome now charges tokens per provider (see _VISION_OUTCOME /
# _record_vision_outcome) and the viral loop gates each provider
# against its own daily budget.
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
#
# TASK-VYR-029: the token charge is split per provider —
# ``estimated_tokens_groq`` for primary (Groq) HTTP attempts and
# ``estimated_tokens_gemini`` for the single fail-over attempt, so
# the loop's daily budget can gate each provider against its own
# limit. ``estimated_tokens`` stays the total (both providers) for
# backward compatibility with the VYR-026 loop accounting.
_VISION_OUTCOME: dict[str, Any] = {
    "seq": 0,
    "status": None,
    "rate_limit_exhausted": False,
    "attempts": 0,
    "estimated_tokens": 0,
    "estimated_tokens_groq": 0,
    "estimated_tokens_gemini": 0,
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
    estimated_tokens_groq: int | None = None,
    estimated_tokens_gemini: int | None = None,
) -> None:
    """Record one logical call's outcome (see last_vision_outcome).

    ``estimated_tokens_groq`` / ``estimated_tokens_gemini`` are the
    per-provider charges (TASK-VYR-029); when omitted they default
    to (total, 0) — the pre-VYR-029 shape, in which every attempt
    was a primary call. Call sites that fail over pass both
    explicitly: the primary attempts charge Groq, the single
    fail-over attempt charges Gemini.
    """
    global _VISION_OUTCOME
    _VISION_OUTCOME = {
        "seq": int(_VISION_OUTCOME.get("seq") or 0) + 1,
        "status": status,
        "rate_limit_exhausted": rate_limit_exhausted,
        "attempts": attempts,
        "estimated_tokens": estimated_tokens,
        "estimated_tokens_groq": (
            estimated_tokens if estimated_tokens_groq is None
            else estimated_tokens_groq
        ),
        "estimated_tokens_gemini": (
            0 if estimated_tokens_gemini is None else estimated_tokens_gemini
        ),
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
    per-request estimate once per HTTP attempt, retries included;
    ``estimated_tokens_groq`` / ``estimated_tokens_gemini`` split
    that total by provider (TASK-VYR-029): primary attempts charge
    Groq, the single fail-over attempt charges Gemini, so the loop
    can budget each provider against its own daily limit.
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

    TASK-VYR-028: once the retries are spent on HTTP 429 (either the
    retry count or the wait cap gives up), exactly one attempt is
    made against the configured fail-over endpoint
    (see _attempt_vision_failover) and ITS response is returned
    instead — the callers' raise_for_status / parse flow then applies
    to the fail-over reply unchanged. No fail-over is attempted when
    the primary succeeds, fails non-429, or is unconfigured.
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
                estimated_tokens_groq=estimated * attempts,
                estimated_tokens_gemini=0,
                called_at=called_at, rate_limit_exhausted=False,
            )
            raise
        if response.status_code == 200:
            _record_vision_outcome(
                status=200, attempts=attempts,
                estimated_tokens=estimated * attempts,
                estimated_tokens_groq=estimated * attempts,
                estimated_tokens_gemini=0,
                called_at=called_at, rate_limit_exhausted=False,
            )
            return response
        _log_vision_failure(context, response)
        exhausted = response.status_code == 429 and attempts > max_retries
        if response.status_code != 429 or exhausted:
            # Fail-over is 429-only: a non-429 failure returns as-is.
            if response.status_code == 429:
                failover_response = _attempt_vision_failover(
                    body, context=context, attempts=attempts, estimated=estimated,
                )
                if failover_response is not None:
                    return failover_response
            _record_vision_outcome(
                status=response.status_code, attempts=attempts,
                estimated_tokens=estimated * attempts,
                estimated_tokens_groq=estimated * attempts,
                estimated_tokens_gemini=0,
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
            failover_response = _attempt_vision_failover(
                body, context=context, attempts=attempts, estimated=estimated,
            )
            if failover_response is not None:
                return failover_response
            _record_vision_outcome(
                status=429, attempts=attempts,
                estimated_tokens=estimated * attempts,
                estimated_tokens_groq=estimated * attempts,
                estimated_tokens_gemini=0,
                called_at=called_at, rate_limit_exhausted=True,
            )
            return response
        log.info(
            "Vision %s rate-limited (429); retry %d/%d in %.0fs",
            context, attempts, max_retries, wait,
        )
        time.sleep(wait)
        waited += wait


def _vision_failover_settings(settings: Any) -> dict[str, str] | None:
    """Fail-over endpoint config (TASK-VYR-028), or None when disabled.

    Disabled unless BOTH a base URL and a key are configured; the
    model defaults to gemini-3.5-flash-lite. All three come from the
    VISION_FAILOVER_* env seams (VyralX/app/config.py); the key is
    deployment env only and is never logged. ``getattr`` defaults
    keep older settings objects (and the VYR-026 test fixture, which
    has no fail-over attributes) working with fail-over disabled.
    """
    base_url = str(getattr(settings, "vision_failover_base_url", "") or "").strip()
    key = str(getattr(settings, "vision_failover_api_key", "") or "").strip()
    if not base_url or not key:
        return None
    model = str(getattr(settings, "vision_failover_model", "") or "").strip()
    return {
        "base_url": base_url.rstrip("/"),
        "key": key,
        "model": model or "gemini-3.5-flash-lite",
    }


def _attempt_vision_failover(
    body: dict[str, Any], *, context: str, attempts: int, estimated: int,
) -> httpx.Response | None:
    """Exactly one fail-over attempt after primary 429 exhaustion.

    Returns the fail-over response (any status — the caller's
    existing raise_for_status / parse flow applies to it unchanged),
    or None when no fail-over is configured. Only ever called after
    the primary's VYR-026 retries are spent, on HTTP 429, and only
    once per logical call: the fail-over is never itself retried.
    The request is the primary's body with only the model swapped,
    so a Gemini reply is parsed and validated exactly like a Groq
    one; the outcome recorded here is what the viral loop budgets
    and counts — a 200 resets the loop's consecutive-exhaustion
    streak exactly like a primary 200, a 429 keeps it exhausted.
    No key material is logged: only the endpoint base URL (which
    carries no secret) names where the attempt went.
    """
    global _LAST_VISION_REQUEST_MONO
    settings = get_settings()
    failover = _vision_failover_settings(settings)
    if failover is None:
        return None
    failover_body = dict(body)
    failover_body["model"] = failover["model"]
    url = failover["base_url"] + "/chat/completions"
    headers = {
        "Authorization": f"Bearer {failover['key']}",
        "Content-Type": "application/json",
        "User-Agent": "VyralX/1.0",
    }
    timeout = float(getattr(settings, "vision_timeout_seconds", 90))
    log.info(
        "Vision %s: primary exhausted (429); trying fail-over endpoint %s",
        context, failover["base_url"],
    )
    _LAST_VISION_REQUEST_MONO = time.monotonic()
    called_at = time.time()
    try:
        response = httpx.post(url, headers=headers, json=failover_body, timeout=timeout)
    except Exception:
        _record_vision_outcome(
            status=None, attempts=attempts + 1,
            estimated_tokens=estimated * (attempts + 1),
            # TASK-VYR-029: the fail-over POST was attempted, so its
            # estimate charges Gemini even though the transport failed
            # (conservative, matching the old total accounting); the
            # primary attempts already made charge Groq.
            estimated_tokens_groq=estimated * attempts,
            estimated_tokens_gemini=estimated,
            called_at=called_at, rate_limit_exhausted=False,
        )
        raise
    if response.status_code != 200:
        _log_vision_failure(context + " (fail-over)", response)
    _record_vision_outcome(
        status=response.status_code, attempts=attempts + 1,
        estimated_tokens=estimated * (attempts + 1),
        estimated_tokens_groq=estimated * attempts,
        estimated_tokens_gemini=estimated,
        called_at=called_at,
        rate_limit_exhausted=response.status_code == 429,
    )
    return response


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
        # Already-captioned sources (TASK-VYR-025, sensitivity raised by
        # TASK-VYR-032): the per-beat captions_present flags collapse to
        # one record-level verdict — a burned-in caption track is present
        # when ANY sampled beat carries speech captions. Render 861
        # slipped past the old strict-majority rule because its track
        # was not visible in two of the three sampled stills.
        "caption_beats": caption_beats,
        "source_caption_track": source_caption_track(caption_beats, len(beats)),
    }


def source_caption_track(caption_beats: int, total_beats: int) -> bool:
    """Any-beat rule for the already-captioned verdict (TASK-VYR-032).

    The vision pass samples three beats; a source counts as carrying a
    burned-in caption track when captions transcribing speech appear in
    ANY of them. TASK-VYR-025 used a strict majority (2 of 3): render
    861 shipped doubled after that gate because its caption track was
    not visible in two of the three sampled stills — word-by-word
    captions flash per word and may be absent during pauses, so a
    majority of stills is the wrong test for a track that runs through
    the clip. Under the record prompt's contract a flagged beat means
    real speech captions (a one-off title or name card is explicitly
    NOT captions), so one flagged beat is evidence of a track, not
    noise. The cost is asymmetric: a false positive only skips one
    candidate from a large pool, while a false negative ships a doubled
    render the owner rejects. The skip stays final for that cycle.
    """
    return total_beats > 0 and caption_beats > 0


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


# --------------------------------------------------------------------------- #
# TASK-VYR-045: dense post-render caption sampling
# --------------------------------------------------------------------------- #
# The pre-render vision gate (TASK-VYR-032, any-beat) still misses
# word-by-word caption tracks: the track flashes per word and may be
# absent from all three sampled stills, which is exactly how render
# 861 shipped doubled. The post-render gate therefore samples the
# RENDERED file densely — at least every 0.5s — and asks the vision
# model what caption text is visible in each frame, with its vertical
# zone. The detections feed viral_quality.caption_track_gate: exactly
# one track passes; two or more (the 823/841/861 class) reject the
# render before it reaches the publish queue.
#
# Cost: the provider caps a request at 3 images and the loop budgets
# ~1,000 tokens per image, so a 20s render costs ~40 frames / ~14
# requests / ~45k tokens. That is the price of the check — a doubled
# render the owner rejects costs more. Batch requests are paced and
# _vision_request's bounded 429 retry still applies, so a starved day
# degrades to caption_gate_unmeasured instead of a crash.

_CAPTION_SAMPLE_INTERVAL = 0.5
_CAPTION_FRAMES_PER_REQUEST = 3
_CAPTION_MAX_FRAMES = 120
# 65s between batches: one 3-image request costs ~6.5k input tokens
# against the free tier's 7k tokens/min, so 10s pacing 429s on the
# second batch of every render (seen live, 2026-11-24). 65s matches
# the loop's own vision pacing and lets each request's tokens age out
# of the rolling minute before the next one lands.
_CAPTION_PACE_SECONDS = 65.0
_CAPTION_ZONE_Y = {"top": 0.15, "middle": 0.50, "bottom": 0.85}

_CAPTION_DETECTION_PROMPT = (
    "These frames are sampled from one rendered short vertical video, in order. "
    "For each frame, list every line of on-screen caption text that transcribes speech — "
    "words spoken in the video, shown as subtitles. Copy each line exactly as it appears. "
    "For each line give its vertical position: \"top\" (upper third), \"middle\" (middle third) "
    "or \"bottom\" (lower third). "
    "Text that is part of the scene being filmed (signs, jerseys, score bugs, screens, printed words) "
    "is NOT captions, and neither is a one-off title or name card that does not transcribe speech. "
    "A watermark, username or channel name stamped on the footage is NOT captions. "
    "Reply with ONE JSON object and nothing else, in exactly this shape:\n"
    '{"frames": [{"frame": 0, "captions": [{"text": "exact words", "zone": "bottom"}]}]}\n'
    "One entry per frame, in order, even when a frame has no captions (empty list). "
    "Never guess words that are not visible. "
    "Report each distinct caption ONCE per frame — do not repeat a word or "
    "phrase that is part of another line you already listed for the same "
    "frame. If one caption wraps onto two lines, report it as ONE line "
    "with the full text."
)


def _coerce_caption_detections(
    payload: dict[str, Any],
    frame_times: list[float],
    interval_seconds: float = _CAPTION_SAMPLE_INTERVAL,
) -> list[dict[str, Any]]:
    """Vision reply -> caption detections for the VYR-045 gate.

    ``payload`` is the parsed JSON object of one batched detection
    reply; ``frame_times`` is the list of sample times (seconds) in
    the same order as the reply's frames. Each caption becomes one
    detection ``{"y", "start", "end", "text"}`` whose window is the
    sample cell centred on the frame. Malformed lines are skipped;
    a frame the reply omits contributes nothing.
    """
    detections: list[dict[str, Any]] = []
    half = max(0.05, float(interval_seconds) / 2.0)
    for entry in payload.get("frames") or []:
        if not isinstance(entry, dict):
            continue
        index = entry.get("frame")
        if not isinstance(index, int) or index < 0 or index >= len(frame_times):
            continue
        at = float(frame_times[index])
        for line in entry.get("captions") or []:
            if not isinstance(line, dict):
                continue
            text = str(line.get("text") or "").strip()
            zone = str(line.get("zone") or "").strip().lower()
            if not text or zone not in _CAPTION_ZONE_Y:
                continue
            detections.append({
                "y": _CAPTION_ZONE_Y[zone],
                "start": max(0.0, at - half),
                "end": at + half,
                "text": text,
            })
    return detections


def _is_word_subsequence(short: str, long: str) -> bool:
    """True when ``short``'s words occur contiguously inside ``long``."""
    a = short.split()
    b = long.split()
    if not a or len(a) >= len(b):
        return False
    return any(b[i:i + len(a)] == a for i in range(len(b) - len(a) + 1))


def _prune_caption_detections(
    detections: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Drop duplicate reads of one visual line within a frame.

    The vision model sometimes reports one caption twice in a frame —
    once as its full text and once as a fragment of it in another
    zone (a wrapped line, or an emphasised first word read on its
    own). Within one frame, a line whose words are a contiguous
    subsequence of a longer line in the same frame is a duplicate
    read, not a second track, so it is dropped. Lines that merely
    share a word but differ otherwise are kept — a real doubled track
    (the 823/841/861 class) shows different wording in the same
    frame, and an out-of-sync second track differs in other frames
    anyway.
    """
    kept: list[dict[str, Any]] = []
    for det in detections:
        text = str(det["text"])
        centre = (float(det["start"]) + float(det["end"])) / 2.0
        duplicate = False
        for other in detections:
            if other is det:
                continue
            other_centre = (float(other["start"]) + float(other["end"])) / 2.0
            if abs(other_centre - centre) > 1e-6:
                continue
            if _is_word_subsequence(text, str(other["text"])):
                duplicate = True
                break
        if not duplicate:
            kept.append(det)
    return kept


def _segments_from_detections(
    detections: list[dict[str, Any]],
    interval_seconds: float,
) -> list[dict[str, Any]]:
    """Merge per-frame detections into caption segments per band.

    A caption line stays on screen ~1.6s, so the same text in one
    band across consecutive frames (allowing one missed frame) is one
    segment. Segments shorter than 1.0s are stray reads, not caption
    lines — the model splits or invents a fragment in a single frame
    (seen on the real Nov 21 render: "WE'RE GONNA FIND" / "OUT WHAT
    HAPPENS" in the middle band, each in exactly one frame, while the
    bottom line held steady) — and counting them would false-reject a
    good render. A real second track (823/841/861 class) is
    phrase-level, so its segments clear 1.0s. Dropping a short segment
    can only remove a track, never invent one; a render whose only
    track is sub-second captions then fails closed as unmeasured /
    no-caption-track-visible downstream.
    """
    by_band: dict[float, list[dict[str, Any]]] = {}
    for det in detections:
        by_band.setdefault(float(det["y"]), []).append(det)
    out: list[dict[str, Any]] = []
    gap = max(0.05, float(interval_seconds or _CAPTION_SAMPLE_INTERVAL))
    for y, dets in by_band.items():
        dets.sort(key=lambda d: (float(d["start"]), float(d["end"])))
        segment: dict[str, Any] | None = None
        for det in dets:
            start = float(det["start"])
            end = float(det["end"])
            text = str(det["text"])
            if (
                segment is not None
                and segment["text"] == text
                and start - float(segment["end"]) <= gap + 1e-6
            ):
                segment["end"] = max(float(segment["end"]), end)
                continue
            if segment is not None and float(segment["end"]) - float(
                segment["start"]
            ) >= 1.0:
                out.append(segment)
            segment = {"y": y, "start": start, "end": end, "text": text}
        if segment is not None and float(segment["end"]) - float(
            segment["start"]
        ) >= 1.0:
            out.append(segment)
    out.sort(key=lambda d: (float(d["start"]), float(d["y"])))
    return out


def sample_render_caption_detections(
    render_path: Path | str,
    duration: float,
    *,
    interval_seconds: float = _CAPTION_SAMPLE_INTERVAL,
    frames_per_request: int = _CAPTION_FRAMES_PER_REQUEST,
    pace_seconds: float = _CAPTION_PACE_SECONDS,
    max_frames: int = _CAPTION_MAX_FRAMES,
    extract_frame=None,
    vision_request=None,
) -> list[dict[str, Any]] | None:
    """Sample a rendered file densely and detect caption text per frame.

    Returns a list of detections (``{"y", "start", "end", "text"}``)
    for :func:`app.services.viral_quality.caption_track_gate`, or
    ``None`` when measurement itself failed — no vision key, a frame
    that would not extract, a vision call that failed, or an unusable
    reply. ``None`` is fail-closed: the caller must skip the render,
    never ship it unmeasured. A render with no captions at all returns
    ``[]`` (the gate then rejects it as ``no_caption_track_visible``).

    ``extract_frame`` and ``vision_request`` are seams for tests; they
    default to :func:`_extract_frame` and :func:`_vision_request`.
    """
    settings = get_settings()
    request = vision_request or _vision_request
    if vision_request is None:
        key = str(getattr(settings, "vision_api_key", "") or "").strip()
        if not key:
            log.warning("Caption sampling unavailable: no vision API key configured")
            return None
    source = Path(render_path)
    length = float(duration or 0.0)
    if not source.is_file() or length <= 0:
        return None
    interval = max(0.1, float(interval_seconds or _CAPTION_SAMPLE_INTERVAL))
    times: list[float] = []
    at = interval / 2.0
    while at < length and len(times) < int(max_frames or _CAPTION_MAX_FRAMES):
        times.append(round(at, 3))
        at += interval
    if not times:
        return None
    extract = extract_frame or _extract_frame
    detections: list[dict[str, Any]] = []
    with tempfile.TemporaryDirectory(prefix="vyralx_caption_") as tmp:
        frames: list[tuple[int, float, Path]] = []
        for index, sample_at in enumerate(times):
            dest = Path(tmp) / f"cap{index:03d}.jpg"
            if not extract(source, sample_at, dest):
                log.warning(
                    "Caption sampling failed: frame at %.2fs did not extract", sample_at
                )
                return None
            frames.append((index, sample_at, dest))
        per_request = max(1, int(frames_per_request or _CAPTION_FRAMES_PER_REQUEST))
        for start in range(0, len(frames), per_request):
            batch = frames[start:start + per_request]
            if start > 0 and pace_seconds:
                wait_for_vision_pacing(float(pace_seconds))
            content: list[dict[str, Any]] = [
                {"type": "text", "text": _CAPTION_DETECTION_PROMPT}
            ]
            for batch_index, (_frame_index, frame_at, dest) in enumerate(batch):
                content.append(
                    {"type": "text", "text": f"Frame {batch_index} (t={frame_at:.2f}s):"}
                )
                content.append(
                    {"type": "image_url", "image_url": {"url": _data_url(dest)}}
                )
            body = {
                "model": settings.vision_model,
                "messages": [{"role": "user", "content": content}],
                "temperature": 0.1,
                # 3 frames, several lines each, plus the model's own
                # framing: 800 truncated real replies mid-object.
                "max_tokens": 1500,
            }
            try:
                response = request(body, context="caption_detection")
                response.raise_for_status()
                payload = response.json()
                text = str(payload["choices"][0]["message"]["content"] or "").strip()
            except Exception as exc:  # noqa: BLE001 - None is the designed failure value
                log.warning(
                    "Caption sampling failed (%s: %s)", type(exc).__name__, str(exc)[:160]
                )
                return None
            # The model often wraps the JSON in a fenced code block
            # (```json ... ```), which json.loads rejects outright.
            stripped = text.strip()
            if stripped.startswith("```"):
                lines = stripped.splitlines()
                if lines and lines[0].startswith("```"):
                    lines = lines[1:]
                if lines and lines[-1].strip() == "```":
                    lines = lines[:-1]
                stripped = "\n".join(lines).strip()
            try:
                parsed = json.loads(stripped)
            except json.JSONDecodeError:
                parsed = _balanced_json_object(stripped)
            if not isinstance(parsed, dict) or not isinstance(parsed.get("frames"), list):
                # The model sometimes drops the final closer(s) of an
                # otherwise complete object (seen live: a 3-frame reply
                # ending "...]}]" with the outer "}" missing). Try
                # appending the missing closers before giving up.
                for suffix in ("}", "]}", "}]}"):
                    try:
                        repaired = json.loads(stripped + suffix)
                    except json.JSONDecodeError:
                        continue
                    if isinstance(repaired, dict) and isinstance(
                        repaired.get("frames"), list
                    ):
                        parsed = repaired
                        break
            if not isinstance(parsed, dict) or not isinstance(parsed.get("frames"), list):
                log.warning(
                    "Caption sampling reply was not usable JSON (%d chars): %s",
                    len(text), text[:500],
                )
                return None
            batch_times = [frame_at for _, frame_at, _ in batch]
            detections.extend(
                _coerce_caption_detections(parsed, batch_times, interval)
            )
    return _segments_from_detections(
        _prune_caption_detections(detections), interval
    )


def scene_text(record: dict[str, Any]) -> str:
    """Render the record as the numbered beat lines the editorial expects."""
    lines = []
    for index, beat in enumerate(record.get("beats") or [], start=1):
        if isinstance(beat, dict) and beat.get("summary"):
            lines.append(f"{index}) {beat['summary']}")
    return "\n".join(lines)
