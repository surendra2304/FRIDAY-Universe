"""TASK-INF-038: needle / Cactus fast-path router for Inference.

Pins: the pilot's two design constraints from TASK-IG-INF-04
(LOCAL_INFERENCE_ASSESSMENT.md §5–§6) — escalate-on-no-call, and a fresh
stateless session per command — plus the gateway pre-stage wiring: a routed
command answers with the tool call and never touches the provider ladder;
anything else (disabled, multi-message, no-call, invalid call, engine
error) falls through to the ladder exactly as before. No network, no live
keys, no cactus package required.
"""

import asyncio
import importlib.util
import json
import os
import sys
import types

# The app lifespan builds an httpx client that reads proxy environment
# variables; some sandboxes export values this httpx version cannot parse.
# These tests are fully in-process, so proxying is never needed here.
for _v in (
    "HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy",
    "ALL_PROXY", "all_proxy", "NO_PROXY", "no_proxy",
):
    os.environ.pop(_v, None)

import pytest

import app.providers
import app.providers.gateway as gateway_module
import app.providers.needle_router as needle_router
from app.providers.base import ProviderMessage, ProviderRequest, ProviderResponse
from app.providers.gateway import KeyPool, ModelGateway
from app.providers.needle_router import (
    CactusNeedleEngine,
    EngineCall,
    NeedleRouter,
    StubNeedleEngine,
    build_engine,
    engine_name,
    fast_path_enabled,
    try_fast_path,
)

# TASK-IG-INF-04 pilot prompt set (LOCAL_INFERENCE_ASSESSMENT.md §5): 6
# command prompts the pilot routed correctly, plus the 2 failure prompts.
# The assessment records the routed tool and the discriminating argument for
# each command (weather cities, reminder minutes, memory query phrases) but
# does not quote the model's exact free-text arguments, so the assertions
# below check only what the pilot documented — tool name plus the
# discriminating argument — not the replayed free-text strings.
PILOT_REPLAY = {
    "What's the weather in Mumbai?": EngineCall(
        "get_weather", {"city": "Mumbai"}, 0.55
    ),
    "Remind me to call the bank in 20 minutes": EngineCall(
        "set_reminder", {"text": "call the bank", "minutes": 20}, 0.66
    ),
    "Search my memory for the Oracle server notes": EngineCall(
        "search_memory", {"query": "Oracle server notes"}, 0.50
    ),
    "What is the capital of France?": None,  # pilot failure 1: dead-end
    "Will it rain in Delhi tomorrow?": EngineCall(
        "get_weather", {"city": "Delhi"}, 0.48
    ),
    "Set a reminder for the eggs in 5 minutes": EngineCall(
        "set_reminder", {"text": "eggs", "minutes": 5}, 0.60
    ),
    "Find what I noted about the voice latency problem": EngineCall(
        "search_memory", {"query": "voice latency problem"}, 0.44
    ),
    "Tell me a one-line joke": None,  # pilot failure 2: stale memory search
}

PILOT_COMMANDS = {
    "What's the weather in Mumbai?": ("get_weather", "city", "Mumbai"),
    "Remind me to call the bank in 20 minutes": ("set_reminder", "minutes", 20),
    "Search my memory for the Oracle server notes": (
        "search_memory",
        "query",
        "Oracle server notes",
    ),
    "Will it rain in Delhi tomorrow?": ("get_weather", "city", "Delhi"),
    "Set a reminder for the eggs in 5 minutes": ("set_reminder", "minutes", 5),
    "Find what I noted about the voice latency problem": (
        "search_memory",
        "query",
        "voice latency problem",
    ),
}


def test_module_import_does_not_require_cactus():
    """The module must import (and the cactus package must stay unimported)
    on a machine without cactus installed — test_module_importability.py
    imports every module under app/."""
    if importlib.util.find_spec("cactus") is not None:
        pytest.skip("cactus is installed in this environment")
    assert "cactus" not in sys.modules
    assert needle_router.PROVIDER_NAME == "needle"


