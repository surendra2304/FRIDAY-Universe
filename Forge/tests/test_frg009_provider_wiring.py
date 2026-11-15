"""
TASK-FRG-009 tests: role provider wiring.

Covers:
- provider selection (configured -> the real Inference provider, fail-closed,
  per-role model alias; explicitly unconfigured/mock -> DirectProvider with
  mock labelling),
- BaseAgent / AgentRegistry integration with the wiring,
- InferenceProvider's fail-closed generate() and its explicitly-marked legacy
  fallback,
- DeveloperRole consuming the file manifest through a real provider
  (per-file contents authored by the provider, not by deterministic
  synthesis or the legacy bypass),
- the degraded-labelling helpers used by the delegate API.
"""

from __future__ import annotations

import re
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from app.agents.base import BaseAgent
from app.agents.provider_wiring import (
    is_mock_provider,
    provider_kind,
    provider_label,
    resolve_role_provider,
    role_model_alias,
)
from app.agents.registry import AgentRegistry
from app.agents.roles import DeveloperRole
from app.core.config import Settings, get_settings
from app.core.workspace import WorkspaceManager
from app.execution.engine import ExecutionEngine
from app.providers.base import (
    BaseModelProvider,
    ProviderCapabilities,
    ProviderHealthStatus,
    ProviderResponse,
    UsageEstimate,
)
from app.providers.direct import DirectProvider
from app.providers.inference import InferenceProvider, InferenceUnavailableError


@pytest.fixture
def role_env(monkeypatch):
    """Set FORGE_ROLE_PROVIDER for one test and restore the settings cache."""

    def _set(value: str | None) -> None:
        if value is None:
            monkeypatch.delenv("FORGE_ROLE_PROVIDER", raising=False)
        else:
            monkeypatch.setenv("FORGE_ROLE_PROVIDER", value)
        get_settings.cache_clear()

    yield _set
    get_settings.cache_clear()


# ----------------------------------------------------------------------
# provider selection
# ----------------------------------------------------------------------


def test_production_default_role_provider_is_inference(role_env):
    role_env(None)  # nothing configured -> production default
    assert Settings().role_provider == "inference"


def test_configured_inference_gives_real_fail_closed_provider():
    provider = resolve_role_provider(
        "architect", settings=Settings(role_provider="inference")
    )
    assert isinstance(provider, InferenceProvider)
    assert provider.model_name == "forge-architect"
    assert provider.enable_fallback is False
    assert is_mock_provider(provider) is False
    assert provider_kind(provider) == "inference"
    assert provider_label(provider).startswith("inference:forge-architect@")


def test_per_role_alias_and_override():
    assert role_model_alias("Developer") == "forge-developer"
    settings = Settings(
        role_provider="inference", role_models={"developer": "custom-coder"}
    )
    provider = resolve_role_provider("developer", settings=settings)
    assert isinstance(provider, InferenceProvider)
    assert provider.model_name == "custom-coder"


def test_explicit_direct_is_mock_and_labelled():
    provider = resolve_role_provider(
        "developer", settings=Settings(role_provider="direct")
    )
    assert isinstance(provider, DirectProvider)
    assert provider.model_name == "direct-developer"
    assert is_mock_provider(provider) is True
    assert provider_kind(provider) == "direct"
    assert provider_label(provider) == "mock/direct"


def test_unknown_provider_falls_back_to_labelled_mock():
    provider = resolve_role_provider(
        "planner", settings=Settings(role_provider="carrier-pigeon")
    )
    assert isinstance(provider, DirectProvider)
    assert provider_label(provider) == "mock/direct"


# ----------------------------------------------------------------------
# BaseAgent / registry integration
# ----------------------------------------------------------------------


def test_base_agent_uses_wiring_by_default(role_env):
    role_env(None)
    agent = DeveloperRole()
    assert isinstance(agent.provider, InferenceProvider)
    assert agent.provider.model_name == "forge-developer"


def test_base_agent_explicit_direct_mode(role_env):
    role_env("direct")
    agent = DeveloperRole()
    assert isinstance(agent.provider, DirectProvider)
    assert agent.provider.model_name == "direct-developer"
    assert provider_label(agent.provider) == "mock/direct"


def test_registry_create_agent_uses_wiring(role_env):
    role_env(None)
    registry = AgentRegistry()
    architect = registry.create_agent("architect")
    assert isinstance(architect.provider, InferenceProvider)
    assert architect.provider.model_name == "forge-architect"


