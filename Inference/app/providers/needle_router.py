"""Needle fast-path router for Inference (TASK-INF-038).

Adapts the cactus-compute Needle tool-calling model (scouted-repos card
``cactus-needle.md``, verdict: adapt) into Inference as an optional
pre-routing stage in ``ModelGateway``.

Background
----------
TASK-IG-INF-04 piloted Needle 2 on the sandbox (cactus-compute 4.2.2, 8
FRIDAY-flavoured prompts; see ``Inference/docs/LOCAL_INFERENCE_ASSESSMENT.md``
§5–§6): 6/6 command prompts routed to the correct tool with correct
arguments, with two design constraints that this module enforces:

1. No-tool prompts can dead-end — "What is the capital of France?" produced
   no answer at all. A fast path must treat needle as a *router* with a
   mandatory escalate-on-no-call rule, never as the final answerer.
2. Session state leaks across commands — "Tell me a one-line joke" re-ran the
   previous turn's memory search. A command fast path must use a fresh,
   stateless session per command. (cactus 4.2.0 supports this natively:
   ``Cactus(..., stateless=True)`` resets state at the start of every call.)

Model confidence (0.36–0.66 in the pilot) does NOT separate success from
failure — the dead-end failure scored 0.60 — so confidence is recorded for
observability only and is never used as a routing gate.

Shape
-----
The gateway calls :func:`try_fast_path` for a request. When the fast path is
enabled and a local needle engine routes the single user command to one of
the fixed FRIDAY device-safe tools, the gateway answers with the tool call
directly (``finish_reason="tool_calls"``) and spends no cloud round trip.
Anything else — disabled, multi-message request, no-call, unknown tool,
invalid arguments, engine error — returns ``None`` and the request falls
through to the normal provider ladder exactly as before. The gateway never
executes tools; the caller executes them with its own executors, so the
engine is used through ``Cactus.complete()`` (routing only), never
``Cactus.run()`` (which executes the tool functions itself).

Configuration (env vars, read directly — see ``token_compression.py``; do not
edit ``app/core/config.py``, which has CRLF line endings):

* ``NEEDLE_FAST_PATH_ENABLED`` — "true"/"1"/"yes" enables the stage.
  Default False. The stage is off until the owner enables it after the
  device admission gate (IG-INF-04 §6: re-run the pilot prompt set, extended
  with the two failure prompts as regression cases, plus a 20-command
  FRIDAY-flavoured set, on the actual device, requiring ≥95% correct
  routing and zero dead-end turns).
* ``NEEDLE_ENGINE`` — engine name. Default "cactus". Only "cactus" exists.

The ``cactus`` package is imported lazily, inside
:class:`CactusNeedleEngine`, so importing this module never requires it
(``test_module_importability.py`` imports every module under ``app/``).
"""

from __future__ import annotations

import asyncio
import json
import os
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Protocol

from app.providers.base import ProviderRequest, ProviderResponse
from app.utils.logger import logger

PROVIDER_NAME = "needle"
MODEL_NAME = "needle-2"

# The pilot's three FRIDAY device-safe tools. The registry is intentionally
# fixed: adding a tool is a code change, reviewed like any other gateway
# change, because a routed tool call is executed by the caller.
DEFAULT_SYSTEM_INSTRUCTION = (
    "You are a fast on-device command router. Route the user's command to "
    "exactly one of the provided tools when it clearly asks for that tool. "
    "If the command does not ask for any of the tools, do not call one."
)


@dataclass(frozen=True)
class ToolSpec:
    """One tool the needle engine may route a command to."""

    name: str
    description: str
    # JSON-schema parameters object, e.g.
    # {"type": "object", "properties": {"city": {"type": "string"}},
    #  "required": ["city"]}
    parameters: dict[str, Any]