def test_fast_path_disabled_by_default(monkeypatch):
    monkeypatch.delenv("NEEDLE_FAST_PATH_ENABLED", raising=False)
    assert fast_path_enabled() is False


@pytest.mark.parametrize(
    "value,expected",
    [
        ("true", True),
        ("TRUE", True),
        ("1", True),
        ("yes", True),
        ("false", False),
        ("0", False),
        ("", False),
    ],
)
def test_fast_path_flag_parsing(monkeypatch, value, expected):
    monkeypatch.setenv("NEEDLE_FAST_PATH_ENABLED", value)
    assert fast_path_enabled() is expected


def test_engine_name_default_and_override(monkeypatch):
    monkeypatch.delenv("NEEDLE_ENGINE", raising=False)
    assert engine_name() == "cactus"
    monkeypatch.setenv("NEEDLE_ENGINE", "  CACTUS  ")
    assert engine_name() == "cactus"


def test_build_engine_unknown_name_raises():
    with pytest.raises(ValueError, match="unknown needle engine"):
        build_engine("nope")


def test_router_routes_pilot_commands():
    """Replay of the 6 pilot command prompts: correct tool, correct
    discriminating argument, confidence recorded."""
    engine = StubNeedleEngine(replay=PILOT_REPLAY)
    router = NeedleRouter(engine)
    for prompt, (tool, key, value) in PILOT_COMMANDS.items():
        decision = router.route(prompt)
        assert decision.routed is True, prompt
        assert decision.tool_name == tool
        assert decision.arguments[key] == value
        assert decision.confidence is not None
        assert decision.latency_seconds >= 0


def test_router_escalates_on_no_call():
    """Pilot constraint 1: a no-call prompt escalates — it is never
    answered, fabricated, or dead-ended."""
    router = NeedleRouter(StubNeedleEngine(replay=PILOT_REPLAY))
    decision = router.route("What is the capital of France?")
    assert decision.routed is False
    assert decision.escalate_reason == "no-call"


def test_router_uses_fresh_session_per_command():
    """Pilot constraint 2: each command gets its own session, so the joke
    prompt cannot inherit the previous turn's memory search. The router
    must create one session per route() and use each session exactly once."""
    engine = StubNeedleEngine(replay=PILOT_REPLAY)
    router = NeedleRouter(engine)
    first = router.route("Search my memory for the Oracle server notes")
    assert first.routed is True
    assert first.tool_name == "search_memory"
    second = router.route("Tell me a one-line joke")
    assert second.routed is False
    assert second.escalate_reason == "no-call"
    assert len(engine.sessions) == 2
    assert engine.sessions[0] is not engine.sessions[1]
    assert engine.sessions[0].calls == [
        "Search my memory for the Oracle server notes"
    ]
    assert engine.sessions[1].calls == ["Tell me a one-line joke"]
    assert all(session.closed for session in engine.sessions)


def test_router_escalates_on_unknown_tool():
    router = NeedleRouter(
        StubNeedleEngine(replay={"do it": EngineCall("delete_everything", {})})
    )
    decision = router.route("do it")
    assert decision.routed is False
    assert decision.escalate_reason == "unregistered-tool:delete_everything"


def test_router_escalates_on_missing_argument():
    router = NeedleRouter(
        StubNeedleEngine(replay={"weather?": EngineCall("get_weather", {})})
    )
    decision = router.route("weather?")
    assert decision.routed is False
    assert decision.escalate_reason == "invalid-arguments:missing-city"


def test_router_escalates_on_bad_argument_type():
    router = NeedleRouter(
        StubNeedleEngine(
            replay={
                "remind me": EngineCall(
                    "set_reminder", {"text": "x", "minutes": "five"}
                )
            }
        )
    )
    decision = router.route("remind me")
    assert decision.routed is False
    assert decision.escalate_reason == "invalid-arguments:bad-type-minutes"


