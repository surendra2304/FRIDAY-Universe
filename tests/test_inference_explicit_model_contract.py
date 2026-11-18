"""Actual-source execution with offline cache/gateway boundaries, never live evidence.

AST selection avoids importing app.main's database/provider SDK graph. Function
and class bodies are not mirrored or rewritten; source-boundary changes fail
loudly. Real Pydantic request/response models still validate every boundary.
"""
import ast
import asyncio
import copy
import json
import os
import re
import time
import uuid
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Callable, Literal, Optional

import pytest
from fastapi import status
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field, field_validator

ROOT = Path(__file__).resolve().parents[1]


def _top_level_name(node):
    if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
        return node.name
    if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
        return node.targets[0].id
    if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
        return node.target.id
    return None


def actual_nodes(relative, names):
    tree = ast.parse((ROOT / relative).read_text())
    selected = []
    for node in tree.body:
        if _top_level_name(node) in names:
            node = copy.deepcopy(node)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
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
    # TASK-REL-052: the extracted route code grew three more module-level
    # dependencies after REL-043 — custom_provider_for_model (TASK-IG-INF-02),
    # model_servability_tracker (TASK-REL-049) and settings.REQUEST_TIMEOUT
    # (TASK-INF-010) — and none of the three PRs extended this namespace, so
    # every route-level test died with NameError and both Monorepo Structure
    # and Safety CI jobs went red on main itself (the REL-042 failure mode,
    # again). The two provider objects are bound by extracting their REAL
    # source below (custom_endpoints.py / model_servability.py), exactly
    # like the route code: with no INFERENCE_CUSTOM_ENDPOINTS configured the
    # real custom_provider_for_model returns None, and the real servability
    # tracker starts with nothing quarantined. settings is the one fixture
    # stand-in: the extracted code reads only settings.REQUEST_TIMEOUT, and
    # the value bound here is the real default from
    # Inference/app/core/config.py (REQUEST_TIMEOUT Field default=60.0).
    calls = []
    state = {'finish': 'stop', 'provenance': None, 'fail': False}
    context = {'__name__': 'offline_inference_contract', 'Any': Any, 'Literal': Literal,
               'BaseModel': BaseModel, 'Field': Field, 'field_validator': field_validator,
               'JSONResponse': JSONResponse, 'StreamingResponse': StreamingResponse, 'status': status,
               'json': json, 'os': os, 're': re, 'deque': deque, 'Callable': Callable, 'Optional': Optional,
               'dataclass': dataclass, 'field': field,
               'settings': SimpleNamespace(REQUEST_TIMEOUT=60.0),
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
    # chat_completions resolves providers through the module-level helper
    # _provider_for_model (TASK-REL-032), which reads the real MODEL_CATALOG /
    # _CATALOG_PROVIDERS tables; all three are extracted as actual source so
    # the route under test executes the same routing code as production.
    # TASK-REL-043: chat_completions also runs the best-suitable selection
    # (_select_best_suitable and its helpers/tables) for non-catalogue ids;
    # every module-level name that path reads is extracted too, per the
    # REL-042 lesson — a helper an extracted symbol depends on joins the
    # extraction set in the same PR that introduces the dependency.
    # TASK-INF-016 (same REL-042 lesson, third recurrence): _infer_task_type
    # now calls the new module-level helper _looks_simple, which reads the
    # three _SIMPLE_*_RES pattern tables — all four join the extraction set
    # in the same PR that introduces the dependency, extracted as actual
    # source like everything else in this set.
    nodes += actual_nodes('Inference/app/api/v1_core_routes.py', {'MODEL_CATALOG', '_CATALOG_PROVIDERS', '_provider_for_model', 'MODEL_CLASS_TIERS', 'MODEL_CLASSES', 'MODEL_SUITABILITY', '_CODE_HINTS', '_REASONING_HINTS', '_LONG_CONTEXT_MIN_CHARS', '_FLAGSHIP_SIZE_HINTS', '_ECONOMY_SIZE_HINTS', '_FLAGSHIP_NAME_HINTS', '_ECONOMY_NAME_HINTS', '_SIMPLE_MATH_RES', '_SIMPLE_LOOKUP_RES', '_SIMPLE_REWRITE_RES', '_looks_simple', '_infer_task_type', '_requested_class', '_provider_available', '_ranked_suitable_models', '_select_best_suitable', 'ChatMessage', 'ChatCompletionRequest', 'chat_completions'})
    # TASK-REL-052 (same REL-042 lesson, second recurrence): the selection /
    # route path also reads module-level helpers and tables that were never
    # in the extraction set — _is_custom_model (TASK-IG-INF-02),
    # _estimate_prompt_tokens / _estimate_context_tokens /
    # MODEL_CONTEXT_WINDOWS / _CONTEXT_FIT_FLOOR_TOKENS (context-fit path),
    # and the gateway's GROQ_PROMPT_TOKEN_LIMIT constant (TASK-INF-012).
    # They are extracted as actual source too, so the boundary assertion
    # still fails loudly if any of them changes shape.
    nodes += actual_nodes('Inference/app/api/v1_core_routes.py', {'_is_custom_model', '_estimate_prompt_tokens', '_estimate_context_tokens', 'MODEL_CONTEXT_WINDOWS', '_CONTEXT_FIT_FLOOR_TOKENS', '_CHARS_PER_TOKEN'})
    nodes += actual_nodes('Inference/app/providers/gateway.py', {'GROQ_PROMPT_TOKEN_LIMIT'})
    # TASK-REL-052: the imported names the route code reads, extracted as
    # actual source from their own modules (see the fixture comment above).
    nodes += actual_nodes('Inference/app/providers/custom_endpoints.py', {'PROVIDER_PREFIX', '_NAME_RE', 'CustomEndpoint', '_parse_entry', 'parse_custom_endpoints', '_cache', 'get_custom_endpoints', 'reset_custom_endpoints_cache', 'enabled_custom_endpoints', 'custom_endpoint_by_provider', 'custom_provider_for_model', 'custom_catalog_entries'})
    nodes += actual_nodes('Inference/app/providers/model_servability.py', {'SERVED', 'SUBSTITUTED', 'FAILED', '_OUTCOMES', '_env_int', 'ModelServabilityTracker', '_default_tracker', 'model_servability_tracker'})
    nodes += actual_nodes('Inference/app/providers/errors.py', {'GatewayError', 'RateLimitError', 'TemporaryUnavailableError', 'TimeoutError', 'ProviderUnconfiguredError', 'AuthenticationError', 'InvalidRequestError', 'ContentPolicyViolationError', 'CapabilityMismatchError', 'normalize_provider_exception'})
    # Only trusted, tracked repository code; no user/network input is executed.
    exec(compile(ast.Module(body=nodes, type_ignores=[]), 'actual_inference_source', 'exec'), context)  # noqa: S102
    # v1_core_routes imports the class under this alias (TASK-REL-052).
    context['ProviderTimeoutError'] = context['TimeoutError']
    # TASK-REL-052: get_custom_endpoints() lazily imports
    # app.core.config.settings on first use, which cannot resolve inside
    # this exec namespace (the root suite's sys.path binds 'app' to another
    # agent's package). Seed the registry cache with the empty registry —
    # the exact state production runs with when INFERENCE_CUSTOM_ENDPOINTS
    # is unset (parse_custom_endpoints('') == []); the real parse/enabled/
    # lookup functions above still execute for every call.
    context['_cache'] = []
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


def test_nonstream_route_forwards_an_explicit_catalogue_model_verbatim(boundary):
    # TASK-REL-043 DISCLOSURE (same pattern as the REL-042 assertion
    # update in this file): this test previously asserted that the
    # RETIRED id llama-3.3-70b-versatile was forwarded to the policy
    # gateway untouched. That was the TASK-REL-032 contract. The owner's
    # 2026-11-15 policy — "Inference should give the best suitable model
    # from the models it have" — supersedes it for non-catalogue ids:
    # forwarding a dead id only guarantees a provider 404 and a
    # ladder-accident substitute (observed live: a free-tier lightweight
    # answering a 70B request). The verbatim-forwarding guarantee now
    # covers catalogue ids and is asserted here with one; the retired-id
    # behaviour is asserted by the next test. Nothing is skipped or
    # loosened: the gateway call's model, provider, stage and token
    # budget are all still pinned exactly.
    completion(boundary, 'qwen/qwen3.8-27b')
    assert boundary.calls[0]['request'].model == 'qwen/qwen3.8-27b'
    assert boundary.calls[0]['provider_name'] == 'groq'
    assert boundary.calls[0]['stage_name'] == 'unified_direct'
    assert boundary.calls[0]['request'].max_tokens == 2400


def test_retired_model_is_replaced_by_best_suitable_with_provenance(boundary):
    # TASK-REL-043: llama-3.3-70b-versatile is not in the verified
    # catalogue, so the route selects the best suitable catalogue model
    # for the task (plain chat -> gemini-3.8-flash) BEFORE execution —
    # the dead id itself never reaches the gateway — and discloses the
    # substitution, its basis and the (absent) downgrade in provenance.
    result = completion(boundary)
    assert boundary.calls[0]['request'].model == 'gemini-3.8-flash'
    assert boundary.calls[0]['provider_name'] == 'gemini'
    assert boundary.calls[0]['stage_name'] == 'unified_direct'
    assert result['model'] == 'gemini-3.8-flash'
    provenance = result['provenance']
    assert provenance['requested_model'] == 'llama-3.3-70b-versatile'
    assert provenance['selected_as'] == 'best_suitable_for_chat'
    assert provenance['selected_model'] == 'gemini-3.8-flash'
    # A 70B (flagship-class) request served by the flagship catalogue
    # model is a substitution, not a downgrade.
    assert provenance['downgrade'] is False
    assert provenance['downgrade_reason'] is None


def test_gpt_oss_models_route_to_groq_not_openai(boundary):
    # TASK-REL-021: the /models catalog advertises openai/gpt-oss-120b as
    # Groq-owned, but the route's substring mapping sent any model containing
    # "openai" to the OpenAI provider (no credentials configured), silently
    # dropping explicit gpt-oss requests to the fallback ladder.
    completion(boundary, 'openai/gpt-oss-120b')
    assert boundary.calls[0]['request'].model == 'openai/gpt-oss-120b'
    assert boundary.calls[0]['provider_name'] == 'groq'
    assert boundary.calls[0]['stage_name'] == 'unified_direct'


def test_two_advertised_groq_models_do_not_share_cache_or_provider_request(boundary):
    # TASK-REL-043 DISCLOSURE: this test previously used the retired ids
    # llama-3.3-70b-versatile / llama-3.1-8b-instant. Under the owner's
    # best-suitable policy both retired ids now select the SAME
    # substitute, so they can no longer demonstrate per-model cache
    # isolation. The guarantee itself — two advertised Groq models never
    # share a cache entry or a provider request, and each response
    # reports its own model — is unchanged and asserted here with the
    # two advertised Groq catalogue models.
    first = completion(boundary, 'openai/gpt-oss-120b')
    second = completion(boundary, 'qwen/qwen3.8-27b')
    assert len(boundary.calls) == 2
    assert first['model'] == 'openai/gpt-oss-120b'
    assert second['model'] == 'qwen/qwen3.8-27b'


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


def test_auto_route_delegates_choice_without_fast_lane_clamp(boundary):
    # DISCLOSURE (2026-11-17, Inference /v1 auto-route truncation fix):
    # this test previously pinned the fast-lane shape for model="auto"
    # (openai/gpt-oss-20b, max_tokens=60, reasoning_effort=low) under the
    # name test_auto_fast_lane_budget_and_model_stay_unchanged. That
    # shape was the defect, not a contract: the route set fast_lane=True
    # for every "auto" caller, so the unified manager silently clamped
    # every auto request to 60 tokens, forced the 20B model and replaced
    # the caller's system prompt — measured live 2026-11-17 (4/4 auto
    # probes at max_tokens=800 stopped at exactly 60 with
    # finish_reason="length"; FRIDAY's autonomous daemon asks for 2,500
    # tokens through this surface and received 60-token stubs). "auto"
    # delegates the CHOICE of model; the OpenAI-compatible request
    # schema has no fast-lane field a caller could opt in with. The fast
    # lane survives only where a caller asks for it by name (/v1/ask
    # with mode="fast", the FRIDAY /ask fast lane) and stays pinned
    # there. Asserted here is the corrected delegation: the manager's
    # normal auto resolution serves the request — for the route's
    # system_architect role that is the manager's role default — and
    # the caller's token budget reaches the gateway intact.
    completion(boundary, 'auto')
    r = boundary.calls[0]['request']
    assert r.model == 'meta-llama/llama-3.3-70b-instruct'
    assert boundary.calls[0]['provider_name'] == 'openrouter'
    assert boundary.calls[0]['stage_name'] == 'unified_direct'
    assert r.max_tokens == 2400


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
    # TASK-REL-032 contract: a degraded result means no model answered, so
    # the route fails honestly — HTTP 503 provider_degraded, retryable —
    # instead of the pre-REL-032 HTTP 200 completion with an empty body.
    # There is no completion at all, so nothing can carry a finish reason.
    # (Mirrors Inference/tests/test_rel030_model_catalogue.py's accepted
    # test_chat_completions_degraded_is_not_a_fake_200.)
    assert result.status_code == 503
    body = json.loads(result.body)
    assert body['error']['code'] == 'provider_degraded'
    assert body['retryable'] is True
    assert body['requested_model'] == 'llama-3.3-70b-versatile'
    assert 'choices' not in body


@pytest.mark.parametrize('model', ['', 'x' * 201])
def test_invalid_model_length_is_rejected_at_public_request_boundary(boundary, model):
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        boundary.c['ChatCompletionRequest'](model=model)
