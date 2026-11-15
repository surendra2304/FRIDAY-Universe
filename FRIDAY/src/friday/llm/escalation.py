"""TASK-REL-044 — FRIDAY routing policy: own keys for chat, Inference for
complex work (owner decision, 2026-11-15).

The owner's policy, in his words: FRIDAY uses the API keys in its own env
to talk and chat with him; when he assigns a COMPLEX task — where its own
keys/usage are not enough — FRIDAY then uses Inference to get more usage.

Before this task, ``FRIDAY_LLM_PROVIDER=gemini`` routed every turn to
FRIDAY's own 5-key Gemini pool (with TASK-REL-010's Groq exhaustion
failover): a one-line chat and a multi-step delegated research task drew
on the same ~20-requests/day/model free-tier pool, while Inference's big
pools (11 Gemini + 14 Groq + 14 OpenRouter, best-suitable substitution
policy since TASK-REL-043) sat unused by FRIDAY's brain.

This module implements the policy as three pieces:

* :class:`TurnRouteContext` — a per-turn record bound in a ContextVar
  (the TASK-REL-025/039 pattern): the turn's channel, its classified
  task kinds, the capability-router verdict, and a running count of
  tool-loop iterations. ``process_message`` binds it before the
  cognitive loop; ``execute_complex_task`` binds a default for direct
  callers and keeps the iteration count current.

* :func:`classify_turn_complexity` — a deterministic classifier over
  signals FRIDAY already has (the goal text, the CapabilityRouter
  verdict, the intent tier's ``required_tools``). No model call, no
  vibes: explicit pattern tables in the codebase's house style.

* :class:`EscalatingLLMProvider` — wraps the own-pool provider stack.
  A generate() call is served by Inference when a trigger holds:
  (a) the turn is classified complex (delegation / research / code
  generation / long-form synthesis / multi-step), or the turn's tool
  chain has grown past the depth threshold; (b) the own pool reports
  credential exhaustion. Every escalation is logged with its trigger
  and the serving model, recorded on the turn context (surfaced in the
  response metadata as ``llm_routing``), and the Inference provenance
  block flows through on the message metadata. If Inference is
  unreachable or degraded, the call falls back to FRIDAY's own pool —
  a turn never hard-fails because escalation failed.

Escalation target — chosen on live probes (Server 1, 2026-11-15):
``/v1/chat/completions``, NOT ``/v1/friday/ask``. The ask contract
capped a complex prompt at 35 words with confidence 0.55 (below
FRIDAY's own 0.70 verification gate; the model visibly fought the
~40-word cap). Chat completions answered the same prompt class with
substance. The model is requested BY TASK KIND from Inference's
verified catalogue (never ``auto`` — its fast lane returned the same
21-word stub twice, served by a non-catalogue 20b model):

* code / reasoning / delegation / research / multi-step ->
  ``openai/gpt-oss-120b`` (catalogue flagship for reasoning and code;
  probe: 187-word correct code answer in 1.3 s)
* long-form synthesis -> ``gemini-3.8-flash`` (catalogue long-context
  flagship; probe: 336-word structured answer, served by
  gemini-3.6-flash WITH the REL-043 provenance block when its route
  substituted)

Inference's gateway has NO native tool-calling surface (its request
schema is messages-only and flattens them into a prompt), so an
escalated call that carries tools bridges through FRIDAY's existing
text tool-markup protocol: the tools are described in the prompt with
the exact ``<tool name="..." params='...'/>`` spelling that
TASK-REL-006A's recovery (``friday.llm.tool_markup``) already parses
back into real tool calls in the agent loop — and this provider runs
the same recovery itself before returning.

Voice is deliberately untouched: turns bound with ``channel="voice"``
never complexity-escalate (the Gemini Live path keeps its exact
behaviour and latency profile); only the pool-exhaustion safety net
applies to them, as it does to every turn. The REL-040 time fast path
never reaches the provider layer at all.

Kill switch: ``FRIDAY_LLM_ESCALATION=off`` disables escalation
entirely (the factory then builds exactly the pre-REL-044 stack).
Depth threshold: ``FRIDAY_LLM_ESCALATION_DEPTH`` (default 3).
Inference call timeout: ``FRIDAY_LLM_ESCALATION_TIMEOUT_S``
(default 150).
"""

from __future__ import annotations

import contextvars
import os
import re
import time
from dataclasses import dataclass, field
from typing import Any