def test_router_escalates_on_engine_error():
    router = NeedleRouter(StubNeedleEngine(error=RuntimeError("engine down")))
    decision = router.route("What's the weather in Mumbai?")
    assert decision.routed is False
    assert decision.escalate_reason == "engine-error"


def test_router_never_gates_on_confidence():
    """The pilot proved confidence does not separate success from failure
    (the dead-end scored 0.60), so a low-confidence call still routes."""
    router = NeedleRouter(
        StubNeedleEngine(
            replay={
                "weather?": EngineCall(
                    "get_weather", {"city": "Mumbai"}, 0.05
                )
            }
        )
    )
    decision = router.route("weather?")
    assert decision.routed is True
    assert decision.confidence == 0.05


def test_cactus_engine_missing_package_raises_with_install_hint():
    def _missing():
        raise ImportError("No module named 'cactus'")

    with pytest.raises(RuntimeError, match="pip install cactus-compute"):
        CactusNeedleEngine(_import_cactus=_missing)


class _FakeCactus:
    """Stand-in for cactus.Cactus (cactus-compute 4.2.0 API surface used
    here: Cactus(tools, system, stateless).complete(prompt) -> dict)."""

    def __init__(self, *, tools=None, system=None, stateless=False, **kwargs):
        self.tools = tools
        self.system = system
        self.stateless = stateless
        self.complete_calls = []
        self.run_calls = []
        self.envelope = {
            "type": "call",
            "function_calls": [
                {"name": "get_weather", "arguments": {"city": "Mumbai"}}
            ],
            "confidence": 0.55,
        }

    def complete(self, text):
        self.complete_calls.append(text)
        return self.envelope

    def run(self, query, **kwargs):
        # The gateway routes; it never executes tools. If the engine ever
        # calls run(), the test must fail loudly.
        self.run_calls.append(query)
        raise AssertionError("run() must never be called: route, don't execute")

    def close(self):
        return None


def _fake_cactus_module():
    return types.SimpleNamespace(Cactus=_FakeCactus)


def test_cactus_engine_routes_via_complete_not_run():
    engine = CactusNeedleEngine(_import_cactus=_fake_cactus_module)
    router = NeedleRouter(engine)
    decision = router.route("What's the weather in Mumbai?")
    assert decision.routed is True
    assert decision.tool_name == "get_weather"
    assert decision.arguments == {"city": "Mumbai"}
    assert decision.confidence == 0.55
    agent = engine._agent(needle_router.DEFAULT_TOOL_REGISTRY,
                          needle_router.DEFAULT_SYSTEM_INSTRUCTION)
    # Stateless sessions are the engine-side half of pilot constraint 2.
    assert agent.stateless is True
    # The engine passes dict schemas (no executables) and never executes.
    assert {schema["name"] for schema in agent.tools} == {
        "get_weather",
        "set_reminder",
        "search_memory",
    }
    assert agent.run_calls == []
    assert agent.complete_calls == ["What's the weather in Mumbai?"]


def test_cactus_engine_no_call_envelope_escalates():
    engine = CactusNeedleEngine(_import_cactus=_fake_cactus_module)
    agent = engine._agent(needle_router.DEFAULT_TOOL_REGISTRY,
                          needle_router.DEFAULT_SYSTEM_INSTRUCTION)
    agent.envelope = {"type": "text", "function_calls": [], "confidence": 0.9}
    router = NeedleRouter(engine)
    decision = router.route("What is the capital of France?")
    assert decision.routed is False
    assert decision.escalate_reason == "no-call"


def test_cactus_engine_rejects_non_dict_envelope():
    engine = CactusNeedleEngine(_import_cactus=_fake_cactus_module)
    agent = engine._agent(needle_router.DEFAULT_TOOL_REGISTRY,
                          needle_router.DEFAULT_SYSTEM_INSTRUCTION)
    agent.envelope = "not a dict"
    router = NeedleRouter(engine)
    decision = router.route("What's the weather in Mumbai?")
    assert decision.routed is False
    assert decision.escalate_reason == "engine-error"


