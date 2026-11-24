"""VyralX AgentTube operator workflow (TASK-VYR-080).

Pattern-only adaptation of AgentTube (darkzOGx/youtube-automation-agent,
MIT) — the open-source AI agent that runs a YouTube channel end to end
with the owner approving every video before it goes out. No upstream code
is vendored here and the upstream stack is NOT adopted: AgentTube runs on
Node.js 18.17+ with Playwright/Chromium slideshow rendering and its own
API keys, none of which fits VyralX's ~180 MB service cap on the ~956 MB
fleet VMs. What is adapted is its workflow discipline, expressed with
VyralX's own services:

* approval-first publishing — a run cannot reach ``publish`` until the
  owner approves it, and this module never uploads anything itself;
* production readiness — a verified check before anything runs on its own
  (narration present, facts linked, a finance-advice screen, and VyralX's
  measured ``compliance_gate`` verdict — unmeasured sync fails the gate);
* resumable, checkpointed production — every stage is checkpointed, so a
  crash or timeout resumes where it stopped instead of starting over;
* Scene Repair Studio — fix one scene without restarting the run
  (``film_pipeline.apply_studio_edit``);
* Shorts Repurposing Studio — turn an approved long video into up to
  three 9:16 Short drafts, reusing existing media (``shorts_generator``
  local mode + ``shorts_live_path`` render plans);
* learning loop — 24-hour and 7-day evidence is compared with the
  channel's own history and a lesson is *proposed*; the owner approves
  each lesson and applies it — the loop never applies anything itself;
* controlled growth experiments — title/thumbnail variants are tested
  through ``content_ab_tester``; a winner is adopted only at the 95%
  evidence threshold, and the original is restored before any decision;
* comment mining — repeated audience requests become video ideas.

FREE ONLY: no paid mode, no LLM call, no MuAPI, no Playwright. Renders
stay unlisted and review-first; publishing is the paused uploader's job,
never this module's. The live end-to-end leg (a real render on
VyralX-Server with real source videos + machine-QA under bad inputs) is
gated by the owner stop order — see the TASK-VYR-080 evidence doc.
"""
from __future__ import annotations

import re
import uuid
from dataclasses import dataclass, field
from typing import Any, Iterable

from app.services import compliance_gate
from app.services import content_ab_tester
from app.services import film_pipeline
from app.services import shorts_generator
from app.services import shorts_live_path

RUN_VERSION = "vyr080-1"
STAGES = ("research", "script", "production", "review", "publish", "learn")
EVIDENCE_THRESHOLD = 0.95
MIN_EXPERIMENT_IMPRESSIONS = 100
MAX_SHORTS_FROM_LONG = 3

# Guardrail: the other four VYR-080 repos must never enter VyralX's
# production path — OpenCut (reference-only, no headless/MCP path yet),
# SANA-WM / WanGP / ComfyUI (reject: GPU-only generation stacks).
# The regression test asserts none of these is imported anywhere under
# VyralX/app, and none of the heavyweight runtimes they need is either.
BANNED_IMPORTS = frozenset({
    "opencut", "sana", "wangp", "wan2gp", "comfyui",
    "torch", "diffusers", "gradio", "playwright",
})


class AgentTubeError(ValueError):
    """Raised when an operator step cannot run (wrong order, not approved)."""


@dataclass
class ChannelMandate:
    """The channel the operator runs: AgentTube's autonomous operator."""

    objective: str
    audience: str
    pillars: list[str] = field(default_factory=list)
    cadence_per_week: int = 3
    blocked_topics: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not str(self.objective or "").strip():
            raise AgentTubeError("channel mandate needs an objective")
        if not str(self.audience or "").strip():
            raise AgentTubeError("channel mandate needs an audience")
        if not self.pillars:
            raise AgentTubeError("channel mandate needs at least one content pillar")
        if not 1 <= int(self.cadence_per_week) <= 7:
            raise AgentTubeError("cadence must be 1..7 videos per week")

    def to_dict(self) -> dict[str, Any]:
        return {
            "objective": self.objective,
            "audience": self.audience,
            "pillars": list(self.pillars),
            "cadence_per_week": int(self.cadence_per_week),
            "blocked_topics": list(self.blocked_topics),
        }


def new_run(
    mandate: ChannelMandate,
    topic: str,
    *,
    lane: str = "space_science",
    source: str = "",
) -> dict[str, Any]:
    """Start one operator run: research first, everything checkpointed."""
    if not str(topic or "").strip():
        raise AgentTubeError("run needs a topic")
    return {
        "version": RUN_VERSION,
        "run_id": f"agt_{uuid.uuid4().hex[:12]}",
        "mandate": mandate.to_dict(),
        "topic": str(topic),
        "lane": lane,
        "source": source,
        "script": "",
        "stage": STAGES[0],
        "stages": {name: {"status": "pending"} for name in STAGES},
        "status": "in_progress",
        "approved": False,
        "approved_by": None,
        "readiness": None,
        "repairs": [],
        "lessons": [],
        "shorts": [],
    }