from friday.core.exceptions import LLMProviderError
from friday.core.logging import get_logger
from friday.core.types import Message, Role, TrustLevel
from friday.llm.base import BaseLLMProvider

logger = get_logger("llm.escalation")

# ---------------------------------------------------------------------------
# Task kinds (the classifier's vocabulary)
# ---------------------------------------------------------------------------

KIND_DELEGATION = "delegation"
KIND_RESEARCH = "research"
KIND_CODE_GENERATION = "code_generation"
KIND_SYNTHESIS = "long_form_synthesis"
KIND_MULTISTEP = "multi_step"

COMPLEX_KINDS = frozenset({
    KIND_DELEGATION,
    KIND_RESEARCH,
    KIND_CODE_GENERATION,
    KIND_SYNTHESIS,
    KIND_MULTISTEP,
})

#: Registered tools whose presence in the intent tier's required_tools
#: marks the turn as that kind of complex work.
_DELEGATION_TOOLS = {"fleet_dispatch"}
_RESEARCH_TOOLS = {"intelx_research", "fetch_webpage_content", "web_search"}
_CODEGEN_TOOLS = {"forge_code_task"}
_SYNTHESIS_TOOLS = {"synthesize_information"}

#: Specialist agent names a delegation can target.
_AGENT_NAMES = (
    "stratex", "intelx", "forge", "sentinel", "cortex",
    "vyralx", "futuris", "memora", "inference",
)

_DELEGATION_RES = (
    re.compile(
        r"\b(?:ask|tell|have|let|get|send|delegate|assign|hand|pass)\b"
        r"[^.?!]{0,60}?\b(?:" + "|".join(_AGENT_NAMES) + r")\b",
        re.IGNORECASE,
    ),
    re.compile(r"\bdelegate\b", re.IGNORECASE),
    re.compile(r"\bsend\s+(?:this|it|the\s+task|that)\s+to\b", re.IGNORECASE),
    re.compile(r"\bhand\s+(?:this|it)\s+(?:off\s+)?to\b", re.IGNORECASE),
)

_RESEARCH_RES = (
    re.compile(r"\bresearch\b", re.IGNORECASE),
    re.compile(r"\binvestigat\w*\b", re.IGNORECASE),
    re.compile(r"\blook\s+into\b", re.IGNORECASE),
    re.compile(r"\bfind\s+out\b", re.IGNORECASE),
    re.compile(r"\bdeep\s*dive\b", re.IGNORECASE),
    re.compile(r"\bgather\s+(?:information|intel|evidence|data)\b", re.IGNORECASE),
    re.compile(r"\bsearch\s+(?:the\s+web|online)\b", re.IGNORECASE),
)

_CODEGEN_RES = (
    re.compile(r"\bwrite\s+(?:me\s+)?(?:a\s+|an\s+|the\s+)?(?:python\s+|bash\s+|shell\s+)?(?:code|script|program|function|app|tool|bot)\b", re.IGNORECASE),
    re.compile(r"\b(?:create|build|make)\s+(?:me\s+)?(?:a\s+|an\s+|the\s+)?(?:python\s+)?(?:script|program|function|app|tool|bot|website|web\s*page)\b", re.IGNORECASE),
    re.compile(r"\bimplement\b", re.IGNORECASE),
    re.compile(r"\bfix\s+(?:the\s+|this\s+)?(?:bug|error|code)\b", re.IGNORECASE),
    re.compile(r"\bdebug\b", re.IGNORECASE),
    re.compile(r"\brefactor\b", re.IGNORECASE),
    re.compile(r"\bcode\s+(?:that|to|for)\b", re.IGNORECASE),
)

_SYNTHESIS_RES = (
    re.compile(r"\bwrite\s+(?:me\s+)?(?:a\s+|an\s+|the\s+)?(?:detailed\s+|full\s+|complete\s+)?(?:report|essay|plan|proposal|article|document|brief|summary|analysis)\b", re.IGNORECASE),
    re.compile(r"\bdraft\b", re.IGNORECASE),
    re.compile(r"\bcompose\b", re.IGNORECASE),
    re.compile(r"\bexplain\s+in\s+detail\b", re.IGNORECASE),
    re.compile(r"\bin\s+detail\b[^.?!]{0,40}?\b(?:explain|describe|cover|analyse|analyze)\b", re.IGNORECASE),
    re.compile(r"\bstep[-\s]by[-\s]step\s+(?:guide|plan|instructions|explanation)\b", re.IGNORECASE),
    re.compile(r"\bdetailed\s+(?:report|analysis|explanation|plan|breakdown)\b", re.IGNORECASE),
)

