"""VyralX channel-automation workflow discipline (TASK-IG2-VYR-09).

Pattern adapted from AgentTube / youtube-automation-agent (MIT,
https://github.com/darkzOGx/youtube-automation-agent): a channel
operator driven by a written mandate, production-readiness checks,
resumable checkpointed generation, scene-level repair, and an
analytics/comment learning loop whose every lesson needs owner
sign-off. This is FRIDAY's own implementation of that workflow
pattern for VyralX's existing autopilot; no AgentTube code (Node.js)
is vendored, and no second channel-running stack is introduced.

What this module is and is not:

* It is the *state machine and gates* around VyralX's production /
  upload / metadata workflow: a job advances stage by stage, every
  transition is checkpointed into a JSON-serialisable dict the
  caller persists, a failed scene can be marked for repair without
  restarting the job, and publishing is approval-first.
* It is not an uploader and performs no network calls. The upload
  step stays VyralX's existing resumable YouTube adapter, invoked
  by the caller only with the plan this module issues.

Owner rules enforced here: uploads are UNLISTED — an upload plan
with any other privacy status is refused, and the plan this module
issues always carries ``privacy_status="unlisted"``; no stage may
be skipped on the way to upload; a learning proposal (from
analytics or comments) is inert until the owner approves it, and
even then applying it is a separate explicit step; Shorts derived
from an approved long video inherit the <60s rule.
"""
from __future__ import annotations

from typing import Any

AUTOMATION_VERSION = "ig2-vyr09-1"

#: AgentTube's pipeline, in order. ``approval`` sits between
#: metadata and upload — nothing publishes without it.
STAGES = (
    "research", "script", "production", "metadata",
    "approval", "upload", "analytics",
)

#: The channel mandate: what the operator may do without asking.
DEFAULT_MANDATE = {
    "lanes": ("space_science", "history_dyk", "tech_ai", "money_stories"),
    "privacy_status": "unlisted",
    "approval_required_before_upload": True,
    "learning_requires_owner_signoff": True,
    "shorts_max_seconds": 59.0,
    "paid_services_allowed": False,
}

#: Production-readiness checks (AgentTube's pre-flight list, adapted).
READINESS_CHECKS = (
    "script_present", "scenes_present", "metadata_present",
    "privacy_unlisted", "finance_screen_clean",
)


class AutomationError(ValueError):
    """Raised when a workflow transition violates the mandate."""


def new_job(job_id: str, title: str, *, lane: str = "space_science",
            mandate: dict[str, Any] | None = None) -> dict[str, Any]:
    """Create a checkpointed job at the first stage."""
    m = {**DEFAULT_MANDATE, **(mandate or {})}
    if lane not in m["lanes"]:
        raise AutomationError(f"lane {lane!r} not in mandate lanes {m['lanes']}")
    if m["privacy_status"] != "unlisted":
        raise AutomationError(
            "mandate privacy_status must be 'unlisted' (owner rule)")
    if not m["approval_required_before_upload"]:
        raise AutomationError("mandate may not disable the approval gate")
    return {
        "version": AUTOMATION_VERSION,
        "kind": "vyralx.channel_automation_job",
        "job_id": str(job_id),
        "title": str(title),
        "lane": lane,
        "mandate": {**m, "lanes": list(m["lanes"])},
        "stage": STAGES[0],
        "completed_stages": [],
        "artifacts": {},
        "scene_repairs": [],
        "approval": {"approved": False, "by": None},
        "learning_proposals": [],
        "checkpoints": [{"stage": STAGES[0], "note": "job created"}],
    }


def _require_stage(job: dict[str, Any], stage: str) -> None:
    if job.get("stage") != stage:
        raise AutomationError(
            f"job is at stage {job.get('stage')!r}, expected {stage!r}; "
            "stages may not be skipped")


def advance(job: dict[str, Any], artifact: Any = None,
            *, note: str = "") -> dict[str, Any]:
    """Move a job one stage forward, checkpointing the transition.

    The ``approval`` stage is special: entering ``upload`` requires
    a recorded owner approval (see :func:`approve`). Returns the
    same job dict, mutated, so callers can persist it as the new
    checkpoint.
    """
    stage = job["stage"]
    if stage == STAGES[-1]:
        raise AutomationError("job is already at the final stage")
    if stage == "approval" and not job["approval"]["approved"]:
        raise AutomationError(
            "approval gate: upload requires recorded owner approval")
    nxt = STAGES[STAGES.index(stage) + 1]
    if artifact is not None:
        job["artifacts"][stage] = artifact
    job["completed_stages"].append(stage)
    job["stage"] = nxt
    job["checkpoints"].append(
        {"stage": nxt, "note": note or f"advanced from {stage}"})
    return job


def approve(job: dict[str, Any], *, by: str = "owner") -> dict[str, Any]:
    """Record the human approval AgentTube requires before publish."""
    _require_stage(job, "approval")
    if not str(by or "").strip():
        raise AutomationError("approval must name who approved")
    job["approval"] = {"approved": True, "by": str(by)}
    job["checkpoints"].append({"stage": "approval", "note": f"approved by {by}"})
    return job