def test_registry_explicit_provider_type_still_honoured(role_env):
    role_env(None)
    registry = AgentRegistry()
    developer = registry.create_agent("developer", provider_type="direct")
    assert isinstance(developer.provider, DirectProvider)
    assert developer.provider.model_name == "direct-developer"


def test_injected_provider_always_wins(role_env):
    role_env(None)
    injected = DirectProvider(model_name="injected", mock_response="ok")
    agent = DeveloperRole(provider=injected)
    assert agent.provider is injected


# ----------------------------------------------------------------------
# InferenceProvider transport behaviour
# ----------------------------------------------------------------------


def _ok_body(content: str = "print('hello')") -> dict:
    return {
        "id": "chatcmpl-test",
        "model": "openai/gpt-oss-120b",
        "choices": [
            {"message": {"content": content}, "finish_reason": "stop"}
        ],
        "usage": {"prompt_tokens": 12, "completion_tokens": 7, "total_tokens": 19},
        "provenance": {"selected_as": "best_suitable_for_code", "downgrade": False},
    }


@pytest.mark.asyncio
async def test_generate_parses_served_model_and_provenance():
    provider = InferenceProvider(model_name="forge-developer", base_url="http://inf.test")
    with patch.object(
        provider, "_chat_completion", new=AsyncMock(return_value=_ok_body())
    ) as mock_call:
        resp = await provider.generate("Write code", system_prompt="You are a dev")
    assert resp.content == "print('hello')"
    assert resp.model == "openai/gpt-oss-120b"
    assert resp.raw_response["served_by_model"] == "openai/gpt-oss-120b"
    assert resp.raw_response["provenance"]["selected_as"] == "best_suitable_for_code"
    assert resp.usage.total_tokens == 19
    messages = mock_call.call_args[0][0]
    assert messages[0] == {"role": "system", "content": "You are a dev"}
    assert messages[1]["role"] == "user"


@pytest.mark.asyncio
async def test_generate_fails_closed_by_default():
    provider = InferenceProvider(model_name="forge-developer", base_url="http://inf.test")
    assert provider.enable_fallback is False
    with patch.object(
        provider,
        "_chat_completion",
        new=AsyncMock(side_effect=InferenceUnavailableError("HTTP 503: degraded")),
    ):
        with pytest.raises(InferenceUnavailableError):
            await provider.generate("Write code")
    assert provider.last_degraded is True


@pytest.mark.asyncio
async def test_generate_empty_completion_fails_closed():
    provider = InferenceProvider(model_name="forge-developer", base_url="http://inf.test")
    with patch.object(
        provider, "_chat_completion", new=AsyncMock(return_value=_ok_body("   "))
    ):
        with pytest.raises(InferenceUnavailableError):
            await provider.generate("Write code")


@pytest.mark.asyncio
async def test_legacy_fallback_is_explicit_and_marked():
    provider = InferenceProvider(
        model_name="forge-developer", base_url="http://inf.test", enable_fallback=True
    )
    with patch.object(
        provider,
        "_chat_completion",
        new=AsyncMock(side_effect=InferenceUnavailableError("gateway down")),
    ):
        resp = await provider.generate("Summarize the task")
    assert "[Direct Completion" in resp.content  # deterministic mock output
    assert resp.raw_response["degraded_fallback"] == "direct"
    assert "gateway down" in resp.raw_response["provider_error"]


@pytest.mark.asyncio
async def test_chat_completion_http_error_raises(monkeypatch):
    import httpx

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            503,
            json={"error": {"message": "No provider could answer", "code": "provider_degraded"}},
        )

    transport = httpx.MockTransport(handler)
    real_client = httpx.AsyncClient

    def factory(**kwargs):
        return real_client(transport=transport, timeout=kwargs.get("timeout"))

    monkeypatch.setattr("app.providers.inference.httpx.AsyncClient", factory)
    provider = InferenceProvider(model_name="forge-x", base_url="http://inf.test")
    with pytest.raises(InferenceUnavailableError, match="503"):
        await provider._chat_completion([{"role": "user", "content": "hi"}], 0.2, None)


@pytest.mark.asyncio
async def test_health_uses_gateway_health_document():
    provider = InferenceProvider(base_url="http://inf.test")
    with patch.object(
        provider,
        "_fetch_health",
        new=AsyncMock(return_value={"status": "healthy", "providers": ["groq"]}),
    ):
        health = await provider.health()
    assert health.healthy is True
    assert health.details["providers"] == ["groq"]