_MULTISTEP_MARKERS = (
    " and then ", " after that ", " then ", " next, ", " finally, ",
    " first ", "; ",
)
_ACTION_VERBS = (
    "open", "close", "send", "create", "write", "check", "find", "search",
    "book", "buy", "download", "upload", "delete", "update", "schedule",
    "call", "play", "set", "turn", "start", "stop", "run", "make",
    "add", "remove", "tell", "ask", "research", "analyse", "analyze",
)


def _matches_any(patterns: tuple[re.Pattern, ...], text: str) -> bool:
    return any(p.search(text) for p in patterns)


def classify_turn_complexity(
    goal: str,
    *,
    routed_capability: str | None = None,
    intent: str | None = None,
    required_tools: list[str] | None = None,
) -> frozenset[str]:
    """Classify a turn into complex-task kinds from signals FRIDAY has.

    Deterministic and table-driven — the same inputs always give the
    same kinds. An empty result means plain conversation: the turn
    stays on FRIDAY's own pool. ``TOOL_EXECUTION`` routing alone is NOT
    complex (a single device action like "open notepad" routes there
    and must keep its native-tool, own-pool path); ``BACKGROUND_TASK``
    routing is a delegation by definition.
    """
    kinds: set[str] = set()
    text = " ".join((goal or "").strip().lower().split())
    tools = {t.strip() for t in (required_tools or []) if t and t.strip()}

    capability = (routed_capability or "").strip().upper()
    if tools & _DELEGATION_TOOLS or capability == "BACKGROUND_TASK":
        kinds.add(KIND_DELEGATION)
    if tools & _RESEARCH_TOOLS:
        kinds.add(KIND_RESEARCH)
    if tools & _CODEGEN_TOOLS:
        kinds.add(KIND_CODE_GENERATION)
    if tools & _SYNTHESIS_TOOLS:
        kinds.add(KIND_SYNTHESIS)

    if text:
        if _matches_any(_DELEGATION_RES, text):
            kinds.add(KIND_DELEGATION)
        if _matches_any(_RESEARCH_RES, text):
            kinds.add(KIND_RESEARCH)
        if _matches_any(_CODEGEN_RES, text):
            kinds.add(KIND_CODE_GENERATION)
        if _matches_any(_SYNTHESIS_RES, text):
            kinds.add(KIND_SYNTHESIS)
        # Multi-step: explicit sequencing markers, a numbered plan, or
        # three or more distinct action verbs in one instruction.
        if (
            sum(1 for m in _MULTISTEP_MARKERS if m in f" {text} ") >= 2
            or re.search(r"\b1[.)]\s.*\b2[.)]\s", text)
            or len({v for v in _ACTION_VERBS if re.search(rf"\b{v}\b", text)}) >= 3
        ):
            kinds.add(KIND_MULTISTEP)
    return frozenset(kinds)


# ---------------------------------------------------------------------------
# Per-turn route context (TASK-REL-025/039 ContextVar pattern)
# ---------------------------------------------------------------------------


@dataclass
class TurnRouteContext:
    """Routing signals + escalation record for one turn."""

    channel: str = "chat"  # "chat" | "voice" | "other"
    goal: str = ""
    task_kinds: frozenset[str] = frozenset()
    routed_capability: str | None = None
    intent: str | None = None
    tool_iterations: int = 0
    events: list[dict[str, Any]] = field(default_factory=list)

    @property
    def is_complex(self) -> bool:
        return bool(self.task_kinds & COMPLEX_KINDS)

    def record_event(self, event: dict[str, Any]) -> None:
        if len(self.events) < 20:  # a turn's record stays small
            self.events.append(event)


_turn_route_context: contextvars.ContextVar[TurnRouteContext | None] = (
    contextvars.ContextVar("friday_turn_route_context", default=None)
)


def bind_turn_route_context(ctx: TurnRouteContext | None) -> TurnRouteContext | None:
    """Bind ``ctx`` as the route context of the current execution context.

    Returns the bound context (or None when clearing), so callers can
    keep a direct handle without a second lookup.
    """
    _turn_route_context.set(ctx)
    return ctx


def current_turn_route_context() -> TurnRouteContext | None:
    """Return the route context bound to this execution context, or None."""
    return _turn_route_context.get()


# ---------------------------------------------------------------------------
# Configuration (env, house kill-switch style)
# ---------------------------------------------------------------------------


