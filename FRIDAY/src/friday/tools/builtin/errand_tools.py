"""Tools for TASK-IG-FRD-004 delegated-errand framework.

FRAMEWORK ONLY: these tools create errands whose external steps (phone /
email / message / purchase) sit behind an explicit owner approval gate
and a budget ledger, and "running" an errand executes approved steps
through a dry-run channel that records what WOULD happen — nothing is
sent, called, or paid. Engine: ``friday.autonomous.errands``.
"""

from __future__ import annotations

from typing import Any, Dict, List

from friday.core.types import SafetyLevel, ToolResult
from friday.tools.base import BaseTool

_engine = None


def _get_engine():
    global _engine
    if _engine is None:
        from friday.autonomous.errands import default_engine

        _engine = default_engine()
    return _engine


class ErrandCreateTool(BaseTool):
    """Create a delegated errand; external steps start unapproved."""

    name = "errand_create"
    description = (
        "Create a delegated errand (framework only): an instruction plus "
        "steps. External steps (channel: phone/email/message/purchase) are "
        "created AWAITING APPROVAL and cannot run until the owner approves "
        "them with errand_approve; a budget_cap (default 0) bounds total "
        "approvable cost. Running an errand is dry-run only — nothing real "
        "is sent or paid."
    )
    safety_level = SafetyLevel.SENSITIVE
    risk_level = "SENSITIVE"
    parameters = {
        "type": "object",
        "properties": {
            "instruction": {"type": "string", "description": "What the errand should accomplish."},
            "steps": {
                "type": "array",
                "description": "Steps: {kind: external|internal, channel (external only), description, estimated_cost}.",
                "items": {"type": "object"},
            },
            "budget_cap": {"type": "number", "description": "Max total approvable cost; default 0."},
        },
        "required": ["instruction", "steps"],
    }

    def execute(self, instruction: str = "", steps: Any = None, budget_cap: float = 0.0, **kwargs: Any) -> ToolResult:
        from friday.autonomous.errands import ErrandError

        if not instruction or not isinstance(steps, list) or not steps:
            return ToolResult(
                name=self.name,
                content="errand_create needs an instruction and a non-empty steps list.",
                is_error=True,
            )
        try:
            errand = _get_engine().create_errand(instruction, steps, budget_cap=float(budget_cap or 0.0))
        except ErrandError as exc:
            return ToolResult(name=self.name, content=str(exc), is_error=True)
        awaiting = [s["id"] for s in errand["steps"] if s["state"] == "awaiting_approval"]
        return ToolResult(
            name=self.name,
            content=(
                f"Errand {errand['id']} created (framework only, budget cap {errand['budget_cap']}). "
                f"Steps awaiting your approval: {', '.join(awaiting) or 'none'}. "
                "Nothing will happen until you approve steps and the errand is run — and running is dry-run only."
            ),
            metadata={"errand_id": errand["id"]},
        )


class ErrandStatusTool(BaseTool):
    """Show an errand's steps, approvals and budget state."""

    name = "errand_status"
    description = "Show a delegated errand's step states, approvals and budget ledger."
    safety_level = SafetyLevel.SAFE
    parameters = {
        "type": "object",
        "properties": {"errand_id": {"type": "string"}},
        "required": ["errand_id"],
    }

    def execute(self, errand_id: str = "", **kwargs: Any) -> ToolResult:
        from friday.autonomous.errands import ErrandError

        try:
            summary = _get_engine().summarise(errand_id)
        except ErrandError as exc:
            return ToolResult(name=self.name, content=str(exc), is_error=True)
        return ToolResult(name=self.name, content=summary)


class ErrandApproveTool(BaseTool):
    """The owner's approval gate for one errand step."""

    name = "errand_approve"
    description = (
        "Approve (or reject) one awaiting step of a delegated errand. This "
        "is the owner's gate: approval is refused if the step's cost would "
        "exceed the errand's remaining budget. Approval does not itself "
        "execute anything; errand_run performs the (dry-run) execution."
    )
    safety_level = SafetyLevel.SENSITIVE
    risk_level = "SENSITIVE"
    parameters = {
        "type": "object",
        "properties": {
            "errand_id": {"type": "string"},
            "step_id": {"type": "string", "description": "Step id, e.g. 's1'."},
            "decision": {"type": "string", "enum": ["approve", "reject"]},
        },
        "required": ["errand_id", "step_id", "decision"],
    }

    def execute(self, errand_id: str = "", step_id: str = "", decision: str = "approve", **kwargs: Any) -> ToolResult:
        from friday.autonomous.errands import ErrandError

        engine = _get_engine()
        try:
            if decision == "reject":
                errand = engine.reject_step(errand_id, step_id)
                verb = "rejected"
            else:
                errand = engine.approve_step(errand_id, step_id)
                verb = "approved"
        except ErrandError as exc:
            return ToolResult(name=self.name, content=str(exc), is_error=True)
        return ToolResult(
            name=self.name,
            content=f"Step {step_id} of errand {errand_id} {verb}. Committed spend: {engine.committed_spend(errand)} of cap {errand['budget_cap']}.",
        )


class ErrandRunTool(BaseTool):
    """Run an errand's approved steps — dry-run channel only."""

    name = "errand_run"
    description = (
        "Run a delegated errand: approved steps execute through the dry-run "
        "channel (records what WOULD happen; nothing real is sent, called "
        "or paid). The run stops at the first unapproved external step."
    )
    safety_level = SafetyLevel.SENSITIVE
    risk_level = "SENSITIVE"
    parameters = {
        "type": "object",
        "properties": {"errand_id": {"type": "string"}},
        "required": ["errand_id"],
    }

    def execute(self, errand_id: str = "", **kwargs: Any) -> ToolResult:
        from friday.autonomous.errands import ErrandError

        engine = _get_engine()
        try:
            errand = engine.run(errand_id)
        except ErrandError as exc:
            return ToolResult(name=self.name, content=str(exc), is_error=True)
        return ToolResult(name=self.name, content=engine.summarise(errand_id))


__all__ = ["ErrandCreateTool", "ErrandStatusTool", "ErrandApproveTool", "ErrandRunTool"]