@pytest.mark.asyncio
async def test_structured_output_invalid_schema_raises():
    from pydantic import BaseModel

    class Demo(BaseModel):
        count: int

    provider = InferenceProvider(model_name="forge-x", base_url="http://inf.test")
    with patch.object(
        provider,
        "_chat_completion",
        new=AsyncMock(return_value=_ok_body('{"count": "not-an-int"}')),
    ):
        with pytest.raises(ValueError):
            await provider.structured_output(prompt="count things", response_model=Demo)


@pytest.mark.asyncio
async def test_prompt_model_records_degraded_fallback():
    provider = InferenceProvider(
        model_name="forge-developer", base_url="http://inf.test", enable_fallback=True
    )
    agent = DeveloperRole(provider=provider)
    with patch.object(
        provider,
        "_chat_completion",
        new=AsyncMock(side_effect=InferenceUnavailableError("gateway down")),
    ):
        await agent.prompt_model("anything")
    assert agent.state.scratchpad.get("provider_degraded") is True


# ----------------------------------------------------------------------
# manifest consumption through a real provider
# ----------------------------------------------------------------------


class FakeRealProvider(BaseModelProvider):
    """A non-mock provider double: authors each requested file with a
    marker line naming the file, and records every prompt it received."""

    def __init__(self) -> None:
        super().__init__(model_name="fake-real-1")
        self.prompts: list[str] = []

    async def generate(self, prompt, system_prompt=None, temperature=0.2, max_tokens=None, **kwargs):
        self.prompts.append(prompt)
        match = re.search(r"### File: (\S+)", prompt)
        filename = match.group(1) if match else "main.py"
        content = f"# authored-by-fake-provider for {filename}\nVALUE = 1\n"
        return ProviderResponse(
            content=f"### File: {filename}\n```python\n{content}```",
            model="fake-real-1",
            usage=UsageEstimate(total_tokens=10),
            raw_response={"served_by_model": "fake-real-1"},
        )

    async def stream(self, prompt, system_prompt=None, temperature=0.2, max_tokens=None, **kwargs):
        yield ""

    async def structured_output(self, prompt, response_model, system_prompt=None, temperature=0.1, **kwargs):
        raise NotImplementedError

    def estimate_usage(self, prompt, output=None):
        return UsageEstimate(total_tokens=1)

    def capabilities(self):
        return ProviderCapabilities(
            provider_name="FakeRealProvider", supported_models=["fake-real-1"]
        )

    async def health(self):
        return ProviderHealthStatus(healthy=True, provider_name="FakeRealProvider")


class FailingProvider(FakeRealProvider):
    async def generate(self, prompt, system_prompt=None, temperature=0.2, max_tokens=None, **kwargs):
        raise InferenceUnavailableError("gateway down (test double)")


@pytest.fixture
def temp_engine(tmp_path: Path):
    settings = Settings()
    settings.workspaces_dir = tmp_path / "workspaces"
    wm = WorkspaceManager(settings=settings)
    engine = ExecutionEngine(wm=wm)
    return engine, wm


MANIFEST = ["pkg/__init__.py", "pkg/core.py", "main.py"]


@pytest.mark.asyncio
async def test_developer_consumes_manifest_from_context_via_provider(temp_engine):
    engine, wm = temp_engine
    task_id = str(uuid4())
    wm.create_workspace(task_id)

    provider = FakeRealProvider()
    developer = DeveloperRole(provider=provider)
    result = await developer.execute_step(
        task_id=task_id,
        node_title="Implement the package",
        context={
            "goal": "Build a tiny pkg package",
            "requirements": ["pkg exists"],
            "file_manifest": list(MANIFEST),
        },
        engine=engine,
    )

    assert result["status"] == "success"
    assert result["fallback_stub"] is False
    for rel in MANIFEST:
        assert rel in result["files_written"]
        content = engine.fs.read_file(task_id, rel, role="developer")
        assert f"authored-by-fake-provider for {rel}" in content
    # one provider call per manifest file (developer skips test/README only)
    assert len(provider.prompts) == len(MANIFEST)
    # the served model was recorded on the agent for task-output stamping
    assert developer.state.scratchpad.get("served_by_model") == "fake-real-1"