def escalation_enabled() -> bool:
    return os.getenv("FRIDAY_LLM_ESCALATION", "").strip().lower() not in (
        "off", "false", "0", "no",
    )


def _depth_threshold() -> int:
    try:
        return max(1, min(20, int(os.getenv("FRIDAY_LLM_ESCALATION_DEPTH", "3"))))
    except ValueError:
        return 3


def _inference_timeout_s() -> float:
    try:
        return max(10.0, min(600.0, float(os.getenv("FRIDAY_LLM_ESCALATION_TIMEOUT_S", "150"))))
    except ValueError:
        return 150.0


#: Verified-catalogue model requested per dominant task kind, following
#: TASK-REL-043's own suitability table (reasoning/code flagship vs
#: long-context flagship). Inference may substitute per its policy; the
#: response's provenance block + top-level model say what actually served.
_MODEL_FOR_KIND = {
    KIND_CODE_GENERATION: "openai/gpt-oss-120b",
    KIND_DELEGATION: "openai/gpt-oss-120b",
    KIND_RESEARCH: "openai/gpt-oss-120b",
    KIND_MULTISTEP: "openai/gpt-oss-120b",
    KIND_SYNTHESIS: "gemini-3.8-flash",
}
_DEFAULT_ESCALATION_MODEL = "openai/gpt-oss-120b"


def preferred_escalation_model(ctx: TurnRouteContext | None) -> str:
    if ctx is not None:
        # Code wins over synthesis when both fire (a "write a report
        # generator script" turn is a coding turn); synthesis-only
        # turns take the long-context flagship.
        if KIND_CODE_GENERATION in ctx.task_kinds:
            return _MODEL_FOR_KIND[KIND_CODE_GENERATION]
        for kind in (KIND_DELEGATION, KIND_RESEARCH, KIND_MULTISTEP, KIND_SYNTHESIS):
            if kind in ctx.task_kinds:
                return _MODEL_FOR_KIND[kind]
    return _DEFAULT_ESCALATION_MODEL


# ---------------------------------------------------------------------------
# Inference chat-completions provider
# ---------------------------------------------------------------------------

_TOOL_PROTOCOL = """

[TOOL USE — you are operating inside FRIDAY's tool loop]
You have the tools listed below. To call a tool, reply with ONLY the
markup line for each call you want to make, in exactly this spelling:
<tool name="TOOL_NAME" params='{"argument": "value"}'/>
Use the tool's real registered name and a JSON object of its arguments.
One call per line; make every call you need in a single reply. When no
tool is needed, answer the user in plain text and emit no markup.

Available tools:
__TOOL_LINES__
"""


def _tool_lines(tools: list[dict[str, Any]]) -> str:
    lines = []
    for tool in tools:
        fn = tool.get("function") if isinstance(tool, dict) else None
        spec = fn if isinstance(fn, dict) else (tool if isinstance(tool, dict) else {})
        name = spec.get("name") or "unknown"
        desc = (spec.get("description") or "").strip().replace("\n", " ")
        if len(desc) > 240:
            desc = desc[:240] + "…"
        params = spec.get("parameters") or {}
        props = params.get("properties") if isinstance(params, dict) else None
        arg_names = ", ".join(props.keys()) if isinstance(props, dict) else ""
        lines.append(f"- {name}({arg_names}): {desc}")
    return "\n".join(lines)


def _to_chat_messages(
    messages: list[Message], tools: list[dict[str, Any]] | None
) -> list[dict[str, str]]:
    """Flatten FRIDAY messages into the chat-completions wire shape."""
    out: list[dict[str, str]] = []
    system_parts: list[str] = []
    for m in messages:
        content = m.content or ""
        if m.role == Role.SYSTEM:
            system_parts.append(content)
        elif m.role == Role.TOOL:
            out.append({
                "role": "user",
                "content": f"[Result from tool '{m.name or 'tool'}']: {content}",
            })
        elif m.role == Role.ASSISTANT:
            if m.tool_calls:
                rendered = "\n".join(
                    f'<tool name="{c.name}" params=\'{_safe_json(c.arguments)}\'/>'
                    for c in m.tool_calls
                )
                content = (content + "\n" + rendered).strip() if content else rendered
            out.append({"role": "assistant", "content": content})
        else:
            out.append({"role": "user", "content": content})
    if tools:
        # str.replace, not .format: the protocol text itself contains
        # literal JSON braces that .format would choke on.
        system_parts.append(_TOOL_PROTOCOL.replace("__TOOL_LINES__", _tool_lines(tools)))
    if system_parts:
        out.insert(0, {"role": "system", "content": "\n\n".join(p for p in system_parts if p)})
    return out


