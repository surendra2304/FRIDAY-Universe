"""Agent/API integration, persistence and causal momentum execution."""
from __future__ import annotations

from dataclasses import asdict
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from friday_core.real_cross_agent_engine import CrossAgentEngine
from friday_core.real_research_api import create_research_router
from Stratex.real_trading_engine import TradingEngine, PriceBar


@pytest.fixture
def engine(tmp_path):
    return CrossAgentEngine(str(tmp_path))


@pytest.fixture
def client(engine, monkeypatch):
    monkeypatch.setenv('FRIDAY_LOCAL_ACTION_TOKEN', 'layer-test-token')
    app = FastAPI()
    app.include_router(create_research_router(engine))
    test_client = TestClient(app)
    test_client.headers.update({'X-FRIDAY-Operator': 'layer-test-token'})
    return test_client


def market():
    return dict(symbol="TEST", price=120, previous_close=118, closes=list(range(100, 120)))


def documents():
    return [dict(url="http://source.onion/leak", title="Observed posting", text=
                 "Unverified claim: 8.8.8.8, invalid 999.999.999.999, contact test@example.com " + "a"*64)]


def test_assistant_routes_to_real_stratex(client):
    response = client.post('/api/assistant/respond', json={'query':'Jarvis, analyze market', 'market':market()})
    assert response.status_code == 200
    result = response.json()
    assert result['source'] == 'local' and result['agent'] == 'Stratex'
    direct = client.post('/api/trading/momentum', json=market()).json()
    assert result['analysis'] == direct
    assert direct['signal'] == 'STRONG BUY'


def test_research_persists_indicators_report_memory(client, engine):
    response = client.post('/api/threat/research', json={'documents':documents()})
    assert response.status_code == 200
    result = response.json()
    assert result['memory_id']
    assert result['report']['sources'] == ['http://source.onion/leak']
    found = engine._threat_intel.search_indicators()
    assert {i.type for i in found} == {'url', 'ip', 'email', 'hash'}
    assert all(i.confidence == 0.3 for i in found)
    assert not any(i.value == '999.999.999.999' for i in found)
    reloaded = CrossAgentEngine(engine._state_dir)
    assert len(reloaded._threat_intel.search_indicators()) == 4
    assert reloaded._threat_intel._reports[-1].report_id == result['report']['report_id']
    assert reloaded._memory.search('IntelX', limit=5)
    # Re-ingestion does not create duplicate indicator identities.
    reloaded.research_threats(documents())
    assert len(reloaded._threat_intel.search_indicators()) == 4


def test_research_assistant_dispatch(client):
    result = client.post('/api/assistant/respond', json={'query':'investigate threat', 'documents':documents()}).json()
    assert result['agent'] == 'IntelX'
    assert len(result['research']['evidence'][0]['indicator_ids']) == 4


def test_refused_sources_never_become_indicators(engine):
    result = engine.research_threats([dict(url='https://evil.com', title='Bad source', text='1.2.3.4')])
    assert result['batch']['rejected_count'] == 1
    assert result['report']['indicators'] == []
    assert not engine._threat_intel.search_indicators()


def test_api_rejects_bad_observations(client):
    for patch in [{'price':0}, {'closes':[-1]*10}]:
        assert client.post('/api/trading/momentum', json={**market(), **patch}).status_code == 422
    assert client.post('/api/assistant/respond', json={'query':'Jarvis,'}).status_code == 422
    assert client.post('/api/threat/research', json={'documents':[], 'per_host_limit':0}).status_code == 422


def test_provider_failover_cooldown_through_workflow(engine):
    calls = []
    def provider(model, messages):
        calls.append(model)
        if model == 'first':
            raise RuntimeError('unavailable')
        return 'cloud answer'
    result = engine.assistant_reply('Explain a concept', provider=provider, models=['first','second'])
    assert result['text'] == 'cloud answer' and calls == ['first','second']
    def limited(*args):
        calls.append('limited')
        raise RuntimeError('429 try again in 60s')
    assert engine.assistant_reply('question', provider=limited, models=['first'])['source'] == 'fallback'
    assert engine.assistant_reply('another')['source'] == 'fallback'
    assert calls.count('limited') == 1
    assert engine.assistant_reply('market', market=market())['agent'] == 'Stratex'