def _next_pending(run: dict[str, Any]) -> str | None:
    for name in STAGES:
        if run["stages"][name]["status"] != "completed":
            return name
    return None


def resume_run(run: dict[str, Any]) -> str | None:
    """Next stage to run: a crash resumes here instead of starting over."""
    nxt = _next_pending(run)
    run["stage"] = nxt or "done"
    return nxt


def advance_run(run: dict[str, Any], stage: str, *, output: str = "") -> dict[str, Any]:
    """Checkpoint one stage complete. Stages run in order, never skipped.

    Advancing into ``publish`` requires the owner approval first — the
    AgentTube rule that turning on autonomy never skips the checks.
    """
    if stage not in STAGES:
        raise AgentTubeError(f"unknown stage {stage!r}")
    nxt = _next_pending(run)
    if stage != nxt:
        raise AgentTubeError(
            f"cannot advance to {stage!r}: next pending stage is {nxt!r}")
    if stage == "publish" and not run.get("approved"):
        raise AgentTubeError("publish needs owner approval first")
    if run.get("status") == "rejected":
        raise AgentTubeError("rejected run cannot advance")
    run["stages"][stage] = {"status": "completed", "output": str(output or "")}
    following = _next_pending(run)
    run["stage"] = following or "done"
    if following is None:
        run["status"] = "completed"
    return run


def set_script(run: dict[str, Any], script: str) -> dict[str, Any]:
    """Record the run's original script (commentary is the main content)."""
    if not str(script or "").strip():
        raise AgentTubeError("script must not be empty")
    run["script"] = str(script)
    return run


def production_readiness(
    run: dict[str, Any],
    *,
    gate_input: dict[str, Any] | None = None,
    narration_present: bool = False,
    facts_linked: Iterable[str] | None = None,
) -> dict[str, Any]:
    """Verified check before anything runs on its own (AgentTube's
    production-readiness step, mapped onto VyralX's measured gate).

    Fail-closed: a missing gate input, missing narration, unlinked facts
    or a finance-advice marker each fail the check. The compliance gate
    itself is fail-closed too — unmeasured sync fails, never passes.
    """
    checks: list[dict[str, Any]] = []

    def add(name: str, ok: bool, detail: str) -> None:
        checks.append({"check": name, "status": "pass" if ok else "FAIL",
                       "detail": detail})

    add("narration_present", bool(narration_present),
        "narration track recorded for this video"
        if narration_present else
        "no narration — a video without working narration cannot be approved")
    facts = [str(f).strip() for f in (facts_linked or []) if str(f).strip()]
    add("facts_linked", bool(facts),
        f"{len(facts)} factual claim(s) linked to a verified source (evidence desk)"
        if facts else "no factual claim linked to a verified source")
    advice = compliance_gate.find_finance_advice(run.get("script") or "")
    add("no_finance_advice", not advice,
        "no prescriptive advice markers in the script"
        if not advice else
        "prescriptive advice markers in the script: "
        + "; ".join(f"{hit['pattern']} ({hit['matched_text']!r})" for hit in advice))
    if gate_input is None:
        add("compliance_gate", False,
            "no measured production record — the gate cannot be evaluated")
    else:
        verdict = compliance_gate.evaluate_compliance_gate(gate_input)
        add("compliance_gate", bool(verdict.passed),
            "gate passed: " + "; ".join(
                f"{c['check']}: {c['detail']}" for c in verdict.checks
                if c["status"] == "pass")[:400]
            if verdict.passed else
            "gate blocked: " + "; ".join(verdict.blocking_failures))
    passed = all(c["status"] == "pass" for c in checks)
    readiness = {"passed": passed, "checks": checks}
    run["readiness"] = readiness
    return readiness


def approve_run(run: dict[str, Any], *, by: str = "owner") -> dict[str, Any]:
    """Owner approval. Requires the readiness check to have passed."""
    readiness = run.get("readiness") or {}
    if not readiness.get("passed"):
        raise AgentTubeError("cannot approve: production readiness has not passed")
    if run.get("status") == "rejected":
        raise AgentTubeError("rejected run cannot be approved")
    run["approved"] = True
    run["approved_by"] = by
    run["status"] = "approved"
    return run


def reject_run(run: dict[str, Any], *, by: str = "owner", reason: str = "") -> dict[str, Any]:
    """Owner rejection. A rejected run never advances and never publishes."""
    run["approved"] = False
    run["approved_by"] = by
    run["status"] = "rejected"
    run["rejection_reason"] = reason
    return run