def request_scene_repair(job: dict[str, Any], scene_index: int,
                         reason: str) -> dict[str, Any]:
    """AgentTube's Scene Repair Studio, state-level: flag ONE scene
    for repair during production without resetting the job or any
    other scene."""
    _require_stage(job, "production")
    if not isinstance(scene_index, int) or scene_index < 0:
        raise AutomationError("scene_index must be a non-negative int")
    if not str(reason or "").strip():
        raise AutomationError("a repair needs a reason")
    repair = {"scene_index": scene_index, "reason": str(reason),
              "status": "requested"}
    job["scene_repairs"].append(repair)
    job["checkpoints"].append(
        {"stage": "production", "note": f"scene {scene_index} repair requested"})
    return repair


def readiness(job: dict[str, Any]) -> dict[str, Any]:
    """Production-readiness check over the job's artifacts.

    Missing evidence is reported as a failed check with its name —
    never assumed. ``finance_screen_clean`` fails closed when the
    script artifact carries no screen result.
    """
    artifacts = job.get("artifacts", {})
    script = artifacts.get("script") or {}
    production = artifacts.get("production") or {}
    metadata = artifacts.get("metadata") or {}
    checks = {
        "script_present": bool(script.get("text")),
        "scenes_present": bool(production.get("scenes")),
        "metadata_present": bool(
            metadata.get("title") and metadata.get("description")),
        "privacy_unlisted":
            job.get("mandate", {}).get("privacy_status") == "unlisted",
        "finance_screen_clean":
            script.get("finance_advice_hits") == [],
    }
    return {"checks": checks, "ready": all(checks.values()),
            "failed": [k for k in READINESS_CHECKS if not checks[k]]}


def issue_upload_plan(job: dict[str, Any]) -> dict[str, Any]:
    """The only upload plan this workflow issues: approved, ready,
    and UNLISTED. The caller hands it to VyralX's existing resumable
    upload adapter; this module uploads nothing itself."""
    _require_stage(job, "upload")
    if not job["approval"]["approved"]:
        raise AutomationError("approval gate: no approved upload plan")
    report = readiness(job)
    if not report["ready"]:
        raise AutomationError(
            f"production-readiness failed: {report['failed']}")
    metadata = job["artifacts"]["metadata"]
    return {
        "version": AUTOMATION_VERSION,
        "job_id": job["job_id"],
        "title": metadata["title"],
        "description": metadata["description"],
        "tags": list(metadata.get("tags", [])),
        "privacy_status": "unlisted",
        "upload_via": "vyralx_existing_resumable_adapter",
        "approved_by": job["approval"]["by"],
    }


def propose_learning(job: dict[str, Any], lesson: str, *,
                     source: str = "analytics") -> dict[str, Any]:
    """Record a lesson from analytics/comments as a PROPOSAL.

    AgentTube's learning loop: lessons never self-apply. A proposal
    sits at ``status="proposed"`` until the owner signs off, and
    sign-off still changes nothing by itself — it only marks the
    proposal eligible for a separate, explicit application step.
    """
    if source not in ("analytics", "comments"):
        raise AutomationError(f"learning source {source!r} not recognised")
    if not str(lesson or "").strip():
        raise AutomationError("a learning proposal needs a lesson")
    proposal = {"lesson": str(lesson), "source": source,
                "status": "proposed", "applied": False}
    job["learning_proposals"].append(proposal)
    return proposal


def signoff_learning(job: dict[str, Any], index: int, *,
                     by: str = "owner") -> dict[str, Any]:
    """Owner sign-off on one proposal. Marks it ``signed_off``;
    ``applied`` stays False — application is a separate decision."""
    proposals = job.get("learning_proposals", [])
    if not 0 <= index < len(proposals):
        raise AutomationError(f"no learning proposal at index {index}")
    proposal = proposals[index]
    if proposal["status"] != "proposed":
        raise AutomationError(
            f"proposal is {proposal['status']!r}, not 'proposed'")
    proposal["status"] = "signed_off"
    proposal["signed_off_by"] = str(by)
    return proposal


def plan_shorts_repurpose(job: dict[str, Any],
                          clips: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Shorts Repurposing Studio, plan-level: clips may only be cut
    from a job that reached upload (i.e. was approved), each clip
    must respect the mandate's <60s Shorts cap, and every derived
    Short stays UNLISTED and unpublished by this module."""
    if "upload" not in job.get("completed_stages", []) \
            and job.get("stage") != "analytics":
        raise AutomationError(
            "shorts may only be repurposed from an approved, uploaded video")
    cap = float(job["mandate"]["shorts_max_seconds"])
    plans = []
    for clip in clips:
        seconds = float(clip.get("duration_s", 0))
        if not 0 < seconds <= cap:
            raise AutomationError(
                f"clip duration {seconds}s outside (0, {cap}] Shorts cap")
        plans.append({
            "source_job_id": job["job_id"],
            "start_s": float(clip.get("start_s", 0)),
            "duration_s": seconds,
            "privacy_if_published": "unlisted",
            "publish": False,
        })
    return plans
