"""The autonomous find -> edit -> produce loop (TASK-VYR-019).

One cycle of the loop the owner ordered on 2026-11-18:

1. **Find** — an all-category trending sweep
   (:mod:`app.services.viral_trending`) merged with the existing
   discovery lanes, deduplicated against everything already used,
   rejected or produced. Breadth is the point: the gated renders kept
   starving on a stale 12-candidate pool from the lanes alone.
2. **Route by the owner's audio rule** — each candidate is auditioned
   with the same speech detector production uses, hardened at the
   routing layer (TASK-VYR-020): a single positive speech detection
   routes voiced, but the commentary route — her narration over the
   source, the dangerous direction — requires two differently-tuned
   detector passes to AGREE there is no speech. A disagreement is
   treated as voiced. (The single-call audition this replaces flipped
   12/12 candidates in gated render #2.)
   * voiced, with a transcript -> **framed** production
     (:mod:`app.services.viral_framing`): source voice kept, her
     hook/payoff frame it, source speech subtitled;
   * voiced, no transcript -> skipped (``no_transcript``): subtitles
     are mandatory and unsubtitlable speech is never shipped;
   * voiceless, short -> **commentary** production
     (:func:`app.services.viral_remix.produce_viral_short`): her full
     narration carries it;
   * voiceless, long -> skipped (``too_long_for_commentary``): short
     excerpts only.
3. **Hold everything** — every publish job is created
   ``pending_approval`` + unlisted (owner decision 4B: he reviews and
   publishes; the loop never uploads). A cycle that cannot guarantee
   the hold refuses to run at all (guards below).
4. **Record** — each produced short is filed under its series in the
   loop manifest and its publish job is tagged with the series slug;
   the cycle summary (including the BGM library state — tracks and
   phonk coverage) lands in ``viral_loop_state.json``.

Guards fail closed, in this order: ``LOOP_DISABLED`` (the loop is off
unless ``viral_loop_enabled`` — or ``force`` for a supervised run),
``BGM_REQUIRED`` (BGM is mandatory; a cycle never runs with beds
disabled), ``PRIVACY_NOT_UNLISTED`` (the loop only ever produces
review-held unlisted jobs), ``NO_COOKIES`` (downloads need the
operator's cookie file, same as the autopilot).

Every Nth cycle the long-form lane gets one compilation attempt when
``viral_loop_longform_enabled`` is on (owner decision B).

Vision rate limits (TASK-VYR-026): the scene-analysis call behind
both production paths rides a free-tier token budget (8k tokens/min,
200k/day) that cycles 6/7 exhausted — 14/24 and 22/24 attempts died
as ``vision_unavailable``. The loop now paces scene calls (minimum
interval, seeded across processes from the persisted state), tracks
the day's estimated vision-token spend in ``viral_loop_state.json``,
and stops the cycle cleanly — ``vision_daily_budget`` when the day's
budget is spent, ``vision_rate_limited`` after a run of consecutive
rate-limit-exhausted calls — instead of burning downloads against a
drained day. The client-side retry lives in
:mod:`app.services.scene_analysis`.
"""
from __future__ import annotations

import json
import logging
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import PublishJob, Source
from app.services import scene_analysis, viral_bgm, viral_framing, viral_remix as vr
from app.services.viral_discovery import Candidate, discover_candidates_api
from app.services.viral_longform import append_manifest, produce_compilation
from app.services.viral_series import SERIES_BY_LABEL, normalise_label
from app.services.viral_trending import trending_candidates

log = logging.getLogger("vyralx.viral_loop")


def manifest_path(settings: Any = None) -> Path:
    settings = settings or get_settings()
    return Path(settings.data_dir) / "viral_loop_manifest.jsonl"


def state_path(settings: Any = None) -> Path:
    settings = settings or get_settings()
    return Path(settings.data_dir) / "viral_loop_state.json"


def _used_source_ids(db: Session) -> set[str]:
    used: set[str] = set()
    for (url,) in db.query(Source.source_url).all():
        text = str(url or "")
        if "v=" in text:
            used.add(text.split("v=", 1)[1].split("&", 1)[0].strip())
        elif "watch?v=" in text:
            used.add(text.rsplit("watch?v=", 1)[1].strip())
    return {value for value in used if value}