@pytest.mark.asyncio
async def test_developer_consumes_manifest_file_via_provider(temp_engine):
    engine, wm = temp_engine
    task_id = str(uuid4())
    paths = wm.create_workspace(task_id)
    (paths.project / "docs").mkdir(parents=True, exist_ok=True)
    import json

    (paths.project / "docs" / "FILE_MANIFEST.json").write_text(
        json.dumps(MANIFEST), encoding="utf-8"
    )
    (paths.project / "docs" / "ARCHITECTURE_SPEC.md").write_text(
        "# Spec\npkg layout as manifested.\n", encoding="utf-8"
    )

    provider = FakeRealProvider()
    developer = DeveloperRole(provider=provider)
    result = await developer.execute_step(
        task_id=task_id,
        node_title="Implement the package",
        context={"goal": "Build a tiny pkg package", "requirements": []},
        engine=engine,
    )

    assert result["status"] == "success"
    for rel in MANIFEST:
        assert rel in result["files_written"]
        content = engine.fs.read_file(task_id, rel, role="developer")
        assert f"authored-by-fake-provider for {rel}" in content
    # the architecture spec reached the provider prompt
    assert any("pkg layout as manifested" in p for p in provider.prompts)


class FlakyFileProvider(FakeRealProvider):
    """Returns unparseable Python for pkg/core.py on the first attempt
    (the write-boundary compile gate refuses it — the FRG-009 G5 battery
    failure mode) and valid content on the corrective retry."""

    def __init__(self) -> None:
        super().__init__()
        self.core_attempts = 0

    async def generate(self, prompt, system_prompt=None, temperature=0.2, max_tokens=None, **kwargs):
        if "contents of the file 'pkg/core.py'" in prompt:
            self.prompts.append(prompt)
            self.core_attempts += 1
            if self.core_attempts == 1:
                return ProviderResponse(
                    content="### File: pkg/core.py\n```python\nthis is not python !!!\n```",
                    model="fake-real-1",
                    usage=UsageEstimate(total_tokens=5),
                    raw_response={"served_by_model": "fake-real-1"},
                )
        return await super().generate(
            prompt, system_prompt=system_prompt, temperature=temperature,
            max_tokens=max_tokens, **kwargs,
        )


class BrokenFileProvider(FakeRealProvider):
    """Always returns unparseable Python for pkg/core.py."""

    async def generate(self, prompt, system_prompt=None, temperature=0.2, max_tokens=None, **kwargs):
        if "contents of the file 'pkg/core.py'" in prompt:
            self.prompts.append(prompt)
            return ProviderResponse(
                content="### File: pkg/core.py\n```python\nstill not python !!!\n```",
                model="fake-real-1",
                usage=UsageEstimate(total_tokens=5),
                raw_response={"served_by_model": "fake-real-1"},
            )
        return await super().generate(
            prompt, system_prompt=system_prompt, temperature=temperature,
            max_tokens=max_tokens, **kwargs,
        )


@pytest.mark.asyncio
async def test_developer_corrective_retry_heals_unparseable_file(temp_engine):
    engine, wm = temp_engine
    task_id = str(uuid4())
    wm.create_workspace(task_id)

    provider = FlakyFileProvider()
    developer = DeveloperRole(provider=provider)
    result = await developer.execute_step(
        task_id=task_id,
        node_title="Implement the package",
        context={
            "goal": "Build a tiny pkg package",
            "requirements": [],
            "file_manifest": list(MANIFEST),
        },
        engine=engine,
    )

    assert result["status"] == "success"
    assert "pkg/core.py" in result["files_written"]
    assert "provider_failed_files" not in result
    assert provider.core_attempts == 2  # one rejection + one corrective retry
    content = engine.fs.read_file(task_id, "pkg/core.py", role="developer")
    assert "authored-by-fake-provider" in content


@pytest.mark.asyncio
async def test_developer_unauthorable_file_recorded_not_fatal(temp_engine):
    engine, wm = temp_engine
    task_id = str(uuid4())
    wm.create_workspace(task_id)

    developer = DeveloperRole(provider=BrokenFileProvider())
    result = await developer.execute_step(
        task_id=task_id,
        node_title="Implement the package",
        context={
            "goal": "Build a tiny pkg package",
            "requirements": [],
            "file_manifest": list(MANIFEST),
        },
        engine=engine,
    )

    # The build continues; the gap is named in the result for verification
    # to judge — it is neither hidden nor allowed to kill the whole node.
    assert result["status"] == "success"
    assert result["provider_failed_files"] == ["pkg/core.py"]
    assert "pkg/__init__.py" in result["files_written"]
    assert "main.py" in result["files_written"]
    with pytest.raises(Exception):
        engine.fs.read_file(task_id, "pkg/core.py", role="developer")