DEFAULT_TOOL_REGISTRY: tuple[ToolSpec, ...] = (
    ToolSpec(
        name="get_weather",
        description="Get the current weather for a city.",
        parameters={
            "type": "object",
            "properties": {
                "city": {
                    "type": "string",
                    "description": "City name, e.g. Mumbai.",
                },
            },
            "required": ["city"],
        },
    ),
    ToolSpec(
        name="set_reminder",
        description="Set a reminder for some minutes from now.",
        parameters={
            "type": "object",
            "properties": {
                "text": {
                    "type": "string",
                    "description": "What to be reminded about.",
                },
                "minutes": {
                    "type": "integer",
                    "description": "Minutes from now.",
                },
            },
            "required": ["text", "minutes"],
        },
    ),
    ToolSpec(
        name="search_memory",
        description="Search the user's stored memory notes for a query.",
        parameters={
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "What to search memory for.",
                },
            },
            "required": ["query"],
        },
    ),
)


@dataclass
class EngineCall:
    """One tool call produced by a needle engine for a prompt."""

    tool_name: str
    arguments: dict[str, Any]
    confidence: float | None = None


@dataclass
class RouteDecision:
    """Outcome of routing one command through the needle fast path."""

    routed: bool
    tool_name: str | None = None
    arguments: dict[str, Any] | None = None
    confidence: float | None = None
    # Why the command was not routed (None when routed). The gateway falls
    # through to the provider ladder on any escalate reason.
    escalate_reason: str | None = None
    latency_seconds: float = 0.0


class NeedleSession(Protocol):
    """One stateless routing session: created per command, used once."""

    def route_once(
        self,
        prompt: str,
        tools: tuple[ToolSpec, ...],
        system_instruction: str,
    ) -> EngineCall | None:
        """Route one prompt. None means the engine made no tool call."""
        ...

    def close(self) -> None:
        """Release session resources (a no-op for engines that share one)."""
        ...


class NeedleEngine(Protocol):
    """A needle engine. Must return a fresh session per command."""

    def new_session(self) -> NeedleSession:
        """Create a fresh, stateless session for one command."""
        ...


def fast_path_enabled() -> bool:
    """Whether the needle fast-path stage is enabled (env, default False)."""
    return os.environ.get("NEEDLE_FAST_PATH_ENABLED", "").strip().lower() in (
        "1",
        "true",
        "yes",
    )


def engine_name() -> str:
    """Configured needle engine name (env, default "cactus")."""
    return os.environ.get("NEEDLE_ENGINE", "cactus").strip().lower() or "cactus"


def _tool_schemas(tools: tuple[ToolSpec, ...]) -> list[dict[str, Any]]:
    """Tool registry as cactus dict schemas (no executables needed)."""
    return [
        {
            "name": tool.name,
            "description": tool.description,
            "parameters": tool.parameters,
        }
        for tool in tools
    ]


_JSON_TYPE_CHECKS: dict[str, Any] = {
    "string": lambda v: isinstance(v, str),
    "integer": lambda v: isinstance(v, int) and not isinstance(v, bool),
    "number": lambda v: isinstance(v, (int, float)) and not isinstance(v, bool),
    "boolean": lambda v: isinstance(v, bool),
}


def _validate_call(
    call: EngineCall, tools: tuple[ToolSpec, ...]
) -> str | None:
    """Validate a routed call against the registry.

    Returns an escalate reason, or None when the call is valid. A call to an
    unregistered tool or with missing/mistyped required arguments is never
    routed — it escalates to the cloud ladder instead.
    """
    spec = next((t for t in tools if t.name == call.tool_name), None)
    if spec is None:
        return f"unregistered-tool:{call.tool_name}"
    if not isinstance(call.arguments, dict):
        return "invalid-arguments:not-an-object"
    properties = (spec.parameters or {}).get("properties") or {}
    for required in (spec.parameters or {}).get("required") or []:
        if required not in call.arguments:
            return f"invalid-arguments:missing-{required}"
        expected = properties.get(required, {}).get("type")
        check = _JSON_TYPE_CHECKS.get(expected) if expected else None
        if check is not None and not check(call.arguments[required]):
            return f"invalid-arguments:bad-type-{required}"
    return None


