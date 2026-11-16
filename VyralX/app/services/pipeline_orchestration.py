"""VyralX pipeline orchestration (TASK-IG2-VYR-02).

Pattern adapted from OpenMontage (AGPL-3.0,
https://github.com/OpenMontageInc/OpenMontage): a video run is a
*manifest* of directed stages, providers are chosen by transparent
scoring under a budget, quality gates sit before and after render,
and a storyboard approval gate stops the run until a human approves.
This is FRIDAY's own implementation of those ideas for VyralX's
lanes; no OpenMontage code is vendored (pattern only — AGPL care
noted on the spec card).

What deliberately does NOT transfer (per the spec card): the full
OpenMontage stack (Node 22+/Remotion/headless rendering, GPU local
generation) far exceeds the ~956MB fleet VMs and ~180MB service
caps. So in every manifest the compose/render stages are marked
``off_fleet`` — planning, scoring, gating and approval run inside
VyralX; the render itself is executed by VyralX's existing pipeline
off the resident service or post-ARM, exactly as before.

Owner rules baked in: FREE generation paths only — the default
budget is $0 and any provider with a non-zero estimated cost is
ineligible unless a run explicitly raises its budget (which this
module never does on its own); Shorts are <60s; lanes are
space/science, history/did-you-know, tech/AI explainers; money is
stories never advice (the script stage's gate runs the compliance
finance-advice finder); publishing stays UNLISTED and is a plan,
never an action, here.
"""
from __future__ import annotations

from typing import Any

from app.services import compliance_gate

ORCHESTRATION_VERSION = "ig2-vyr02-1"

ALLOWED_LANES = ("space_science", "history", "tech_ai")

#: Stage directors: (stage, where it runs). Render-bearing stages
#: are off_fleet per the card; everything else is planning/gating.
_STAGE_FLOW: tuple[tuple[str, str], ...] = (
    ("research", "on_fleet"),
    ("script", "on_fleet"),
    ("storyboard", "on_fleet"),
    ("assets", "on_fleet"),
    ("voice", "off_fleet"),
    ("compose", "off_fleet"),
    ("quality", "on_fleet"),
    ("approval", "on_fleet"),
    ("publish_plan", "on_fleet"),
)

#: Pipeline manifests, adapted from OpenMontage's 12 pipelines to
#: the subset that fits VyralX's lanes and formats.
PIPELINES: dict[str, dict[str, Any]] = {
    "explainer_short": {
        "format": "shorts", "max_seconds": 59,
        "lanes": ALLOWED_LANES,
        "summary": "Animated-explainer pattern cut to a <60s Short.",
    },
    "documentary_montage": {
        "format": "long", "max_seconds": 1800,
        "lanes": ("space_science", "history"),
        "summary": "Archive-footage montage (NASA/Archive.org/Wikimedia).",
    },
    "clip_factory": {
        "format": "shorts", "max_seconds": 59,
        "lanes": ALLOWED_LANES,
        "summary": "One long-form source sliced into many Shorts.",
    },
    "podcast_repurpose": {
        "format": "long", "max_seconds": 3600,
        "lanes": ALLOWED_LANES,
        "summary": "Audio episode (TASK-IG2-VYR-01 lane) to video plan.",
    },
    "tech_explainer": {
        "format": "long", "max_seconds": 1200,
        "lanes": ("tech_ai",),
        "summary": "Screen-demo / explainer pattern for tech & AI topics.",
    },
}


class OrchestrationError(ValueError):
    """Raised when a run violates a manifest, budget or gate rule."""


def list_pipelines() -> list[str]:
    return sorted(PIPELINES)


def get_pipeline(name: str) -> dict[str, Any]:
    try:
        return {"name": name, **PIPELINES[name]}
    except KeyError:
        raise OrchestrationError(
            f"unknown pipeline {name!r}; known: {list_pipelines()}") from None


# --------------------------------------------------------------------------- #
# Scored provider selection (OpenMontage pattern), free-first
# --------------------------------------------------------------------------- #
def score_provider(candidate: dict[str, Any], *, budget_usd: float = 0.0) -> dict[str, Any]:
    """Score one provider candidate; ineligible ones are explained.

    Score rewards free, fleet-feasible, higher-quality providers.
    A candidate over budget (default $0 — free only) or requiring a
    GPU is ineligible outright: the fleet has no GPU and paid
    generation is an owner decision, not a pipeline default.
    """
    cost = float(candidate.get("estimated_cost_usd", 0.0))
    reasons: list[str] = []
    if cost > budget_usd:
        reasons.append(f"cost ${cost:.2f} exceeds budget ${budget_usd:.2f}")
    if candidate.get("requires_gpu"):
        reasons.append("requires GPU (fleet has none)")
    score = 0.0
    if not reasons:
        score += 50.0 if cost == 0.0 else 20.0
        score += 25.0 if candidate.get("fleet_feasible", False) else 0.0
        score += float(candidate.get("quality", 0.0)) * 25.0
    return {
        "name": candidate.get("name"),
        "eligible": not reasons,
        "score": round(score, 2),
        "reasons": reasons,
    }


