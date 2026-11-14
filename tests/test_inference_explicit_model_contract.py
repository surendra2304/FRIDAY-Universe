"""Actual-source execution with offline cache/gateway boundaries, never live evidence.

AST selection avoids importing app.main's database/provider SDK graph. Function
and class bodies are not mirrored or rewritten; source-boundary changes fail
loudly. Real Pydantic request/response models still validate every boundary.
"""
import ast
import asyncio
import copy
import json
import time
import uuid
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Literal

import pytest
from pydantic import BaseModel, Field, field_validator

ROOT = Path(__file__).resolve().parents[1]


def actual_nodes(relative, names):
    tree = ast.parse((ROOT / relative).read_text())
    selected = []
    for node in tree.body:
        if isinstance(node, (ast.ClassDef, ast.AsyncFunctionDef)) and node.name in names:
            node = copy.deepcopy(node)
            if isinstance(node, ast.AsyncFunctionDef):
                node.decorator_list = []  # registration only, not function logic
            selected.append(node)
    assert len(selected) == len(names), 'Source boundaries changed: inspect, do not substitute copied logic'
    return selected


class OfflineCache:
    def __init__(self):
        self.values = {}

    def get_query(self, question, **kwargs):
        return self.values.get(json.dumps([question, kwargs], sort_keys=True))

    def set_query(self, *, question, value, **kwargs):
        self.values[json.dumps([question, kwargs], sort_keys=True)] = value


@pytest.fixture
def boundary():
    calls = []
    state = {'finish': 'stop', 'provenance': None, 'fail': False}
    context = {'__name__': 'offline_inference_contract', 'Any': Any, 'Literal': Literal,
               'BaseModel': BaseModel, 'Field': Field, 'field_validator': field_validator,
               'time': time, 'uuid': uuid, 'perf_cache': OfflineCache(),
               'as_answer_pair': lambda value: value,
               'agent_registry': SimpleNamespace(get_agent=lambda _: None),
               'provider_failure_reason': lambda *_: 'fixture-provider-failure',
               'logger': SimpleNamespace(info=lambda *a: None, warning=lambda *a: None)}

    async def execute(*, request, provider_name='groq', **kwargs):
        calls.append({'request': request, 'provider_name': provider_name, **kwargs})
        if state['fail']:
            raise RuntimeError('offline fixture failure, not a cloud call')
        return context['ProviderResponse'](
            content='offline fixture, NOT model output',
            model='local-fixture' if state['provenance'] else request.model or 'default-fixture',
            provider='local' if state['provenance'] else provider_name,
            finish_reason=state['finish'], total_tokens=5,
            raw_response={'fallback_provenance': state['provenance']} if state['provenance'] else {},
        )

    async def execute_speculative(providers, request, **kwargs):
        return await execute(request=request, provider_name=providers[0], **kwargs)

    context['model_gateway'] = SimpleNamespace(execute=execute, execute_speculative=execute_speculative)
    nodes = actual_nodes('Inference/app/providers/base.py', {'ProviderMessage', 'ProviderRequest', 'ProviderResponse'})
    nodes += actual_nodes('Inference/app/providers/unified_manager.py', {'UnifiedExecutionRequest', 'UnifiedExecutionResponse', 'UnifiedProviderManager'})
    nodes += actual_nodes('Inference/app/api/v1_core_routes.py', {'ChatMessage', 'ChatCompletionRequest', 'chat_completions'})
    # Only trusted, tracked repository code; no user/network input is executed.
    exec(compile(ast.Module(body=nodes, type_ignores=[]), 'actual_inference_source', 'exec'), context)  # noqa: S102
    manager = context['UnifiedProviderManager']()
    context['unified_provider_manager'] = manager
    return SimpleNamespace(c=context, manager=manager, calls=calls, state=state)


def request(b, **overrides):
    fields = {'provider': 'groq', 'agent_role': None, 'prompt': 'public offline fixture', 'max_tokens': 2400}
    fields.update(overrides)
    return b.c['UnifiedExecutionRequest'](**fields)