def _request(content="What's the weather in Mumbai?", multi=False):
    messages = [ProviderMessage(role="user", content=content)]
    if multi:
        messages.append(ProviderMessage(role="assistant", content="Sure."))
    return ProviderRequest(
        messages=messages,
        model="drill-model",
        extra_params={"timeout": 10.0},
    )


def _enable_fast_path(monkeypatch, engine):
    monkeypatch.setenv("NEEDLE_FAST_PATH_ENABLED", "true")
    monkeypatch.setattr(needle_router, "build_engine", lambda name: engine)


def test_try_fast_path_disabled_returns_none(monkeypatch):
    monkeypatch.delenv("NEEDLE_FAST_PATH_ENABLED", raising=False)
    engine = StubNeedleEngine(replay=PILOT_REPLAY)
    assert asyncio.run(try_fast_path(_request(), engine=engine)) is None


def test_try_fast_path_multi_message_returns_none(monkeypatch):
    _enable_fast_path(monkeypatch, StubNeedleEngine(replay=PILOT_REPLAY))
    assert asyncio.run(try_fast_path(_request(multi=True))) is None


def test_try_fast_path_empty_prompt_returns_none(monkeypatch):
    _enable_fast_path(monkeypatch, StubNeedleEngine(replay=PILOT_REPLAY))
    assert asyncio.run(try_fast_path(_request(content="   "))) is None


def test_try_fast_path_routed_response_shape(monkeypatch):
    _enable_fast_path(monkeypatch, StubNeedleEngine(replay=PILOT_REPLAY))
    resp = asyncio.run(try_fast_path(_request()))
    assert resp is not None
    assert resp.provider == "needle"
    assert resp.model == "needle-2"
    assert resp.finish_reason == "tool_calls"
    assert resp.content == ""
    assert resp.tool_calls is not None and len(resp.tool_calls) == 1
    call = resp.tool_calls[0]
    assert call["type"] == "function"
    assert call["function"]["name"] == "get_weather"
    assert json.loads(call["function"]["arguments"]) == {"city": "Mumbai"}
    assert (resp.raw_response or {}).get("needle", {}).get("tool") == "get_weather"


def test_try_fast_path_no_call_returns_none(monkeypatch):
    _enable_fast_path(monkeypatch, StubNeedleEngine(replay=PILOT_REPLAY))
    assert (
        asyncio.run(
            try_fast_path(_request(content="What is the capital of France?"))
        )
        is None
    )


def test_try_fast_path_engine_error_returns_none(monkeypatch):
    _enable_fast_path(
        monkeypatch, StubNeedleEngine(error=RuntimeError("engine down"))
    )
    assert asyncio.run(try_fast_path(_request())) is None


def test_try_fast_path_unknown_engine_returns_none(monkeypatch):
    monkeypatch.setenv("NEEDLE_FAST_PATH_ENABLED", "true")
    monkeypatch.setenv("NEEDLE_ENGINE", "nope")
    assert asyncio.run(try_fast_path(_request())) is None


def test_provider_response_tool_calls_defaults_none():
    resp = ProviderResponse(content="hi", model="m", provider="groq")
    assert resp.tool_calls is None


# --- Gateway integration (adapted from test_inf030_apinex_fallback.py) ---

PROVIDERS = [
    "gemini", "groq", "cerebras", "mistral", "openrouter", "cohere",
    "huggingface", "nvidia", "apinex",
]


class _Limiter:
    async def acquire(self, cost=1.0):
        return None

    def release(self):
        return None


class _Health:
    def __init__(self):
        self.successes = []
        self.failures = []

    def record_success(self, provider, latency, **kwargs):
        self.successes.append(provider)

    def record_failure(self, provider, error, **kwargs):
        self.failures.append((provider, str(error)))

    def update_key_counts(self, *args, **kwargs):
        return None