def select_provider(
    candidates: list[dict[str, Any]],
    *,
    budget_usd: float = 0.0,
) -> dict[str, Any]:
    """Pick the best eligible provider; fail honestly if none fit."""
    scored = [score_provider(c, budget_usd=budget_usd) for c in candidates]
    eligible = [s for s in scored if s["eligible"]]
    if not eligible:
        raise OrchestrationError(
            f"no eligible provider within budget ${budget_usd:.2f}: "
            f"{scored}")
    winner = max(eligible, key=lambda s: s["score"])
    return {"selected": winner["name"], "scored": scored}


# --------------------------------------------------------------------------- #
# Quality gates (pre/post render)
# --------------------------------------------------------------------------- #
def evaluate_quality_gate(
    artifact: dict[str, Any],
    *,
    pipeline: str,
) -> dict[str, Any]:
    """Run the gate checks for one stage artifact.

    Checks: Shorts duration cap, captions present, source
    provenance present, and — for script artifacts — the
    compliance finance-advice screen.
    """
    manifest = get_pipeline(pipeline)
    checks: dict[str, bool] = {}
    duration = artifact.get("duration_seconds")
    if duration is not None:
        checks["duration_within_cap"] = float(duration) <= manifest["max_seconds"]
    if artifact.get("kind") == "video":
        checks["captions_present"] = bool(artifact.get("has_captions"))
        checks["provenance_present"] = bool(artifact.get("provenance"))
    if artifact.get("kind") == "script":
        hits = compliance_gate.find_finance_advice(
            str(artifact.get("text", "")))
        checks["no_finance_advice"] = not hits
    passed = all(checks.values()) and bool(checks)
    return {"passed": passed, "checks": checks, "pipeline": pipeline}


# --------------------------------------------------------------------------- #
# Run state machine with the storyboard approval gate
# --------------------------------------------------------------------------- #
def create_run(pipeline: str, topic: str, *, lane: str) -> dict[str, Any]:
    manifest = get_pipeline(pipeline)
    if lane not in manifest["lanes"]:
        raise OrchestrationError(
            f"lane {lane!r} not allowed for pipeline {pipeline!r} "
            f"(allowed: {manifest['lanes']})")
    return {
        "version": ORCHESTRATION_VERSION,
        "pipeline": pipeline,
        "topic": topic,
        "lane": lane,
        "format": manifest["format"],
        "stages": [
            {"stage": stage, "runs": runs, "status": "pending"}
            for stage, runs in _STAGE_FLOW
        ],
        "current_stage": _STAGE_FLOW[0][0],
        "budget_usd": 0.0,
        "paid_services_used": False,
        "publish": False,
        "privacy_if_published": "unlisted",
    }


def advance_run(
    run: dict[str, Any],
    *,
    approved: bool = False,
    artifact: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Advance the run one stage, enforcing gates.

    * The ``storyboard`` stage is the approval gate (OpenMontage's
      Backlot pattern): advancing past it without ``approved=True``
      raises — a human storyboard OK is required before any asset
      or render work.
    * Advancing into ``quality`` requires an artifact that passes
      :func:`evaluate_quality_gate`.
    """
    stages = run["stages"]
    current = next(
        (s for s in stages if s["status"] == "pending"), None)
    if current is None:
        raise OrchestrationError("run already complete")
    stage = current["stage"]

    if stage == "storyboard" and not approved:
        raise OrchestrationError(
            "storyboard approval gate: a human must approve the "
            "storyboard before production stages run")
    if stage == "quality":
        if artifact is None:
            raise OrchestrationError(
                "quality stage requires an artifact to gate")
        gate = evaluate_quality_gate(artifact, pipeline=run["pipeline"])
        if not gate["passed"]:
            raise OrchestrationError(f"quality gate failed: {gate}")
        current["gate"] = gate

    current["status"] = "done"
    remaining = [s["stage"] for s in stages if s["status"] == "pending"]
    run["current_stage"] = remaining[0] if remaining else "complete"
    return run
