"""Forge workflow passes — adopted Agency roles as code.

TASK-FRG-022: adopt the Agency repo's Reality Checker and AI Code Auditor
roles as workflow passes, coordinated by an agents-orchestrator pattern.

Source (read first-hand 2026-11-25):
- The Agency, msitarzewski/agency-agents (MIT, ~170k stars):
  - testing/testing-reality-checker.md — "TestingRealityChecker":
    stops fantasy approvals, defaults to "NEEDS WORK", requires
    overwhelming proof for production readiness.
  - security/security-ai-generated-code-auditor.md — "AI-Generated Code
    Security Auditor": hunts hardcoded secrets, broken row-level
    security, and prompt-injection sinks; CWE-mapped findings, scan /
    fix / rescan loop, honest confidence.
  - specialized/agents-orchestrator.md — "AgentsOrchestrator": the
    conductor that runs the dev pipeline from spec to ship; quality
    gates, max 3 attempts per task before escalation, fail-closed on
    inconclusive evidence; Reality Checker is its Phase 4 final gate.
- Carousel that filed the task: @madiyarbegenov "The Agency"
  (Instagram Df9NFPKivh7, via CLASSIFICATION-2026-11-24.md §1 item 11).

The Agency roles are prompt-personas for LLM agents. The Forge adoption
is deterministic stdlib-only Python implementing the same rules — no LLM
calls, no network, no telemetry. A pass that cannot prove something says
so instead of guessing.
"""

from __future__ import annotations

from .ai_code_auditor import AICodeAuditor, AuditFinding, AuditReport, RescanDiff
from .orchestrator import AgentsOrchestrator, ShipVerdict
from .reality_checker import (
    EvidenceItem,
    RealityChecker,
    RealityIssue,
    RealityReport,
    ShipCandidate,
    SpecCompliance,
)

__all__ = [
    "AICodeAuditor",
    "AgentsOrchestrator",
    "AuditFinding",
    "AuditReport",
    "EvidenceItem",
    "RealityChecker",
    "RealityIssue",
    "RealityReport",
    "RescanDiff",
    "ShipCandidate",
    "ShipVerdict",
    "SpecCompliance",
]