class NeedleRouter:
    """Routes one command through a needle engine, enforcing the pilot's
    two constraints: escalate-on-no-call, and a fresh session per command."""

    def __init__(
        self,
        engine: NeedleEngine,
        tools: tuple[ToolSpec, ...] = DEFAULT_TOOL_REGISTRY,
        system_instruction: str = DEFAULT_SYSTEM_INSTRUCTION,
    ) -> None:
        self._engine = engine
        self._tools = tools
        self._system_instruction = system_instruction

    def route(self, prompt: str) -> RouteDecision:
        """Route one command. Never raises for an engine failure — a failed
        engine escalates to the cloud ladder like a no-call does."""
        started = time.monotonic()
        try:
            session = self._engine.new_session()
        except Exception as exc:  # noqa: BLE001 - engine failure escalates
            logger.warning("NEEDLE: engine error; escalating to cloud: %s", exc)
            return RouteDecision(
                routed=False,
                escalate_reason="engine-error",
                latency_seconds=time.monotonic() - started,
            )
        try:
            try:
                call = session.route_once(
                    prompt, self._tools, self._system_instruction
                )
            except Exception as exc:  # noqa: BLE001 - engine failure escalates
                logger.warning("NEEDLE: engine error; escalating to cloud: %s", exc)
                return RouteDecision(
                    routed=False,
                    escalate_reason="engine-error",
                    latency_seconds=time.monotonic() - started,
                )
        finally:
            try:
                session.close()
            except Exception:  # noqa: BLE001 - close must never break routing
                pass
        if call is None:
            # Pilot constraint 1: a no-call is an escalate, never an answer.
            return RouteDecision(
                routed=False,
                escalate_reason="no-call",
                latency_seconds=time.monotonic() - started,
            )
        invalid = _validate_call(call, self._tools)
        if invalid is not None:
            logger.warning("NEEDLE: invalid routed call (%s); escalating.", invalid)
            return RouteDecision(
                routed=False,
                escalate_reason=invalid,
                latency_seconds=time.monotonic() - started,
            )
        # Confidence is recorded for observability only — the pilot proved it
        # does not separate success from failure, so it is never a gate.
        return RouteDecision(
            routed=True,
            tool_name=call.tool_name,
            arguments=call.arguments,
            confidence=call.confidence,
            latency_seconds=time.monotonic() - started,
        )


class _CactusSession:
    """One routing session over the shared Cactus instance.

    The agent is constructed with ``stateless=True``, so every
    ``complete()`` call resets engine state first — a session can never see
    a previous command's context (pilot constraint 2).
    """

    def __init__(self, engine: "CactusNeedleEngine") -> None:
        self._engine = engine

    def route_once(
        self,
        prompt: str,
        tools: tuple[ToolSpec, ...],
        system_instruction: str,
    ) -> EngineCall | None:
        agent = self._engine._agent(tools, system_instruction)
        response = agent.complete(prompt)
        if not isinstance(response, dict):
            raise RuntimeError(
                f"cactus complete() returned {type(response).__name__}, expected dict"
            )
        calls = response.get("function_calls") or []
        if response.get("type") != "call" or not calls:
            return None
        first = calls[0]
        if not isinstance(first, dict):
            return None
        return EngineCall(
            tool_name=str(first.get("name") or ""),
            arguments=first.get("arguments") or {},
            confidence=response.get("confidence"),
        )

    def close(self) -> None:
        # The Cactus instance is shared and process-owned; nothing to close
        # per session. State is reset by the engine itself on each call.
        return None


class CactusNeedleEngine:
    """Needle engine backed by the cactus-compute package (Needle 2).

    The ``cactus`` package is imported lazily, inside the constructor, so
    this module imports cleanly where the package is absent. The Cactus
    agent itself is built lazily on first use (first construction downloads
    the ~71 MB engine + weights cache, ~53 s on the sandbox pilot) and then
    cached for the process; it is constructed once per tool registry +
    system instruction.
    """

    def __init__(self, _import_cactus: Any = None) -> None:
        self._import_cactus = _import_cactus or _default_import_cactus
        try:
            self._cactus = self._import_cactus()
        except ImportError as exc:
            raise RuntimeError(
                "cactus package is not installed; the needle fast path "
                "needs it: pip install cactus-compute (or cactus>=4.2). "
                "Install it on the device that runs the fast path, then "
                "set NEEDLE_FAST_PATH_ENABLED=true."
            ) from exc
        self._lock = threading.Lock()
        self._agent: Any = None
        self._agent_key: tuple[Any, ...] | None = None

    def _agent(self, tools: tuple[ToolSpec, ...], system_instruction: str) -> Any:
        key = (tuple((t.name, t.description) for t in tools), system_instruction)
        with self._lock:
            if self._agent is None or self._agent_key != key:
                # cactus dict schemas carry no executables: complete() only
                # routes; the caller executes the tool call.
                self._agent = self._cactus.Cactus(
                    tools=_tool_schemas(tools),
                    system=system_instruction,
                    stateless=True,
                )
                self._agent_key = key
            return self._agent

    def new_session(self) -> NeedleSession:
        return _CactusSession(self)

    def close(self) -> None:
        """Close the shared agent (process shutdown only)."""
        with self._lock:
            agent, self._agent = self._agent, None
            self._agent_key = None
        if agent is not None:
            try:
                agent.close()
            except Exception:  # noqa: BLE001 - close must never raise
                pass


