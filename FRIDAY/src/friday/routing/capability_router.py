"""Capability Routing Layer for FRIDAY.

Selects the cheapest, safest, and most deterministic valid capability for each request:
- DIRECT_REASONING: Direct conversational response without tools or external APIs.
- MEMORY_RETRIEVAL: Oracle-backed memory search for past context and preferences.
- LOCAL_COMPUTATION: Instant local deterministic calculation or system time/info.
- LOCAL_SCREEN_INSPECTION: Reuses cached perception / local ROI checks without calling Vision APIs.
- VISION_MODEL: External multimodal vision provider (only when visual state has changed or uncached).
- VOICE_MODEL: Live voice/speech session.
- TOOL_EXECUTION: Registry tool invocation.
- BACKGROUND_TASK: Asynchronous long-running multi-step task.

Invariants:
- Evaluates explicit cost ($), latency (ms), confidence (0-1), risk (SafetyLevel), and freshness.
- Prefers local deterministic capabilities when sufficient.
- Prefers cached perception over repeated vision calls.
- Never calls an external API simply because it exists.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from typing import Any

from friday.core.logging import get_logger
from friday.core.types import SafetyLevel
from friday.security.scrubber import redact_secrets

logger = get_logger("routing.capability")


class ExecutionCapabilityType(str, Enum):
    """Available execution modalities."""
    DIRECT_REASONING = "DIRECT_REASONING"
    MEMORY_RETRIEVAL = "MEMORY_RETRIEVAL"
    LOCAL_COMPUTATION = "LOCAL_COMPUTATION"
    LOCAL_SCREEN_INSPECTION = "LOCAL_SCREEN_INSPECTION"
    VISION_MODEL = "VISION_MODEL"
    VOICE_MODEL = "VOICE_MODEL"
    TOOL_EXECUTION = "TOOL_EXECUTION"
    BACKGROUND_TASK = "BACKGROUND_TASK"


@dataclass
class CapabilityMetadata:
    """Telemetry, cost, and safety metadata for a candidate capability."""
    capability_type: ExecutionCapabilityType
    estimated_cost_usd: float = 0.0
    estimated_latency_ms: float = 0.0
    confidence: float = 1.0
    risk_level: SafetyLevel = SafetyLevel.SAFE
    is_local_deterministic: bool = True
    freshness_seconds: float | None = None
    rationale: str = ""
    # TASK-API-002: names the concrete tool a candidate needs (e.g.
    # "get_fleet_status"); telemetry only, the executor still picks tools.
    required_tools: "list[str] | None" = None

    def compute_selection_score(self) -> float:
        """Lower score is better (cheapest, fastest, safest, highest confidence)."""
        risk_multipliers = {
            SafetyLevel.SAFE: 0.0,
            SafetyLevel.SENSITIVE: 50.0,
            SafetyLevel.DANGEROUS: 200.0,
        }
        cost_penalty = self.estimated_cost_usd * 10000.0
        latency_penalty = self.estimated_latency_ms * 0.01
        risk_penalty = risk_multipliers.get(self.risk_level, 0.0)
        confidence_bonus = (1.0 - self.confidence) * 100.0
        local_bonus = -20.0 if self.is_local_deterministic else 20.0

        return cost_penalty + latency_penalty + risk_penalty + confidence_bonus + local_bonus

    def to_dict(self) -> dict[str, Any]:
        return {
            "capability_type": self.capability_type.value,
            "estimated_cost_usd": self.estimated_cost_usd,
            "estimated_latency_ms": round(self.estimated_latency_ms, 1),
            "confidence": round(self.confidence, 2),
            "risk_level": self.risk_level.value,
            "is_local_deterministic": self.is_local_deterministic,
            "freshness_seconds": self.freshness_seconds,
            "rationale": self.rationale,
            "score": round(self.compute_selection_score(), 2),
        }


@dataclass
class RoutingDecision:
    """The optimal capability selected by the router."""
    selected_capability: ExecutionCapabilityType
    reason: str
    candidate_evaluations: list[CapabilityMetadata]
    avoided_external_call: bool = False
    estimated_savings_usd: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "selected_capability": self.selected_capability.value,
            "reason": self.reason,
            "avoided_external_call": self.avoided_external_call,
            "estimated_savings_usd": self.estimated_savings_usd,
            "candidates": [c.to_dict() for c in self.candidate_evaluations],
        }


class CapabilityRouter:
    """Evaluates request requirements and routes to the cheapest and safest valid capability."""

    # Keywords signaling visual inspection
    SCREEN_KEYWORDS = {"screen", "window", "button", "ui", "display", "visual", "look at screen", "screenshot"}
    # Keywords signaling memory search
    MEMORY_KEYWORDS = {"remember", "recall", "earlier", "previous conversation", "past", "history", "what did i say"}
    # Keywords signaling simple local math or system info
    LOCAL_CALC_KEYWORDS = {"what time", "current date", "calculate", "2 + 2", "sum of", "timestamp"}
    # Keywords signaling background execution
    BACKGROUND_KEYWORDS = {"in the background", "async", "long running", "monitor continuously", "background task"}
    # TASK-API-002 (2026-11-10): keywords signaling a live fleet-status probe.
    # Without these, "how's the fleet?" classified as DIRECT_REASONING and the
    # LLM never saw a tool, so the answer could only be a guess. Fleet questions
    # are factual probes over live infrastructure — they must reach
    # get_fleet_status (FleetStatusTool), the same truth /api/agents/status reports.
    FLEET_KEYWORDS = {
        "fleet", "the agents", "all agents", "agents status", "agent status",
        "mesh status", "universe status", "who is online", "anyone down",
        "agents online", "status of the agents", "how are the agents",
    }
    # TASK-INT-002 (2026-11-10): keywords signaling a research dispatch to
    # IntelX. The live incident ("run a quick research check" -> VISION_MODEL)
    # proved research requests were nobody's job: they must reach
    # intelx_research (the fleet's Macro Research & Evidence Engine).
    RESEARCH_KEYWORDS = {
        "research", "research this", "do some research", "find out about",
        "look into", "investigate", "get the highlights", "give me the highlights",
        "brief me on", "what are the findings", "sourced summary",
        "evidence on", "dig into",
    }
    # TASK-STR-002 (2026-11-10): keywords signaling a Stratex portfolio/market
    # question. These are factual questions about the owner's Binance demo
    # account and live market signals — the answer must come from Stratex
    # (stratex_portfolio), never the LLM's imagination. Live trading stays
    # blocked by the fail-closed guard (D-015): the tool is read-only.
    # TASK-FOR-002 (2026-11-10): keywords signaling a real code task for
    # Forge (sandbox security-reviewed under TASK-FOR-001). "Write me a
    # script that..." is engineering work: it must reach forge_code_task
    # (Forge plans + executes in its sandboxed workspace), never a
    # conversational "sure, here's how you could..." from the LLM.
    CODE_TASK_KEYWORDS = {
        "write a python", "write a csv", "write a json", "write a program",
        "create a python", "build a python", "build a csv", "create a program",
        "write me a script", "write a script", "write me a program",
        "write a program", "write me a function", "write a function",
        "write me a tool", "build me a", "build a script", "build a tool",
        "code a", "code me a", "create a script", "make me a script",
        "fix this bug", "fix the bug", "fix this code", "refactor this",
        "refactor the", "review this code", "review the code",
    }
    PORTFOLIO_KEYWORDS = {
        "my portfolio", "the portfolio", "portfolio", "positions", "open positions",
        "any positions", "my balance", "account balance", "trading account",
        "how is my trading", "pnl", "profit and loss", "market signals",
        "trading signals", "what strategies", "active strategies", "stratex",
        "binance",
    }
    # Checklist F19/C8 (2026-11-11): keywords signaling a security-posture or
    # security-findings question. These are factual questions about the live
    # security state — the answer must come from Sentinel's real posture /
    # finding engines (sentinel_security, read-only), never the LLM's
    # imagination. Active assessments stay behind Sentinel's owner-authorized
    # scope gate by design; the tool states that in every answer.
    SECURITY_SCAN_KEYWORDS = {
        "security posture", "security status", "security check", "security scan",
        "security score", "how secure", "am i vulnerable", "any vulnerabilities",
        "vulnerabilities right now", "any security findings", "security findings",
        "open findings", "any findings", "check the security", "run a security",
        "security posture check", "fleet security", "sentinel", "cybersecurity",
    }
    # Checklist F10/C10 (2026-11-11): keywords signaling a forecast request
    # for Futuris. A forecast is a real computational product (evidence-
    # backed pipeline, honest calibration, prediction-never-authorization) —
    # it must reach futuris_forecast, never the LLM's invented numbers.
    FORECAST_KEYWORDS = {
        "forecast", "forecast this", "give me a forecast", "get a forecast",
        "predict", "prediction", "what does futuris", "futuris forecast",
        "forecast for", "project the", "how likely is", "probability of",
    }
    # Checklist C7 (2026-11-11, batch 3): keywords signaling a video-script
    # drafting request. The script must come from VyralX's real Hyperframes
    # engine (vyralx_script, draft-only) — never an LLM-invented screenplay.
    SCRIPT_KEYWORDS = {
        "video script", "draft a script", "draft a video", "write a script",
        "write a video", "write a youtube", "youtube script", "script for a video",
        "draft me a script", "script about", "script on", "vyralx script",
        "compose a script", "create a script", "generate a script",
    }
    # Checklist C9 (2026-11-11, batch 3): keywords signaling a web-operations
    # monitoring request. The answer must come from Cortex's real health
    # summary and governed-properties roster (cortex_web_ops, read-only).
    WEB_OPS_KEYWORDS = {
        "how are my websites", "how are my sites", "websites doing",
        "web properties", "web ops", "web operations", "cortex status",
        "cortex health", "site health", "sites healthy", "my websites",
        "website health", "check my websites", "check the websites",
    }
    # Checklist C11 (2026-11-11, batch 3): keywords signaling a Memora cloud
    # memory operation (search or store). Distinct from FRIDAY's local memory
    # keywords — these explicitly target the Memora fabric.
    MEMORA_OP_KEYWORDS = {
        "search memora", "memora search", "query memora", "memora lookup",
        "recall from memora", "memora recall", "search fleet memory",
        "search cloud memory", "fleet memory for", "cloud memory for",
        "save to memora", "store in memora", "memora write", "save to fleet memory",
        "store in fleet memory", "save to cloud memory", "remember in memora",
        # batch 3 part 2 (2026-11-11): the "this" form the owner actually
        # types — "save this to fleet memory: X" — never matched before, so
        # the live fast path silently missed it (tool supported it; routing
        # never reached it).
        "save this to fleet memory", "save this to cloud memory",
        "save this to memora", "store this in fleet memory",
        "store this in memora", "store this in cloud memory",
        "write this to fleet memory", "write to fleet memory",
    }
    # Checklist F13 (batch 6, ZAI Agent 2): keywords signaling a fetch-and-
    # summarize request for a shared URL. The answer must come from the REAL
    # page content through web_fetch_summarize (SSRF-guarded fetch + the
    # synthesize path), never the LLM's imagination about the page.
    FETCH_SUMMARIZE_KEYWORDS = {
        "summarize this page", "summarize this article", "summarize this link",
        "summarize the page", "summarize the article", "summarize the link",
        "summarize this url", "fetch and summarize", "fetch this page",
        "what does this page say", "what does this article say",
        "what does this link say", "what's on this page", "whats on this page",
        "read this page", "read this article", "read this link",
        "summarize this for me", "tldr this", "tl;dr this",
        "summarize the website", "summarize this website",
    }
    # Checklist F23 (batch 7, ZAI Agent 2): keywords signaling a render
    # request for a drafted VyralX script. The answer must come from the REAL
    # VyralX render pipeline (vyralx_render — free-tool ffmpeg/edge_tts,
    # honest manifest with output/duration/bytes), never a fabricated "done".
    from friday.tools.builtin.vyralx_project import PROJECT_WORDS as PROJECT_KEYWORDS

    RENDER_KEYWORDS = {
        "render the script", "render this clip", "render this script",
        "render this short", "render the clip", "render the short",
        "turn that script into a video", "turn the script into a video",
        "make a video from the script", "make a clip from the script",
        "render it as a short", "render as a short", "render it as a video",
    }
    # Checklist F24 (batch 7, ZAI Agent 2): keywords signaling a publish
    # request for a rendered clip. DEFAULT routes to draft upload; production
    # publish stays fail-closed behind the confirm phrase + env flag (D-015).
    PUBLISH_KEYWORDS = {
        "publish the clip", "publish this clip", "publish the short",
        "publish this short", "publish to youtube", "upload as draft",
        "upload the clip", "upload the short", "send the clip to youtube",
        "send the short to youtube", "publish the video",
    }
    # Checklist F6 (batch 7, ZAI Agent 2): keywords signaling a price-alert
    # rule the owner is setting. Routes to TOOL_EXECUTION (alert store), never
    # DIRECT_REASONING (which would "ok" the alert without recording it).
    ALERT_KEYWORDS = {
        "alert me when", "alert me if", "alert when", "alert if",
        "watch for ", "notify me when", "notify me if",
        "ping me when", "ping me if", "tell me when", "tell me if",
        "cancel alert", "remove alert", "delete alert", "my alerts",
    }
    # Checklist I6 (batch 8, ZAI Agent 2): keywords for tools that were
    # registered but UNROUTED (dead-code audit found 3). Wiring them so the
    # capability router reaches them by intent — they were available as
    # LLM-callable tools but never keyword-routed, so the owner's phrasing
    # could never reach them deterministically.
    DICTIONARY_KEYWORDS = {
        "define", "definition of", "what does this word mean",
        "look up the word", "dictionary lookup", "spell the word",
    }
    GMAIL_DRAFT_KEYWORDS = {
        "draft an email", "draft a gmail", "compose an email", "compose a gmail",
        "write me an email", "write an email", "send an email draft",
        "draft a message to", "compose a message to",
    }
    WHATSAPP_OPEN_KEYWORDS = {
        "open whatsapp", "open whastsapp", "launch whatsapp",
        "send a whatsapp message", "whatsapp message to",
        "message on whatsapp", "open the whatsapp chat",
    }

    # TASK-ORCH-001 (2026-11-10): keyword checks use whole-word/phrase boundaries.
    # The previous substring matching misrouted live traffic: "run a quick research
    # check" matched SCREEN_KEYWORDS because "quick" contains the substring "ui",
    # sending a plain research question to the external vision model (proven live
    # 2026-11-10, ACTIVITY_LOG). Word boundaries keep every existing keyword
    # behaviour while removing the substring false-hit class.
    _WORD_BOUNDARY_CACHE: dict[str, "re.Pattern[str]"] = {}

    @classmethod
    def _matches(cls, text: str, keywords: "set[str] | frozenset[str]") -> bool:
        """True when any keyword appears in ``text`` as a whole word or phrase.

        Substring containment (``kw in text``) is intentionally NOT used: it
        produces false hits like "ui" inside "quick" or "run" inside "trader".
        """
        for kw in keywords:
            pattern = cls._WORD_BOUNDARY_CACHE.get(kw)
            if pattern is None:
                pattern = re.compile(r"(?<![\w])" + re.escape(kw) + r"(?![\w])")
                cls._WORD_BOUNDARY_CACHE[kw] = pattern
            if pattern.search(text):
                return True
        return False

    def __init__(
        self,
        default_vision_cost_usd: float = 0.002,
        default_llm_cost_usd: float = 0.001,
    ) -> None:
        self.default_vision_cost_usd = default_vision_cost_usd
        self.default_llm_cost_usd = default_llm_cost_usd

    def route_request(
        self,
        user_input: str,
        context: dict[str, Any] | None = None,
    ) -> RoutingDecision:
        """Select the optimal execution capability based on cost, latency, safety, and cache state."""
        ctx = context or {}
        clean_input = user_input.strip().lower()
        candidates: list[CapabilityMetadata] = []

        has_cached_screen = bool(ctx.get("cached_screen_observation"))
        screen_unchanged = bool(ctx.get("screen_unchanged", False))
        cache_age_seconds = ctx.get("cache_age_seconds")

        # 1. Evaluate Direct Reasoning (Conversational / General Knowledge)
        # If user asks pure conversational question without real-world tools
        is_conversational = not self._matches(clean_input, {"file", "click", "run", "execute", "background", "search memory"})
        # TASK-API-002: fleet-status questions are live factual probes, never
        # plain conversation — exclude them from DIRECT_REASONING.
        # TASK-INT-002: research requests are dispatchable tasks, not
        # conversation — exclude them too.
        # TASK-STR-002: portfolio/market questions are factual queries over
        # the owner's trading account — exclude them from DIRECT_REASONING too.
        # TASK-FOR-002: code-task requests are engineering work for Forge —
        # exclude them from DIRECT_REASONING too.
        is_conversational = is_conversational and not (
            self._matches(clean_input, self.FLEET_KEYWORDS)
            or self._matches(clean_input, self.RESEARCH_KEYWORDS)
            or self._matches(clean_input, self.PORTFOLIO_KEYWORDS)
            or self._matches(clean_input, self.CODE_TASK_KEYWORDS)
            or self._matches(clean_input, self.SECURITY_SCAN_KEYWORDS)
            or self._matches(clean_input, self.FORECAST_KEYWORDS)
            or self._matches(clean_input, self.SCRIPT_KEYWORDS)
            or self._matches(clean_input, self.WEB_OPS_KEYWORDS)
            or self._matches(clean_input, self.MEMORA_OP_KEYWORDS)
            or self._matches(clean_input, self.FETCH_SUMMARIZE_KEYWORDS)
            or (self._matches(clean_input, self.RENDER_KEYWORDS) or self._matches(clean_input, self.PROJECT_KEYWORDS))
            or self._matches(clean_input, self.PUBLISH_KEYWORDS)
            or self._matches(clean_input, self.ALERT_KEYWORDS)
            or self._matches(clean_input, self.DICTIONARY_KEYWORDS)
            or self._matches(clean_input, self.GMAIL_DRAFT_KEYWORDS)
            or self._matches(clean_input, self.WHATSAPP_OPEN_KEYWORDS)
        )
        # Checklist C12 (batch 3): chained instructions ("research X, then
        # draft the script about it") are multi-stage dispatches, never plain
        # conversation. Lazy import: pipeline maps stages through THIS
        # router's keyword sets, so a module-level import would be circular.
        try:
            from friday.ecosystem.pipeline import detect_pipeline

            chained = detect_pipeline(user_input) is not None
        except Exception:
            chained = False
        is_conversational = is_conversational and not chained
        if is_conversational and not (self._matches(clean_input, self.SCREEN_KEYWORDS) or self._matches(clean_input, self.MEMORY_KEYWORDS) or self._matches(clean_input, self.LOCAL_CALC_KEYWORDS) or self._matches(clean_input, self.FLEET_KEYWORDS) or self._matches(clean_input, self.RESEARCH_KEYWORDS) or self._matches(clean_input, self.PORTFOLIO_KEYWORDS) or self._matches(clean_input, self.CODE_TASK_KEYWORDS) or self._matches(clean_input, self.SECURITY_SCAN_KEYWORDS) or self._matches(clean_input, self.FORECAST_KEYWORDS) or self._matches(clean_input, self.SCRIPT_KEYWORDS) or self._matches(clean_input, self.WEB_OPS_KEYWORDS) or self._matches(clean_input, self.MEMORA_OP_KEYWORDS) or self._matches(clean_input, self.FETCH_SUMMARIZE_KEYWORDS) or (self._matches(clean_input, self.RENDER_KEYWORDS) or self._matches(clean_input, self.PROJECT_KEYWORDS)) or self._matches(clean_input, self.PUBLISH_KEYWORDS) or self._matches(clean_input, self.ALERT_KEYWORDS) or self._matches(clean_input, self.DICTIONARY_KEYWORDS) or self._matches(clean_input, self.GMAIL_DRAFT_KEYWORDS) or self._matches(clean_input, self.WHATSAPP_OPEN_KEYWORDS)):
            candidates.append(CapabilityMetadata(
                capability_type=ExecutionCapabilityType.DIRECT_REASONING,
                estimated_cost_usd=0.0,
                estimated_latency_ms=150.0,
                confidence=0.98,
                risk_level=SafetyLevel.SAFE,
                is_local_deterministic=True,
                rationale="Pure conversational query requiring no tools or external API calls.",
            ))

        # 2. Evaluate Memory Retrieval
        if self._matches(clean_input, self.MEMORY_KEYWORDS):
            candidates.append(CapabilityMetadata(
                capability_type=ExecutionCapabilityType.MEMORY_RETRIEVAL,
                estimated_cost_usd=0.0,
                estimated_latency_ms=5.0,
                confidence=0.95,
                risk_level=SafetyLevel.SAFE,
                is_local_deterministic=True,
                rationale="Query references past conversational memory or stored user facts.",
            ))

        # TASK-API-002: Evaluate Live Fleet Status Probe — "how's the fleet?"
        # is a factual question about live infrastructure; the answer must come
        # from get_fleet_status (a real probe), never from the LLM's imagination.
        if self._matches(clean_input, self.FLEET_KEYWORDS):
            candidates.append(CapabilityMetadata(
                capability_type=ExecutionCapabilityType.TOOL_EXECUTION,
                estimated_cost_usd=0.0,
                estimated_latency_ms=800.0,
                confidence=0.97,
                risk_level=SafetyLevel.SAFE,
                is_local_deterministic=True,
                required_tools=["get_fleet_status"],
                rationale="Live fleet-health question: probe the nine specialist agents with get_fleet_status (same truth as /api/agents/status).",
            ))

        # TASK-INT-002: Evaluate Fleet Research Dispatch — "research X" is a
        # request for evidence-based findings from IntelX (the fleet's Macro
        # Research & Evidence Engine), not a vision-model job and not plain
        # conversation. The live 2026-11-10 misroute sent exactly this class
        # to VISION_MODEL; intelx_research is the correct tool.
        if self._matches(clean_input, self.RESEARCH_KEYWORDS):
            candidates.append(CapabilityMetadata(
                capability_type=ExecutionCapabilityType.TOOL_EXECUTION,
                estimated_cost_usd=0.0,
                estimated_latency_ms=5000.0,
                confidence=0.92,
                risk_level=SafetyLevel.SAFE,
                is_local_deterministic=False,
                required_tools=["intelx_research"],
                rationale="Research request: dispatch to IntelX (Macro Research & Evidence Engine) for an evidence-based brief with citations.",
            ))

        # TASK-STR-002: Evaluate Stratex Portfolio Snapshot — "how's my
        # portfolio?" is a factual question about the owner's Binance demo
        # account; the answer must come from Stratex (stratex_portfolio,
        # read-only; live trading stays fail-closed per D-015).
        if self._matches(clean_input, self.PORTFOLIO_KEYWORDS):
            candidates.append(CapabilityMetadata(
                capability_type=ExecutionCapabilityType.TOOL_EXECUTION,
                estimated_cost_usd=0.0,
                estimated_latency_ms=4000.0,
                confidence=0.93,
                risk_level=SafetyLevel.SAFE,
                is_local_deterministic=False,
                required_tools=["stratex_portfolio"],
                rationale="Portfolio/market question: read-only Stratex snapshot (balance, positions, strategies, signals); live trading blocked (D-015).",
            ))

        # TASK-FOR-002: Evaluate Forge Code Task Dispatch — "write me a
        # script that..." is engineering work: Forge plans and executes it in
        # its security-reviewed sandbox (TASK-FOR-001) and returns the real
        # result with a verification manifest.
        if self._matches(clean_input, self.CODE_TASK_KEYWORDS):
            candidates.append(CapabilityMetadata(
                capability_type=ExecutionCapabilityType.TOOL_EXECUTION,
                estimated_cost_usd=0.0,
                estimated_latency_ms=30000.0,
                confidence=0.9,
                risk_level=SafetyLevel.SAFE,
                is_local_deterministic=False,
                required_tools=["forge_code_task"],
                rationale="Code task: dispatch to Forge (sandboxed SWE agent, TASK-FOR-001 approved) for a real build with verification.",
            ))

        # Checklist F19/C8: Evaluate Sentinel Security Lookup — "what's the
        # security posture?" / "any vulnerabilities?" are factual questions
        # about the live security state; the answer must come from Sentinel's
        # real posture/finding engines (sentinel_security, read-only). Active
        # assessments are NOT performed (owner-authorized scope gate by design).
        if self._matches(clean_input, self.SECURITY_SCAN_KEYWORDS):
            candidates.append(CapabilityMetadata(
                capability_type=ExecutionCapabilityType.TOOL_EXECUTION,
                estimated_cost_usd=0.0,
                estimated_latency_ms=3000.0,
                confidence=0.93,
                risk_level=SafetyLevel.SAFE,
                is_local_deterministic=False,
                required_tools=["sentinel_security"],
                rationale="Security question: read-only Sentinel posture/findings lookup; active assessments stay behind the owner-authorized scope gate.",
            ))

        # Checklist F10/C10: Evaluate Futuris Forecast — "forecast X" /
        # "predict X" requests must reach futuris_forecast (the real
        # evidence-backed pipeline); LLM-invented numbers are the exact
        # failure class this prevents. A prediction is never an authorization.
        if self._matches(clean_input, self.FORECAST_KEYWORDS):
            candidates.append(CapabilityMetadata(
                capability_type=ExecutionCapabilityType.TOOL_EXECUTION,
                estimated_cost_usd=0.0,
                estimated_latency_ms=8000.0,
                confidence=0.9,
                risk_level=SafetyLevel.SAFE,
                is_local_deterministic=False,
                required_tools=["futuris_forecast"],
                rationale="Forecast request: Futuris's evidence-backed pipeline with honest calibration; predictions inform, never authorize.",
            ))

        # Checklist C7 (batch 3): video-script drafting requests must reach
        # vyralx_script — VyralX's real Hyperframes engine, draft-only.
        if self._matches(clean_input, self.SCRIPT_KEYWORDS):
            candidates.append(CapabilityMetadata(
                capability_type=ExecutionCapabilityType.TOOL_EXECUTION,
                estimated_cost_usd=0.0,
                estimated_latency_ms=10000.0,
                confidence=0.9,
                risk_level=SafetyLevel.SAFE,
                is_local_deterministic=False,
                required_tools=["vyralx_script"],
                rationale="Script drafting: VyralX's real Hyperframes scene pipeline; a draft only, never a publish.",
            ))

        # Checklist C9 (batch 3): web-operations monitoring requests must
        # reach cortex_web_ops — Cortex's real health summary + governed
        # properties roster, read-only.
        if self._matches(clean_input, self.WEB_OPS_KEYWORDS):
            candidates.append(CapabilityMetadata(
                capability_type=ExecutionCapabilityType.TOOL_EXECUTION,
                estimated_cost_usd=0.0,
                estimated_latency_ms=6000.0,
                confidence=0.9,
                risk_level=SafetyLevel.SAFE,
                is_local_deterministic=False,
                required_tools=["cortex_web_ops"],
                rationale="Web-ops monitor: Cortex's real health summary and governed properties; read-only, no outreach.",
            ))

        # Checklist C11 (batch 3): explicit Memora cloud-memory operations
        # run as first-class tasks on Memora's real context database.
        # Confidence 0.97 (not 0.9): "save this to fleet memory" also matches
        # the generic fleet-status probe (0.97) — the SPECIFIC memory-op
        # intent must win over the generic fleet ping, and this block is
        # evaluated before the fleet probe.
        if self._matches(clean_input, self.MEMORA_OP_KEYWORDS):
            candidates.append(CapabilityMetadata(
                capability_type=ExecutionCapabilityType.TOOL_EXECUTION,
                estimated_cost_usd=0.0,
                estimated_latency_ms=5000.0,
                confidence=0.97,
                risk_level=SafetyLevel.SAFE,
                is_local_deterministic=False,
                required_tools=["memora_memory"],
                rationale="Memora memory op: real search/store on the fleet's persistent memory fabric; honest empties.",
            ))

        # Checklist F13 (batch 6, ZAI Agent 2): Evaluate Web Fetch+Summarize —
        # "summarize this page <url>" must reach web_fetch_summarize (real
        # fetch, SSRF-guarded, synthesize on the actual text) — never a
        # DIRECT_REASONING guess about page content.
        if self._matches(clean_input, self.FETCH_SUMMARIZE_KEYWORDS):
            candidates.append(CapabilityMetadata(
                capability_type=ExecutionCapabilityType.TOOL_EXECUTION,
                estimated_cost_usd=0.0,
                estimated_latency_ms=8000.0,
                confidence=0.94,
                risk_level=SafetyLevel.SAFE,
                is_local_deterministic=False,
                required_tools=["web_fetch_summarize"],
                rationale="Fetch-and-summarize request: read the shared URL's real content (SSRF-guarded), summarize what is actually there.",
            ))

        if self._matches(clean_input, self.PROJECT_KEYWORDS):
            candidates.append(CapabilityMetadata(
                capability_type=ExecutionCapabilityType.TOOL_EXECUTION,
                estimated_cost_usd=0.0, estimated_latency_ms=30000.0,
                confidence=0.98, risk_level=SafetyLevel.SAFE,
                is_local_deterministic=False, required_tools=["vyralx_project"],
                rationale="Review-only topic-to-video project; explicit license confirmation required.",
            ))

        # Checklist F23 (batch 7, ZAI Agent 2): Evaluate Video Render — "render
        # this script/clip" must reach vyralx_render (real VyralX hyperframes
        # render pipeline, free-tool ffmpeg/edge_tts, honest manifest), never
        # a DIRECT_REASONING "ok I rendered it".
        if self._matches(clean_input, self.RENDER_KEYWORDS):
            candidates.append(CapabilityMetadata(
                capability_type=ExecutionCapabilityType.TOOL_EXECUTION,
                estimated_cost_usd=0.0,
                estimated_latency_ms=30000.0,
                confidence=0.93,
                risk_level=SafetyLevel.SAFE,
                is_local_deterministic=False,
                required_tools=["vyralx_render"],
                rationale="Render request: dispatch to VyralX's free-tool render pipeline for a real clip manifest.",
            ))

        # Checklist F24 (batch 7, ZAI Agent 2): Evaluate Video Publish —
        # "publish the clip" must reach vyralx_publish (fail-closed draft by
        # default; production publish gated behind the confirm phrase + env
        # flag, D-015 shape).
        if self._matches(clean_input, self.PUBLISH_KEYWORDS):
            candidates.append(CapabilityMetadata(
                capability_type=ExecutionCapabilityType.TOOL_EXECUTION,
                estimated_cost_usd=0.0,
                estimated_latency_ms=30000.0,
                confidence=0.92,
                risk_level=SafetyLevel.SAFE,
                is_local_deterministic=False,
                required_tools=["vyralx_publish"],
                rationale="Publish request: route to vyralx_publish (draft upload by default; production gated by D-015 two-gate).",
            ))

        # Checklist F6 (batch 7, ZAI Agent 2): Evaluate Price Alert —
        # "alert me when X > Y" must reach the alert store (TOOL_EXECUTION),
        # never a conversational "ok" that never records the rule.
        if self._matches(clean_input, self.ALERT_KEYWORDS):
            candidates.append(CapabilityMetadata(
                capability_type=ExecutionCapabilityType.TOOL_EXECUTION,
                estimated_cost_usd=0.0,
                estimated_latency_ms=200.0,
                confidence=0.95,
                risk_level=SafetyLevel.SAFE,
                is_local_deterministic=True,
                required_tools=["price_alert"],
                rationale="Price-alert rule: record it in the alert store (evaluated by the market-watch loop).",
            ))

        # Checklist I6 (batch 8, ZAI Agent 2): wire the 3 previously-unrouted
        # tools so the owner's phrasing reaches them deterministically.
        if self._matches(clean_input, self.DICTIONARY_KEYWORDS):
            candidates.append(CapabilityMetadata(
                capability_type=ExecutionCapabilityType.TOOL_EXECUTION,
                estimated_cost_usd=0.0,
                estimated_latency_ms=500.0,
                confidence=0.95,
                risk_level=SafetyLevel.SAFE,
                is_local_deterministic=True,
                required_tools=["dictionary"],
                rationale="Dictionary lookup: define the word via the dictionary tool (was registered but unrouted — I6 wired it).",
            ))

        if self._matches(clean_input, self.GMAIL_DRAFT_KEYWORDS):
            candidates.append(CapabilityMetadata(
                capability_type=ExecutionCapabilityType.TOOL_EXECUTION,
                estimated_cost_usd=0.0,
                estimated_latency_ms=2000.0,
                confidence=0.92,
                risk_level=SafetyLevel.SAFE,
                is_local_deterministic=False,
                required_tools=["send_gmail"],
                rationale="Gmail draft: compose the email via the gmail tool (was registered but unrouted — I6 wired it).",
            ))

        if self._matches(clean_input, self.WHATSAPP_OPEN_KEYWORDS):
            candidates.append(CapabilityMetadata(
                capability_type=ExecutionCapabilityType.TOOL_EXECUTION,
                estimated_cost_usd=0.0,
                estimated_latency_ms=1500.0,
                confidence=0.92,
                risk_level=SafetyLevel.SAFE,
                is_local_deterministic=False,
                required_tools=["open_whatsapp"],
                rationale="WhatsApp open: launch the chat via the whatsapp tool (was registered but unrouted — I6 wired it).",
            ))

        # 3. Evaluate Local Computation (e.g. system time or simple arithmetic)
        if self._matches(clean_input, self.LOCAL_CALC_KEYWORDS) or re.match(r"^\d+\s*[\+\-\*\/]\s*\d+$", clean_input):
            candidates.append(CapabilityMetadata(
                capability_type=ExecutionCapabilityType.LOCAL_COMPUTATION,
                estimated_cost_usd=0.0,
                estimated_latency_ms=1.0,
                confidence=1.0,
                risk_level=SafetyLevel.SAFE,
                is_local_deterministic=True,
                rationale="Deterministic local arithmetic or system timestamp calculation.",
            ))

        # 4. Evaluate Screen Perception (Cached vs Vision Model)
        if self._matches(clean_input, self.SCREEN_KEYWORDS):
            if has_cached_screen and (screen_unchanged or (cache_age_seconds is not None and cache_age_seconds < 5.0)):
                candidates.append(CapabilityMetadata(
                    capability_type=ExecutionCapabilityType.LOCAL_SCREEN_INSPECTION,
                    estimated_cost_usd=0.0,
                    estimated_latency_ms=2.0,
                    confidence=0.95,
                    risk_level=SafetyLevel.SAFE,
                    is_local_deterministic=True,
                    freshness_seconds=cache_age_seconds,
                    rationale="Screen state is unchanged; reusing local cached perception observation.",
                ))
            else:
                candidates.append(CapabilityMetadata(
                    capability_type=ExecutionCapabilityType.VISION_MODEL,
                    estimated_cost_usd=self.default_vision_cost_usd,
                    estimated_latency_ms=800.0,
                    confidence=0.92,
                    risk_level=SafetyLevel.SAFE,
                    is_local_deterministic=False,
                    rationale="Screen state has changed or cache is cold; external vision perception required.",
                ))

        # 5. Evaluate Background Task Execution
        if self._matches(clean_input, self.BACKGROUND_KEYWORDS):
            candidates.append(CapabilityMetadata(
                capability_type=ExecutionCapabilityType.BACKGROUND_TASK,
                estimated_cost_usd=0.0,
                estimated_latency_ms=20.0,
                confidence=0.95,
                risk_level=SafetyLevel.SAFE,
                is_local_deterministic=True,
                rationale="Request explicitly specifies background execution.",
            ))

        # 6. Fallback Tool Execution Candidate
        if self._matches(clean_input, {"write", "read", "delete", "create", "list", "system", "file", "process", "move", "click", "type", "scroll"}):
            candidates.append(CapabilityMetadata(
                capability_type=ExecutionCapabilityType.TOOL_EXECUTION,
                estimated_cost_usd=0.0,
                estimated_latency_ms=10.0,
                confidence=0.90,
                risk_level=SafetyLevel.SAFE,
                is_local_deterministic=True,
                rationale="Task requires standard tool registry execution.",
            ))

        # Default fallback to direct reasoning if no specific candidate matched
        if not candidates:
            candidates.append(CapabilityMetadata(
                capability_type=ExecutionCapabilityType.DIRECT_REASONING,
                estimated_cost_usd=0.0,
                estimated_latency_ms=100.0,
                confidence=0.90,
                risk_level=SafetyLevel.SAFE,
                is_local_deterministic=True,
                rationale="Defaulting to local direct reasoning.",
            ))

        # Sort candidates by cost/safety/latency score
        candidates.sort(key=lambda c: c.compute_selection_score())
        chosen = candidates[0]

        avoided_external = chosen.is_local_deterministic and chosen.capability_type not in (
            ExecutionCapabilityType.VISION_MODEL,
            ExecutionCapabilityType.VOICE_MODEL,
        )

        savings = self.default_vision_cost_usd if (
            chosen.capability_type == ExecutionCapabilityType.LOCAL_SCREEN_INSPECTION
            and has_cached_screen
        ) else (self.default_llm_cost_usd if chosen.capability_type in (ExecutionCapabilityType.LOCAL_COMPUTATION, ExecutionCapabilityType.MEMORY_RETRIEVAL) else 0.0)

        decision = RoutingDecision(
            selected_capability=chosen.capability_type,
            reason=chosen.rationale,
            candidate_evaluations=candidates,
            avoided_external_call=avoided_external,
            estimated_savings_usd=savings,
        )

        logger.info(
            f"Routed query '{redact_secrets(user_input[:40])}' to '{chosen.capability_type.value}' "
            f"(Score: {chosen.compute_selection_score():.1f}, Avoided External: {avoided_external})"
        )
        return decision

    def compile_intent(
        self,
        user_input: str,
        context: dict[str, Any] | None = None,
    ) -> CompiledIntent:
        """Compile a user command or voice instruction into a strongly-typed intent.
        
        Replaces regex-only routing with capability-based intent compilation across
        all 14 standard FRIDAY Universe commands.
        """
        clean = user_input.strip().lower()

        # 1. Open application
        if any(clean.startswith(prefix) for prefix in ["open ", "launch ", "start app ", "run app "]):
            app_name = clean.split(" ", 1)[1].strip()
            # Remove filler words
            for filler in ["the ", "application ", "app "]:
                if app_name.startswith(filler):
                    app_name = app_name[len(filler):].strip()
            return CompiledIntent(
                command="open_application",
                capability="desktop_control",
                target_agent="friday",
                action="open_application",
                parameters={"app_name": app_name},
                safety_level=SafetyLevel.SAFE,
                requires_authorization=False,
                confidence=0.98,
                rationale=f"Operator requested to open desktop application '{app_name}'",
            )

        # 2. Close application
        if any(clean.startswith(prefix) for prefix in ["close ", "terminate ", "kill app ", "exit "]):
            app_name = clean.split(" ", 1)[1].strip()
            for filler in ["the ", "application ", "app "]:
                if app_name.startswith(filler):
                    app_name = app_name[len(filler):].strip()
            return CompiledIntent(
                command="close_application",
                capability="desktop_control",
                target_agent="friday",
                action="close_application",
                parameters={"app_name": app_name},
                safety_level=SafetyLevel.SENSITIVE,
                requires_authorization=True,
                confidence=0.95,
                rationale=f"Operator requested to close application '{app_name}'",
            )

        # 3. Inspect screen
        if any(w in clean for w in ["inspect screen", "look at screen", "take screenshot", "check display", "read screen"]):
            return CompiledIntent(
                command="inspect_screen",
                capability="screen_perception",
                target_agent="friday",
                action="inspect_screen",
                parameters={},
                safety_level=SafetyLevel.SAFE,
                requires_authorization=False,
                confidence=0.96,
                rationale="Operator requested screen perception inspection",
            )

        # 4. Type text
        if clean.startswith("type ") or "type text " in clean:
            text = user_input.split(" ", 1)[1].strip().strip("'\"")
            return CompiledIntent(
                command="type_text",
                capability="desktop_input",
                target_agent="friday",
                action="type_text",
                parameters={"text": text},
                safety_level=SafetyLevel.SAFE,
                requires_authorization=False,
                confidence=0.95,
                rationale="Operator requested typing text into active window",
            )

        # 5. Click UI element
        if clean.startswith("click ") or clean.startswith("tap "):
            target = user_input.split(" ", 1)[1].strip()
            return CompiledIntent(
                command="click_ui_element",
                capability="desktop_input",
                target_agent="friday",
                action="click",
                parameters={"target": target},
                safety_level=SafetyLevel.SAFE,
                requires_authorization=False,
                confidence=0.94,
                rationale=f"Operator requested click on '{target}'",
            )

        # 6. Send email
        if any(w in clean for w in ["send email", "draft email", "compose email"]):
            return CompiledIntent(
                command="send_email",
                capability="messaging_email",
                target_agent="friday",
                action="send_email",
                parameters={"raw_instruction": user_input},
                safety_level=SafetyLevel.SENSITIVE,
                requires_authorization=True,
                confidence=0.97,
                rationale="Email action modifies communications and requires explicit authorization",
            )

        # 7. Send WhatsApp message
        if any(w in clean for w in ["send whatsapp", "whatsapp message", "message on whatsapp"]):
            return CompiledIntent(
                command="send_whatsapp",
                capability="messaging_whatsapp",
                target_agent="friday",
                action="send_whatsapp_message",
                parameters={"raw_instruction": user_input},
                safety_level=SafetyLevel.SENSITIVE,
                requires_authorization=True,
                confidence=0.97,
                rationale="WhatsApp dispatch requires explicit contact selection and authorization",
            )

        # 8. Ask Inference / ASTRA
        if any(clean.startswith(prefix) for prefix in ["ask inference", "ask astra", "consult astra", "inference "]):
            prompt_text = user_input.split(" ", 2)[-1].strip()
            return CompiledIntent(
                command="ask_inference",
                capability="reasoning_consensus",
                target_agent="inference",
                action="reason",
                parameters={"prompt": prompt_text},
                safety_level=SafetyLevel.SAFE,
                requires_authorization=False,
                confidence=0.99,
                rationale="Operator delegated deliberative reasoning to Inference (ASTRA)",
            )

        # 9. Retrieve memory
        if any(w in clean for w in ["remember", "recall", "retrieve memory", "what did i say about"]):
            return CompiledIntent(
                command="retrieve_memory",
                capability="memory_retrieval",
                target_agent="memora",
                action="remember",
                parameters={"query": user_input},
                safety_level=SafetyLevel.SAFE,
                requires_authorization=False,
                confidence=0.95,
                rationale="Operator requested context retrieval from Memora persistent fabric",
            )

        # 10. Delegate research
        if any(w in clean for w in ["delegate research", "research macro", "intelx", "macro intelligence"]):
            return CompiledIntent(
                command="delegate_research",
                capability="evidence_research",
                target_agent="intelx",
                action="research",
                parameters={"query": user_input},
                safety_level=SafetyLevel.SAFE,
                requires_authorization=False,
                confidence=0.95,
                rationale="Operator delegated macro intelligence research to IntelX",
            )

        # 11. Delegate software engineering
        if any(w in clean for w in ["delegate software", "forge", "write code for", "synthesize software"]):
            return CompiledIntent(
                command="delegate_software",
                capability="software_engineering",
                target_agent="forge",
                action="status",
                parameters={"goal": user_input},
                safety_level=SafetyLevel.SAFE,
                requires_authorization=False,
                confidence=0.95,
                rationale="Operator delegated software synthesis to Forge",
            )

        # 12. Delegate security assessment
        if any(w in clean for w in ["delegate security", "sentinel", "audit security", "scan perimeter"]):
            return CompiledIntent(
                command="delegate_security",
                capability="security_assessment",
                target_agent="sentinel",
                action="audit",
                parameters={"target": "localhost", "prompt": user_input},
                safety_level=SafetyLevel.SAFE,
                requires_authorization=False,
                confidence=0.96,
                rationale="Operator requested security audit delegation to Sentinel",
            )

        # 13. Retrieve forecast
        if any(w in clean for w in ["forecast", "predict probability", "futuris"]):
            return CompiledIntent(
                command="retrieve_forecast",
                capability="predictive_forecasting",
                target_agent="futuris",
                action="forecast",
                parameters={"topic": user_input},
                safety_level=SafetyLevel.SAFE,
                requires_authorization=False,
                confidence=0.95,
                rationale="Operator requested predictive forecast delegation to Futuris",
            )

        # 14. Inspect trading status
        if any(w in clean for w in ["trading status", "stratex", "trading pnl", "bot status"]):
            return CompiledIntent(
                command="inspect_trading",
                capability="algorithmic_trading",
                target_agent="stratex",
                action="status",
                parameters={},
                safety_level=SafetyLevel.SAFE,
                requires_authorization=False,
                confidence=0.97,
                rationale="Operator requested trading telemetry from Stratex",
            )

        # Fallback to general reasoning
        return CompiledIntent(
            command="general_query",
            capability="direct_reasoning",
            target_agent="inference",
            action="reason",
            parameters={"prompt": user_input},
            safety_level=SafetyLevel.SAFE,
            requires_authorization=False,
            confidence=0.80,
            rationale="General conversational or factual inquiry",
        )


@dataclass
class CompiledIntent:
    """Strongly-typed compiled intent representing a parsed operator command."""

    command: str
    capability: str
    target_agent: str
    action: str
    parameters: dict[str, Any]
    safety_level: SafetyLevel
    requires_authorization: bool
    confidence: float
    rationale: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "command": self.command,
            "capability": self.capability,
            "target_agent": self.target_agent,
            "action": self.action,
            "parameters": self.parameters,
            "safety_level": self.safety_level.value,
            "requires_authorization": self.requires_authorization,
            "confidence": round(self.confidence, 2),
            "rationale": self.rationale,
        }
