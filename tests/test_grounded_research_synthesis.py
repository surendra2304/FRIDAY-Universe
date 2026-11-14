"""Pure grounding boundary tests; no fixtures are live provider evidence."""
import asyncio
import importlib.util
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest.mock import AsyncMock

import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('grounded_synthesis', ROOT / 'IntelX/intelx/api/grounded_live_research.py')
m = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = m
spec.loader.exec_module(m)

TEXT = 'A quote character encloses fields containing delimiters, preserving a comma inside a quoted field.'
DOCS = [{'source_id': 'public-one', 'title': 'Explicit fixture', 'url': 'https://example.org/source', 'text': TEXT}]


def result(quote=TEXT, source_id='public-one', insufficient=False):
    return m.GroundedDraft(findings=[m.GroundedFinding(statement='Quoted delimiters remain within the field.', source_id=source_id, quote=quote)], insufficient_evidence=insufficient)


def run(parsed, provider='inference', docs=None):
    gateway = SimpleNamespace(complete=AsyncMock(return_value=SimpleNamespace(provider=provider, parsed=parsed)))
    return asyncio.run(m.synthesize_grounded('How are quoted commas handled?', DOCS if docs is None else docs, gateway)), gateway


def test_source_grounded_draft_preserves_real_source_link_and_unverified_state():
    d, gateway = run(result())
    assert d['status'] == 'SUCCESS'
    assert d['quotes_verified'] is True
    assert d['semantic_entailment_verified'] is False
    assert d['question_answered'] is False
    assert d['findings'][0]['citations'][0]['source_url'] == DOCS[0]['url']
    assert 'untrusted data' in gateway.complete.call_args.kwargs['messages'][0]['content']
    assert gateway.complete.await_count == 1


@pytest.mark.parametrize('parsed', [result(quote='This invented quotation was never present in any fetched source document.'), result(source_id='invented'), result(insufficient=True), m.GroundedDraft(findings=[], insufficient_evidence=False), None])
def test_invalid_or_insufficient_grounding_never_returns_completed_findings(parsed):
    d, _ = run(parsed)
    assert d['status'] == 'DEGRADED'
    assert not d['findings']


def test_mock_response_is_never_live_synthesis():
    d, _ = run(result(), provider='mock')
    assert d['status'] == 'DEGRADED'
    assert d['error'] == 'mock_synthesis_refused'


def test_an_omitted_source_prefix_cannot_justify_a_model_quote():
    hidden_quote = 'This omitted material contains a sentence never supplied to the model.'
    docs = [{**DOCS[0], 'text': 'x' * 18000 + hidden_quote}]
    d, _ = run(result(quote=hidden_quote), docs=docs)
    assert d['status'] == 'DEGRADED'


def test_source_prompt_is_bounded_and_contains_no_owner_state():
    docs = [{**DOCS[0], 'source_id': str(i), 'text': TEXT * 1000} for i in range(10)]
    d, gateway = run(m.GroundedDraft(findings=[], insufficient_evidence=True), docs=docs)
    messages = gateway.complete.call_args.kwargs['messages']
    import json
    supplied = json.loads(messages[1]['content'])['source_documents']
    assert sum(len(x['text']) for x in supplied) <= 16000
    assert len(supplied) <= 5
    assert d['status'] == 'DEGRADED'


def test_model_cancellation_propagates_without_fake_draft():
    gateway = SimpleNamespace(complete=AsyncMock(side_effect=asyncio.CancelledError))
    with pytest.raises(asyncio.CancelledError):
        asyncio.run(m.synthesize_grounded('fixture question', DOCS, gateway))


def test_whitespace_only_quote_does_not_pass_substring_check():
    d, _ = run(result(quote=' ' * 35))
    assert d['status'] == 'DEGRADED'