def _rejected_ids(settings: Any) -> set[str]:
    path = Path(settings.data_dir) / "rejected_sources.json"
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return set()
    if isinstance(raw, dict):
        return {str(key) for key in raw.keys()}
    if isinstance(raw, list):
        return {
            str(item.get("video_id"))
            for item in raw
            if isinstance(item, dict) and item.get("video_id")
        }
    return set()


def _manifest_ids(path: Path) -> set[str]:
    ids: set[str] = set()
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return ids
    for line in lines:
        try:
            payload = json.loads(line)
        except ValueError:
            continue
        if isinstance(payload, dict) and payload.get("video_id"):
            ids.add(str(payload["video_id"]))
    return ids


def _load_state(path: Path) -> dict[str, Any]:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return raw if isinstance(raw, dict) else {}


def _tag_publish_job_series(db: Session, publish_job_id: int | None, label: str) -> None:
    """File the held job under its series (slug tag; owner files the playlist)."""
    if not publish_job_id:
        return
    job = db.get(PublishJob, publish_job_id)
    if job is None:
        return
    try:
        tags = json.loads(job.tags_json or "[]")
    except ValueError:
        tags = []
    if not isinstance(tags, list):
        tags = []
    slug = SERIES_BY_LABEL[label]["slug"]
    for tag in (slug, f"vyralx {slug}"):
        if tag not in tags:
            tags.append(tag)
    job.tags_json = json.dumps(tags[:30])
    db.commit()


# TASK-VYR-020: the confirmation pass for the commentary route. It is
# deliberately MORE speech-sensitive than the production pass (a wider
# beam and a lower VAD threshold keep and decode more borderline
# audio), so if any speech is really there it is the pass most likely
# to hear it.
_AUDITION_CONFIRM_KWARGS: dict[str, Any] = {"beam_size": 5, "vad_threshold": 0.25}


def _verdict(report: Any) -> dict[str, Any]:
    """Compact, loggable shape of one detector verdict."""
    return {
        "has_speech": bool(getattr(report, "has_speech", False)),
        "speech_seconds": round(float(getattr(report, "speech_seconds", 0.0) or 0.0), 2),
        "cues": len(getattr(report, "cues", ()) or ()),
    }


def _routing_audition(
    candidate: Candidate, audio_path: Path, *, commentary_cap: float
) -> tuple[Any, dict[str, Any]]:
    """Audition one candidate for routing (TASK-VYR-020).

    Pass 1 is the production detector at its production settings. A
    positive verdict routes voiced on its own — production re-auditions
    and fails closed, so one call is enough in that direction. A
    negative verdict is only trusted for the commentary route when a
    second, differently-tuned pass agrees there is no speech; on
    disagreement the candidate is treated as voiced and the second
    pass's report (with any transcript it found) drives routing. The
    second pass runs only for candidates that would otherwise take the
    commentary route (no speech heard, short enough) — long candidates
    skip either way, so confirming them would buy nothing.

    Returns ``(effective_report, audit)``; the audit records both
    verdicts and the agreement outcome, and is logged per candidate.
    """
    first = vr.detect_speech(audio_path)
    audit: dict[str, Any] = {
        "pass1": _verdict(first),
        "pass2": None,
        "agreement": "voiced_first_pass",
        "disagreement": False,
    }
    if first.has_speech:
        log.info(
            "Routing audition %s: pass1=%s -> voiced (single positive suffices)",
            candidate.video_id, audit["pass1"],
        )
        return first, audit
    if float(candidate.duration or 0) > commentary_cap:
        audit["agreement"] = "no_second_pass_too_long"
        log.info(
            "Routing audition %s: pass1=%s -> no confirmation pass "
            "(over the commentary cap; skips either way)",
            candidate.video_id, audit["pass1"],
        )
        return first, audit
    second = vr.detect_speech(audio_path, **_AUDITION_CONFIRM_KWARGS)
    audit["pass2"] = _verdict(second)
    if second.has_speech:
        audit["agreement"] = "disagreement_treated_voiced"
        audit["disagreement"] = True
        log.warning(
            "Routing audition %s DISAGREEMENT: pass1=%s pass2=%s -> "
            "treated as voiced (commentary requires two-pass agreement)",
            candidate.video_id, audit["pass1"], audit["pass2"],
        )
        return second, audit
    audit["agreement"] = "agree_no_speech"
    log.info(
        "Routing audition %s: pass1=%s pass2=%s -> agree no speech, "
        "commentary allowed",
        candidate.video_id, audit["pass1"], audit["pass2"],
    )
    return first, audit


