"""Bounded complete-source repair requests survive prompt/context construction."""
from types import SimpleNamespace

import pytest
from pydantic import ValidationError
from app.services.code_generation import CodeGenerationRequest, CodeGenerationService
from app.providers.unified_manager import unified_provider_manager


def request(source=None):
    source = source or ('# padding\n' * 500 + 'def add(a, b):\n    return a - b\n')
    return CodeGenerationRequest(filename='math_tool.py', requirements=['preserve API'], context={
        'project_goal': 'Addition utility',
        'repair': {'original_source': source, 'failure_evidence': 'AssertionError: expected 5, got -1'}})


def test_complete_repair_source_is_in_actual_prompt_and_pruned_context():
    service = CodeGenerationService()
    req = request()
    prompt = service._build_prompt(req)
    assert req.context['repair']['original_source'] in prompt
    assert 'AssertionError: expected 5, got -1' in prompt
    assert 'Never weaken/remove/skip tests' in prompt
    assert service._prune_context(req.context)['repair'] == req.context['repair']


@pytest.mark.parametrize('repair', [
    'not an object', {}, {'original_source': ''},
    {'original_source': 'x' * 32001},
    {'original_source': 'x = 1', 'failure_evidence': 'x' * 12001},
])
def test_invalid_or_oversize_repair_inputs_are_rejected_not_sliced(repair):
    with pytest.raises(ValidationError):
        CodeGenerationRequest(filename='main.py', context={'repair': repair})


def test_repair_cache_includes_source_and_failure():
    service = CodeGenerationService()
    first = request()
    second = first.model_copy(deep=True)
    second.context['repair']['failure_evidence'] = 'new failing case'
    third = first.model_copy(deep=True)
    third.context['repair']['original_source'] += '\n# changed'
    assert len({service._get_cache_key(x) for x in [first, second, third]}) == 3


@pytest.mark.asyncio
async def test_real_generation_service_forwards_complete_source_to_provider(monkeypatch):
    captured = []
    async def execute(req):
        captured.append(req)
        return SimpleNamespace(content='def add(a, b):\n    return a + b', degraded=False,
                               status='success', token_usage={'total_tokens': 20}, error=None)
    monkeypatch.setattr(unified_provider_manager, 'execute', execute)
    req = request()
    result = await CodeGenerationService().generate_code(req)
    assert result.generation_path == 'agent' and 'a + b' in result.code
    assert req.context['repair']['original_source'] in captured[0].prompt
    assert captured[0].context['repair'] == req.context['repair']