def _safe_json(value: Any) -> str:
    import json as _json

    try:
        return _json.dumps(value if isinstance(value, dict) else {"value": value})
    except (TypeError, ValueError):
        return "{}"


class InferenceChatProvider(BaseLLMProvider):
    """FRIDAY-side provider for Inference's /v1/chat/completions surface.

    The escalation target of TASK-REL-044. Requests a verified-catalogue
    model chosen by the turn's task kind; captures the serving model and
    REL-043 provenance block onto the returned message's metadata; when
    the call carries tools, bridges them through the text tool-markup
    protocol and recovers any emitted calls before returning.
    """

    def __init__(
        self,
        base_url: str,
        api_key: str = "",
        temperature: float = 0.7,
        max_tokens: int = 4096,
        timeout: float | None = None,
    ) -> None:
        super().__init__(
            model="inference-escalation",
            temperature=temperature,
            max_tokens=max_tokens,
        )
        self.base_url = (base_url or "").rstrip("/")
        self.api_key = api_key or ""
        self.timeout = timeout if timeout is not None else _inference_timeout_s()

    @property
    def provider_name(self) -> str:
        return "inference"

    def generate(
        self,
        messages: list[Message],
        tools: list[dict[str, Any]] | None = None,
    ) -> Message:
        import httpx

        ctx = current_turn_route_context()
        model = preferred_escalation_model(ctx)
        payload = {
            "model": model,
            "messages": _to_chat_messages(messages, tools),
            "temperature": self.temperature,
            "max_tokens": max(256, min(int(self.max_tokens or 4096), 8192)),
        }
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
            headers["X-API-Key"] = self.api_key
        started = time.perf_counter()
        try:
            with httpx.Client(timeout=self.timeout) as client:
                resp = client.post(
                    f"{self.base_url}/v1/chat/completions",
                    json=payload,
                    headers=headers,
                )
        except Exception as exc:
            raise LLMProviderError(
                f"INFERENCE_UNAVAILABLE: transport error ({type(exc).__name__})"
            ) from exc
        latency = time.perf_counter() - started
        if resp.status_code != 200:
            # Body excerpt is operator detail for the log only; the raised
            # error stays sanitized (status + class, never payload/keys).
            logger.warning(
                f"Inference escalation call failed: HTTP {resp.status_code} "
                f"after {latency:.1f}s (body: {resp.text[:200]!r})"
            )
            raise LLMProviderError(
                f"INFERENCE_UNAVAILABLE: HTTP {resp.status_code}"
            )
        try:
            body = resp.json()
            content = body["choices"][0]["message"]["content"] or ""
        except Exception as exc:
            raise LLMProviderError(
                "INFERENCE_UNAVAILABLE: malformed chat-completions response"
            ) from exc
        served_model = body.get("model") or model
        provenance = body.get("provenance")
        logger.info(
            f"ESCALATION served by Inference: requested={model} "
            f"served={served_model} latency={latency:.1f}s "
            f"provenance={provenance if provenance else 'none (served as requested)'}"
        )
        metadata: dict[str, Any] = {
            "provider": "inference",
            "model": served_model,
            "requested_model": model,
            "inference_provenance": provenance,
            "escalation_latency_s": round(latency, 2),
        }
        if tools:
            from friday.llm.tool_markup import extract_markup_tool_calls

            calls, remaining = extract_markup_tool_calls(content)
            if calls:
                return Message(
                    role=Role.ASSISTANT,
                    content=remaining.strip(),
                    tool_calls=calls,
                    trust_level=TrustLevel.MODEL_OUTPUT,
                    metadata=metadata,
                )
        return Message(
            role=Role.ASSISTANT,
            content=content,
            trust_level=TrustLevel.MODEL_OUTPUT,
            metadata=metadata,
        )


# ---------------------------------------------------------------------------
# The escalating wrapper
# ---------------------------------------------------------------------------