def bars():
    prices = list(range(100, 125)) + list(range(125, 95, -1))
    return [PriceBar(i, p, p+1, p-1, p) for i,p in enumerate(prices)]


def test_real_signal_path_is_causal(tmp_path):
    engine = TradingEngine(str(tmp_path))
    history = bars()
    all_signals = engine.generate_signals('X', history, 'jarvis_momentum')
    early = engine.generate_signals('X', history[:20], 'jarvis_momentum')
    assert early and [asdict(s) for s in early] == [asdict(s) for s in all_signals if s.timestamp < 20]
    assert {s.signal for s in all_signals} == {'buy','sell'}
    assert all(s.timestamp in {b.timestamp for b in history} for s in all_signals)


def test_backtest_fees_reproducibility_and_next_open(tmp_path):
    engine = TradingEngine(str(tmp_path))
    history = bars()
    first_signal = engine.generate_signals('X', history, 'jarvis_momentum')[0]
    result = engine.backtest('X', history, 'jarvis_momentum')
    assert result.total_trades > 0
    assert result.trades[0].entry_price == history[int(first_signal.timestamp)+1].open
    assert result.final_equity == pytest.approx(10000 + sum(t.pnl for t in result.trades))
    again = engine.backtest('X', history, 'jarvis_momentum')
    assert again.final_equity == result.final_equity
    assert again.total_trades == result.total_trades
    no_fees = engine.backtest('X', history, 'jarvis_momentum', fee_pct=0)
    assert no_fees.final_equity > result.final_equity


def test_engine_redirect_is_resolved_before_ingestion(engine):
    result = engine.research_threats([dict(engine_url='http://engine.onion',
        url='/redirect?target=http%3A%2F%2Ftarget.onion%2Fpost', title='Target report', text='8.8.4.4')])
    assert result['report']['sources'] == ['http://target.onion/post']
    assert engine._threat_intel.search_indicators(value='8.8.4.4')


def test_actual_cloud_adapter_payload_and_rate_limit(monkeypatch):
    import io
    import json
    from urllib.error import HTTPError
    from friday_core.real_hybrid_assistant import GroqChatProvider, CloudProviderError
    requests = []
    def transport(request, timeout):
        requests.append((request, timeout))
        return io.BytesIO(json.dumps({'choices':[{'message':{'content':'answer'}}]}).encode())
    monkeypatch.setattr('urllib.request.urlopen', transport)
    provider = GroqChatProvider('test-key')
    assert provider('model', [{'role':'user','content':'question'}]) == 'answer'
    request, timeout = requests[0]
    assert json.loads(request.data)['messages'][0]['content'] == 'question'
    assert timeout == 15
    assert request.full_url == 'https://api.groq.com/openai/v1/chat/completions'
    def limited(*args, **kwargs):
        raise HTTPError(request.full_url, 429, 'limited', {'Retry-After':'12'}, io.BytesIO())
    monkeypatch.setattr('urllib.request.urlopen', limited)
    with pytest.raises(CloudProviderError) as error:
        provider('model', [])
    assert error.value.status_code == 429
    assert error.value.headers['Retry-After'] == '12'
    assert 'test-key' not in str(error.value)


def test_existing_trading_workflow_uses_jarvis_strategy(engine):
    result = engine.run_trading_workflow('X', [b.close for b in bars()], strategy='jarvis_momentum')
    assert result.status == 'completed'
    assert result.steps[0].result['signal_count'] > 0
    assert result.steps[1].result['trades'] > 0


def test_actual_server_signal_and_backtest_routes():
    from friday_core.real_api_server import app
    client = TestClient(app)
    payload = {'symbol':'X', 'prices':[b.close for b in bars()], 'strategy':'jarvis_momentum'}
    response = client.post('/api/trading/signals', json=payload)
    assert response.status_code == 200
    assert response.json()['signals'][0]['timestamp'] == 9
    result = client.post('/api/trading/backtest', json=payload)
    assert result.status_code == 200
    assert result.json()['total_trades'] > 0
