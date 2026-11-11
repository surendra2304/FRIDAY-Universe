"""Checklist C12 (batch 3): multi-agent pipelines — chained dispatch.

"Research X, then draft the script about it" is TWO delegations with a data
dependency: the second stage should consume the first stage's real output.
Before this module a chained request was eaten by the first stage's
single-intent fast path (e.g. the research dispatch) and the second half of
the owner's instruction silently never happened.

Design:
- ``detect_pipeline`` splits a request on chain connectors (", then",
  "after that", "and then", "followed by", "; then") and maps every fragment
  to a known stage kind via the same keyword sets the router uses. A request
  is a pipeline only when at least TWO fragments map to known kinds — one
  unmatched fragment means the sentence is not a chain and the single-intent
  fast paths keep their behavior.
- ``run_pipeline`` executes the stages SEQUENTIALLY with real tool dispatches
  (IntelX research, VyralX script drafting, Memora memory writes, Futuris
  forecasts, Cortex web ops). Stage N receives stage N-1's output summary as
  context — that is the "chained" in chained dispatch. A failed stage is
  reported honestly and its (empty) context is still passed on: nothing is
  invented to fill the gap.
- Every stage dispatch emits a live activity event (checklist D11) so the
  dashboard's ACTIVITY tab shows the chain as it runs.

Truthfulness rules (same contract as every other delegation):
- stage outputs come only from the real agent engines;
- a stage failure is reported with its reason, never padded;
- the combined report labels each stage and says which agent ran it.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Callable

from friday.core.logging import get_logger

logger = get_logger("ecosystem.pipeline")

# Stage kinds, each backed by a real agent engine.
STAGE_RESEARCH = "research"        # IntelX — evidence brief
STAGE_SCRIPT = "script"            # VyralX — Hyperframes draft (draft-only)
STAGE_MEMORY_WRITE = "memory_write"  # Memora — persistent fleet memory
STAGE_FORECAST = "forecast"        # Futuris — evidence-backed prediction
STAGE_WEB_OPS = "web_ops"          # Cortex — health summary (read-only)

STAGE_LABELS: dict[str, str] = {
    STAGE_RESEARCH: "IntelX research",
    STAGE_SCRIPT: "VyralX script draft",
    STAGE_MEMORY_WRITE: "Memora memory write",
    STAGE_FORECAST: "Futuris forecast",
    STAGE_WEB_OPS: "Cortex web ops",
}

# Chain connectors: the linguistic seams of a chained instruction. Matched on
# a lowercased input with punctuation kept, so ", then" and "; then" both hit.
_CHAIN_CONNECTOR_RE = re.compile(
    r"\s*(?:,|;)?\s*\b(?:and\s+then|then|after\s+that|followed\s+by|next[,\s]+)\b\s*",
    re.IGNORECASE,
)

# A connector only counts when BOTH sides are non-trivial (>= 3 chars), so
# ordinary uses of "then" ("back then", "until then") never split anything.
_MIN_FRAGMENT_LEN = 3


@dataclass
class PipelineStage:
    """One link of a chained dispatch."""

    kind: str                 # one of the STAGE_* kinds
    text: str                 # the fragment as spoken
    question: str             # operand-rich question for the stage tool
    result: dict[str, Any] = field(default_factory=dict)
    success: bool = False
    summary: str = ""


def _stage_kind(fragment: str) -> str | None:
    """Map one fragment to a stage kind using the router's keyword sets."""
    from friday.routing.capability_router import CapabilityRouter

    low = fragment.lower().strip().rstrip(".!? ")
    if CapabilityRouter._matches(low, CapabilityRouter.SCRIPT_KEYWORDS):
        return STAGE_SCRIPT
    if CapabilityRouter._matches(low, CapabilityRouter.MEMORA_OP_KEYWORDS):
        # only the WRITE half of the Memora op set starts a useful chain stage
        if re.search(r"\b(?:save|store|remember|write)\b", low):
            return STAGE_MEMORY_WRITE
        return None
    if CapabilityRouter._matches(low, CapabilityRouter.FORECAST_KEYWORDS):
        return STAGE_FORECAST
    if CapabilityRouter._matches(low, CapabilityRouter.WEB_OPS_KEYWORDS):
        return STAGE_WEB_OPS
    if CapabilityRouter._matches(low, CapabilityRouter.RESEARCH_KEYWORDS):
        return STAGE_RESEARCH
    return None


def detect_pipeline(text: str) -> list[PipelineStage] | None:
    """Return the chain's stages, or None when ``text`` is not a pipeline.

    A pipeline needs: (a) a connector, (b) at least two fragments, and
    (c) every fragment mapping to a known stage kind. Anything less is a
    single-intent request and must fall through to the existing fast paths.
    """
    low = (text or "").lower().strip()
    if not _CHAIN_CONNECTOR_RE.search(low):
        return None
    fragments = [
        f.strip().rstrip(",;.!? ")
        for f in _CHAIN_CONNECTOR_RE.split(low)
        if f and len(f.strip()) >= _MIN_FRAGMENT_LEN
    ]
    if len(fragments) < 2:
        return None
    stages: list[PipelineStage] = []
    for fragment in fragments:
        kind = _stage_kind(fragment)
        if kind is None:
            return None  # unmappable fragment: not a chain, don't guess
        stages.append(PipelineStage(kind=kind, text=fragment, question=fragment))
    return stages