def publish_decision(run: dict[str, Any]) -> dict[str, Any]:
    """What happens at the publish stage: nothing uploads here.

    An approved run waits in the review queue, unlisted. The uploader is
    paused and this module never calls it — publishing is the uploader's
    job, after a human looks at the render.
    """
    if not run.get("approved"):
        raise AgentTubeError("publish needs owner approval first")
    readiness = run.get("readiness") or {}
    if not readiness.get("passed"):
        raise AgentTubeError("publish needs production readiness to have passed")
    return {
        "publish": False,
        "privacy_if_published": "unlisted",
        "review": "pending_review",
        "note": "approved run waits in the review queue; this module never uploads",
    }


def repair_scene(run: dict[str, Any], film: dict[str, Any], edit: dict[str, Any]) -> dict[str, Any]:
    """Scene Repair Studio: fix one scene without restarting the run.

    Delegates to ``film_pipeline.apply_studio_edit`` (trim/move/restyle/
    retype); unknown ops and unknown shots raise there and are never
    silently dropped. The repair is logged on the run.
    """
    if run.get("status") == "rejected":
        raise AgentTubeError("rejected run cannot be repaired")
    repaired = film_pipeline.apply_studio_edit(film, edit)
    run["repairs"].append({"op": edit.get("op"), "shot_id": edit.get("shot_id")})
    return repaired


def repurpose_shorts(
    run: dict[str, Any],
    transcript: dict[str, Any],
    *,
    source_path: str,
    output_dir: str,
    tone: str = "ambient_explainer",
    music_dir: str | None = None,
) -> list[dict[str, Any]]:
    """Shorts Repurposing Studio: an approved long video becomes up to
    three 9:16 Short drafts, reusing existing media so no new generation
    credits are spent. Local mode only — a paid mode is rejected by
    ``shorts_generator``. Drafts stay unlisted and review-first.
    """
    if run.get("status") != "approved":
        raise AgentTubeError("only an approved video can be repurposed into Shorts")
    result = shorts_generator.generate_shorts(
        transcript, mode="local", lane=run.get("lane") or "space_science",
        max_clips=MAX_SHORTS_FROM_LONG)
    if not result.get("available") or not result.get("clips"):
        raise AgentTubeError(
            f"no Shorts could be repurposed: {result.get('reason', 'no clips')}")
    plans = [
        shorts_live_path.build_clip_render_plan(
            clip, transcript.get("timed_words") or [],
            source_path=source_path, output_dir=output_dir,
            tone=tone, music_dir=music_dir)
        for clip in result["clips"]
    ]
    run["shorts"] = [p.get("destination") for p in plans]
    return plans


_REQUEST_PATTERNS = (
    re.compile(r"video\s+(?:on|about)\s+(.+)", re.IGNORECASE),
    re.compile(r"make\s+(?:a\s+)?video\s+(?:on|about)\s+(.+)", re.IGNORECASE),
    re.compile(r"(?:please\s+)?cover\s+(.+)", re.IGNORECASE),
)


def _request_topic(text: str) -> str | None:
    """Extract the requested topic from one comment, or None if it asks
    for nothing. Punctuation and trailing filler are stripped."""
    cleaned = " ".join(str(text or "").split())
    for pattern in _REQUEST_PATTERNS:
        match = pattern.search(cleaned)
        if not match:
            continue
        topic = re.sub(r"[!?.,;:]+$", "", match.group(1).strip()).strip()
        topic = re.sub(r"\s+please$", "", topic, flags=re.IGNORECASE).strip()
        topic = re.sub(r"\s+", " ", topic)[:80]
        if len(topic) >= 3:
            return topic
    return None


def mine_comment_ideas(
    comments: Iterable[dict[str, Any]],
    *,
    min_mentions: int = 2,
) -> list[dict[str, Any]]:
    """Audience Engagement Studio: repeated requests become video ideas.

    Only a request mentioned at least ``min_mentions`` times becomes an
    idea; one-off comments never do. Returns ideas ranked by mentions.
    """
    counts: dict[str, dict[str, Any]] = {}
    for comment in comments or []:
        topic = _request_topic(comment.get("text") or "")
        if topic is None:
            continue
        key = topic.casefold()
        entry = counts.setdefault(key, {"idea": topic, "mentions": 0, "example": ""})
        entry["mentions"] += 1
        if not entry["example"]:
            entry["example"] = str(comment.get("text") or "")[:200]
    ideas = [entry for entry in counts.values() if entry["mentions"] >= min_mentions]
    ideas.sort(key=lambda e: (-e["mentions"], e["idea"]))
    return ideas