class EscalatingLLMProvider(BaseLLMProvider):
    """Own-pool provider guarded by the Inference escalation policy.

    ``provider_name``/``model`` delegate to the own stack so existing
    surface telemetry (which reads ``agent.llm.provider_name``) keeps
    reporting FRIDAY's configured brain; per-call truth about which
    brain answered lives in the message metadata, the turn's
    ``llm_routing`` record, and the logs.
    """

    def __init__(
        self,
        own: BaseLLMProvider,
        inference: InferenceChatProvider,
        depth_threshold: int | None = None,
    ) -> None:
        super().__init__(
            model=own.model,
            temperature=own.temperature,
            max_tokens=own.max_tokens,
        )
        self.own = own
        self.inference = inference
        self.depth_threshold = (
            depth_threshold if depth_threshold is not None else _depth_threshold()
        )

    @property
    def provider_name(self) -> str:
        return self.own.provider_name

    def _route(
        self,
        ctx: TurnRouteContext | None,
        messages: list[Message],
        tools: list[dict[str, Any]] | None,
    ) -> tuple[str, str]:
        """Decide ('own'|'inference', trigger) for one generate() call."""
        if not escalation_enabled():
            return "own", "escalation_disabled"
        if ctx is not None:
            if ctx.channel != "voice" and ctx.is_complex:
                kinds = "+".join(sorted(ctx.task_kinds & COMPLEX_KINDS))
                return "inference", f"complex_task:{kinds}"
            if ctx.tool_iterations >= self.depth_threshold:
                return "inference", f"tool_chain_depth:{ctx.tool_iterations}"
            return "own", "chat"
        # No turn context (internal callers — planning, synthesis, lab):
        # a long tool-result trail is the shape of mid-chain complex work.
        tool_msgs = sum(1 for m in messages if m.role == Role.TOOL)
        if tool_msgs >= self.depth_threshold:
            return "inference", f"tool_chain_depth:shape:{tool_msgs}"
        return "own", "chat"

    def generate(
        self,
        messages: list[Message],
        tools: list[dict[str, Any]] | None = None,
    ) -> Message:
        ctx = current_turn_route_context()
        route, trigger = self._route(ctx, messages, tools)
        if route == "inference":
            try:
                msg = self.inference.generate(messages, tools)
            except Exception as exc:
                logger.warning(
                    f"ESCALATION trigger={trigger} failed ({type(exc).__name__}: {exc}); "
                    "falling back to FRIDAY's own pool for this call."
                )
                if ctx is not None:
                    ctx.record_event({
                        "route": "own",
                        "trigger": trigger,
                        "escalation_failed": type(exc).__name__,
                    })
                return self._generate_own(messages, tools, ctx, trigger)
            logger.info(
                f"ESCALATION trigger={trigger} served by Inference "
                f"model={msg.metadata.get('model')}"
            )
            if ctx is not None:
                ctx.record_event({
                    "route": "inference",
                    "trigger": trigger,
                    "model": msg.metadata.get("model"),
                    "requested_model": msg.metadata.get("requested_model"),
                    "provenance": msg.metadata.get("inference_provenance"),
                })
            msg.metadata.setdefault("llm_route", "inference")
            msg.metadata.setdefault("escalation_trigger", trigger)
            return msg
        return self._generate_own(messages, tools, ctx, trigger)

    def _generate_own(
        self,
        messages: list[Message],
        tools: list[dict[str, Any]] | None,
        ctx: TurnRouteContext | None,
        trigger: str,
    ) -> Message:
        try:
            msg = self.own.generate(messages, tools)
        except LLMProviderError as exc:
            if "CREDENTIAL_EXHAUSTED" not in str(exc):
                raise
            # Trigger (b): FRIDAY's own pool is dead — Inference is the
            # rung that brings more usage. (In the production gemini
            # stack the REL-010 exhaustion failover already routes here
            # first; this catch covers stacks whose own provider is bare.)
            logger.warning(
                "Own pool reports credential exhaustion; escalating to "
                "Inference for more usage (trigger=pool_exhausted)."
            )
            try:
                msg = self.inference.generate(messages, tools)
            except Exception:
                # Both brains are down: surface the ORIGINAL exhaustion
                # error — it names the root problem (the dead own pool),
                # not the failed rescue.
                raise exc
            if ctx is not None:
                ctx.record_event({
                    "route": "inference",
                    "trigger": "pool_exhausted",
                    "model": msg.metadata.get("model"),
                    "requested_model": msg.metadata.get("requested_model"),
                    "provenance": msg.metadata.get("inference_provenance"),
                })
            msg.metadata.setdefault("llm_route", "inference")
            msg.metadata.setdefault("escalation_trigger", "pool_exhausted")
            return msg
        msg.metadata.setdefault("llm_route", "own")
        return msg