@pytest.mark.asyncio
async def test_developer_provider_failure_fails_closed(temp_engine):
    engine, wm = temp_engine
    task_id = str(uuid4())
    wm.create_workspace(task_id)

    developer = DeveloperRole(provider=FailingProvider())
    with pytest.raises(InferenceUnavailableError):
        await developer.execute_step(
            task_id=task_id,
            node_title="Implement the package",
            context={
                "goal": "Build a tiny pkg package",
                "requirements": [],
                "file_manifest": list(MANIFEST),
            },
            engine=engine,
        )


# ----------------------------------------------------------------------
# architect manifest rescue (real-model truncation failure mode)
# ----------------------------------------------------------------------


class SpecOnlyThenManifestProvider(FakeRealProvider):
    """Emulates the real-gateway failure mode proven in the FRG-009
    battery: the combined spec+manifest completion spends its budget on
    the spec and never emits the manifest block; the manifest-only
    follow-up call returns it."""

    async def generate(self, prompt, system_prompt=None, temperature=0.2, max_tokens=None, **kwargs):
        self.prompts.append(prompt)
        if "Return ONLY the project file manifest" in prompt:
            return ProviderResponse(
                content=(
                    "### File: docs/FILE_MANIFEST.json\n```json\n"
                    '["pkg/__init__.py", "pkg/core.py", "main.py"]\n```'
                ),
                model="fake-real-1",
                usage=UsageEstimate(total_tokens=5),
                raw_response={"served_by_model": "fake-real-1"},
            )
        return ProviderResponse(
            content="### File: docs/ARCHITECTURE_SPEC.md\n```markdown\n# Spec\nlong spec, no manifest block\n```",
            model="fake-real-1",
            usage=UsageEstimate(total_tokens=5),
            raw_response={"served_by_model": "fake-real-1"},
        )


@pytest.mark.asyncio
async def test_architect_manifest_rescue_followup_call(temp_engine):
    engine, wm = temp_engine
    task_id = str(uuid4())
    wm.create_workspace(task_id)

    from app.agents.roles import ArchitectRole

    provider = SpecOnlyThenManifestProvider()
    architect = ArchitectRole(provider=provider)
    result = await architect.execute_step(
        task_id=task_id,
        node_title="System Architecture & Module Design",
        context={"goal": "Build a tiny pkg package", "requirements": []},
        engine=engine,
    )

    import json

    raw = engine.fs.read_file(task_id, "docs/FILE_MANIFEST.json", role="architect")
    assert json.loads(raw) == ["pkg/__init__.py", "pkg/core.py", "main.py"]
    # exactly one combined call + one manifest-only follow-up
    assert len(provider.prompts) == 2
    assert result["status"] == "success"


# ----------------------------------------------------------------------
# delegate labelling helpers
# ----------------------------------------------------------------------


@pytest.mark.asyncio
async def test_delegate_provider_summary_aggregation():
    from app.api.delegate import _degraded_suffix, _task_provider_summary

    class FakeStore:
        async def get_latest_task_graph_for_project(self, task_id):
            return SimpleNamespace(
                nodes={
                    "n1": SimpleNamespace(
                        result={
                            "provider": "inference:forge-architect@http://x",
                            "served_by_model": "gemini-3.8-flash",
                        }
                    ),
                    "n2": SimpleNamespace(
                        result={"provider": "mock/direct", "generation_degraded": True}
                    ),
                }
            )

    summary = await _task_provider_summary(SimpleNamespace(store=FakeStore()), "t1")
    assert summary["generation_degraded"] is True
    assert summary["served_by_model"] == ["gemini-3.8-flash"]
    assert "mock/direct" in _degraded_suffix(summary)
    assert _degraded_suffix({"generation_degraded": False}) == ""
    assert _degraded_suffix({}) == ""


def test_wiring_describe_reports_mock_state():
    from app.agents.provider_wiring import describe_role_providers

    info = describe_role_providers(Settings(role_provider="direct"))
    assert info["mock"] is True
    info = describe_role_providers(Settings(role_provider="inference"))
    assert info["mock"] is False
    assert info["inference_base_url"]
