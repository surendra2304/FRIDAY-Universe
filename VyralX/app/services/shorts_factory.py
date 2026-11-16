"""VyralX Shorts factory (TASK-IG2-VYR-03).

Pattern adapted from YILS-LIN/short-video-factory (AGPL-3.0,
https://github.com/YILS-LIN/short-video-factory): prompt +
storyboard material in -> AI copy -> free EdgeTTS voice -> auto
mix/edit -> subtitled Short out, produced in *batches* that keep
filling a queue to a preset target. This is FRIDAY's own
implementation of that batch-factory pattern for VyralX; no
upstream code is vendored (pattern only — AGPL care noted on the
spec card).

What does NOT transfer (per the spec card): the upstream app is a
TypeScript/Electron desktop GUI — it cannot run inside VyralX's
~180MB service cap on the ~956MB fleet VMs. So the factory here is
the headless planning core of the pattern: it turns each request
into a complete, validated job spec (copy, EdgeTTS voice plan,
auto-mix segment plan, timed subtitle cues via VyralX's own
captions service) and manages the batch queue. Rendering a spec is
done by VyralX's existing renderer — by hand the factory renders
nothing, uploads nothing, publishes nothing.

Owner rules baked in: Shorts are <60s (a job whose narration
estimate reaches 60s is rejected, never silently trimmed); lanes
are space/science, history/did-you-know, tech/AI explainers; money
is stories never advice (copy is compliance-screened); TTS is
EdgeTTS only (free — the upstream app's one hard dependency choice
we keep); copy generation is a deterministic template here, with
the job spec marking where an OpenAI-compatible free-tier endpoint
may be swapped in by the caller; storyboard materials must carry
licence/provenance or the job is refused; anything eventually
published stays UNLISTED.
"""
from __future__ import annotations

from typing import Any, Iterable

from app.services import captions, compliance_gate

FACTORY_VERSION = "ig2-vyr03-1"

ALLOWED_LANES = ("space_science", "history", "tech_ai")

SHORTS_MAX_SECONDS = 59.0
_WORDS_PER_MINUTE = 150.0

#: Free EdgeTTS voices (upstream uses EdgeTTS; so does VyralX).
EDGE_VOICE = "en-US-AriaNeural"

_HOOK_TEMPLATES = (
    "Stop scrolling — {topic} will change how you see this.",
    "Nobody tells you this about {topic}.",
    "60 seconds on {topic} — watch to the end.",
)


class ShortsFactoryError(ValueError):
    """Raised when a factory job or batch violates a rule."""


def estimate_seconds(script: str) -> float:
    return round(len(str(script).split()) / _WORDS_PER_MINUTE * 60.0, 2)


def build_copy(topic: str, facts: Iterable[str], *, index: int = 0) -> dict[str, Any]:
    """Deterministic copy for one Short: hook + narration + title.

    ``facts`` are the caller's storyboard beats (already researched
    upstream); the factory writes the copy around them and screens
    the result — it never invents facts of its own.
    """
    facts = [str(f).strip() for f in facts if str(f).strip()]
    if not facts:
        raise ShortsFactoryError("a factory job needs at least one fact beat")
    hook = _HOOK_TEMPLATES[index % len(_HOOK_TEMPLATES)].format(topic=topic)
    narration = " ".join([hook, *facts])
    hits = compliance_gate.find_finance_advice(narration)
    if hits:
        raise ShortsFactoryError(
            f"copy blocked by finance-advice screen: {hits}")
    return {
        "title": f"{topic} — in under 60 seconds",
        "hook": hook,
        "narration": narration,
        "finance_advice_hits": [],
    }


def build_job(
    topic: str,
    facts: Iterable[str],
    materials: Iterable[dict[str, Any]],
    *,
    lane: str = "space_science",
    index: int = 0,
) -> dict[str, Any]:
    """One complete factory job spec from prompt + storyboard material.

    Materials are storyboard clips/images; every item must carry a
    licence name and a source page URL (provenance), matching how
    VyralX's stocked catalogues describe media.
    """
    if lane not in ALLOWED_LANES:
        raise ShortsFactoryError(
            f"lane {lane!r} not in VyralX lanes {ALLOWED_LANES}")
    materials = list(materials)
    if not materials:
        raise ShortsFactoryError("storyboard materials are required")
    for m in materials:
        if not m.get("license_name") or not m.get("page_url"):
            raise ShortsFactoryError(
                f"storyboard material lacks licence/provenance: {m!r}")

    copy = build_copy(topic, facts, index=index)
    seconds = estimate_seconds(copy["narration"])
    if seconds >= 60.0:
        raise ShortsFactoryError(
            f"narration estimates {seconds}s — Shorts must be <60s; "
            "shorten the facts, do not trim silently")

    cues = captions.segment_script(copy["narration"], seconds,
                                   max_words_per_cue=3)
    return {
        "version": FACTORY_VERSION,
        "kind": "vyralx.shorts_factory_job",
        "status": "planned",
        "topic": topic,
        "lane": lane,
        "format": "shorts",
        "width": 1080,
        "height": 1920,
        "estimated_seconds": seconds,
        "copy": copy,
        "voice_plan": {
            "provider": "edge",
            "voice": EDGE_VOICE,
            "paid": False,
            "text": copy["narration"],
        },
        "mix_plan": {
            "segments": [
                {"order": i, "material": m.get("catalog_id") or m["page_url"],
                 "license_name": m["license_name"]}
                for i, m in enumerate(materials)
            ],
            "auto_mix": True,
            "bgm_duck_under_voice": True,
        },
        "subtitle_cues": cues,
        "render": "vyralx_existing_renderer",
        "publish": False,
        "privacy_if_published": "unlisted",
    }


def fill_batch(
    requests: Iterable[dict[str, Any]],
    *,
    target_count: int,
) -> dict[str, Any]:
    """Build a batch that fills the queue to ``target_count`` jobs.

    The upstream factory's signature behaviour: it keeps
    synthesising until the preset queue size is reached. Here,
    requests cycle deterministically until the target is met (each
    pass varies the hook by index); a request that fails validation
    fails the batch loudly rather than being silently skipped.
    """
    requests = list(requests)
    if not requests:
        raise ShortsFactoryError("batch needs at least one request")
    if target_count < 1:
        raise ShortsFactoryError("target_count must be >= 1")
    jobs: list[dict[str, Any]] = []
    i = 0
    while len(jobs) < target_count:
        req = requests[i % len(requests)]
        jobs.append(build_job(
            req["topic"], req["facts"], req["materials"],
            lane=req.get("lane", "space_science"), index=i))
        i += 1
    return {
        "version": FACTORY_VERSION,
        "kind": "vyralx.shorts_factory_batch",
        "target_count": target_count,
        "jobs": jobs,
        "job_count": len(jobs),
        "all_planned": all(j["status"] == "planned" for j in jobs),
        "publish": False,
        "privacy_if_published": "unlisted",
    }