def _emit_activity(event: dict[str, Any]) -> None:
    """Checklist D11: fire-and-forget live activity event; never fatal."""
    try:
        from friday.api.activity_stream import emit

        emit(event)
    except Exception as exc:  # pragma: no cover - defensive
        logger.debug(f"pipeline activity emit skipped: {exc}")


def _stage_context_suffix(prev: PipelineStage) -> str:
    """The context stage N receives from stage N-1 (honest on failure)."""
    if prev.success and prev.summary:
        clipped = prev.summary[:400].strip()
        return f" Context from the previous stage ({STAGE_LABELS[prev.kind]}): {clipped}"
    return (
        f" Context from the previous stage ({STAGE_LABELS[prev.kind]}): "
        "that stage FAILED, so no upstream result is available."
    )


def _run_stage(stage: PipelineStage, context_suffix: str) -> PipelineStage:
    """Execute one stage against its real agent engine."""
    question = (stage.question + context_suffix).strip()
    _emit_activity({
        "type": "agent_action",
        "agent": stage.kind,
        "action": f"pipeline stage: {STAGE_LABELS[stage.kind]}",
        "status": "running",
        "detail": stage.text[:120],
    })
    if stage.kind == STAGE_RESEARCH:
        from friday.tools.builtin.intelx_research import IntelXResearchTool

        result = IntelXResearchTool().execute(query=stage.question)
    elif stage.kind == STAGE_SCRIPT:
        from friday.tools.builtin.vyralx_script import VyralXScriptTool

        result = VyralXScriptTool().execute(question=question)
    elif stage.kind == STAGE_MEMORY_WRITE:
        from friday.tools.builtin.memora_memory import MemoraMemoryTool

        # The chain's payload is the upstream context; save that verbatim.
        content = stage.question
        if context_suffix:
            content = f"{stage.question}. {context_suffix.strip()}"
        result = MemoraMemoryTool().execute(
            question=f"save this to fleet memory: {content}", op="write"
        )
    elif stage.kind == STAGE_FORECAST:
        from friday.tools.builtin.futuris_forecast import FuturisForecastTool

        result = FuturisForecastTool().execute(question=question)
    elif stage.kind == STAGE_WEB_OPS:
        from friday.tools.builtin.cortex_web_ops import CortexWebOpsTool

        result = CortexWebOpsTool().execute(question=question)
    else:  # pragma: no cover - kinds are constrained by detect_pipeline
        stage.result = {"reply": f"Unknown stage kind {stage.kind!r}", "success": False}
        stage.success = False
        stage.summary = ""
        return stage

    stage.result = {
        "content": result.content,
        "metadata": result.metadata or {},
        "is_error": bool(result.is_error),
    }
    stage.success = not result.is_error
    # The summary the NEXT stage and the report both consume: the real tool
    # reply, clipped. Empty replies stay empty — never padded.
    stage.summary = (result.content or "").strip()
    _emit_activity({
        "type": "agent_action",
        "agent": stage.kind,
        "action": f"pipeline stage: {STAGE_LABELS[stage.kind]}",
        "status": "completed" if stage.success else "failed",
        "detail": stage.summary[:120],
    })
    return stage


def run_pipeline(stages: list[PipelineStage]) -> dict[str, Any]:
    """Execute the chain sequentially; return an honest combined report."""
    executed: list[PipelineStage] = []
    for i, stage in enumerate(stages):
        suffix = _stage_context_suffix(executed[-1]) if executed else ""
        executed.append(_run_stage(stage, suffix))

    lines = [f"🔗 [PIPELINE] {len(executed)}-stage chain executed:"]
    for i, stage in enumerate(executed, 1):
        verdict = "OK" if stage.success else "FAILED"
        lines.append("")
        lines.append(f"STAGE {i} — {STAGE_LABELS[stage.kind]} [{verdict}]")
        lines.append(stage.summary if stage.summary else "(no output was returned)")
    all_ok = all(s.success for s in executed)
    if not all_ok:
        failed = ", ".join(f"stage {i + 1}" for i, s in enumerate(executed) if not s.success)
        lines.append("")
        lines.append(
            f"Honest note: {failed} did not complete; downstream stages ran with "
            "that gap marked, nothing was invented to fill it."
        )
    return {
        "reply": "\n".join(lines),
        "stages": [
            {
                "index": i,
                "kind": s.kind,
                "label": STAGE_LABELS[s.kind],
                "text": s.text,
                "success": s.success,
                "summary": s.summary[:600],
            }
            for i, s in enumerate(executed, 1)
        ],
        "success": all_ok,
    }
