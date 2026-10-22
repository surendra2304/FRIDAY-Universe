"""
Unit tests for Model Routing and AgentRegistry model preferences.
"""

from app.agents.registry import AgentRegistry
from app.agents.roles import ArchitectRole, TesterRole
from app.providers.anthropic import AnthropicProvider
from app.providers.direct import DirectProvider
from app.providers.factory import get_provider
from app.providers.openai import OpenAIProvider


def test_registry_roles_have_preferred_models():
    registry = AgentRegistry()

    # Architect role routing
    assert registry.get_preferred_model("architect", "openai") == "gpt-4o"
    assert registry.get_preferred_model("architect", "anthropic") == "claude-3-5-sonnet-20241022"
    assert registry.get_preferred_model("architect", "direct") == "direct-architect"

    # Tester role routing (faster / cheaper)
    assert registry.get_preferred_model("tester", "openai") == "gpt-4o-mini"
    assert registry.get_preferred_model("tester", "anthropic") == "claude-3-5-haiku-20241022"
    assert registry.get_preferred_model("tester", "direct") == "direct-tester"

    # Code reviewer routing
    assert registry.get_preferred_model("code_reviewer", "openai") == "gpt-4o-mini"


def test_registry_dynamic_preferred_model_override():
    registry = AgentRegistry()
    registry.set_preferred_model("architect", "openai", "o1")

    assert registry.get_preferred_model("architect", "openai") == "o1"


def test_create_agent_with_openai_routing():
    registry = AgentRegistry()

    # Create Architect with OpenAI routing
    architect = registry.create_agent("architect", provider_type="openai")
    assert isinstance(architect, ArchitectRole)
    assert isinstance(architect.provider, OpenAIProvider)
    assert architect.provider.model_name == "gpt-4o"

    # Create Tester with OpenAI routing -> faster/cheaper model
    tester = registry.create_agent("tester", provider_type="openai")
    assert isinstance(tester, TesterRole)
    assert isinstance(tester.provider, OpenAIProvider)
    assert tester.provider.model_name == "gpt-4o-mini"


def test_create_agent_with_anthropic_routing():
    registry = AgentRegistry()

    # Create Architect with Anthropic routing
    architect = registry.create_agent("architect", provider_type="anthropic")
    assert isinstance(architect, ArchitectRole)
    assert isinstance(architect.provider, AnthropicProvider)
    assert architect.provider.model_name == "claude-3-5-sonnet-20241022"

    # Create Tester with Anthropic routing -> cheaper haiku model
    tester = registry.create_agent("tester", provider_type="anthropic")
    assert isinstance(tester, TesterRole)
    assert isinstance(tester.provider, AnthropicProvider)
    assert tester.provider.model_name == "claude-3-5-haiku-20241022"


def test_provider_factory_resolution():
    # Direct / mock provider
    prov_direct = get_provider("direct")
    assert isinstance(prov_direct, DirectProvider)

    prov_mock = get_provider("mock")
    assert isinstance(prov_mock, DirectProvider)

    # Explicit OpenAI provider
    prov_openai = get_provider("openai", model_name="gpt-4o-mini")
    assert isinstance(prov_openai, OpenAIProvider)
    assert prov_openai.model_name == "gpt-4o-mini"

    # Heuristic inference from model name
    prov_inferred_openai = get_provider(model_name="gpt-4o")
    assert isinstance(prov_inferred_openai, OpenAIProvider)

    prov_inferred_anthropic = get_provider(model_name="claude-3-5-sonnet")
    assert isinstance(prov_inferred_anthropic, AnthropicProvider)