def _default_import_cactus() -> Any:
    import cactus  # noqa: PLC0415 - lazy import; package is optional

    return cactus


class StubNeedleEngine:
    """Deterministic replay engine for tests.

    ``replay`` maps a prompt to the call the engine returns for it (or None
    for a no-call). Unknown prompts return None. ``error`` makes every
    ``route_once`` raise, simulating an engine failure. Sessions are tracked
    so tests can assert the router creates a fresh session per command.
    """

    def __init__(
        self,
        replay: dict[str, EngineCall | None] | None = None,
        error: Exception | None = None,
    ) -> None:
        self._replay = dict(replay or {})
        self._error = error
        self.sessions: list[_StubSession] = []

    def new_session(self) -> NeedleSession:
        session = _StubSession(self)
        self.sessions.append(session)
        return session

    def _lookup(self, prompt: str) -> EngineCall | None:
        if self._error is not None:
            raise self._error
        return self._replay.get(prompt)


class _StubSession:
    def __init__(self, engine: StubNeedleEngine) -> None:
        self._engine = engine
        self.calls: list[str] = []
        self.closed = False

    def route_once(
        self,
        prompt: str,
        tools: tuple[ToolSpec, ...],
        system_instruction: str,
    ) -> EngineCall | None:
        self.calls.append(prompt)
        return self._engine._lookup(prompt)

    def close(self) -> None:
        self.closed = True


def build_engine(name: str) -> NeedleEngine:
    """Build a needle engine by name. Only "cactus" exists."""
    if name == "cactus":
        return CactusNeedleEngine()
    raise ValueError(f"unknown needle engine: {name!r} (only 'cactus' exists)")


async def try_fast_path(
    request: ProviderRequest, engine: NeedleEngine | None = None
) -> ProviderResponse | None:
    """Try the needle fast path for one request.

    Returns a tool-call ``ProviderResponse`` when the request is a single
    user command that the needle engine routes to a registry tool, else
    ``None`` (fast path disabled, multi-message request, no-call, invalid
    call, engine error). Never raises: a fast-path failure must never break
    serving — the caller falls through to the provider ladder.
    """
    if not fast_path_enabled():
        return None
    if len(request.messages) != 1 or request.messages[0].role != "user":
        return None
    prompt = request.messages[0].content or ""
    if not prompt.strip():
        return None
    try:
        resolved = engine if engine is not None else build_engine(engine_name())
    except Exception as exc:  # noqa: BLE001 - engine build failure escalates
        logger.warning("NEEDLE: engine unavailable; escalating to cloud: %s", exc)
        return None
    router = NeedleRouter(resolved)
    try:
        decision = await asyncio.to_thread(router.route, prompt)
    except Exception as exc:  # noqa: BLE001 - routing failure escalates
        logger.warning("NEEDLE: routing failed; escalating to cloud: %s", exc)
        return None
    if not decision.routed:
        return None
    tool_call = {
        "id": f"needle-{int(time.time() * 1000)}",
        "type": "function",
        "function": {
            "name": decision.tool_name,
            "arguments": json.dumps(decision.arguments or {}),
        },
    }
    return ProviderResponse(
        content="",
        model=MODEL_NAME,
        provider=PROVIDER_NAME,
        finish_reason="tool_calls",
        tool_calls=[tool_call],
        latency_seconds=decision.latency_seconds,
        raw_response={
            "tool_calls": [tool_call],
            "needle": {
                "tool": decision.tool_name,
                "confidence": decision.confidence,
                "latency_seconds": decision.latency_seconds,
            },
        },
    )
