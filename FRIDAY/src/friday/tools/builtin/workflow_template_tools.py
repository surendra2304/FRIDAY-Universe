"""Tools for TASK-IG-FRD-005 ready-made workflow templates."""

from __future__ import annotations

import json
from typing import Any

from friday.core.types import SafetyLevel, ToolResult
from friday.tools.base import BaseTool


class WorkflowTemplateListTool(BaseTool):
    """List the ready-made workflow templates."""

    name = "workflow_template_list"
    description = (
        "List FRIDAY's ready-made automation workflow templates (content, "
        "social, business, research, work, life), with the parameters each "
        "one takes."
    )
    safety_level = SafetyLevel.SAFE
    parameters = {
        "type": "object",
        "properties": {
            "category": {"type": "string", "description": "Optional category filter."},
        },
        "required": [],
    }

    def execute(self, category: str = "", **kwargs: Any) -> ToolResult:
        from friday.workflows.templates import list_templates

        templates = list_templates(category or None)
        if not templates:
            return ToolResult(name=self.name, content="No templates in that category.")
        lines = []
        for t in templates:
            params = ", ".join(
                p["name"] + ("*" if p.get("required") else "") for p in t["params"]
            )
            lines.append(
                f"- {t['id']} [{t['category']}] {t['name']}: {t['description']} "
                f"({t['step_count']} steps; params: {params or 'none'})"
            )
        return ToolResult(name=self.name, content="\n".join(lines))


class WorkflowTemplateRunTool(BaseTool):
    """Instantiate a template into a plan, optionally enqueuing its steps."""

    name = "workflow_template_run"
    description = (
        "Instantiate a ready-made workflow template with parameters and "
        "return the concrete step plan. With enqueue=true the steps are "
        "also added to the mission queue for execution. Required template "
        "parameters must be supplied — they are never silently defaulted."
    )
    safety_level = SafetyLevel.SENSITIVE
    risk_level = "SENSITIVE"
    parameters = {
        "type": "object",
        "properties": {
            "template_id": {"type": "string", "description": "Template id from workflow_template_list."},
            "params": {
                "type": "string",
                "description": "JSON object of parameter values, e.g. '{\"topic\": \"AI agents\"}'.",
            },
            "enqueue": {"type": "boolean", "description": "Also enqueue the steps as missions."},
        },
        "required": ["template_id"],
    }

    def execute(self, template_id: str = "", params: Any = None, enqueue: bool = False, **kwargs: Any) -> ToolResult:
        from friday.workflows.templates import TemplateError, instantiate, render_plan

        parsed: dict = {}
        if isinstance(params, dict):
            parsed = params
        elif isinstance(params, str) and params.strip():
            try:
                parsed = json.loads(params)
            except ValueError:
                return ToolResult(
                    name=self.name,
                    content="params must be a JSON object string.",
                    is_error=True,
                )
        try:
            plan = instantiate(template_id, parsed, enqueue=bool(enqueue))
        except TemplateError as exc:
            return ToolResult(name=self.name, content=str(exc), is_error=True)
        return ToolResult(
            name=self.name,
            content=render_plan(plan),
            metadata={"enqueued": plan["enqueued"], "mission_ids": plan["mission_ids"]},
        )


__all__ = ["WorkflowTemplateListTool", "WorkflowTemplateRunTool"]
