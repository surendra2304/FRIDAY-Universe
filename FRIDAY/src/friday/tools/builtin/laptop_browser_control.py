"""``laptop_browser_task`` — drive the owner's own browser by instruction.

TASK-IG-LAP-04 (corpus item Dc3pMkakrid, browser-use pattern). The
planner loop lives in ``friday.remote.laptop_browser_agent``; this tool
is its agent-facing surface: it wires the loop to the LAP-001 laptop
bridge and renders the outcome honestly (a task that runs out of steps
or hits a safety gate reports exactly that).

SENSITIVE: the loop clicks and types inside the owner's logged-in
browser session. The code-level gates (credential refusal, sign-in
form stop, banking/payment stop) live in the planner module.
"""

from __future__ import annotations

from typing import Any

from friday.core.logging import get_logger
from friday.core.types import SafetyLevel, ToolResult
from friday.remote.laptop_browser_agent import make_llm_decider, run_browser_task
from friday.tools.base import BaseTool
from friday.tools.builtin.laptop_control import _execute_on_laptop, _run

logger = get_logger("tools.laptop_browser_control")


class LaptopBrowserTaskTool(BaseTool):
    """Natural-language task execution in the owner's laptop browser."""

    name = "laptop_browser_task"
    description = (
        "Carry out a task in the owner's OWN browser on his laptop — the "
        "one with his logins — by natural-language instruction: FRIDAY "
        "looks at the screen (screenshot + OCR), then opens pages, clicks "
        "and types step by step until the task is done or provably stuck. "
        "Use for tasks on sites where the owner is signed in. It refuses "
        "credentials, stops at sign-in forms and banking/payment pages, "
        "and reports honestly when it cannot finish. For a browser on "
        "FRIDAY's server instead, use the browser automation tools."
    )
    safety_level = SafetyLevel.SENSITIVE
    parameters = {
        "type": "object",
        "properties": {
            "instruction": {
                "type": "string",
                "description": "What to do in the owner's browser, in plain language.",
            },
            "laptop_id": {
                "type": "string",
                "description": "Optional laptop id when more than one is connected.",
            },
            "max_steps": {
                "type": "integer",
                "description": "Step budget for the task (default 10, max 25).",
            },
        },
        "required": ["instruction"],
    }

    def _error(self, message: str) -> ToolResult:
        return ToolResult(
            name=self.name, content=message, is_error=True, safety_level=self.safety_level
        )

    def execute(
        self,
        instruction: str = "",
        laptop_id: str = "",
        max_steps: int = 10,
        **kwargs: Any,
    ) -> ToolResult:
        task = (instruction or "").strip()
        if not task:
            return self._error("No instruction provided.")
        try:
            budget = max(1, min(int(max_steps), 25))
        except (TypeError, ValueError):
            budget = 10

        target_laptop = laptop_id or None

        def execute_command(command: str, args: dict[str, Any]) -> dict[str, Any]:
            return _run(
                lambda: _execute_on_laptop(command, args, 60.0, target_laptop)
            )

        try:
            decider = make_llm_decider()
        except Exception as exc:
            return self._error(f"No planner LLM available: {type(exc).__name__}: {exc}")
        result = run_browser_task(execute_command, task, decider, max_steps=budget)
        transcript = []
        for step in result.get("steps", []):
            label = step.get("action", "?")
            detail = step.get("output") or step.get("note") or step.get("error") or ""
            transcript.append(f"step {step.get('step')}: {label} {detail}".rstrip())
        content = result["summary"]
        if transcript:
            content += "\n\nSteps:\n" + "\n".join(transcript)
        return ToolResult(
            name=self.name,
            content=content,
            is_error=not result["ok"],
            safety_level=self.safety_level,
            metadata={
                "command": "browser_task",
                "stop_reason": result["stop_reason"],
                "steps": len(result.get("steps", [])),
            },
        )