def completion(b, model='llama-3.3-70b-versatile'):
    req = b.c['ChatCompletionRequest'](model=model, messages=[{'role': 'user', 'content': 'public offline fixture'}], max_tokens=2400, temperature=0)
    return asyncio.run(b.c['chat_completions'](req))


def test_nonstream_route_forwards_the_explicit_model_to_policy_gateway(boundary):
    completion(boundary)
    assert boundary.calls[0]['request'].model == 'llama-3.3-70b-versatile'
    assert boundary.calls[0]['provider_name'] == 'groq'
    assert boundary.calls[0]['stage_name'] == 'unified_direct'
    assert boundary.calls[0]['request'].max_tokens == 2400


def test_two_advertised_groq_models_do_not_share_cache_or_provider_request(boundary):
    first = completion(boundary, 'llama-3.3-70b-versatile')
    second = completion(boundary, 'llama-3.1-8b-instant')
    assert len(boundary.calls) == 2
    assert first['model'] == 'llama-3.3-70b-versatile'
    assert second['model'] == 'llama-3.1-8b-instant'


def test_role_defaults_cannot_overwrite_explicit_model(boundary):
    asyncio.run(boundary.manager.execute(request(boundary, model='explicit-fixture', agent_role='researcher')))
    assert boundary.calls[0]['request'].model == 'explicit-fixture'


@pytest.mark.parametrize('finish', ['stop', 'length', None])
def test_finish_reason_survives_real_manager_cache_hit(boundary, finish):
    boundary.state['finish'] = finish
    one = asyncio.run(boundary.manager.execute(request(boundary)))
    two = asyncio.run(boundary.manager.execute(request(boundary)))
    assert one.finish_reason == two.finish_reason == finish
    assert two.status == 'cache_hit'
    assert len(boundary.calls) == 1


@pytest.mark.parametrize('finish', ['length', None])
def test_oai_route_never_turns_truncated_or_unknown_finish_into_stop(boundary, finish):
    boundary.state['finish'] = finish
    one, two = completion(boundary), completion(boundary)
    assert one['choices'][0]['finish_reason'] == finish
    assert two['choices'][0]['finish_reason'] == finish
    assert len(boundary.calls) == 1


def test_auto_fast_lane_budget_and_model_stay_unchanged(boundary):
    completion(boundary, 'auto')
    r = boundary.calls[0]['request']
    assert r.model == 'openai/gpt-oss-20b'
    assert r.max_tokens == 60
    assert r.extra_params['reasoning_effort'] == 'low'


def test_identical_explicit_model_requests_still_reuse_cache(boundary):
    one, two = completion(boundary), completion(boundary)
    assert one['model'] == two['model']
    assert len(boundary.calls) == 1


def test_served_model_and_local_policy_provenance_remain_honest_on_cache_hit(boundary):
    boundary.state['provenance'] = {'actual_provider': 'local', 'fallback_reason': 'local_preferred'}
    one = asyncio.run(boundary.manager.execute(request(boundary, model='requested-fixture')))
    two = asyncio.run(boundary.manager.execute(request(boundary, model='requested-fixture')))
    assert one.model_used == two.model_used == 'local-fixture'
    assert one.provider_used == two.provider_used == 'local'
    assert one.served_by_policy is two.served_by_policy is True
    assert one.served_by_provider == two.served_by_provider == 'local'
    assert boundary.calls[0]['request'].model == 'requested-fixture'


def test_speculative_finish_reason_survives_response_and_cache(boundary):
    boundary.state['finish'] = 'length'
    one = asyncio.run(boundary.manager.execute(request(boundary, speculative=True)))
    two = asyncio.run(boundary.manager.execute(request(boundary, speculative=True)))
    assert one.finish_reason == two.finish_reason == 'length'
    assert len(boundary.calls) == 1


def test_failed_provider_never_gets_completed_finish_reason(boundary):
    boundary.state['fail'] = True
    result = completion(boundary)
    assert result['choices'][0]['message']['content'] == ''
    assert result['choices'][0]['finish_reason'] is None


@pytest.mark.parametrize('model', ['', 'x' * 201])
def test_invalid_model_length_is_rejected_at_public_request_boundary(boundary, model):
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        boundary.c['ChatCompletionRequest'](model=model)