def propose_lesson(
    run: dict[str, Any],
    *,
    kpi: str = "views",
    value_24h: float | None,
    value_7d: float | None,
    baseline: float,
) -> dict[str, Any]:
    """Learning loop: compare 24-hour and 7-day evidence with the
    channel's own history and *propose* a change. Measured numbers only —
    a missing measurement is an error, never a zero. The proposal is
    never applied by the loop; the owner approves and applies it.
    """
    if value_24h is None or value_7d is None:
        raise AgentTubeError("lesson needs measured 24h and 7d evidence, never estimates")
    if baseline is None or float(baseline) <= 0:
        raise AgentTubeError("lesson needs a positive channel baseline")
    direction = "below" if float(value_7d) < float(baseline) else "above"
    if direction == "below":
        proposal = (
            f"{kpi} 7d {value_7d} is below the channel baseline {baseline}; "
            "review the hook and first-30s retention for the next video in this lane"
        )
    else:
        proposal = (
            f"{kpi} 7d {value_7d} is above the channel baseline {baseline}; "
            "repeat this video's format for the next video in this lane"
        )
    lesson = {
        "lesson_id": f"les_{uuid.uuid4().hex[:8]}",
        "kpi": kpi,
        "value_24h": value_24h,
        "value_7d": value_7d,
        "baseline": baseline,
        "direction": direction,
        "proposal": proposal,
        "status": "proposed",
        "approved": False,
        "applied": False,
    }
    run["lessons"].append(lesson)
    return lesson


def approve_lesson(run: dict[str, Any], lesson_id: str) -> dict[str, Any]:
    """Owner approves a lesson. Approval is not application: ``applied``
    stays False until a human applies the change."""
    for lesson in run.get("lessons") or []:
        if lesson.get("lesson_id") == lesson_id:
            lesson["approved"] = True
            lesson["status"] = "approved"
            return lesson
    raise AgentTubeError(f"no lesson {lesson_id!r} on this run")


def reject_lesson(run: dict[str, Any], lesson_id: str) -> dict[str, Any]:
    """Owner rejects a lesson; it is recorded, not deleted."""
    for lesson in run.get("lessons") or []:
        if lesson.get("lesson_id") == lesson_id:
            lesson["approved"] = False
            lesson["status"] = "rejected"
            return lesson
    raise AgentTubeError(f"no lesson {lesson_id!r} on this run")


def run_title_experiment(
    tester: content_ab_tester.ContentABTester,
    *,
    video_id: str,
    name: str,
    hypothesis: str,
    variants: list[dict[str, str]],
    results: Iterable[tuple[str, int, int]],
) -> dict[str, Any]:
    """Controlled growth experiment: title/thumbnail variants on a live
    video, through ``content_ab_tester``. A winner is adopted only at the
    95% evidence threshold with at least 100 impressions; anything weaker
    adopts nothing. The original is restored before any decision — this
    function never changes the live title itself, it only reports.
    """
    if len(variants) < 2:
        raise AgentTubeError("an experiment needs at least two variants")
    experiment_id = tester.create_experiment(name, video_id, hypothesis, variants)
    # Variant ids are only exposed through the tester's internal store
    # (no public accessor exists); map variant name -> id from there.
    experiment = tester._experiments[experiment_id]
    by_name = {v.name: v.variant_id for v in experiment.variants}
    total_impressions = 0
    for variant_name, impressions, conversions in results:
        variant_id = by_name.get(variant_name)
        if variant_id is None:
            raise AgentTubeError(f"unknown variant {variant_name!r}")
        if impressions < 0 or conversions < 0 or conversions > impressions:
            raise AgentTubeError("results must satisfy 0 <= conversions <= impressions")
        total_impressions += impressions
        for _ in range(int(impressions)):
            tester.record_result(experiment_id, variant_id, True, False)
        for _ in range(int(conversions)):
            tester.record_result(experiment_id, variant_id, False, True)
    concluded = tester.conclude_experiment(experiment_id)
    adopted = bool(
        concluded.significance >= EVIDENCE_THRESHOLD
        and total_impressions >= MIN_EXPERIMENT_IMPRESSIONS
    )
    winner = None
    if adopted:
        winner_variant = next(
            (v for v in concluded.variants if v.variant_id == concluded.winner_id), None)
        winner = winner_variant.name if winner_variant else None
    return {
        "experiment_id": experiment_id,
        "winner": winner,
        "significance": concluded.significance,
        "total_impressions": total_impressions,
        "adopted": adopted,
        "original_restored": True,
        "note": (
            "winner adopted at the 95% evidence threshold; original restored"
            if adopted else
            "no winner adopted — evidence below the 95% threshold; original restored"
        ),
    }
