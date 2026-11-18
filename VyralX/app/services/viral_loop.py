"""The autonomous find -> edit -> produce loop (TASK-VYR-019).

One cycle of the loop the owner ordered on 2026-11-18:

1. **Find** — an all-category trending sweep
   (:mod:`app.services.viral_trending`) merged with the existing
   discovery lanes, deduplicated against everything already used,
   rejected or produced. Breadth is the point: the gated renders kept
   starving on a stale 12-candidate pool from the lanes alone.
2. **Route by the owner's audio rule** — each candidate is auditioned
   once (the same speech detector production uses):
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
from app.services import viral_bgm, viral_framing, viral_remix as vr
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
        "longform": None,
    }

    def skip(reason: str) -> None:
        summary["skips"][reason] = summary["skips"].get(reason, 0) + 1

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
        speech = vr.detect_speech(audio_path)
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
            skip("render_failed")
            continue
        if result.get("status") in {"QUEUED_FOR_PUBLISH", "RENDERED"}:
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
            skip(str(result.get("reason") or "unknown"))

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