def _guard(settings: Any, force: bool) -> str | None:
    if not force and not bool(getattr(settings, "viral_loop_enabled", False)):
        return "LOOP_DISABLED"
    if not bool(getattr(settings, "viral_music_bed_enabled", True)):
        return "BGM_REQUIRED"
    if str(getattr(settings, "autonomous_publish_privacy", "unlisted")) != "unlisted":
        return "PRIVACY_NOT_UNLISTED"
    cookies = str(
        getattr(settings, "youtube_cookies_file", "")
        or getattr(settings, "youtube_cookies_path", "")
        or ""
    )
    if not cookies or not Path(cookies).is_file():
        return "NO_COOKIES"
    return None


def run_viral_loop_cycle(db: Session, *, force: bool = False) -> dict[str, Any]:
    """Run one find -> edit -> produce cycle. See module docstring."""
    settings = get_settings()
    started = time.monotonic()
    guard = _guard(settings, force)
    if guard:
        log.warning("Viral loop cycle refused: %s", guard)
        return {"status": "GUARDED", "guard": guard}

    state_file = state_path(settings)
    manifest_file = manifest_path(settings)
    state = _load_state(state_file)
    cycle_no = int(state.get("cycles_completed") or 0) + 1

    max_source = float(getattr(settings, "viral_loop_max_source_seconds", 600.0))
    commentary_cap = float(getattr(settings, "viral_max_source_seconds", 58.0))
    max_attempts = int(getattr(settings, "viral_loop_max_attempts_per_cycle", 24))
    budget = float(getattr(settings, "viral_loop_cycle_budget_seconds", 5400))

    # TASK-VYR-026: the day's estimated vision-token spend lives in
    # the loop's persisted state so it survives across the separate
    # processes that run supervised cycles. The date is UTC — the
    # provider's daily limits are day-scoped, and UTC is the only
    # day boundary both sides agree on. The pacing clock is seeded
    # from the persisted last-call epoch for the same reason.
    vision_min_interval = float(
        getattr(settings, "viral_loop_vision_min_interval_seconds", 65.0)
    )
    vision_daily_budget = int(
        getattr(settings, "viral_loop_vision_daily_token_budget", 180000)
    )
    vision_stop_threshold = int(
        getattr(settings, "viral_loop_vision_rate_limit_stop_threshold", 3)
    )
    today = datetime.now(timezone.utc).date().isoformat()
    vision_budget_state = state.get("vision_budget")
    if not isinstance(vision_budget_state, dict) or vision_budget_state.get("date") != today:
        vision_budget_state = {"date": today, "estimated_tokens": 0, "last_call_at": None}
    state["vision_budget"] = vision_budget_state
    scene_analysis.seed_vision_clock(vision_budget_state.get("last_call_at"))
    consecutive_rate_limited = 0

    exclude = _used_source_ids(db) | _rejected_ids(settings) | _manifest_ids(manifest_file)
    pool: dict[str, Candidate] = {}
    for candidate in trending_candidates(
        per_category=int(getattr(settings, "viral_loop_trending_per_category", 10)),
        exclude_ids=exclude,
        max_seconds=max_source,
        region=str(getattr(settings, "viral_loop_region", "") or ""),
    ):
        pool[candidate.video_id] = candidate
    try:
        for candidate in discover_candidates_api(
            limit=24,
            exclude_ids=exclude,
            max_seconds=max_source,
        ):
            pool.setdefault(candidate.video_id, candidate)
    except Exception as exc:  # the lanes are best-effort; trending is the breadth
        log.info("Lane discovery unavailable this cycle (%s)", type(exc).__name__)
    ranked = sorted(pool.values(), key=lambda item: item.score, reverse=True)

    summary: dict[str, Any] = {
        "status": "COMPLETED",
        "cycle": cycle_no,
        "pool": len(ranked),
        "attempts": 0,
        "produced": 0,
        "held_publish_jobs": [],
        "by_series": {},
        "skips": {},
        "audition_second_passes": 0,
        "audition_disagreements": 0,
        "longform": None,
    }

    def skip(reason: str) -> None:
        summary["skips"][reason] = summary["skips"].get(reason, 0) + 1

    def _persist_vision_budget() -> None:
        state_file.parent.mkdir(parents=True, exist_ok=True)
        state_file.write_text(json.dumps(state, indent=2), encoding="utf-8")

    def _account_vision(seq_before: int) -> bool:
        """Fold one attempt's vision outcome into budget + streak.

        Returns True when the attempt's vision call died rate-limited
        after all retries. A call that succeeded — or failed for any
        other reason — resets the consecutive-exhaustion streak.
        Attempts that made no vision call leave both untouched.
        """
        nonlocal consecutive_rate_limited
        outcome = scene_analysis.last_vision_outcome()
        if int(outcome.get("seq") or 0) == seq_before:
            return False
        vision_budget_state["estimated_tokens"] = int(
            vision_budget_state.get("estimated_tokens") or 0
        ) + int(outcome.get("estimated_tokens") or 0)
        if outcome.get("called_at"):
            vision_budget_state["last_call_at"] = outcome["called_at"]
        _persist_vision_budget()
        if outcome.get("rate_limit_exhausted"):
            return True
        consecutive_rate_limited = 0
        return False

    audio_dir = settings.media_dir / "viral_audio_probe"
    for candidate in ranked:
        if summary["attempts"] >= max_attempts:
            summary["stopped"] = "attempt_budget"
            break
        if time.monotonic() - started > budget:
            summary["stopped"] = "time_budget"
            break
        label = normalise_label(str(getattr(candidate, "category", "") or "VIRAL"))
        if float(candidate.duration or 0) > max_source:
            skip("source_too_long")
            continue
        summary["attempts"] += 1
        audio_path = vr.download_audio_only(candidate.video_id, audio_dir)
        if audio_path is None:
            skip("audio_unavailable")
            continue
        speech, audition = _routing_audition(
            candidate, audio_path, commentary_cap=commentary_cap
        )
        if audition["pass2"] is not None:
            summary["audition_second_passes"] += 1
        if audition["disagreement"]:
            summary["audition_disagreements"] += 1
        # TASK-VYR-026: only the two production routes consume vision.
        # Candidates that skip without producing (no transcript, too
        # long for commentary) never touch the budget or the pacing
        # clock, so the gate sits exactly here — the last point before
        # a scene-analysis call can happen.
        vision_seq = scene_analysis.vision_call_seq()
        needs_vision = bool(speech.cues) if speech.has_speech else (
            float(candidate.duration or 0) <= commentary_cap
        )
        if needs_vision:
            if (
                vision_daily_budget > 0
                and int(vision_budget_state.get("estimated_tokens") or 0)
                >= vision_daily_budget
            ):
                summary["stopped"] = "vision_daily_budget"
                log.warning(
                    "Viral loop cycle %d stopped: vision daily budget spent "
                    "(%d >= %d estimated tokens)",
                    cycle_no,
                    int(vision_budget_state.get("estimated_tokens") or 0),
                    vision_daily_budget,
                )
                break
            waited = scene_analysis.wait_for_vision_pacing(vision_min_interval)
            if waited > 0:
                log.info(
                    "Vision pacing: waited %.1fs before %s",
                    waited, candidate.video_id,
                )
        try:
            if speech.has_speech:
                if not speech.cues:
                    skip("no_transcript")
                    continue
                result = viral_framing.produce_framed_short(
                    candidate, db, publish=True, hold_for_review=True
                )
            elif float(candidate.duration or 0) <= commentary_cap:
                result = vr.produce_viral_short(
                    candidate, db, publish=True, hold_for_review=True
                )
            else:
                skip("too_long_for_commentary")
                continue
        except Exception as exc:
            log.warning(
                "Production failed for %s (%s: %s)",
                candidate.video_id, type(exc).__name__, str(exc)[:200],
            )
            _account_vision(vision_seq)
            skip("render_failed")
            continue
        if result.get("status") in {"QUEUED_FOR_PUBLISH", "RENDERED"}:
            _account_vision(vision_seq)
            summary["produced"] += 1
            summary["by_series"][label] = summary["by_series"].get(label, 0) + 1
            if result.get("publish_job_id"):
                summary["held_publish_jobs"].append(result["publish_job_id"])
            _tag_publish_job_series(db, result.get("publish_job_id"), label)
            append_manifest(manifest_file, {
                "kind": "short",
                "cycle": cycle_no,
                "video_id": candidate.video_id,
                "series": label,
                "edit_mode": result.get("edit_mode", ""),
                "render": result.get("render", ""),
                "render_job_id": result.get("render_job_id"),
                "publish_job_id": result.get("publish_job_id"),
                "title": result.get("title", ""),
                "bgm_source": result.get("bgm_source", ""),
                "status": "HELD",
            })
        else:
            exhausted = _account_vision(vision_seq)
            reason = str(result.get("reason") or "unknown")
            if reason == "vision_unavailable" and exhausted:
                consecutive_rate_limited += 1
                if consecutive_rate_limited >= vision_stop_threshold:
                    # The day is drained: stop cleanly under the
                    # distinct reason instead of burning the remaining
                    # attempt budget on downloads that cannot pass the
                    # vision stage (cycle 7 lost 22 attempts this way).
                    skip("vision_rate_limited")
                    summary["stopped"] = "vision_rate_limited"
                    log.warning(
                        "Viral loop cycle %d stopped: %d consecutive "
                        "rate-limit-exhausted vision calls",
                        cycle_no, consecutive_rate_limited,
                    )
                    break
            skip(reason)

    summary["vision"] = {
        "estimated_tokens_today": int(vision_budget_state.get("estimated_tokens") or 0),
        "daily_budget": vision_daily_budget,
        "rate_limit_streak": consecutive_rate_limited,
    }

    if bool(getattr(settings, "viral_loop_longform_enabled", False)):
        every_n = int(getattr(settings, "viral_loop_longform_every_n_cycles", 6))
        if every_n > 0 and cycle_no % every_n == 0:
            try:
                summary["longform"] = produce_compilation(
                    db,
                    manifest_path=manifest_file,
                    min_clips=int(getattr(settings, "viral_loop_longform_min_clips", 3)),
                )
            except Exception as exc:
                log.warning("Long-form attempt failed (%s)", type(exc).__name__)
                summary["longform"] = {"status": "FAILED", "reason": "render_failed"}

    bgm_status = viral_bgm.library_status(settings)
    summary["bgm"] = bgm_status
    warnings: list[str] = []
    if bgm_status["policy"] == "growth" and bgm_status["tracks_available"] == 0:
        warnings.append(
            "bgm_library_empty: growth policy has no popular tracks provisioned; "
            "beds fell back to the synth bed (labelled on each render)"
        )
    if bgm_status["policy"] == "growth" and bgm_status["phonk_tracks"] == 0:
        warnings.append(
            "phonk_shelf_empty: no phonk tracks in the growth library; the owner's "
            "named phonk category is unstocked"
        )
    summary["warnings"] = warnings
    summary["elapsed_seconds"] = round(time.monotonic() - started, 1)

    state.update({
        "cycles_completed": cycle_no,
        "last_cycle_at": datetime.now(timezone.utc).isoformat(),
        "last_summary": summary,
    })
    state_file.parent.mkdir(parents=True, exist_ok=True)
    state_file.write_text(json.dumps(state, indent=2), encoding="utf-8")
    log.info("Viral loop cycle %d complete: %s", cycle_no, summary)
    return summary
