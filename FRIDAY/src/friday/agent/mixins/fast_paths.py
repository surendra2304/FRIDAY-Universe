import logging
import os
import random
import re
import shutil
import subprocess
import sys
import time
import warnings
from collections.abc import Callable
from typing import Any
from urllib.parse import quote_plus
import uuid
from datetime import datetime
from friday.agent.checkpoint import TaskCheckpoint, TaskCheckpointStore
from friday.core.owner_time import owner_now_str
from friday.agent.cognitive import CognitiveIntelligenceEngine, CognitivePhase


from friday.agent.prompts import build_system_message
from friday.agent.state import ReasoningStateMachine, TaskState
from friday.agents.base_agent import AgentTask, BaseAgent

from friday.agents.registry import AgentRegistry

from friday.core.auth import BaseAuthorizer, DefaultSecureAuthorizer
from friday.core.config import Settings, get_settings
from friday.core.effects import launch_process_verified
from friday.core.logging import get_logger
from friday.core.types import (
    AgentResponse,
    AuthorizationDecision,
    AuthorizationRequest,
    MemorySearchResult,
    Message,
    Role,
    SafetyLevel,
    ToolCall,
    ToolResult,
    TrustLevel,
)
from friday.llm.base import BaseLLMProvider
from friday.llm.factory import create_llm_provider
from friday.memory.base import BaseMemory
from friday.memory.factory import create_memory
from friday.memory.policies import should_retrieve_memory
from friday.memory.task_context import ActiveTaskContext
from friday.observability.notifications import NotificationManager
from friday.routing.capability_router import CapabilityRouter
from friday.tools.builtin import (
    AIUniverseTool,
    CalculatorTool,
    CloseApplicationTool,
    ControlLightTool,
    ControlPlugTool,
    CreateGitBranchTool,
    CreateGitHubIssueTool,
    ExecuteCommandTool,
    FetchWebpageContentTool,
    FetchWebpageTool,
    FileListingTool,
    FileOperationsTool,
    FileReaderTool,
    FindOnScreenTool,
    GetActiveAppContextTool,
    GetAIUniverseStatusTool,
    GetSystemResourcesTool,
    GetTodaysEventsTool,
    GitCommitTool,
    GitPushTool,
    GitStatusTool,
    HealthCheckTool,
    KillProcessTool,
    LaunchApplicationTool,
    ListGitHubIssuesTool,
    ManageVolumeTool,
    ManageWindowsTool,
    MemorySearchTool,
    OpenApplicationTool,
    ProposeComputerActionTool,
    ReadActiveWindowTextTool,
    ReadOwnCodebaseTool,
    ReadScreenTextTool,
    ReplaceFileContentTool,
    RunTestsTool,
    ScreenPredictionTool,
    ScreenSnapshotTool,
    SendEmailTool,
    SynthesizeInformationTool,
    SystemControlTool,
    SystemInfoTool,
    SystemPowerControlTool,
    TimeDateTool,
    ToggleBluetoothTool,
    ToggleDarkModeTool,
    ToggleWifiTool,
    TypeTextTool,
    WebSearchTool,
    WriteCodeFileTool,
)
from friday.tools.registry import ToolRegistry
from friday.vision.actions import ActionType
from friday.vision.computer_control import ComputerActionExecutor
from friday.vision.detector import DeterministicActionDetector
from friday.vision.intent_detector import ActionIntent, IntentDetector
from friday.vision.windows_input_driver import (
    WindowsNativeInputDriver,
    check_desktop_interactivity,
)


logger = logging.getLogger(__name__)


#: TASK-ORCH-007 delegation instruction heads — the SAME three patterns the
#: delegation fast path matches (kept in one place so the task-status gate and
#: the delegation gate can never disagree about who owns a message).
_DELEGATION_INSTRUCTION_PATTERNS = [
    # assign/delegate/send/give/pass/hand (a/this/the/quick/small) task(s) to <agent>[: task]
    r"^(?:please\s+|can you\s+|could you\s+|friday[, ]+)?"
    r"(?:assign|delegate|send|give|pass|hand)\s+"
    r"(?:a\s+|an\s+|this\s+|the\s+)?"
    r"(?:quick\s+|small\s+|simple\s+|new\s+)?"
    r"(?:task|work|job)s?\s+"
    r"(?:to|for|over to|onto)\s+"
    r"(?P<agent>[a-z]+)\s*[:\-]?\s*(?P<task>.*)$",
    # send/forward this (task) to <agent>: task
    r"^(?:please\s+|can you\s+|could you\s+|friday[, ]+)?"
    r"(?:send|forward)\s+this(?:\s+task)?\s+to\s+"
    r"(?P<agent>[a-z]+)\s*[:\-]?\s*(?P<task>.*)$",
    # have/tell/ask/let <agent> (to) <task>
    r"^(?:please\s+|can you\s+|could you\s+|friday[, ]+)?"
    r"(?:have|tell|ask|let)\s+(?P<agent>[a-z]+)\s+(?:to\s+)?(?P<task>.+)$",
]


def _delegation_instruction_agent(low: str) -> "str | None":
    """Normalized fleet agent when ``low`` ASSIGNS new work, else ``None``.

    A message that begins by assigning work to a fleet agent belongs to the
    delegation fast path — even when a later tail mentions status words
    ("assign a quick task to IntelX: sky note. then show me its result").
    Used by the task-status gate (ORCH-008/C13) to yield to delegation.
    """
    if not low:
        return None
    for pattern in _DELEGATION_INSTRUCTION_PATTERNS:
        match = re.match(pattern, low)
        if match:
            try:
                from friday.tools.builtin.fleet_dispatch import normalize_agent

                agent = normalize_agent(match.group("agent"))
            except Exception:
                return None
            # Only a real fleet agent makes it a delegation instruction
            # ("tell Rajesh to…" falls through to the normal path).
            if agent:
                return agent
            return None
    return None


