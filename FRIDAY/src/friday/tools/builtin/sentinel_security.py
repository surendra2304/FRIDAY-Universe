"""Checklist F19/C8 (MASTER_COMPLETION_CHECKLIST): Sentinel security answers via chat.

The owner can ask for the fleet's security posture or the open security
findings in plain words and get Sentinel's REAL data — the same engines behind
Sentinel's /api/v1/friday/posture and /api/v1/findings endpoints. Read-only
by construction:

- posture: overall + per-domain scores, severity counts, audit-chain verdict
  (FleetClient.ask_sentinel — the real probe with circuit breaker);
- findings: the open finding ledger, optionally by severity
  (FleetClient.ask_sentinel_findings — new, read-only, honest empty lists).

An actual security ASSESSMENT (active scanning) is NOT performed here and
cannot be: Sentinel's delegation ingress is deliberately fail-closed behind a
complete owner-authorized scope (owner, written authorization reference,
targets, allowed methods, time window, maximum impact, rate limit). Every
answer states this so the owner is never misled about what ran.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

from friday.tools.base import BaseTool
from friday.core.types import SafetyLevel, ToolResult

_ALLOWED_ACTIONS = ("posture", "findings")  # read-only surface, by construction


class SentinelSecurityTool(BaseTool):
    """Answer security-posture and security-findings questions with Sentinel's real data."""

    name = "sentinel_security"
    description = (
        "Get the live security posture and open security findings from "
        "Sentinel, the fleet's security operations agent: overall posture "
        "score, per-domain scores (web/api/network/cloud), open findings by "
        "severity, most critical finding and the audit-chain verdict. "
        "Read-only: active security assessments stay behind Sentinel's "
        "owner-authorized scope gate by design. Use for questions like 'what "
        "is the security posture', 'run a security check', 'any security "
        "findings', 'any vulnerabilities right now', 'show critical "
        "findings'."
    )
    safety_level = SafetyLevel.SAFE
    timeout = 30.0
    parameters = {
        "type": "object",
        "properties": {
            "question": {
                "type": "string",
                "description": "The security question (e.g. 'how is the security posture').",
            },
            "action": {
                "type": "string",
                "enum": ["posture", "findings"],
                "description": "'posture' (default) for the overall security score; 'findings' for the open finding ledger.",
                "default": "posture",
            },
            "severity": {
                "type": "string",
                "enum": ["critical", "high", "medium", "low"],
                "description": "Optional severity filter for findings; omit to include all severities (default: all).",
            },
        },
        "required": [],
    }

    def __init__(self, fleet_client: Any | None = None) -> None:
        super().__init__()
        self._fleet_client = fleet_client

    def _client(self) -> Any:
        if self._fleet_client is not None:
            return self._fleet_client
        from friday.ecosystem.fleet_client import FleetClient

        return FleetClient()

    def execute(
        self,
        question: str = "",
        action: str = "posture",
        severity: str = "",
        **kwargs: Any,
    ) -> ToolResult:
        action = (action or "posture").strip().lower()
        if action not in _ALLOWED_ACTIONS:
            action = "posture"
        severity = (severity or "").strip().lower()
        if severity not in {"", "critical", "high", "medium", "low"}:
            severity = ""

        try:
            if action == "findings":
                result = asyncio.run(
                    self._client().ask_sentinel_findings(severity=severity, limit=15)
                )
            else:
                result = asyncio.run(self._client().ask_sentinel(question or "security posture"))
        except Exception as exc:
            return ToolResult(
                name=self.name,
                content=(
                    f"I could not reach Sentinel for that ({type(exc).__name__}: {exc}). "
                    "I won't guess at your security posture — try again shortly."
                ),
                is_error=True,
                safety_level=self.safety_level,
                metadata={"error": f"{type(exc).__name__}: {exc}"},
            )

        reply = str((result or {}).get("reply", "") or "")
        metadata = (result or {}).get("metadata", {}) or {}
        if not reply:
            return ToolResult(
                name=self.name,
                content=(
                    "Sentinel did not return a readable answer for that request. "
                    "That is the real outcome — nothing was invented."
                ),
                is_error=True,
                safety_level=self.safety_level,
                metadata={"error": "empty_reply"},
            )
        return ToolResult(
            name=self.name,
            content=reply,
            is_error=False,
            safety_level=self.safety_level,
            metadata={
                "sentinel": {
                    "action": action,
                    "severity_filter": severity,
                    "assessment_completed": False,
                    "read_only": True,
                    **{k: v for k, v in metadata.items() if k != "agent_id"},
                },
                "raw": json.dumps(result, default=str)[:4000],
            },
        )