@pytest.mark.parametrize('finish_reason', ['stop', 'length'])
def test_inference_completion_honors_budget_auth_and_refuses_truncation(monkeypatch, finish_reason):
    import httpx
    settings_module = ModuleType('intelx.core.settings')
    settings_module.get_settings = lambda: SimpleNamespace(MOCK_MODE=False, INFERENCE_URL='https://inference.example.test', INFERENCE_API_KEY='fixture-only-key')
    # Other root suites legitimately install a lightweight intelx.core stub.
    # Patch only this import for this test; monkeypatch restores prior state.
    monkeypatch.setitem(sys.modules, 'intelx.core.settings', settings_module)
    requests = []

    def respond(request):
        requests.append(request)
        assert str(request.url) == 'https://inference.example.test/v1/chat/completions'
        return httpx.Response(200, json={
            'model': 'real-fixture-model', 'choices': [{'finish_reason': finish_reason, 'message': {'content': result().model_dump_json()}}]})

    real_client = httpx.AsyncClient
    monkeypatch.setattr(m.httpx, 'AsyncClient', lambda **kwargs: real_client(transport=httpx.MockTransport(respond), **kwargs))
    call = m.GroundedInferenceGateway().complete([{'role': 'user', 'content': 'Public fixture'}], schema_model=m.GroundedDraft, max_tokens=2400, temperature=0)
    if finish_reason == 'length':
        with pytest.raises(ValueError, match='Incomplete') as refused:
            asyncio.run(call)
        assert refused.value.public_details['finish_reason'] == 'length'
        assert 'output' not in refused.value.public_details
    else:
        assert asyncio.run(call).parsed.findings[0].quote == TEXT
    assert len(requests) == 1
    request = requests[0]
    import json
    assert json.loads(request.content)['max_tokens'] == 2400
    assert json.loads(request.content)['model'] != 'auto'  # auto activates a 60-token fast lane
    assert request.headers['X-API-Key'] == 'fixture-only-key'


def test_completion_gateway_mock_mode_refused_before_network(monkeypatch):
    settings_module = ModuleType('intelx.core.settings')
    settings_module.get_settings = lambda: SimpleNamespace(MOCK_MODE=True)
    monkeypatch.setitem(sys.modules, 'intelx.core.settings', settings_module)
    with pytest.raises(ValueError, match='MOCK_MODE'):
        asyncio.run(m.GroundedInferenceGateway().complete([], schema_model=m.GroundedDraft, max_tokens=2400, temperature=0))


# TASK-REL-007: a truncated route (finish_reason 'length') must not be the
# final word — Inference rotates providers per call, so one retry is made.
# Every other refusal stays final, and the success path still calls once.

def _flaky_gateway(failures_before_success, error_details=None):
    calls = {"n": 0}

    async def complete(**kwargs):
        calls["n"] += 1
        if calls["n"] <= failures_before_success:
            raise m.GroundedCompletionError(
                "Incomplete inference completion refused",
                error_details or {"reason_code": "incomplete_completion", "finish_reason": "length", "output_characters": 125},
            )
        return SimpleNamespace(provider="inference", parsed=result())

    return SimpleNamespace(complete=complete), calls


def test_incomplete_completion_is_retried_once_and_can_succeed():
    gateway, calls = _flaky_gateway(1)
    d = asyncio.run(m.synthesize_grounded("How are quoted commas handled?", DOCS, gateway))
    assert d["status"] == "SUCCESS"
    assert calls["n"] == 2


def test_incomplete_completion_retry_is_bounded():
    gateway, calls = _flaky_gateway(99)
    with pytest.raises(m.GroundedCompletionError):
        asyncio.run(m.synthesize_grounded("How are quoted commas handled?", DOCS, gateway))
    assert calls["n"] == 2


def test_other_completion_refusals_are_not_retried():
    gateway, calls = _flaky_gateway(99, {"reason_code": "invalid_schema", "finish_reason": "stop", "output_characters": 40})
    with pytest.raises(m.GroundedCompletionError):
        asyncio.run(m.synthesize_grounded("How are quoted commas handled?", DOCS, gateway))
    assert calls["n"] == 1