class _FakeProvider:
    """Scripted provider; records every generate() call."""

    def __init__(self, name, behaviour="ok"):
        self.name = name
        self.behaviour = behaviour
        self.calls = []

    async def get_best_free_model(self, capability="general"):
        return "test/free-model"

    async def generate(self, request):
        self.calls.append(request)
        if self.behaviour == "ok":
            return ProviderResponse(
                content=f"answer:{self.name}", model=request.model or "m",
                provider=self.name, raw_response={},
            )
        raise AssertionError(self.behaviour)


def _gateway(monkeypatch, script):
    gateway = ModelGateway.__new__(ModelGateway)
    gateway.key_pools = {p: KeyPool(p, [f"{p}-key-1", f"{p}-key-2"]) for p in PROVIDERS}
    gateway.rate_limiters = {p: _Limiter() for p in PROVIDERS}
    gateway.health_tracker = _Health()
    created = []

    def get_provider(name, **kwargs):
        provider = _FakeProvider(name, script.get(name, "ok"))
        created.append(provider)
        return provider

    monkeypatch.setattr(app.providers, "get_provider", get_provider)
    monkeypatch.setattr(gateway_module, "provider_has_credentials", lambda prov: True)
    monkeypatch.setattr(gateway_module.settings, "LOCAL_ENABLED", False)
    monkeypatch.setattr(gateway_module.settings, "LOCAL_PREFERRED", False)
    monkeypatch.setattr(
        gateway_module.settings, "INFERENCE_LITELLM_FALLBACK_ENABLED", False
    )
    return gateway, created


def test_gateway_ladder_unchanged_when_fast_path_disabled(monkeypatch):
    """Fast path off (the default): the ladder serves exactly as before."""
    monkeypatch.delenv("NEEDLE_FAST_PATH_ENABLED", raising=False)
    gateway, created = _gateway(monkeypatch, {p: "ok" for p in PROVIDERS})
    resp = asyncio.run(gateway.execute("groq", _request()))
    assert resp.provider == "groq"
    assert resp.content == "answer:groq"
    assert resp.tool_calls is None
    assert sum(len(p.calls) for p in created) == 1


def test_gateway_fast_path_routes_before_ladder(monkeypatch):
    """Fast path on + routed command: the needle response returns directly
    and no provider's generate() is ever called."""
    _enable_fast_path(monkeypatch, StubNeedleEngine(replay=PILOT_REPLAY))
    gateway, created = _gateway(monkeypatch, {p: "ok" for p in PROVIDERS})
    resp = asyncio.run(gateway.execute("groq", _request()))
    assert resp.provider == "needle"
    assert resp.model == "needle-2"
    assert resp.finish_reason == "tool_calls"
    assert resp.tool_calls[0]["function"]["name"] == "get_weather"
    assert sum(len(p.calls) for p in created) == 0


def test_gateway_falls_through_on_no_call(monkeypatch):
    _enable_fast_path(monkeypatch, StubNeedleEngine(replay=PILOT_REPLAY))
    gateway, created = _gateway(monkeypatch, {p: "ok" for p in PROVIDERS})
    resp = asyncio.run(
        gateway.execute("groq", _request(content="What is the capital of France?"))
    )
    assert resp.provider == "groq"
    assert resp.content == "answer:groq"


def test_gateway_falls_through_on_engine_error(monkeypatch):
    _enable_fast_path(
        monkeypatch, StubNeedleEngine(error=RuntimeError("engine down"))
    )
    gateway, created = _gateway(monkeypatch, {p: "ok" for p in PROVIDERS})
    resp = asyncio.run(gateway.execute("groq", _request()))
    assert resp.provider == "groq"
    assert resp.content == "answer:groq"


def test_gateway_fast_path_skips_multi_message(monkeypatch):
    _enable_fast_path(monkeypatch, StubNeedleEngine(replay=PILOT_REPLAY))
    gateway, created = _gateway(monkeypatch, {p: "ok" for p in PROVIDERS})
    resp = asyncio.run(gateway.execute("groq", _request(multi=True)))
    assert resp.provider == "groq"
    assert resp.content == "answer:groq"