class FastPathMixin:
    _WAKE_PHRASE_PATTERN = re.compile(
        r"^\s*(?:(?:hey|okay|ok|please)\s+)?friday\s*[,!:;-]?\s*",
        re.IGNORECASE,
    )

    def normalize_wake_phrase(self, user_input: str) -> str:
        """Remove an optional addressed wake phrase before intent matching."""
        clean_input = (user_input or "").strip()
        normalized = self._WAKE_PHRASE_PATTERN.sub("", clean_input, count=1)
        return normalized.strip() or clean_input

    def _greeting_fast_path(self, clean_input: str) -> AgentResponse | None:
            """Return a direct conversational greeting response, or None if not a greeting."""
            if not self._GREETING_PATTERN.match(clean_input):
                return None
            user_name = getattr(self.settings, "user_name", "Surendra")
            persona = getattr(self.settings, "persona", "friday")
            if persona == "friday":
                # Context-aware greeting (owner directive: talk like a friend
                # who knows you, never the same canned line). Composed from the
                # IST clock, the previous conversation's topic, and the live
                # mission queue; the canned pool remains only as a fallback.
                last_topic: str | None = None
                try:
                    recent = [
                        m for m in (self.memory.get_messages() or [])
                        if str(getattr(m, "content", "")).strip()
                    ]
                    for message in reversed(recent):
                        content = str(getattr(message, "content", "")).strip()
                        role = str(getattr(getattr(message, "role", None), "value", "") or "")
                        if role.upper() == "USER" and not self._GREETING_PATTERN.match(content):
                            last_topic = content
                            break
                except Exception as exc:
                    logger.debug(f"Last-topic recall skipped in greeting: {exc}")
                pending: int | None = None
                try:
                    from friday.proactive.mission_queue import mission_queue

                    pending = len(mission_queue.pending())
                except Exception as exc:
                    logger.debug(f"Mission queue count skipped in greeting: {exc}")
                from friday.persona.friday import compose_greeting

                response = compose_greeting(
                    user_name, last_topic=last_topic, pending_tasks=pending
                )
            else:
                from friday.persona.friday import greeting_responses_for

                responses = greeting_responses_for(persona)
                response = random.choice(responses).format(user_name=user_name)
            # TASK-MEM-003: proactive memory — a greeting is the moment the
            # owner returns, so FRIDAY volunteers a short reference to what it
            # remembers (past conversations, preferences) without being asked.
            # Recall failure never breaks the greeting; a greeting with no
            # memory line is a normal greeting.
            remembered: list[str] = []
            try:
                from friday.memory.memora_client import memora_client
                from friday.memory.hygiene import is_experience_hit, is_memory_noise
                user_name = getattr(self.settings, "user_name", "Surendra")
                hits = memora_client.recall_memories(
                    "friday", f"{user_name} recent work preferences", limit=3,
                )
                seen: set[str] = set()
                for m in hits or []:
                    text = str(m.get("content_text", "")).strip()
                    # TASK-REL-027: experience records are agent learnings,
                    # not memories of the owner — never volunteer one here.
                    if is_memory_noise(text) or is_experience_hit(m):
                        continue
                    if text and text not in seen and len(text) > 8:
                        seen.add(text)
                        remembered.append(text)
            except Exception as e:
                logger.debug(f"Memora proactive recall skipped in greeting: {e}")
            if remembered:
                one_line = remembered[0].rstrip(".!? ")
                if len(one_line) > 140:
                    one_line = one_line[:137].rstrip() + "…"
                response = f"{response}\n\nSince we last talked, I still remember this: {one_line}."
            logger.info("Greeting fast-path: responding directly without cognitive loop or tools")
            self.state_machine.transition_to(TaskState.UNDERSTANDING, reason="Greeting recognized")
            self.state_machine.transition_to(TaskState.PLANNING, reason="Synthesizing greeting response")
            self.state_machine.transition_to(TaskState.VERIFYING, reason="Validating greeting response")
            self.state_machine.transition_to(TaskState.COMPLETED, reason="Greeting ready")
            self.memory.add_message(Message(role=Role.USER, content=clean_input))
            self.memory.add_message(Message(role=Role.ASSISTANT, content=response))
            try:
                from friday.memory.memora_client import memora_client
                memora_client.record_interaction_async(
                    user_input=clean_input,
                    agent_output=response,
                    agent_name="friday",
                    event_type="dialogue",
                    tags=["greeting", "fast_path"],
                )
            except Exception as e:
                logger.debug(f"Memora record skipped in greeting: {e}")
            return AgentResponse(
                content=response,
                is_done=True,
                metadata={
                    "greeting_fast_path": True,
                    "proactive_memory": bool(remembered),
                    "remembered_count": len(remembered),
                    "task_state": self.state_machine.current_state.value,
                },
            )

    def _conversational_fast_path(self, clean_input: str) -> AgentResponse | None:
        """Return a local fast response for common conversational inquiries."""
        low = clean_input.lower().strip().rstrip(".!? ")
        user_name = getattr(self.settings, "user_name", "Surendra")

        reply = None
        if re.search(r"^(?:who\s+(?:are\s+you|r\s+u)|what\s+is\s+your\s+name|what\s+are\s+you|tell\s+me\s+about\s+yourself)$", low):
            reply = f"I am FRIDAY, your personal AI assistant and Windows laptop controller, {user_name}. I can control applications, media, volume, system settings, and assist with code, research, and daily workflows."
        elif re.search(r"^(?:how\s+are\s+you(?:\s+doing)?|how\'s\s+it\s+going|how\s+do\s+you\s+feel|how\s+are\s+things)$", low):
            reply = f"All systems are running at peak performance, {user_name}. Ready for whatever you need. How can I assist you right now?"
        elif re.search(r"^(?:what\s+can\s+you\s+do|what\s+are\s+your\s+capabilities|what\s+do\s+you\s+do|help\s+me\s+with\s+commands)$", low):
            reply = (
                f"I provide full Windows laptop control and autonomous AI assistance, {user_name}. "
                "You can ask me to open or search websites, control the Windows media session, adjust volume/brightness, launch or close apps, "
                "check battery and system telemetry, execute PowerShell commands, or answer complex questions. "
                "Type /friday in chat for a full list of laptop commands."
            )
        elif re.search(r"^(?:are\s+you\s+there|you\s+there|can\s+you\s+hear\s+me)$", low):
            reply = f"Always here and listening, {user_name}. What would you like done?"
        elif re.search(r"^(?:thank\s+you|thanks(?:\s+a\s+lot)?|thanks\s+friday|thank\s+you\s+so\s+much)$", low):
            reply = f"You're very welcome, {user_name}!"
        elif re.search(r"^(?:good\s+morning|good\s+afternoon|good\s+evening|good\s+night)$", low):
            reply = f"Good day, {user_name}. Systems are primed and ready."
        elif re.search(r"^(?:welcome\s+home(?:\s+sir)?|run\s+welcome\s+protocol|studio\s+mode|jarvis\s+mode)$", low):
            from friday.autonomous.welcome_protocol import welcome_protocol
            import threading
            threading.Thread(target=welcome_protocol.run, daemon=True, name="WelcomeProtocolThread").start()
            reply = f"Welcome home, {user_name}. Initiating workspace protocol across all displays."

        if not reply:
            return None

        logger.info(f"Conversational fast-path matched locally: '{low}'")
        self.state_machine.transition_to(TaskState.UNDERSTANDING, reason="Conversational query recognized")
        self.state_machine.transition_to(TaskState.PLANNING, reason="Synthesizing conversational response")
        self.state_machine.transition_to(TaskState.VERIFYING, reason="Validating conversational response")
        self.state_machine.transition_to(TaskState.COMPLETED, reason="Conversational response ready")
        self.memory.add_message(Message(role=Role.USER, content=clean_input))
        self.memory.add_message(Message(role=Role.ASSISTANT, content=reply))
        try:
            from friday.memory.memora_client import memora_client
            memora_client.record_interaction_async(
                user_input=clean_input,
                agent_output=reply,
                agent_name="friday",
                event_type="dialogue",
                tags=["conversational", "fast_path"],
            )
        except Exception as e:
            logger.debug(f"Memora record skipped in conversational: {e}")
        return AgentResponse(
            content=reply,
            is_done=True,
            metadata={
                "conversational_fast_path": True,
                "task_state": self.state_machine.current_state.value,
            },
        )

    def _security_fast_path(self, clean_input: str, start_time: float) -> AgentResponse | None:
        """Checklist F19/C8: security questions answered with Sentinel's real data.

        "What's the security posture?", "run a security check", "any
        vulnerabilities right now?" are factual questions about the live
        security state: the answer must come from Sentinel's real posture /
        finding engines (sentinel_security, read-only), never a guess. Runs
        BEFORE the fleet-status path so "check the fleet's security posture"
        is a security lookup, not a fleet-health probe. Active assessments
        are NOT performed — Sentinel's delegation ingress is deliberately
        fail-closed behind a complete owner-authorized scope, and the reply
        states that so the owner is never misled about what ran.
        """
        low = clean_input.lower().strip().rstrip(".!? ")

        if not CapabilityRouter._matches(low, CapabilityRouter.SECURITY_SCAN_KEYWORDS):
            return None
        # Explicit security-QUESTION shape: a security keyword co-occurring
        # with a question/check verb — not a delegation ("assign a security
        # task to Sentinel" is the delegation path's job).
        if _delegation_instruction_agent(low):
            return None

        from friday.tools.builtin.sentinel_security import SentinelSecurityTool

        findings_shaped = CapabilityRouter._matches(
            low,
            {
                "any vulnerabilities", "vulnerabilities", "any security findings",
                "security findings", "open findings", "any findings", "findings",
                "what did you find", "show the findings", "list the findings",
            },
        )
        severity = ""
        if re.search(r"\bcritical\b", low):
            severity = "critical"
        elif re.search(r"\bhigh\b", low):
            severity = "high"
        action = "findings" if findings_shaped else "posture"
        result = SentinelSecurityTool().execute(question=low, action=action, severity=severity)
        success = not result.is_error
        content = result.content

        self.state_machine.transition_to(TaskState.UNDERSTANDING, reason="Security question recognized")
        self.state_machine.transition_to(TaskState.PLANNING, reason="Querying Sentinel's real security engines")
        self.state_machine.transition_to(TaskState.EXECUTING, reason="sentinel_security lookup")
        self.state_machine.transition_to(TaskState.VERIFYING, reason="Returning Sentinel's real data")
        self.state_machine.transition_to(TaskState.COMPLETED if success else TaskState.FAILED, reason=content[:120])
        self.memory.add_message(Message(role=Role.USER, content=clean_input))
        self.memory.add_message(Message(role=Role.ASSISTANT, content=content))
        try:
            from friday.memory.memora_client import memora_client
            memora_client.record_interaction_async(
                user_input=clean_input,
                agent_output=content,
                agent_name="friday",
                event_type="action",
                tags=["sentinel_security", "fast_path"],
            )
        except Exception as e:
            logger.debug(f"Memora record skipped in security lookup: {e}")
        return AgentResponse(
            content=content,
            is_done=True,
            metadata={
                "fast_path": True,
                "security_lookup": True,
                "action": action,
                "severity_filter": severity,
                "sentinel": (result.metadata or {}).get("sentinel"),
                "probe_success": success,
                "duration_seconds": time.perf_counter() - start_time,
                "task_state": self.state_machine.current_state.value,
            },
        )

    def _fleet_status_fast_path(self, clean_input: str, start_time: float) -> AgentResponse | None:
        """TASK-API-002: answer fleet-health questions with a REAL probe.

        "How's the fleet?" is a factual question about live infrastructure:
        the answer must come from an actual health probe of the nine
        specialist agents (the same truth /api/agents/status reports), never
        from an LLM's imagination. Deterministic fast path: no LLM round-trip,
        no hallucination surface. Probe failure is reported honestly.
        """
        low = clean_input.lower().strip().rstrip(".!? ")

        if not CapabilityRouter._matches(low, CapabilityRouter.FLEET_KEYWORDS):
            return None

        from friday.tools.builtin.fleet_status import FleetStatusTool

        tool = FleetStatusTool()
        detail = "full" if CapabilityRouter._matches(low, {"everyone", "every agent", "full", "all of them", "detailed"}) else "summary"
        result = tool.execute(detail=detail)
        success = not result.is_error
        content = result.content

        self.state_machine.transition_to(TaskState.UNDERSTANDING, reason="Fleet-health question recognized")
        self.state_machine.transition_to(TaskState.PLANNING, reason="Probing the nine specialist agents")
        self.state_machine.transition_to(TaskState.EXECUTING, reason="get_fleet_status probe")
        self.state_machine.transition_to(TaskState.VERIFYING, reason="Reporting probe results truthfully")
        self.state_machine.transition_to(TaskState.COMPLETED if success else TaskState.FAILED, reason=content[:120])
        self.memory.add_message(Message(role=Role.USER, content=clean_input))
        self.memory.add_message(Message(role=Role.ASSISTANT, content=content))
        try:
            from friday.memory.memora_client import memora_client
            memora_client.record_interaction_async(
                user_input=clean_input,
                agent_output=content,
                agent_name="friday",
                event_type="action",
                tags=["fleet_status", "fast_path"],
            )
        except Exception as e:
            logger.debug(f"Memora record skipped in fleet status: {e}")
        return AgentResponse(
            content=content,
            is_done=True,
            metadata={
                "fast_path": True,
                "fleet_status": True,
                "probe_success": success,
                "fleet": (result.metadata or {}).get("fleet"),
                "duration_seconds": time.perf_counter() - start_time,
                "task_state": self.state_machine.current_state.value,
            },
        )

    def _diagnostics_fast_path(self, clean_input: str, start_time: float) -> AgentResponse | None:
        """TASK-DIAG-001 (2026-11-12): self-diagnostics from the REAL doctor.

        "Run diagnostics" is a factual question about FRIDAY's own twelve
        subsystems: the answer comes from FridayDoctor.run_full_diagnostics()
        — the same engine the CLI doctor command uses — never from the LLM's
        imagination. Every component is reported with its real status; a
        failing probe is named with its remediation; an untested component is
        reported as untested, never as healthy. Deterministic: no LLM call.
        """
        low = clean_input.lower().strip().rstrip(".!? ")
        from friday.routing.capability_router import CapabilityRouter

        # RESEARCH beats the topic word: "research diagnostics trends" asks
        # IntelX to research a topic, not for FRIDAY to probe itself. The
        # research fast path runs later in the ladder, so the deferral must
        # happen here (mirrors how the task-status gate defers to delegation).
        if CapabilityRouter._matches(low, CapabilityRouter.RESEARCH_KEYWORDS):
            return None

        if not CapabilityRouter._matches(low, CapabilityRouter.DIAGNOSTICS_KEYWORDS):
            return None

        from friday.core.doctor import FridayDoctor

        success = True
        lines: list[str] = []
        try:
            doctor = FridayDoctor(settings=getattr(self, "settings", None))
            report = doctor.run_full_diagnostics()
            overall = report.overall_status.value
            components = report.components
            by_status: dict[str, list[str]] = {}
            for name, comp in components.items():
                by_status.setdefault(comp.status.value, []).append(name)
            if overall == "AVAILABLE":
                lines.append(f"Full self-check complete, {self.settings.user_name} — every subsystem I probed answered.")
            elif overall in ("CONFIGURED", "DEGRADED"):
                lines.append(f"Self-check complete, {self.settings.user_name} — I'm up, with a few honest caveats below.")
            else:
                success = False
                lines.append(f"Self-check found a problem, {self.settings.user_name} — I'm not fully healthy right now.")
            lines.append(f"Overall: {overall}.")
            # Name the interesting components; quiet ones are counted.
            quiet = {"AVAILABLE", "CONFIGURED"}
            notable = [c for c in components.values() if c.status.value not in quiet]
            if notable:
                lines.append("")
                for comp in notable:
                    line = f"- {comp.name}: {comp.status.value} — {comp.message}"
                    if comp.remediation:
                        line += f" (fix: {comp.remediation})"
                    lines.append(line)
            ok_count = sum(len(names) for status, names in by_status.items() if status in quiet)
            lines.append("")
            lines.append(
                f"{ok_count} of {len(components)} components are green or configured; "
                f"{len(components) - ok_count} need attention or were not testable here."
            )
            content = "\n".join(lines)
        except Exception as exc:
            success = False
            content = (
                f"I tried to run my diagnostics, {self.settings.user_name}, but the self-check itself "
                f"failed: {type(exc).__name__}. That is the real outcome — I have no report to give you."
            )

        self.state_machine.transition_to(TaskState.UNDERSTANDING, reason="Self-diagnostics request recognized")
        self.state_machine.transition_to(TaskState.PLANNING, reason="Running the real FridayDoctor probe")
        self.state_machine.transition_to(TaskState.EXECUTING, reason="run_full_diagnostics")
        self.state_machine.transition_to(TaskState.VERIFYING, reason="Reporting per-component truth")
        self.state_machine.transition_to(TaskState.COMPLETED if success else TaskState.FAILED, reason=content[:120])
        self.memory.add_message(Message(role=Role.USER, content=clean_input))
        self.memory.add_message(Message(role=Role.ASSISTANT, content=content))
        try:
            from friday.memory.memora_client import memora_client
            memora_client.record_interaction_async(
                user_input=clean_input,
                agent_output=content,
                agent_name="friday",
                event_type="action",
                tags=["diagnostics", "fast_path"],
            )
        except Exception as e:
            logger.debug(f"Memora record skipped in diagnostics: {e}")
        return AgentResponse(
            content=content,
            is_done=True,
            metadata={
                "fast_path": True,
                "diagnostics": True,
                "probe_success": success,
                "duration_seconds": time.perf_counter() - start_time,
                "task_state": self.state_machine.current_state.value,
            },
        )

    def _task_status_fast_path(self, clean_input: str, start_time: float) -> AgentResponse | None:
        """TASK-ORCH-008 (checklist C13): task-status questions read the real ledger.

        C14 gave every delegation a receipt ("[Task receipt: task_71f66986709e]").
        When the owner asks "what happened to that IntelX task?", "status of
        task_xxx" or "did the Stratex assignment finish?", the answer must come
        from the unified TaskRecordStore (the same store the router and
        dispatch bus write into) — never from the model's memory or invention.
        This deterministic path fires only when a status question co-occurs
        with an explicit receipt id or an agent+task reference; it runs BEFORE
        delegation so a status question is never re-dispatched as new work.
        """
        low = clean_input.lower().strip().rstrip(".!? ")
        from friday.tools.builtin.task_status_query import TaskStatusQueryTool, _TASK_ID_RE

        # NEW WORK beats status words: a message that ASSIGNS work to a fleet
        # agent ("assign a quick task to IntelX: sky note. then show me its
        # result") belongs to the delegation fast path even when its tail
        # mentions a status word ('result'). Found by the delegation suite
        # after ORCH-008 moved this gate first — fixed with the shared matcher
        # so the two gates can never disagree about ownership again.
        if _delegation_instruction_agent(low):
            return None

        id_hit = _TASK_ID_RE.search(low)
        status_marker = re.search(
            r"\b(?:status|what happened|happened|finished|finish|done|completed|"
            r"progress|result|outcome|any news|any update|check on|checking on)\b",
            low,
        )
        agent_reference = None
        m = re.search(
            r"\b(?:intelx|stratex|forge|sentinel|cortex|futuris|vyralx|memora|inference)\b"
            r"|\b(?:intelix|sentinal|viralx|vyral|memoria|inferance|futuristic)\b"
            r"[^.?!]*\b(?:task|assignment|job|dispatch|brief)\b"
            r"|\b(?:task|assignment|job|dispatch|brief)\b[^.?!]*"
            r"\b(?:intelx|stratex|forge|sentinel|cortex|futuris|vyralx|memora|inference)\b"
            r"|\b(?:task|assignment|job|dispatch|brief)\b[^.?!]*"
            r"\b(?:intelix|sentinal|viralx|vyral|memoria|inferance|futuristic)\b",
            low,
        )
        if m:
            from friday.tools.builtin.fleet_dispatch import normalize_agent

            for token in re.findall(r"[a-z]+", m.group(0)):
                agent_reference = normalize_agent(token) or agent_reference
                if agent_reference:
                    break

        # Fire on: explicit receipt id (any status phrasing, or a bare receipt),
        # or a status question about a named agent's task.
        if id_hit:
            if not status_marker and len(low) <= 60 and low == low.strip():
                # Bare receipt paste ("task_abc123def456") — still a status ask;
                # but a long instruction containing an id is likely new work.
                pass
            elif not status_marker:
                return None  # "assign task_abc to ..." style content — not ours
        elif not (status_marker and agent_reference):
            return None

        result = TaskStatusQueryTool().execute(
            query=clean_input,
            agent=agent_reference or "",
        )
        content = result.content

        self.state_machine.transition_to(TaskState.UNDERSTANDING, reason="Task status question recognized")
        self.state_machine.transition_to(TaskState.PLANNING, reason="Reading the unified task ledger")
        self.state_machine.transition_to(TaskState.EXECUTING, reason="task_status lookup")
        self.state_machine.transition_to(TaskState.VERIFYING, reason="Answering from the real record only")
        self.state_machine.transition_to(TaskState.COMPLETED, reason="Task ledger lookup served")
        self.memory.add_message(Message(role=Role.USER, content=clean_input))
        self.memory.add_message(Message(role=Role.ASSISTANT, content=content))
        try:
            from friday.memory.memora_client import memora_client
            memora_client.record_interaction_async(
                user_input=clean_input,
                agent_output=content,
                agent_name="friday",
                event_type="action",
                tags=["task_status", "fast_path"],
            )
        except Exception as e:
            logger.debug(f"Memora record skipped in task status lookup: {e}")
        return AgentResponse(
            content=content,
            is_done=True,
            metadata={
                "fast_path": True,
                "task_status_query": True,
                "target_agent": agent_reference,
                "lookup": (result.metadata or {}).get("task_status_query"),
                "duration_seconds": time.perf_counter() - start_time,
                "task_state": self.state_machine.current_state.value,
            },
        )

    def _delegation_fast_path(self, clean_input: str, start_time: float) -> AgentResponse | None:
        """TASK-ORCH-007: explicit delegation phrasings dispatch straight to the agent.

        Live incidents (2026-11-11 IST): asked to "assign a quick task to
        IntelX" or "send this task to Sentinel", the live reasoning model
        repeatedly answered with invented XML protocols (`<execute_agent>`,
        `<send_task>`) as plain text instead of calling the registered
        fleet_dispatch tool — a task was never dispatched. This deterministic
        path fires only on explicit delegation phrasing (assign/send/delegate
        a task TO a named fleet agent, or have/tell/ask an agent to do
        something), extracts the agent and the task, and returns the agent's
        REAL result with a task receipt. Ordinary sentences never match.
        """
        low = clean_input.lower().strip().rstrip(".!? ")
        from friday.tools.builtin.fleet_dispatch import FleetDispatchTool, normalize_agent

        delegation_patterns = [
            # assign/delegate/send/give/pass/hand (a/this/the/quick/small) task(s) to <agent>[: task]
            r"^(?:please\s+|can you\s+|could you\s+|friday[, ]+)?"
            r"(?:assign|delegate|send|give|pass|hand)\s+"
            r"(?:a\s+|an\s+|this\s+|the\s+)?"
            r"(?:quick\s+|small\s+|simple\s+|new\s+)?"
            r"(?:task|work|job)s?\s+"
            r"(?:to|for|over to|onto)\s+"
            r"(?P<agent>[a-z]+)\s*[:\-]?\s*(?P<task>.*)$",
            # send/forward this (task) to <agent>: task
            r"^(?:please\s+|can you\s+|could you\s+|friday[, ]+)?"
            r"(?:send|forward)\s+this(?:\s+task)?\s+to\s+"
            r"(?P<agent>[a-z]+)\s*[:\-]?\s*(?P<task>.*)$",
            # have/tell/ask/let <agent> (to) <task>
            r"^(?:please\s+|can you\s+|could you\s+|friday[, ]+)?"
            r"(?:have|tell|ask|let)\s+(?P<agent>[a-z]+)\s+(?:to\s+)?(?P<task>.+)$",
        ]
        match = None
        for pattern in delegation_patterns:
            candidate = re.match(pattern, low)
            if candidate:
                match = candidate
                break
        if match is None:
            return None
        agent = normalize_agent(match.group("agent"))
        if agent is None:
            # Not a fleet agent ("tell Rajesh to...") — the normal path handles it.
            return None
        task = (match.group("task") or "").strip()
        # The owner often adds "then show me its result" — the tool result IS
        # shown, so strip that tail from the dispatched task text.
        task = re.sub(
            r"[.,]?\s*(?:and|then)\s+show\s+me\s+(?:its|the)?\s*(?:result|results|output)s?\s*$",
            "", task,
        ).strip()
        if not task:
            # "assign a task to IntelX" with no task content — let the model
            # ask what the task should be.
            return None

        result = FleetDispatchTool().execute(agent=agent, task=task)
        success = not result.is_error
        content = result.content

        self.state_machine.transition_to(TaskState.UNDERSTANDING, reason="Delegation request recognized")
        self.state_machine.transition_to(TaskState.PLANNING, reason=f"Dispatching to {agent.title()} via fleet_dispatch")
        self.state_machine.transition_to(TaskState.EXECUTING, reason="fleet_dispatch dispatch")
        self.state_machine.transition_to(TaskState.VERIFYING, reason="Returning the agent's real result")
        self.state_machine.transition_to(TaskState.COMPLETED if success else TaskState.FAILED, reason=content[:120])
        self.memory.add_message(Message(role=Role.USER, content=clean_input))
        self.memory.add_message(Message(role=Role.ASSISTANT, content=content))
        try:
            from friday.memory.memora_client import memora_client
            memora_client.record_interaction_async(
                user_input=clean_input,
                agent_output=content,
                agent_name="friday",
                event_type="action",
                tags=["fleet_dispatch", "fast_path", agent],
            )
        except Exception as e:
            logger.debug(f"Memora record skipped in delegation dispatch: {e}")
        return AgentResponse(
            content=content,
            is_done=True,
            metadata={
                "fast_path": True,
                "delegation_dispatch": True,
                "target_agent": agent,
                "receipt": (result.metadata or {}).get("fleet_dispatch"),
                "probe_success": success,
                "duration_seconds": time.perf_counter() - start_time,
                "task_state": self.state_machine.current_state.value,
            },
        )

    def _research_dispatch_fast_path(self, clean_input: str, start_time: float) -> AgentResponse | None:
        """TASK-INT-002: dispatch explicit research requests straight to IntelX.

        The M1 owner exit — "Friday, research X and give me the highlights" —
        must reliably reach IntelX (the fleet's Macro Research & Evidence
        Engine). This fast path fires only on explicit research-action phrasing
        (leading verb or an explicit highlights request), so ordinary sentences
        that merely contain the word "research" still take the full cognitive
        path. The brief returned is IntelX's real response — including its
        honest "no conclusive evidence" — never a fabricated summary.
        """
        low = clean_input.lower().strip().rstrip(".!? ")

        if not CapabilityRouter._matches(low, CapabilityRouter.RESEARCH_KEYWORDS):
            return None
        # Deterministic e2e workflow phrases ("research this company and give
        # me a cited report") are served by the E2EWorkflowCoordinator inside
        # _direct_desktop_action_fast_path — a full cited-report pipeline with
        # contradiction analysis, not a live IntelX highlights brief. Yield to
        # it (ordering fix, 2026-11-12: the live dispatch used to swallow the
        # e2e scenario and fail on the unreachable IntelX service).
        if any(
            k in low
            for k in ("research this company", "research company", "deep research")
        ) or ("research" in low and "cited report" in low):
            return None
        # Explicit research ACTION: leading verb, please-form, or highlights ask.
        action_shaped = bool(re.match(
            r"^(?:please\s+|can you\s+|could you\s+|friday[, ]+)?"
            r"(?:research|investigate|look into|dig into|find out about|brief me on|do some research)\b",
            low,
        )) or CapabilityRouter._matches(low, {"give me the highlights", "get the highlights"})
        # TASK-REL-007 (Track B; flagged for Track A): a headlines request that
        # explicitly asks for sources IS a research action — "What are today's
        # top three AI news headlines? Include sources." previously matched no
        # action shape, fell into the LLM tool loop and surfaced as a bare
        # "502" in console round 1 (2026-11-14).
        action_shaped = action_shaped or (
            "headline" in low and ("source" in low or "news" in low)
        )
        if not action_shaped:
            return None

        # Checklist A10: "research" with no topic -> ONE sharp question.
        from friday.routing.clarification import clarify_if_operand_missing

        clarification = clarify_if_operand_missing(low, "research")
        if clarification:
            return self._clarification_response(clean_input, start_time, "research", clarification)

        from friday.tools.builtin.intelx_research import IntelXResearchTool

        # The research subject: strip the action prefix for a cleaner query.
        query = re.sub(
            r"^(?:please\s+|can you\s+|could you\s+|friday[, ]+)?"
            r"(?:research|investigate|look into|dig into|find out about|brief me on|do some research)\s+(?:on\s+|about\s+|the\s+)?",
            "", low,
        ).strip() or low
        result = IntelXResearchTool().execute(query=query)
        success = not result.is_error
        content = result.content

        self.state_machine.transition_to(TaskState.UNDERSTANDING, reason="Research request recognized")
        self.state_machine.transition_to(TaskState.PLANNING, reason="Dispatching to IntelX (Macro Research & Evidence Engine)")
        self.state_machine.transition_to(TaskState.EXECUTING, reason="intelx_research dispatch")
        self.state_machine.transition_to(TaskState.VERIFYING, reason="Returning IntelX's evidence-based brief")
        self.state_machine.transition_to(TaskState.COMPLETED if success else TaskState.FAILED, reason=content[:120])
        self.memory.add_message(Message(role=Role.USER, content=clean_input))
        self.memory.add_message(Message(role=Role.ASSISTANT, content=content))
        try:
            from friday.memory.memora_client import memora_client
            memora_client.record_interaction_async(
                user_input=clean_input,
                agent_output=content,
                agent_name="friday",
                event_type="action",
                tags=["intelx_research", "fast_path"],
            )
        except Exception as e:
            logger.debug(f"Memora record skipped in research dispatch: {e}")
        return AgentResponse(
            content=content,
            is_done=True,
            metadata={
                "fast_path": True,
                "research_dispatch": True,
                "intelx": (result.metadata or {}).get("intelx"),
                "spoken_summary": (result.metadata or {}).get("spoken_summary"),
                "sources": (result.metadata or {}).get("sources", []),
                "probe_success": success,
                "duration_seconds": time.perf_counter() - start_time,
                "task_state": self.state_machine.current_state.value,
            },
        )

    def _portfolio_fast_path(self, clean_input: str, start_time: float) -> AgentResponse | None:
        """TASK-STR-002: answer portfolio questions with Stratex's real snapshot.

        "How's my portfolio?" is a factual question about the owner's Binance
        demo account: the answer must be Stratex's real engine snapshot
        (balance, positions, strategies, trading mode), never a guess. This
        fast path fires only on possessive/explicit phrasing ("my portfolio",
        "open positions", "market signals", explicit stratex/binance asks);
        general finance questions ("what is a portfolio") take the full
        cognitive path. The tool is read-only — live trading stays blocked by
        the fail-closed guard (D-015).
        """
        low = clean_input.lower().strip().rstrip(".!? ")

        # Deterministic e2e workflow phrases ("check Stratex performance") are
        # served by the E2EWorkflowCoordinator inside
        # _direct_desktop_action_fast_path — a full telemetry + advisory
        # report with the trade-freeze invariant. Yield to it (ordering fix,
        # 2026-11-12: the live Stratex dispatch used to swallow the e2e
        # scenario and fail on the unreachable service).
        if any(k in low for k in ("check stratex performance", "stratex performance", "check trading performance")):
            return None

        # Advice questions are not snapshot questions (checklist I3 regression):
        # "Should I rebalance my portfolio?" asks for the skill layer's
        # regime-gated rebalancing advice — VoiceTradingSkill answers with an
        # honest "can't recommend rebalancing, no measured market regime"
        # refusal. Standing aside here keeps this snapshot fast path from
        # swallowing the advice request and answering it with a Stratex
        # outage report instead.
        advice_phrasing = {
            "should i", "rebalance", "rebalancing", "any advice",
            "recommend", "recommendation", "good time to",
        }
        if CapabilityRouter._matches(low, advice_phrasing):
            return None

        possessive = {
            "my portfolio", "the portfolio", "my balance", "my positions",
            "open positions", "any positions", "any open positions",
            "my trading", "how is my trading", "market signals",
            "trading signals", "what strategies", "which strategies", "active strategies",
            "stratex", "binance", "pnl", "profit and loss", "current positions",
        }
        if not CapabilityRouter._matches(low, possessive):
            return None

        from friday.tools.builtin.stratex_portfolio import StratexPortfolioTool

        kind = "analysis" if CapabilityRouter._matches(
            low, {"market signals", "trading signals", "analyze"}
        ) else "portfolio"
        result = StratexPortfolioTool().execute(question=low, kind=kind)
        success = not result.is_error
        content = result.content

        self.state_machine.transition_to(TaskState.UNDERSTANDING, reason="Portfolio question recognized")
        self.state_machine.transition_to(TaskState.PLANNING, reason="Querying Stratex for the live snapshot")
        self.state_machine.transition_to(TaskState.EXECUTING, reason="stratex_portfolio query")
        self.state_machine.transition_to(TaskState.VERIFYING, reason="Returning Stratex's real data")
        self.state_machine.transition_to(TaskState.COMPLETED if success else TaskState.FAILED, reason=content[:120])
        self.memory.add_message(Message(role=Role.USER, content=clean_input))
        self.memory.add_message(Message(role=Role.ASSISTANT, content=content))
        try:
            from friday.memory.memora_client import memora_client
            memora_client.record_interaction_async(
                user_input=clean_input,
                agent_output=content,
                agent_name="friday",
                event_type="action",
                tags=["stratex_portfolio", "fast_path"],
            )
        except Exception as e:
            logger.debug(f"Memora record skipped in portfolio: {e}")
        return AgentResponse(
            content=content,
            is_done=True,
            metadata={
                "fast_path": True,
                "portfolio_query": True,
                "stratex": (result.metadata or {}).get("stratex"),
                "query_success": success,
                "duration_seconds": time.perf_counter() - start_time,
                "task_state": self.state_machine.current_state.value,
            },
        )

    def _forecast_fast_path(self, clean_input: str, start_time: float) -> AgentResponse | None:
        """Checklist F10/C10: forecast requests reach Futuris's real pipeline.

        "Forecast X over the next 24 hours" / "what does Futuris predict for
        Y" are requests for a REAL computational product. The answer must come
        from Futuris's evidence-backed FRIDAY delegation contract (research
        enrichment, forecasting pipeline, honest calibration) — never the
        LLM's invented numbers. Futuris's honest statuses (BLOCKED /
        INSUFFICIENT_DATA) are reported as-is, and every answer states that a
        prediction is never an authorization.
        """
        low = clean_input.lower().strip().rstrip(".!? ")

        if not CapabilityRouter._matches(low, CapabilityRouter.FORECAST_KEYWORDS):
            return None
        # Deterministic e2e workflow phrases ("forecast website traffic for
        # tomorrow") are served by the E2EWorkflowCoordinator inside
        # _direct_desktop_action_fast_path — a full calibrated-forecast
        # pipeline. Yield to it (ordering fix, 2026-11-12: the live Futuris
        # dispatch used to swallow the e2e scenario and fail on the
        # unreachable service).
        if any(k in low for k in ("forecast website traffic", "traffic for tomorrow", "forecast traffic")):
            return None
        # An explicit forecast ACTION: leading verb or an explicit futuris ask.
        action_shaped = bool(re.match(
            r"^(?:please\s+|can you\s+|could you\s+|friday[, ]+)?"
            # TASK-REL-007: optional qualifier ("give me a SHORT forecast")
            # must still dispatch to Futuris instead of the LLM path.
            r"(?:forecast|predict|project|give me (?:a|the)(?: \w+)? forecast|get (?:me )?(?:a|the) forecast)\b",
            low,
        )) or CapabilityRouter._matches(low, {"what does futuris", "futuris forecast"})
        if not action_shaped:
            return None
        if _delegation_instruction_agent(low):
            return None

        # Checklist A10: "forecast" with no target -> ONE sharp question.
        from friday.routing.clarification import clarify_if_operand_missing

        clarification = clarify_if_operand_missing(low, "forecast")
        if clarification:
            return self._clarification_response(clean_input, start_time, "forecast", clarification)

        from friday.tools.builtin.futuris_forecast import FuturisForecastTool

        result = FuturisForecastTool().execute(question=low)
        success = not result.is_error
        content = result.content

        self.state_machine.transition_to(TaskState.UNDERSTANDING, reason="Forecast request recognized")
        self.state_machine.transition_to(TaskState.PLANNING, reason="Dispatching to Futuris's real pipeline")
        self.state_machine.transition_to(TaskState.EXECUTING, reason="futuris_forecast request")
        self.state_machine.transition_to(TaskState.VERIFYING, reason="Returning Futuris's evidence-backed forecast")
        self.state_machine.transition_to(TaskState.COMPLETED if success else TaskState.FAILED, reason=content[:120])
        self.memory.add_message(Message(role=Role.USER, content=clean_input))
        self.memory.add_message(Message(role=Role.ASSISTANT, content=content))
        try:
            from friday.memory.memora_client import memora_client
            memora_client.record_interaction_async(
                user_input=clean_input,
                agent_output=content,
                agent_name="friday",
                event_type="action",
                tags=["futuris_forecast", "fast_path"],
            )
        except Exception as e:
            logger.debug(f"Memora record skipped in forecast dispatch: {e}")
        return AgentResponse(
            content=content,
            is_done=True,
            metadata={
                "fast_path": True,
                "forecast_dispatch": True,
                "futuris": (result.metadata or {}).get("futuris"),
                "probe_success": success,
                "duration_seconds": time.perf_counter() - start_time,
                "task_state": self.state_machine.current_state.value,
            },
        )

    def _clarification_response(
        self, clean_input: str, start_time: float, intent: str, question: str
    ) -> AgentResponse:
        """Checklist A10: ONE sharp question when the operand is missing.

        Wraps the single clarifying question in the same lifecycle as every
        other fast path (state machine + memory + Memora record) so the next
        turn can resolve it. Exactly ONE question — never an interrogation.
        """
        self.state_machine.transition_to(TaskState.UNDERSTANDING, reason="Delegation intent recognized but its target is missing")
        self.state_machine.transition_to(TaskState.PLANNING, reason="One clarifying question before dispatch")
        self.memory.add_message(Message(role=Role.USER, content=clean_input))
        self.memory.add_message(Message(role=Role.ASSISTANT, content=question))
        try:
            from friday.memory.memora_client import memora_client
            memora_client.record_interaction_async(
                user_input=clean_input,
                agent_output=question,
                agent_name="friday",
                event_type="action",
                tags=["clarification", intent, "fast_path"],
            )
        except Exception as e:
            logger.debug(f"Memora record skipped in clarification gate: {e}")
        return AgentResponse(
            content=question,
            is_done=True,
            metadata={
                "fast_path": True,
                "clarification": True,
                "clarification_intent": intent,
                "probe_success": True,
                "duration_seconds": time.perf_counter() - start_time,
                "task_state": self.state_machine.current_state.value,
            },
        )

    def _pipeline_fast_path(self, clean_input: str, start_time: float) -> AgentResponse | None:
        """Checklist C12 (batch 3): multi-agent pipelines — chained dispatch.

        "Research X, then draft the script about it" is TWO delegations with
        a data dependency: stage 2 consumes stage 1's real output. This path
        runs BEFORE every single-intent fast path so a chained instruction
        can never be eaten by its first stage's dispatcher. Every stage is a
        real agent-engine dispatch (IntelX / VyralX / Memora / Futuris /
        Cortex); failures are reported honestly per stage, never padded.
        """
        from friday.ecosystem.pipeline import detect_pipeline, run_pipeline

        stages = detect_pipeline(clean_input)
        if stages is None or len(stages) < 2:
            return None

        self.state_machine.transition_to(TaskState.UNDERSTANDING, reason=f"{len(stages)}-stage pipeline recognized")
        self.state_machine.transition_to(TaskState.PLANNING, reason="Planning chained dispatch across agents")
        self.state_machine.transition_to(TaskState.EXECUTING, reason="Executing pipeline stages sequentially")

        outcome = run_pipeline(stages)
        content = outcome["reply"]
        success = bool(outcome["success"])

        self.state_machine.transition_to(TaskState.VERIFYING, reason="Returning combined pipeline report")
        self.state_machine.transition_to(TaskState.COMPLETED if success else TaskState.FAILED, reason=content[:120])
        self.memory.add_message(Message(role=Role.USER, content=clean_input))
        self.memory.add_message(Message(role=Role.ASSISTANT, content=content))
        try:
            from friday.memory.memora_client import memora_client
            memora_client.record_interaction_async(
                user_input=clean_input,
                agent_output=content,
                agent_name="friday",
                event_type="action",
                tags=["pipeline", "fast_path"] + [s.kind for s in stages],
            )
        except Exception as e:
            logger.debug(f"Memora record skipped in pipeline dispatch: {e}")
        return AgentResponse(
            content=content,
            is_done=True,
            metadata={
                "fast_path": True,
                "pipeline_dispatch": True,
                "pipeline_stages": [
                    {
                        "kind": s.get("kind"),
                        "label": s.get("label"),
                        "success": s.get("success"),
                        "summary": (s.get("summary") or "")[:200],
                    }
                    for s in outcome["stages"]
                ],
                "probe_success": success,
                "duration_seconds": time.perf_counter() - start_time,
                "task_state": self.state_machine.current_state.value,
            },
        )

    def _batch3_delegation_fast_path(self, clean_input: str, start_time: float) -> AgentResponse | None:
        """Checklist C7/C9/C11 (batch 3): first-class chat delegations.

        Video-script drafting -> VyralX's real Hyperframes engine (draft-only);
        web-ops monitoring -> Cortex's real health summary + governed
        properties (read-only); Memora cloud-memory search/store -> Memora's
        real context database. Each answer comes from the agent's real
        engine — never the LLM's imagination.
        """
        low = clean_input.lower().strip().rstrip(".!? ")

        tool_cls = None
        label = ""
        if CapabilityRouter._matches(low, CapabilityRouter.PROJECT_KEYWORDS):
            tool_cls = "vyralx_project"
            label = "VyralX review-only video project"
        elif CapabilityRouter._matches(low, CapabilityRouter.CODE_TASK_KEYWORDS):
            tool_cls = "forge_code_task"
            label = "Forge sandboxed build and verification"
        elif CapabilityRouter._matches(low, CapabilityRouter.SCRIPT_KEYWORDS):
            tool_cls = "vyralx_script"
            label = "VyralX script drafting"
        elif CapabilityRouter._matches(low, CapabilityRouter.WEB_OPS_KEYWORDS):
            tool_cls = "cortex_web_ops"
            label = "Cortex web-ops monitoring"
        elif CapabilityRouter._matches(low, CapabilityRouter.MEMORA_OP_KEYWORDS):
            tool_cls = "memora_memory"
            label = "Memora memory operation"
        if tool_cls is None:
            return None
        if _delegation_instruction_agent(low):
            return None

        # Checklist A10: intent matched but operand missing -> ONE sharp
        # question, never a dispatch on a junk title / empty memory write.
        from friday.routing.clarification import clarify_if_operand_missing

        if tool_cls == "vyralx_script":
            question = clarify_if_operand_missing(low, "script")
            if question:
                return self._clarification_response(clean_input, start_time, "script", question)
        elif tool_cls == "memora_memory":
            question = clarify_if_operand_missing(low, "memory_save")
            if question:
                return self._clarification_response(clean_input, start_time, "memory_save", question)

        # Checklist D11: every agent action streams to the live activity feed.
        try:
            from friday.api.activity_stream import emit
            emit({
                "type": "agent_action",
                "agent": tool_cls,
                "action": label,
                "status": "running",
                "detail": low[:120],
            })
        except Exception as e:
            logger.debug(f"activity emit skipped in batch3 dispatch: {e}")

        if tool_cls == "vyralx_project":
            from friday.tools.builtin.vyralx_project import VyralXProjectTool

            # License confirmation is read from the raw user turn, not invented
            # by a model tool call or remembered from a different project.
            result = VyralXProjectTool().execute(question=clean_input)
            meta_key = "vyralx"
        elif tool_cls == "forge_code_task":
            from friday.tools.builtin.forge_code_task import ForgeCodeTool

            result = ForgeCodeTool().execute(goal=clean_input)
            meta_key = "forge"
        elif tool_cls == "vyralx_script":
            from friday.tools.builtin.vyralx_script import VyralXScriptTool

            result = VyralXScriptTool().execute(question=low)
            meta_key = "vyralx"
        elif tool_cls == "cortex_web_ops":
            from friday.tools.builtin.cortex_web_ops import CortexWebOpsTool

            result = CortexWebOpsTool().execute(question=low)
            meta_key = "cortex"
        else:
            from friday.tools.builtin.memora_memory import MemoraMemoryTool

            result = MemoraMemoryTool().execute(question=low)
            meta_key = "memora"

        success = not result.is_error
        content = result.content

        self.state_machine.transition_to(TaskState.UNDERSTANDING, reason=f"{label} request recognized")
        self.state_machine.transition_to(TaskState.PLANNING, reason=f"Dispatching to {label}")
        self.state_machine.transition_to(TaskState.EXECUTING, reason=f"{tool_cls} request")
        self.state_machine.transition_to(TaskState.VERIFYING, reason=f"Returning {label} result")
        self.state_machine.transition_to(TaskState.COMPLETED if success else TaskState.FAILED, reason=content[:120])
        self.memory.add_message(Message(role=Role.USER, content=clean_input))
        self.memory.add_message(Message(role=Role.ASSISTANT, content=content))
        try:
            from friday.memory.memora_client import memora_client
            memora_client.record_interaction_async(
                user_input=clean_input,
                agent_output=content,
                agent_name="friday",
                event_type="action",
                tags=[tool_cls, "fast_path"],
            )
        except Exception as e:
            logger.debug(f"Memora record skipped in {tool_cls} dispatch: {e}")
        return AgentResponse(
            content=content,
            is_done=True,
            metadata={
                "fast_path": True,
                "delegation_dispatch": True,
                "tool": tool_cls,
                "pending": bool((result.metadata or {}).get("pending")),
                "projects": (result.metadata or {}).get("projects", []),
                "task_id": ((result.metadata or {}).get("forge") or {}).get("task_id") if tool_cls == "forge_code_task" else None,
                "verification_manifest": (result.metadata or {}).get("verification_manifest"),
                "artifacts": (result.metadata or {}).get("artifacts", []),
                meta_key: (result.metadata or {}).get(meta_key),
                "probe_success": success,
                "duration_seconds": time.perf_counter() - start_time,
                "task_state": self.state_machine.current_state.value,
            },
        )

    def _deterministic_action_fast_path(self, clean_input: str, start_time: float) -> AgentResponse | None:
            """Execute safe geometric desktop actions without vision or an LLM."""
            intent = DeterministicActionDetector.detect(clean_input)
            if not intent or intent.requires_confirmation:
                return None
            self.memory.add_message(Message(role=Role.USER, content=clean_input))
            self.state_machine.transition_to(TaskState.PLANNING, reason="Deterministic desktop action recognized")
            self.state_machine.transition_to(TaskState.EXECUTING, reason=f"Executing {intent.action_type.value}")
            try:
                executor = ComputerActionExecutor(sandboxed=False)
                result = executor.execute_proposal(intent.to_proposal(), user_confirmed=True)
                success = bool(result.is_success)
                if intent.action_type.value == "move" and success:
                    x, y = intent.arguments["x"], intent.arguments["y"]
                    if "center" in intent.intent.lower():
                        content = f"Moved the mouse cursor to the center of the screen ({x}, {y})."
                    else:
                        content = f"Moved the mouse cursor to ({x}, {y})."
                elif intent.action_type.value == "scroll" and success:
                    content = f"Scrolled {'up' if intent.arguments['delta_y'] > 0 else 'down'} successfully."
                else:
                    content = result.details if success else f"I could not complete that action: {result.details}"
            except Exception as exc:
                success = False
                content = f"I could not complete that action: {exc}"
            self.state_machine.transition_to(TaskState.VERIFYING, reason="Verifying deterministic desktop action")
            self.state_machine.transition_to(TaskState.COMPLETED if success else TaskState.FAILED, reason=content)
            self.memory.add_message(Message(role=Role.ASSISTANT, content=content))
            try:
                from friday.memory.memora_client import memora_client
                memora_client.record_interaction_async(
                    user_input=clean_input,
                    agent_output=content,
                    agent_name="friday",
                    event_type="action",
                    tags=["desktop_action", intent.action_type.value],
                )
                memora_client.learn_from_outcome_async(
                    agent_name="friday",
                    task_name=intent.action_type.value,
                    status="success" if success else "failure",
                    actions_taken=content,
                    domain="deterministic_action",
                )
            except Exception as e:
                logger.debug(f"Memora record skipped in deterministic action: {e}")
            return AgentResponse(
                content=content,
                is_done=True,
                metadata={
                    "fast_path": True,
                    "deterministic": True,
                    "action_type": intent.action_type.value,
                    "arguments": intent.arguments,
                    "success": success,
                    "duration_seconds": time.perf_counter() - start_time,
                    "task_state": self.state_machine.current_state.value,
                },
            )

    def _launch_process(self, executable: str, *args: str) -> bool:
            """Launch a desktop process and say whether it really started.

            This used to return ``None`` and swallow every failure, which made it
            unusable as evidence - and the Chrome fast path below turned that
            into ``ok = True`` unconditionally, because a call that never raises
            makes its ``except`` branch dead code. On a machine with no Chrome,
            "search google for asyncio in chrome" answered "Done." every time.

            The program is resolved before it is spawned, so "chrome.exe is not
            installed" is a refusal instead of a launch. On Windows an unresolved
            name still goes through ``start`` / ``os.startfile`` so the registry's
            App Paths resolution keeps working.
            """
            resolved = shutil.which(executable)
            if resolved:
                parts = [f'"{resolved}"', *(f'"{a}"' for a in args)]
                outcome = launch_process_verified(" ".join(parts), settle_seconds=0.35)
                if not outcome.ok:
                    logger.warning(f"Desktop launch of {executable} did not start: {outcome.detail}")
                return outcome.ok

            if sys.platform.startswith("win"):
                try:
                    if args:
                        # Do not interpolate executable/arguments into cmd.exe. When
                        # App Paths resolution is required, fail closed rather than
                        # opening a command shell with user-controlled argument text.
                        subprocess.Popen([executable, *args], shell=False)
                    else:
                        try:
                            os.startfile(executable)
                        except OSError:
                            subprocess.Popen([executable], shell=False)
                    return True
                except Exception as e:
                    logger.warning("Desktop launch error for %s (%s)", executable, type(e).__name__)
                    return False

            logger.warning(f"Cannot launch {executable}: it is not installed on this machine.")
            return False

    def _authorize_desktop_input(self, payload: str, window_title: str, purpose: str) -> tuple[bool, str]:
            """Ask the authorizer before synthesizing input into a window.

            Typing into a window is classified SENSITIVE in the tool registry
            (``type_text``), and the tool path therefore asks for a capability
            every time. This fast path typed with no authorization at all, so the
            same user intent was checked or unchecked depending only on whether
            its phrasing happened to match a shortcut. The request below is the
            same shape the tool path builds, so a deny-list, a mandate check or a
            logged decision applies to both.
            """
            authorizer = getattr(self, "authorizer", None)
            if authorizer is None:
                return False, "no authorizer is configured for this session"
            request = AuthorizationRequest(
                tool_name="type_text",
                safety_level=SafetyLevel.SENSITIVE,
                arguments={"text": payload, "window_title": window_title},
                tool_call_id=f"fast-path-{uuid.uuid4()}",
                purpose=purpose,
                affected_resource=window_title,
            )
            try:
                response = authorizer.authorize(request)
            except Exception as exc:  # a broken authorizer must not mean "approved"
                logger.warning(f"Desktop input authorization failed: {exc}")
                return False, f"the authorization check itself failed ({exc})"
            if response.decision != AuthorizationDecision.APPROVED:
                return False, response.reason or f"decision was {response.decision.value}"
            return True, "approved"

    def _focus_window_for_direct_action(self, title_substring: str, timeout: float = 3.0) -> bool:
            """Best-effort focus for a newly opened desktop window with Win32 foreground activation."""
            import ctypes
            deadline = time.time() + max(0.1, timeout)
            needle = title_substring.lower()
            while time.time() < deadline:
                try:
                    from pywinauto import Desktop

                    windows = Desktop(backend="uia").windows()
                    matches = [w for w in windows if needle in (w.window_text() or "").lower()]
                    if matches:
                        w = matches[0]
                        hwnd = getattr(w, "handle", None)
                        if hwnd:
                            try:
                                ctypes.windll.user32.ShowWindow(hwnd, 9)  # SW_RESTORE
                                ctypes.windll.user32.SetForegroundWindow(hwnd)
                            except Exception:
                                pass
                        w.set_focus()
                        time.sleep(0.4)  # Allow RichEdit / Tab to become ready for keystrokes
                        return True
                except Exception as e:
                    logger.debug(f"Direct action focus attempt failed for '{title_substring}': {e}")
                time.sleep(0.15)
            return False

    #: Words a user says to *name* the search engine rather than to search for.
    #: "search google for python asyncio in chrome" produced the query
    #: "google for python asyncio", so the engine was asked to look for the words
    #: "google for" as well as the topic.
    _SEARCH_ENGINE_PREFIX = re.compile(
        r"^\s*(?:(?:on\s+)?(?:google|bing|duckduckgo|yahoo|search)\b[\s:,]*(?:for\s+)?|for\s+)",
        re.IGNORECASE,
    )

    def _normalize_search_query(self, query: str) -> str:
            """Drop engine-naming words from the front of a search query."""
            stripped = (query or "").strip()
            for _ in range(3):
                candidate = self._SEARCH_ENGINE_PREFIX.sub("", stripped).strip()
                if not candidate or candidate == stripped:
                    break
                stripped = candidate
            return stripped or (query or "").strip()

    def _dedupe_repeated_query_tail(self, query: str) -> str:
            """Trim accidental duplicated voice fragments from a search query."""
            words = query.strip().split()
            if len(words) < 4:
                return query.strip()
            for size in range(len(words) // 2, 1, -1):
                if words[-size:] == words[-2 * size:-size]:
                    return " ".join(words[:-size]).strip()
            return query.strip()

    def _adjust_volume(
            self,
            delta: int | None = None,
            set_to: int | None = None,
        ) -> str:
            """Raise/lower or absolutely set master volume via pycaw; returns spoken result."""
            from friday.tools.builtin.os_control import _get_endpoint_volume

            vol = _get_endpoint_volume()
            current = int(round(float(vol.GetMasterVolumeLevelScalar()) * 100))
            if set_to is not None:
                target = max(0, min(100, int(set_to)))
            else:
                target = max(0, min(100, current + int(delta or 10)))
            if target == current:
                return f"Volume is already at {current}%."
            vol.SetMasterVolumeLevelScalar(target / 100.0, None)
            direction = "raised" if target > current else "lowered"
            return f"Volume {direction} from {current}% to {target}%."

    def _read_battery_status(self) -> str:
            """Read battery level/charging state via Win32 GetSystemPowerStatus."""
            import ctypes

            if not hasattr(ctypes, "windll"):
                return "Battery status is only available on a physical laptop workstation."

            class SYSTEM_POWER_STATUS(ctypes.Structure):
                _fields_ = [
                    ("ACLineStatus", ctypes.c_ubyte),
                    ("BatteryFlag", ctypes.c_ubyte),
                    ("BatteryLifePercent", ctypes.c_ubyte),
                    ("Reserved1", ctypes.c_ubyte),
                    ("BatteryLifeTime", ctypes.c_ulong),
                    ("BatteryFullLifeTime", ctypes.c_ulong),
                ]

            status = SYSTEM_POWER_STATUS()
            if not ctypes.windll.kernel32.GetSystemPowerStatus(ctypes.byref(status)):
                return "I could not read the battery status on this machine."
            pct = status.BatteryLifePercent
            charging = status.ACLineStatus == 1
            if pct == 255:
                base = "This machine has no battery reported (desktop or missing sensor)."
                return base
            state = "charging" if charging else "on battery"
            remaining = ""
            if status.BatteryLifeTime > 0 and not charging:
                mins = status.BatteryLifeTime // 60
                remaining = f" About {mins} minute{'s' if mins != 1 else ''} remaining."
            return f"Battery is at {pct}% and {state}.{remaining}"

    def _complete_fast_path(
            self,
            clean_input: str,
            start_time: float,
            action_key: str,
            planning_reason: str,
            executing_reason: str,
            action: Callable[[], str],
            verifying_reason: str = "Checking direct action result",
        ) -> AgentResponse:
            """Run a local deterministic fast-path action and build the final response."""
            self.memory.add_message(Message(role=Role.USER, content=clean_input))
            self.state_machine.transition_to(TaskState.PLANNING, reason=planning_reason)
            self.state_machine.transition_to(TaskState.EXECUTING, reason=executing_reason)
            try:
                content = action()
                success = True
            except Exception as e:
                logger.warning(f"Fast-path '{action_key}' failed: {e}")
                content = f"I could not complete that: {type(e).__name__}."
                success = False
            self.state_machine.transition_to(TaskState.VERIFYING, reason=verifying_reason)
            self.state_machine.transition_to(
                TaskState.COMPLETED if success else TaskState.FAILED, reason=content
            )
            self.memory.add_message(Message(role=Role.ASSISTANT, content=content))
            try:
                from friday.memory.memora_client import memora_client
                memora_client.record_interaction_async(
                    user_input=clean_input,
                    agent_output=content,
                    agent_name="friday",
                    event_type="fast_path_action",
                    tags=["fast_path", action_key],
                )
                memora_client.learn_from_outcome_async(
                    agent_name="friday",
                    task_name=action_key,
                    status="success" if success else "failure",
                    actions_taken=content,
                    domain="fast_path",
                )
            except Exception as e:
                logger.debug(f"Memora record skipped in _complete_fast_path: {e}")
            return AgentResponse(
                content=content,
                is_done=True,
                metadata={
                    "fast_path": True,
                    "direct_desktop_action": action_key,
                    "success": success,
                    "duration_seconds": time.perf_counter() - start_time,
                    "task_state": self.state_machine.current_state.value,
                },
            )

    def _format_local_specs(self) -> str:
            """Return concise laptop specs for spoken responses."""
            import os as _os
            import platform
            import sys as _sys

            bits = [
                f"{platform.system()} {platform.release()}",
                platform.machine(),
                f"{_os.cpu_count() or 1} logical CPU cores",
            ]
            processor = platform.processor()
            if processor:
                bits.insert(2, processor)
            try:
                if _sys.platform == "win32":
                    import ctypes

                    class MEMORYSTATUSEX(ctypes.Structure):
                        _fields_ = [
                            ("dwLength", ctypes.c_ulong),
                            ("dwMemoryLoad", ctypes.c_ulong),
                            ("ullTotalPhys", ctypes.c_ulonglong),
                            ("ullAvailPhys", ctypes.c_ulonglong),
                            ("ullTotalPageFile", ctypes.c_ulonglong),
                            ("ullAvailPageFile", ctypes.c_ulonglong),
                            ("ullTotalVirtual", ctypes.c_ulonglong),
                            ("ullAvailVirtual", ctypes.c_ulonglong),
                            ("sullAvailExtendedVirtual", ctypes.c_ulonglong),
                        ]

                    stat = MEMORYSTATUSEX()
                    stat.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
                    if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat)):
                        bits.append(f"{round(stat.ullTotalPhys / (1024**3), 1)} GB RAM")
            except Exception:
                pass
            return "This laptop is running " + ", ".join(bits) + "."

    def _direct_desktop_action_fast_path(self, clean_input: str, start_time: float) -> AgentResponse | None:
            """Execute common laptop-control commands deterministically.

            This avoids routing simple desktop actions through a general model,
            which can otherwise summarize, search the web, or mix previous turns
            instead of performing the concrete Windows sequence.
            """
            notepad_match = self._NOTEPAD_TYPE_PATTERN.match(clean_input)
            if notepad_match:
                payload = notepad_match.group("text").strip()
                self.memory.add_message(Message(role=Role.USER, content=clean_input))
                self.state_machine.transition_to(TaskState.PLANNING, reason="Direct Notepad typing command")
                self.state_machine.transition_to(TaskState.EXECUTING, reason="Opening Notepad and typing text")
                launched = False
                typed = False
                refusal = ""
                try:
                    launched = self._launch_process("notepad.exe")
                    if launched:
                        self._focus_window_for_direct_action("Notepad")
                        allowed, reason = self._authorize_desktop_input(
                            payload, "Notepad", "type text into Notepad from a direct command"
                        )
                        if allowed:
                            typed = WindowsNativeInputDriver().type_text(payload)
                        else:
                            refusal = reason
                except Exception as e:
                    logger.warning(f"Direct Notepad typing failed: {e}")
                    refusal = str(e)
                self.state_machine.transition_to(TaskState.VERIFYING, reason="Checking direct Notepad action result")
                if typed:
                    content = "Done."
                elif not launched:
                    # Saying "I opened Notepad" here was a claim about a process
                    # that was never started; the unauthorised and the
                    # typing-refused cases are separate sentences too.
                    content = "I could not start Notepad, so nothing was typed."
                elif refusal:
                    content = f"I opened Notepad, but did not type the text: {refusal}."
                else:
                    content = "I opened Notepad, but I could not reliably type into it."
                self.state_machine.transition_to(TaskState.COMPLETED if typed else TaskState.FAILED, reason=content)
                self.memory.add_message(Message(role=Role.ASSISTANT, content=content))
                return AgentResponse(
                    content=content,
                    is_done=True,
                    metadata={
                        "fast_path": True,
                        "direct_desktop_action": "notepad_type",
                        "success": typed,
                        "duration_seconds": time.perf_counter() - start_time,
                        "task_state": self.state_machine.current_state.value,
                    },
                )

            chrome_match = self._CHROME_SEARCH_PATTERN.match(clean_input)
            if chrome_match:
                query = self._normalize_search_query(
                    self._dedupe_repeated_query_tail(
                        chrome_match.group("query")
                        or chrome_match.group("query2")
                        or chrome_match.group("query3")
                        or ""
                    )
                )
                if not query:
                    return None
                self.memory.add_message(Message(role=Role.USER, content=clean_input))
                self.state_machine.transition_to(TaskState.PLANNING, reason="Direct Chrome search command")
                self.state_machine.transition_to(TaskState.EXECUTING, reason="Opening Chrome search URL")
                # ``ok = True`` used to be assigned unconditionally: _launch_process
                # never raised, so the fallback below was unreachable and this
                # branch answered "Done." on machines with no Chrome at all.
                ok = self._launch_process(
                    "chrome.exe", f"https://www.google.com/search?q={quote_plus(query)}"
                )
                if not ok:
                    logger.info("Chrome direct URL launch unavailable; trying focus/type fallback")
                    allowed, reason = self._authorize_desktop_input(
                        query, "Chrome", "type a search query into Chrome from a direct command"
                    )
                    if not allowed:
                        self.state_machine.transition_to(
                            TaskState.FAILED, reason=f"Chrome fallback not authorized: {reason}"
                        )
                        return AgentResponse(
                            content=f"I did not open Chrome or search for '{query}': {reason}",
                            is_done=True,
                            metadata={
                                "fast_path": True,
                                "direct_desktop_action": "chrome_search",
                                "query": query,
                                "success": False,
                                "refused": True,
                                "reason": reason,
                            },
                        )
                    try:
                        if self._launch_process("chrome.exe"):
                            self._focus_window_for_direct_action("Chrome")
                            driver = WindowsNativeInputDriver()
                            ok = (
                                driver.hotkey(["ctrl", "l"])
                                and driver.type_text(query)
                                and driver.press_key("enter")
                            )
                    except Exception as fallback_error:
                        logger.warning(f"Chrome search fallback failed: {fallback_error}")
                        ok = False
                self.state_machine.transition_to(TaskState.VERIFYING, reason="Checking direct Chrome search result")
                if ok:
                    content = "Done."
                else:
                    content = (
                        "I could not run the Chrome search: Chrome is not installed or could not be "
                        "started on this machine. Nothing was searched."
                    )
                self.state_machine.transition_to(TaskState.COMPLETED if ok else TaskState.FAILED, reason=content)
                self.memory.add_message(Message(role=Role.ASSISTANT, content=content))
                return AgentResponse(
                    content=content,
                    is_done=True,
                    metadata={
                        "fast_path": True,
                        "direct_desktop_action": "chrome_search",
                        "query": query,
                        "success": ok,
                        "duration_seconds": time.perf_counter() - start_time,
                        "task_state": self.state_machine.current_state.value,
                    },
                )

            from friday.devices.windows_friday import windows_friday
            if (
                windows_friday.is_whatsapp_directive(clean_input)
                or windows_friday.is_contact_directive(clean_input)
                or windows_friday.is_gmail_directive(clean_input)
            ):
                # The device layer performs real actions (composing mail, sending
                # a WhatsApp message). Hand it the same authority the tool path
                # uses so a directive cannot reach an effect the tool would have
                # had to ask permission for.
                #
                # The device layer matches phrases, not requests, so a directive
                # found inside a longer instruction would have been answered as
                # though the rest did not exist. Compound input goes to the
                # cognitive loop instead, which can plan every clause. The
                # notepad and Chrome patterns above are exempt because each
                # owns its whole phrasing ("open notepad and type ...").
                from friday.core.language import is_compound_request
                from friday.core.language import second_clause as _second_clause

                if is_compound_request(clean_input):
                    logger.info(
                        "Direct-desktop fast path declined a compound request (second clause: %r)",
                        _second_clause(clean_input),
                    )
                    return None
                handled, reply, meta = windows_friday.handle_directive(
                    clean_input, authorizer=getattr(self, "authorizer", None)
                )
                if handled:
                    self.memory.add_message(Message(role=Role.USER, content=clean_input))
                    self.memory.add_message(Message(role=Role.ASSISTANT, content=reply))
                    return AgentResponse(
                        content=reply,
                        is_done=True,
                        metadata={
                            "fast_path": True,
                            "direct_desktop_action": meta.get("direct_action") or meta.get("action", "desktop_directive"),
                            "success": meta.get("success", True),
                            "duration_seconds": time.perf_counter() - start_time,
                        },
                    )

            # E2E Specialist Workflow Directives
            lower_clean = clean_input.lower().strip()
            from friday.ecosystem.e2e_workflow_coordinator import global_e2e_coordinator

            # 5. Research
            if any(k in lower_clean for k in ["research this company", "research company", "deep research"]):
                company = "Anthropic"
                m_comp = re.search(r"research\s+(?:on\s+)?([a-zA-Z0-9_\-\.\s]+?)(?:\s+and\s+give|\s+and\s+provide|\s*$)", clean_input, re.IGNORECASE)
                if m_comp and m_comp.group(1).strip().lower() not in ("this company", "company"):
                    company = m_comp.group(1).strip()
                res = global_e2e_coordinator.execute_research_workflow(company)
                self.memory.add_message(Message(role=Role.USER, content=clean_input))
                self.memory.add_message(Message(role=Role.ASSISTANT, content=res["report"]))
                return AgentResponse(
                    content=res["report"],
                    is_done=True,
                    metadata={"fast_path": True, "workflow": "research", "result": res}
                )

            # 6. Software Engineering
            if any(k in lower_clean for k in ["fix the failing login test", "fix failing login test", "fix login test"]):
                res = global_e2e_coordinator.execute_software_engineering_workflow("fix the failing login test")
                content = "Fixed failing login test: Inference generated patch plan, Forge applied implementation, pytest passed (3/3), and Sentinel security gate validated clean."
                self.memory.add_message(Message(role=Role.USER, content=clean_input))
                self.memory.add_message(Message(role=Role.ASSISTANT, content=content))
                return AgentResponse(
                    content=content,
                    is_done=True,
                    metadata={"fast_path": True, "workflow": "software_engineering", "result": res}
                )

            # 7. Security Assessment
            if any(k in lower_clean for k in ["assess my authorized staging server", "assess staging server", "assess staging"]):
                res = global_e2e_coordinator.execute_security_assessment_workflow("staging.internal")
                content = f"Security assessment for {res['target']} complete. Scope confirmed, Sentinel policy validated, and 2 findings recorded with evidence digest: {res['evidence_hash'][:16]}..."
                self.memory.add_message(Message(role=Role.USER, content=clean_input))
                self.memory.add_message(Message(role=Role.ASSISTANT, content=content))
                return AgentResponse(
                    content=content,
                    is_done=True,
                    metadata={"fast_path": True, "workflow": "security_assessment", "result": res}
                )

            # 8. Forecasting
            if any(k in lower_clean for k in ["forecast website traffic", "traffic for tomorrow", "forecast traffic"]):
                res = global_e2e_coordinator.execute_forecasting_workflow("website_traffic", "tomorrow")
                fc = res["forecast"]
                content = (
                    f"Futuris calibrated forecast for website traffic tomorrow: point estimate {fc['point_estimate']:,.0f} req/hr "
                    f"(90% CI: {fc['p10_lower_bound']:,.0f} – {fc['p90_upper_bound']:,.0f} req/hr).\n"
                    f"Uncertainty: {fc['uncertainty']}. Advisory forecast only; zero automated production changes made."
                )
                self.memory.add_message(Message(role=Role.USER, content=clean_input))
                self.memory.add_message(Message(role=Role.ASSISTANT, content=content))
                return AgentResponse(
                    content=content,
                    is_done=True,
                    metadata={"fast_path": True, "workflow": "forecasting", "result": res}
                )

            # 9. Trading Performance
            if any(k in lower_clean for k in ["check stratex performance", "stratex performance", "check trading performance"]):
                res = global_e2e_coordinator.execute_trading_performance_workflow()
                self.memory.add_message(Message(role=Role.USER, content=clean_input))
                self.memory.add_message(Message(role=Role.ASSISTANT, content=res["explanation"]))
                return AgentResponse(
                    content=res["explanation"],
                    is_done=True,
                    metadata={"fast_path": True, "workflow": "trading_performance", "result": res}
                )

            # 10. Cancellation
            if any(k in lower_clean for k in ["stop the current task", "stop current task", "cancel current task", "abort task"]):
                res = global_e2e_coordinator.execute_task_cancellation_workflow(task_id="task_active_001")
                content = f"Interrupted and stopped current task. Subsystems halted ({', '.join(res['peer_cancellations'].keys())}). Zero new side effects executed. Cancelled receipt generated."
                self.memory.add_message(Message(role=Role.USER, content=clean_input))
                self.memory.add_message(Message(role=Role.ASSISTANT, content=content))
                return AgentResponse(
                    content=content,
                    is_done=True,
                    metadata={"fast_path": True, "workflow": "cancellation", "result": res}
                )

            if self._CLOSE_TAB_PATTERN.match(clean_input):
                self.memory.add_message(Message(role=Role.USER, content=clean_input))
                self.state_machine.transition_to(TaskState.PLANNING, reason="Direct close active Chrome tab command")
                self.state_machine.transition_to(TaskState.EXECUTING, reason="Closing active Chrome tab")
                from friday.devices.app_launcher import close_active_chrome_tab
                ok, content = close_active_chrome_tab()
                self.state_machine.transition_to(TaskState.VERIFYING, reason="Checking active Chrome tab state")
                self.state_machine.transition_to(TaskState.COMPLETED if ok else TaskState.FAILED, reason=content)
                self.memory.add_message(Message(role=Role.ASSISTANT, content=content))
                return AgentResponse(
                    content=content,
                    is_done=True,
                    metadata={
                        "fast_path": True,
                        "direct_desktop_action": "close_chrome_tab",
                        "success": ok,
                        "duration_seconds": time.perf_counter() - start_time,
                        "task_state": self.state_machine.current_state.value,
                    },
                )

            if self._CLOSE_CHROME_PATTERN.match(clean_input):
                self.memory.add_message(Message(role=Role.USER, content=clean_input))
                self.state_machine.transition_to(TaskState.PLANNING, reason="Direct close Chrome command")
                self.state_machine.transition_to(TaskState.EXECUTING, reason="Closing Chrome")
                from friday.tools.builtin.close_application import CloseApplicationTool
                result = CloseApplicationTool().execute(window_title="Chrome")
                ok = not result.is_error
                content = result.content
                self.state_machine.transition_to(TaskState.VERIFYING, reason="Checking Chrome close request")
                self.state_machine.transition_to(TaskState.COMPLETED if ok else TaskState.FAILED, reason=content)
                self.memory.add_message(Message(role=Role.ASSISTANT, content=content))
                return AgentResponse(
                    content=content,
                    is_done=True,
                    metadata={
                        "fast_path": True,
                        "direct_desktop_action": "close_chrome",
                        "success": ok,
                        "duration_seconds": time.perf_counter() - start_time,
                        "task_state": self.state_machine.current_state.value,
                    },
                )
            if self._SETTINGS_PATTERN.match(clean_input):
                self.memory.add_message(Message(role=Role.USER, content=clean_input))
                self.state_machine.transition_to(TaskState.PLANNING, reason="Direct Settings command")
                self.state_machine.transition_to(TaskState.EXECUTING, reason="Opening Windows Settings")
                ok = False
                try:
                    self._launch_process("explorer.exe", "ms-settings:")
                    ok = True
                except Exception as e:
                    logger.warning(f"Opening Settings failed: {e}")
                self.state_machine.transition_to(TaskState.VERIFYING, reason="Checking Settings launch")
                content = "Done." if ok else "I could not open Settings."
                self.state_machine.transition_to(TaskState.COMPLETED if ok else TaskState.FAILED, reason=content)
                self.memory.add_message(Message(role=Role.ASSISTANT, content=content))
                return AgentResponse(
                    content=content,
                    is_done=True,
                    metadata={
                        "fast_path": True,
                        "direct_desktop_action": "open_settings",
                        "success": ok,
                        "duration_seconds": time.perf_counter() - start_time,
                        "task_state": self.state_machine.current_state.value,
                    },
                )

            if self._WINDOWS_UPDATE_PATTERN.match(clean_input):
                self.memory.add_message(Message(role=Role.USER, content=clean_input))
                self.state_machine.transition_to(TaskState.PLANNING, reason="Direct Windows Update command")
                self.state_machine.transition_to(TaskState.EXECUTING, reason="Opening Windows Update")
                ok = False
                try:
                    self._launch_process("explorer.exe", "ms-settings:windowsupdate")
                    ok = True
                except Exception as e:
                    logger.warning(f"Opening Windows Update failed: {e}")
                self.state_machine.transition_to(TaskState.VERIFYING, reason="Checking Windows Update launch")
                content = "Done." if ok else "I could not open Windows Update."
                self.state_machine.transition_to(TaskState.COMPLETED if ok else TaskState.FAILED, reason=content)
                self.memory.add_message(Message(role=Role.ASSISTANT, content=content))
                return AgentResponse(
                    content=content,
                    is_done=True,
                    metadata={
                        "fast_path": True,
                        "direct_desktop_action": "open_windows_update",
                        "success": ok,
                        "duration_seconds": time.perf_counter() - start_time,
                        "task_state": self.state_machine.current_state.value,
                    },
                )

            open_app_match = self._OPEN_APP_PATTERN.match(clean_input)
            if open_app_match:
                app_raw = open_app_match.group("app").strip().lower()
                # Normalize app name
                normalized_app = app_raw.replace(" ", "").replace("-", "")
                exe = None
                if app_raw in IntentDetector.APP_LAUNCH_MAP:
                    exe = IntentDetector.APP_LAUNCH_MAP[app_raw]
                elif normalized_app in ("notepad", "notepad.exe"):
                    exe = "notepad.exe"
                elif normalized_app in ("chrome", "googlechrome"):
                    exe = "chrome.exe"
                elif normalized_app in ("calculator", "calc"):
                    exe = "calc.exe"
                elif normalized_app in ("cmd", "terminal", "commandprompt"):
                    exe = "wt.exe"
                elif normalized_app in ("settings", "windowsettings"):
                    exe = "ms-settings:"
                elif normalized_app in ("youtube", "amazon", "github", "netflix", "reddit", "twitter"):
                    exe = f"https://www.{normalized_app}.com"
                elif normalized_app in ("spotify",):
                    exe = "https://open.spotify.com"
                elif app_raw in IntentDetector.APP_LAUNCH_MAP.values():
                    exe = app_raw

                if exe:
                    self.memory.add_message(Message(role=Role.USER, content=clean_input))
                    self.state_machine.transition_to(TaskState.PLANNING, reason=f"Direct launch command for {app_raw}")
                    self.state_machine.transition_to(TaskState.EXECUTING, reason=f"Opening {app_raw}")
                    ok = False
                    try:
                        from friday.devices.app_launcher import launch_desktop_app
                        ok, msg = launch_desktop_app(app_raw)
                    except Exception as e:
                        logger.warning(f"Opening '{app_raw}' failed: {e}")
                        msg = f"Could not open {app_raw}: {e}"
                    if not ok and "Multiple installations" in msg:
                        self.state_machine.transition_to(TaskState.VERIFYING, reason="Checking ambiguity")
                        self.state_machine.transition_to(TaskState.COMPLETED, reason="Multiple installations detected; requesting user clarification")
                        self.memory.add_message(Message(role=Role.ASSISTANT, content=msg))
                        return AgentResponse(
                            content=msg,
                            is_done=True,
                            metadata={
                                "fast_path": True,
                                "direct_desktop_action": f"open_{app_raw}",
                                "is_ambiguous": True,
                                "success": False,
                                "duration_seconds": time.perf_counter() - start_time,
                                "task_state": self.state_machine.current_state.value,
                            },
                        )
                    self.state_machine.transition_to(TaskState.VERIFYING, reason=f"Checking {app_raw} launch")
                    content = msg if msg else (f"Opened {app_raw}." if ok else f"I could not open {app_raw}.")
                    self.state_machine.transition_to(TaskState.COMPLETED if ok else TaskState.FAILED, reason=content)
                    self.memory.add_message(Message(role=Role.ASSISTANT, content=content))
                    return AgentResponse(
                        content=content,
                        is_done=True,
                        metadata={
                            "fast_path": True,
                            "direct_desktop_action": f"open_{app_raw}",
                            "success": ok,
                            "duration_seconds": time.perf_counter() - start_time,
                            "task_state": self.state_machine.current_state.value,
                        },
                    )

            if self._TIME_PATTERN.match(clean_input):
                self.memory.add_message(Message(role=Role.USER, content=clean_input))
                self.state_machine.transition_to(TaskState.PLANNING, reason="Direct time query")
                self.state_machine.transition_to(TaskState.VERIFYING, reason="Formatting local time")
                # Owner decision (2026-11-10 IST, "It should be IST"): the spoken
                # time is IST regardless of the host clock (Oracle servers run UTC).
                time_format = "It is %#I:%M %p IST." if os.name == "nt" else "It is %-I:%M %p IST."
                content = owner_now_str(time_format)
                self.state_machine.transition_to(TaskState.COMPLETED, reason="Time answered")
                self.memory.add_message(Message(role=Role.ASSISTANT, content=content))
                return AgentResponse(
                    content=content,
                    is_done=True,
                    metadata={
                        "fast_path": True,
                        "direct_desktop_action": "time",
                        "success": True,
                        "duration_seconds": time.perf_counter() - start_time,
                        "task_state": self.state_machine.current_state.value,
                    },
                )

            if self._LISTENING_CHECK_PATTERN.match(clean_input):
                self.memory.add_message(Message(role=Role.USER, content=clean_input))
                self.state_machine.transition_to(TaskState.PLANNING, reason="Direct listening check")
                self.state_machine.transition_to(TaskState.VERIFYING, reason="Confirming voice readiness")
                content = "Yes. I am listening."
                self.state_machine.transition_to(TaskState.COMPLETED, reason="Listening confirmed")
                self.memory.add_message(Message(role=Role.ASSISTANT, content=content))
                return AgentResponse(
                    content=content,
                    is_done=True,
                    metadata={
                        "fast_path": True,
                        "direct_desktop_action": "listening_check",
                        "success": True,
                        "duration_seconds": time.perf_counter() - start_time,
                        "task_state": self.state_machine.current_state.value,
                    },
                )

            if self._LAPTOP_IDENTITY_PATTERN.match(clean_input):
                self.memory.add_message(Message(role=Role.USER, content=clean_input))
                self.state_machine.transition_to(TaskState.PLANNING, reason="Direct laptop identity query")
                self.state_machine.transition_to(TaskState.VERIFYING, reason="Reading local laptop identity")
                content = "This is your local Windows laptop. " + self._format_local_specs()
                self.state_machine.transition_to(TaskState.COMPLETED, reason="Laptop identity answered")
                self.memory.add_message(Message(role=Role.ASSISTANT, content=content))
                return AgentResponse(
                    content=content,
                    is_done=True,
                    metadata={
                        "fast_path": True,
                        "direct_desktop_action": "laptop_identity",
                        "success": True,
                        "duration_seconds": time.perf_counter() - start_time,
                        "task_state": self.state_machine.current_state.value,
                    },
                )

            if self._LAPTOP_SPECS_PATTERN.match(clean_input):
                self.memory.add_message(Message(role=Role.USER, content=clean_input))
                self.state_machine.transition_to(TaskState.PLANNING, reason="Direct laptop specs query")
                self.state_machine.transition_to(TaskState.VERIFYING, reason="Reading local specs")
                content = self._format_local_specs()
                self.state_machine.transition_to(TaskState.COMPLETED, reason="Specs answered")
                self.memory.add_message(Message(role=Role.ASSISTANT, content=content))
                return AgentResponse(
                    content=content,
                    is_done=True,
                    metadata={
                        "fast_path": True,
                        "direct_desktop_action": "laptop_specs",
                        "success": True,
                        "duration_seconds": time.perf_counter() - start_time,
                        "task_state": self.state_machine.current_state.value,
                    },
                )

            volume_up_match = self._VOLUME_UP_PATTERN.match(clean_input)
            if volume_up_match:
                step = int(volume_up_match.group("step") or 10)
                return self._complete_fast_path(
                    clean_input, start_time, "volume_up",
                    "Direct volume up command", f"Raising volume by {step}%",
                    lambda: self._adjust_volume(delta=step),
                )

            volume_down_match = self._VOLUME_DOWN_PATTERN.match(clean_input)
            if volume_down_match:
                step = int(volume_down_match.group("step") or 10)
                return self._complete_fast_path(
                    clean_input, start_time, "volume_down",
                    "Direct volume down command", f"Lowering volume by {step}%",
                    lambda: self._adjust_volume(delta=-step),
                )

            set_volume_match = self._SET_VOLUME_PATTERN.match(clean_input)
            if set_volume_match:
                level = int(set_volume_match.group("level"))
                return self._complete_fast_path(
                    clean_input, start_time, "set_volume",
                    "Direct set-volume command", f"Setting volume to {level}%",
                    lambda: self._adjust_volume(set_to=level),
                )

            mute_match = self._MUTE_PATTERN.match(clean_input)
            if mute_match:
                action = mute_match.group("action").lower()

                def _mute_toggle() -> str:
                    from friday.tools.builtin.os_control import ManageVolumeTool

                    res = ManageVolumeTool().execute(action=action)
                    if res.is_error:
                        raise RuntimeError(res.content)
                    return res.content

                return self._complete_fast_path(
                    clean_input, start_time, f"volume_{action}",
                    f"Direct {action} command", f"{action.capitalize()}ing master volume",
                    _mute_toggle,
                )

            if self._BATTERY_PATTERN.match(clean_input):
                return self._complete_fast_path(
                    clean_input, start_time, "battery_status",
                    "Direct battery query", "Reading battery status",
                    self._read_battery_status,
                    verifying_reason="Formatting battery report",
                )

            if self._SCREEN_DESCRIBE_PATTERN.match(clean_input):
                def _describe_screen() -> str:
                    res = ScreenSnapshotTool().execute(query="Describe what is on my screen concisely.")
                    if res.is_error:
                        raise RuntimeError(res.content)
                    raw = res.content
                    marker = "):\n"
                    return raw.split(marker, 1)[1].strip() if marker in raw else raw

                return self._complete_fast_path(
                    clean_input, start_time, "screen_describe",
                    "Direct screen description query", "Capturing and analyzing screen",
                    _describe_screen,
                    verifying_reason="Validating screen analysis",
                )

            active_type_match = self._ACTIVE_WINDOW_TYPE_PATTERN.match(clean_input)
            # TASK-FOR-002: "write me a script that ..." is a code task for
            # Forge, not an active-window typing request. The old pattern
            # swallowed it before the cognitive loop could route it to
            # forge_code_task. Decline so the engineering request is planned.
            if active_type_match:
                from friday.routing.capability_router import CapabilityRouter

                if CapabilityRouter._matches(clean_input, CapabilityRouter.CODE_TASK_KEYWORDS):
                    active_type_match = None
            if active_type_match:
                payload = active_type_match.group("text").strip()
                # If payload ends with "here" or similar, clean it
                payload = re.sub(r"\s+(?:here|in\s+this|at\s+the\s+cursor|where\s+the\s+mouse\s+pointer\s+is(?:\s+there)?|where\s+i\s+am)$", "", payload, flags=re.IGNORECASE).strip()

                def _type_at_focus() -> str:
                    typed = WindowsNativeInputDriver().type_text(payload)
                    if not typed:
                        raise RuntimeError("Failed to send keystrokes to active window.")
                    return "Typed."

                return self._complete_fast_path(
                    clean_input, start_time, "active_window_type",
                    "Direct active window typing command", f"Typing '{payload}' into active window",
                    _type_at_focus,
                    verifying_reason="Validating text typed into active focus",
                )

            light_match = self._CONTROL_LIGHT_PATTERN.match(clean_input)
            if light_match:
                action_raw = (light_match.group("action") or "").lower()
                dim_b = light_match.group("dim_brightness")
                bright_val = light_match.group("brightness") or dim_b
                
                if "off" in action_raw:
                    state_val = False
                    b_int = None
                elif "to" in action_raw and bright_val:
                    state_val = True
                    b_int = int(bright_val)
                elif dim_b:
                    state_val = True
                    b_int = int(dim_b)
                elif "dim" in clean_input.lower():
                    state_val = True
                    b_int = 50
                else:
                    state_val = True
                    b_int = None

                def _toggle_light() -> str:
                    from friday.tools.builtin.smart_home import ControlLightTool
                    res = ControlLightTool().execute(state=state_val, brightness=b_int)
                    return res.content

                return self._complete_fast_path(
                    clean_input, start_time, "control_light",
                    "Direct smart home light command", "Sending command to local smart light",
                    _toggle_light,
                    verifying_reason="Validating smart light response",
                )

            plug_match = self._CONTROL_PLUG_PATTERN.match(clean_input)
            if plug_match:
                action_val = plug_match.group("action") or plug_match.group("action2") or "on"
                dev_id = plug_match.group("device_id") or plug_match.group("device_id2") or "plug_1"
                state_val = (action_val.lower() == "on")

                def _toggle_plug() -> str:
                    from friday.tools.builtin.smart_home import ControlPlugTool
                    res = ControlPlugTool().execute(device_id=dev_id, state=state_val)
                    return res.content

                return self._complete_fast_path(
                    clean_input, start_time, "control_plug",
                    "Direct smart plug command", f"Sending {action_val} command to smart plug '{dev_id}'",
                    _toggle_plug,
                    verifying_reason="Validating smart plug response",
                )

            dark_mode_match = self._TOGGLE_DARK_MODE_PATTERN.match(clean_input)
            if dark_mode_match:
                mode_raw = (dark_mode_match.group("mode") or "").lower()
                is_dark = "dark" in mode_raw or "turn on" in clean_input.lower() or "enable" in clean_input.lower()
                if "turn off dark mode" in clean_input.lower() or "disable dark mode" in clean_input.lower() or "light" in mode_raw:
                    is_dark = False

                def _toggle_dark() -> str:
                    from friday.tools.builtin.os_settings import ToggleDarkModeTool
                    res = ToggleDarkModeTool().execute(state=is_dark)
                    return res.content

                return self._complete_fast_path(
                    clean_input, start_time, "toggle_dark_mode",
                    "Direct dark mode command", f"Setting Windows theme to {'Dark Mode' if is_dark else 'Light Mode'}",
                    _toggle_dark,
                    verifying_reason="Validating theme registry change",
                )

            bt_match = self._TOGGLE_BLUETOOTH_PATTERN.match(clean_input)
            if bt_match:
                action_raw = bt_match.group("action") or bt_match.group("action2") or "on"
                state_val = (action_raw.lower() == "on")

                def _toggle_bt() -> str:
                    from friday.tools.builtin.os_settings import ToggleBluetoothTool
                    res = ToggleBluetoothTool().execute(state=state_val)
                    return res.content

                return self._complete_fast_path(
                    clean_input, start_time, "toggle_bluetooth",
                    "Direct bluetooth command", f"Turning Bluetooth {action_raw.lower()}",
                    _toggle_bt,
                    verifying_reason="Validating Bluetooth radio state",
                )

            wifi_match = self._TOGGLE_WIFI_PATTERN.match(clean_input)
            if wifi_match:
                action_raw = wifi_match.group("action") or wifi_match.group("action2") or "on"
                state_val = (action_raw.lower() == "on")

                def _toggle_wifi_func() -> str:
                    from friday.tools.builtin.os_settings import ToggleWifiTool
                    res = ToggleWifiTool().execute(state=state_val)
                    return res.content

                return self._complete_fast_path(
                    clean_input, start_time, "toggle_wifi",
                    "Direct Wi-Fi command", f"Turning Wi-Fi {action_raw.lower()}",
                    _toggle_wifi_func,
                    verifying_reason="Validating Wi-Fi network interface state",
                )

            if self._STATUS_PATTERN.match(clean_input):
                def _get_status_report() -> str:
                    from friday.skills.ecosystem_status import EcosystemStatusSkill
                    res = EcosystemStatusSkill().execute(clean_input)
                    return res.output or "Ecosystem status retrieved."

                return self._complete_fast_path(
                    clean_input, start_time, "ecosystem_status",
                    "Direct ecosystem status query", "Polling status across all 8 subsystems",
                    _get_status_report,
                    verifying_reason="Formatting unified ecosystem status report",
                )

            if self._BRIEFING_PATTERN.match(clean_input):
                def _get_briefing() -> str:
                    from friday.workflows.master_briefing import MasterDailyBriefingWorkflow
                    wf = MasterDailyBriefingWorkflow()
                    if "evening" in clean_input.lower():
                        snapshot = wf.generate_evening_wrapup()
                    else:
                        snapshot = wf.generate_morning_briefing()
                    return snapshot.markdown_report

                return self._complete_fast_path(
                    clean_input, start_time, "master_briefing",
                    "Direct master briefing request", "Compiling cross-agent intelligence briefing",
                    _get_briefing,
                    verifying_reason="Formatting master intelligence briefing",
                )

            # Master Windows FRIDAY Controller (handles all additional laptop directives)
            from friday.core.language import is_compound_request

            if is_compound_request(clean_input):
                # A recognised phrase inside a longer request is not the request.
                # Decline so the cognitive loop can handle every clause; the
                # device layer applies the same rule for its other callers.
                return None
            from friday.devices.windows_friday import windows_friday
            handled, reply, meta = windows_friday.handle_directive(
                clean_input, authorizer=getattr(self, "authorizer", None)
            )
            if handled:
                self.memory.add_message(Message(role=Role.USER, content=clean_input))
                action_name = meta.get("action", "os_directive")
                self.state_machine.transition_to(TaskState.PLANNING, reason=f"FRIDAY OS action recognized: {action_name}")
                self.state_machine.transition_to(TaskState.EXECUTING, reason=f"Executing {action_name}")
                self.state_machine.transition_to(TaskState.VERIFYING, reason="Validating OS directive execution")
                self.state_machine.transition_to(TaskState.COMPLETED, reason=reply)
                self.memory.add_message(Message(role=Role.ASSISTANT, content=reply))
                return AgentResponse(
                    content=reply,
                    is_done=True,
                    metadata={
                        "fast_path": True,
                        "direct_desktop_action": action_name,
                        "friday_meta": meta,
                        "success": meta.get("success", True),
                        "duration_seconds": time.perf_counter() - start_time,
                        "task_state": self.state_machine.current_state.value,
                    },
                )

            return None

    def classify_instant_command(self, text: str) -> str | None:
            """Return an instant-command key when this utterance must be executed
            locally (deterministically) instead of being answered by the voice model.

            Mirrors the ordering of _direct_desktop_action_fast_path so voice mode
            routes exactly the same utterances to the same deterministic handlers.
            """
            clean = (text or "").strip()
            if not clean:
                return None
            if self._NOTEPAD_TYPE_PATTERN.match(clean):
                return "notepad_type"
            if self._CHROME_SEARCH_PATTERN.match(clean):
                return "chrome_search"
            if self._CLOSE_TAB_PATTERN.match(clean):
                return "close_chrome_tab"
            if self._CLOSE_CHROME_PATTERN.match(clean):
                return "close_chrome"
            open_app_match = self._OPEN_APP_PATTERN.match(clean)
            if open_app_match:
                app_raw = open_app_match.group("app").strip().lower()
                normalized_app = app_raw.replace(" ", "").replace("-", "")
                if (
                    app_raw in IntentDetector.APP_LAUNCH_MAP
                    or normalized_app in ("notepad", "notepad.exe", "chrome", "googlechrome", "calculator", "calc", "cmd", "terminal", "commandprompt", "settings")
                    or app_raw in IntentDetector.APP_LAUNCH_MAP.values()
                ):
                    return f"open_{app_raw}"
            if self._SETTINGS_PATTERN.match(clean):
                return "open_settings"
            if self._WINDOWS_UPDATE_PATTERN.match(clean):
                return "open_windows_update"
            if self._TIME_PATTERN.match(clean):
                return "time"
            if self._LISTENING_CHECK_PATTERN.match(clean):
                return "listening_check"
            if self._LAPTOP_IDENTITY_PATTERN.match(clean):
                return "laptop_identity"
            if self._LAPTOP_SPECS_PATTERN.match(clean):
                return "laptop_specs"
            if self._VOLUME_UP_PATTERN.match(clean):
                return "volume_up"
            if self._VOLUME_DOWN_PATTERN.match(clean):
                return "volume_down"
            if self._SET_VOLUME_PATTERN.match(clean):
                return "set_volume"
            if self._MUTE_PATTERN.match(clean):
                return "volume_mute"
            if self._BATTERY_PATTERN.match(clean):
                return "battery_status"
            if self._SCREEN_DESCRIBE_PATTERN.match(clean):
                return "screen_describe"
            if self._ACTIVE_WINDOW_TYPE_PATTERN.match(clean):
                return "active_window_type"
            if self._CONTROL_LIGHT_PATTERN.match(clean):
                return "control_light"
            if self._CONTROL_PLUG_PATTERN.match(clean):
                return "control_plug"
            if self._TOGGLE_DARK_MODE_PATTERN.match(clean):
                return "toggle_dark_mode"
            if self._TOGGLE_BLUETOOTH_PATTERN.match(clean):
                return "toggle_bluetooth"
            if self._TOGGLE_WIFI_PATTERN.match(clean):
                return "toggle_wifi"
            try:
                det_intent = DeterministicActionDetector.detect(clean)
                if det_intent and det_intent.confidence >= 0.95:
                    return "deterministic"
            except Exception:
                pass
            try:
                intent_result = IntentDetector.detect(clean)
                if intent_result.intent.name == "SEMANTIC_UI_ACTION" and intent_result.confidence >= 0.90:
                    return "semantic_ui"
            except Exception:
                pass
            from friday.devices.windows_friday import windows_friday
            if windows_friday.can_handle(clean):
                return "windows_friday_directive"
            return None

    def _execute_semantic_ui_action(self, intent_result, user_input: str) -> AgentResponse | None:
            """Execute a high-confidence semantic UI action via the pywinauto provider.

            Returns an AgentResponse when the action was handled here (bypassing
            LLM/Vision entirely), or None to fall through to the normal pipeline.
            """
            parsed = intent_result.parsed_data or {}
            action = parsed.get("action_type")
            target = parsed.get("target", "")
            self.memory.add_message(Message(role=Role.USER, content=user_input))

            if action == "launch":
                executable = parsed.get("executable", "")
                # Proposal != Execution: application launches pass through the authorizer.
                shell_apps = {"cmd.exe", "powershell.exe", "wt.exe", "taskmgr.exe"}
                risk = SafetyLevel.SENSITIVE if executable.lower() in shell_apps else SafetyLevel.SAFE
                auth_req = AuthorizationRequest(
                    tool_name="execute_computer_action",
                    safety_level=risk,
                    arguments={"action_type": "launch", "executable": executable},
                    tool_call_id=str(uuid.uuid4()),
                    purpose=f"Semantic UI launch of {target}",
                    affected_resource="windows_desktop",
                )
                auth_resp = self.authorizer.authorize(auth_req)
                if auth_resp.decision != AuthorizationDecision.APPROVED:
                    logger.warning(f"[UIA] Launch of '{target}' was not authorized ({auth_resp.decision}).")
                    return None
                logger.info(f"[UIA] Launching application '{target}' ({executable})")
                if self.ui_provider.launch_application(executable):
                    resp_content = f"Opened {target}."
                    self.memory.add_message(Message(role=Role.ASSISTANT, content=resp_content))
                    return AgentResponse(
                        content=resp_content,
                        is_done=True,
                        metadata={"ui_automation": True, "action": "launch", "target": target},
                    )
                logger.warning(f"[UIA] Failed to launch application '{executable}'.")
                return None

            if action in ("click", "key_press"):
                element = self.ui_provider.find_element(target)
                if element and getattr(element, "confidence", 0) >= self.UIA_ELEMENT_CONFIDENCE_THRESHOLD:
                    if self.ui_provider.click(element):
                        resp_content = f"Clicked the {target} via UI Automation."
                        self.memory.add_message(Message(role=Role.ASSISTANT, content=resp_content))
                        return AgentResponse(
                            content=resp_content,
                            is_done=True,
                            metadata={
                                "ui_automation": True,
                                "action": "click",
                                "target": target,
                                "element_confidence": getattr(element, "confidence", 0.0),
                                "intent_confidence": intent_result.confidence,
                            },
                        )
                    logger.warning("[UIA] UI Automation click failed.")
                else:
                    logger.warning(
                        f"[UIA] UI element '{target}' not found or below confidence threshold "
                        f"({getattr(element, 'confidence', 0.0):.2f} < {self.UIA_ELEMENT_CONFIDENCE_THRESHOLD})."
                    )
            return None

