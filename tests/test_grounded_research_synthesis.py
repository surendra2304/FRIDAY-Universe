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
    # TASK-REL-052: the statement must satisfy the TASK-INT-005 entailment
    # screen (>=80% content-word coverage of the cited source text) for the
    # SUCCESS path; the previous paraphrase scored 3/5 and correctly
    # degraded. Statement wording is drawn from the source's own tokens.
    return m.GroundedDraft(findings=[m.GroundedFinding(statement='Fields containing delimiters are enclosed by a quote character, preserving a comma inside a quoted field.', source_id=source_id, quote=quote)], insufficient_evidence=insufficient)


def run(parsed, provider='inference', docs=None):
    gateway = SimpleNamespace(complete=AsyncMock(return_value=SimpleNamespace(provider=provider, parsed=parsed)))
    return asyncio.run(m.synthesize_grounded('How are quoted commas handled?', DOCS if docs is None else docs, gateway)), gateway


def test_source_grounded_draft_preserves_real_source_link_and_unverified_state():
    d, gateway = run(result())
    assert d['status'] == 'SUCCESS'
    assert d['quotes_verified'] is True
    # TASK-INT-005/009: entailment is now really screened (statement_support),
    # so a SUCCESS draft reports semantic_entailment_verified True; the old
    # hardcoded False was the defect INT-005 fixed.
    assert d['semantic_entailment_verified'] is True
    assert d['question_answered'] is False
    assert d['findings'][0]['citations'][0]['source_url'] == DOCS[0]['url']
    assert 'untrusted data' in gateway.complete.call_args.kwargs['messages'][0]['content']
    assert gateway.complete.await_count == 1


# TASK-INT-018: a failed synthesis is a non-success, never a reason to
# destroy evidence already retrieved. The pre-#78 deployed path returned
# the extractive excerpts; the #78 synthesis path discarded them
# (findings: []) on every failure. The failure return now preserves them,
# labelled as raw source passages — never as a synthesised brief.
@pytest.mark.parametrize('parsed', [result(quote='This invented quotation was never present in any fetched source document.'), result(source_id='invented'), result(insufficient=True), m.GroundedDraft(findings=[], insufficient_evidence=False), None])
def test_invalid_or_insufficient_grounding_returns_raw_excerpts_not_completed_findings(parsed):
    d, _ = run(parsed)
    assert d['status'] == 'DEGRADED'
    assert d['answer_kind'] == 'unsynthesised_raw_findings'
    assert d['question_answered'] is False
    assert d['findings']
    assert all(f['status'] == 'source_excerpt' for f in d['findings'])
    assert all(f['quote'] in TEXT for f in d['findings'])


def test_synthesis_failure_excerpts_are_verbatim_and_cited():
    d, _ = run(result(quote='This invented quotation was never present in any fetched source document.'))
    assert d['status'] == 'DEGRADED'
    assert d['error'] == 'synthesis_quote_unverified'
    assert d['answer_kind'] == 'unsynthesised_raw_findings'
    assert d['question_answered'] is False
    assert d['findings']
    for f in d['findings']:
        assert f['status'] == 'source_excerpt'
        assert f['statement'] == f['quote']
        assert f['quote'] in TEXT
        assert f['independently_verified'] is False
        assert f['single_source'] is True
        assert f['citations'][0]['source_url'] == DOCS[0]['url']
        assert f['citations'][0]['source_id'] == DOCS[0]['source_id']


def test_no_source_material_has_no_excerpts_to_preserve():
    gateway = SimpleNamespace(complete=AsyncMock(return_value=SimpleNamespace(provider='inference', parsed=result())))
    d = asyncio.run(m.synthesize_grounded('How are quoted commas handled?', [], gateway))
    assert d['status'] == 'DEGRADED'
    assert d['error'] == 'no_source_material'
    assert d['findings'] == []


def test_mock_response_is_never_live_synthesis():
    d, _ = run(result(), provider='mock')
    assert d['status'] == 'DEGRADED'
    assert d['error'] == 'mock_synthesis_refused'
    # TASK-INT-018: the refusal still preserves the raw excerpts.
    assert d['findings'] and all(f['status'] == 'source_excerpt' for f in d['findings'])


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


# TASK-INT-053: an entailment failure must name its failing leg, and gets
# one retry with a fresh draft — the gateway routes across providers/models
# per call (REL-007), so a second draw is genuinely different text. The
# retry relaxes no gate: the fresh draft passes the quote gate and the
# entailment screen unchanged, and a second entailment failure is final.

def failing_result(entity="Zanzibar"):
    # The statement is drawn from the source's own tokens except for one
    # named entity the source never mentions, so it fails exactly the
    # entity leg with unsupported_entity:<entity>; the quote is verbatim.
    return m.GroundedDraft(findings=[m.GroundedFinding(
        statement=f'Fields containing delimiters are enclosed by a quote character, preserving a comma inside a quoted field, announced by {entity}.',
        source_id='public-one', quote=TEXT)], insufficient_evidence=False)


def _sequenced_gateway(*parsed_list):
    calls = {"n": 0}

    async def complete(**kwargs):
        parsed = parsed_list[min(calls["n"], len(parsed_list) - 1)]
        calls["n"] += 1
        return SimpleNamespace(provider="inference", parsed=parsed)

    return SimpleNamespace(complete=complete), calls


def test_entailment_failure_records_per_finding_reason():
    d, gateway = run(failing_result())
    assert d["status"] == "DEGRADED"
    assert d["error"] == "synthesis_entailment_unverified"
    assert d["entailment_failures"] == [{"source_id": "public-one", "reason": "unsupported_entity:Zanzibar"}]
    # The same failing draft is drawn again once, then the failure is final.
    assert gateway.complete.await_count == 2
    assert d["findings"] and all(f["status"] == "source_excerpt" for f in d["findings"])


def test_entailment_failure_retried_once_and_can_succeed():
    gateway, calls = _sequenced_gateway(failing_result(), result())
    d = asyncio.run(m.synthesize_grounded("How are quoted commas handled?", DOCS, gateway))
    assert d["status"] == "SUCCESS"
    assert d["findings"][0]["entailment_verified"] is True
    assert calls["n"] == 2


def test_entailment_failure_retry_is_bounded():
    gateway, calls = _sequenced_gateway(failing_result(), failing_result())
    d = asyncio.run(m.synthesize_grounded("How are quoted commas handled?", DOCS, gateway))
    assert d["status"] == "DEGRADED"
    assert d["error"] == "synthesis_entailment_unverified"
    assert d["entailment_failures"] == [{"source_id": "public-one", "reason": "unsupported_entity:Zanzibar"}]
    assert calls["n"] == 2


def test_quote_failure_is_not_retried():
    d, gateway = run(result(quote='This invented quotation was never present in any fetched source document.'))
    assert d["status"] == "DEGRADED"
    assert d["error"] == "synthesis_quote_unverified"
    assert gateway.complete.await_count == 1


def test_entailment_failures_lists_every_failing_finding():
    draft = m.GroundedDraft(findings=[
        m.GroundedFinding(statement=failing_result().findings[0].statement, source_id='public-one', quote=TEXT),
        m.GroundedFinding(statement=failing_result("Quixotic").findings[0].statement, source_id='public-one', quote=TEXT[0:60]),
    ], insufficient_evidence=False)
    d, gateway = run(draft)
    assert d["status"] == "DEGRADED"
    assert d["entailment_failures"] == [
        {"source_id": "public-one", "reason": "unsupported_entity:Zanzibar"},
        {"source_id": "public-one", "reason": "unsupported_entity:Quixotic"},
    ]
    assert gateway.complete.await_count == 2
