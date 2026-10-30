"""Jarvis complete paths: live chart adapter, actions, voice and HTTP workplace."""
from __future__ import annotations

import importlib.util
import io
import json
from pathlib import Path
import sys
from types import SimpleNamespace
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from friday_core.real_cross_agent_engine import CrossAgentEngine
from friday_core.real_capability_api import create_capability_router as create_research_router
from friday_core.real_approved_actions import LocalActionEngine, HomeAssistantRoomAdapter
from Stratex.real_market_service import MarketDataService


def load(name,path):
    spec=importlib.util.spec_from_file_location(name,Path(__file__).resolve().parents[1]/path)
    module=importlib.util.module_from_spec(spec);sys.modules[name]=module;spec.loader.exec_module(module)
    return module

voice=load('test_voice_interaction','VyralX/app/agents/real_voice_interaction.py')
speech=load('test_speech_bridge','VyralX/app/agents/real_speech_bridge.py')


def chart():
    return {'chart':{'result':[{'meta':{'regularMarketPrice':120,'chartPreviousClose':100,'currency':'INR',
        'regularMarketDayHigh':122,'regularMarketDayLow':98},'indicators':{'quote':[{'close':list(range(100,120))}]}}]}}


def test_market_cache_stale_and_copy():
    now=[100];calls=[]
    def fetch(symbol):
        calls.append(symbol)
        if len(calls)>1:raise OSError('feed offline')
        return chart()
    service=MarketDataService(fetch,ttl=60,clock=lambda:now[0])
    first=service.get('TCS.NS');first.closes.clear()
    assert service.get('TCS.NS').closes and len(calls)==1
    now[0]=200
    stale=service.get('TCS.NS')
    assert stale.stale and stale.observed_at==100
    assert 'Cached quote' in service.watchlist(['TCS.NS'])['briefing']


def test_market_failures_and_url_injection():
    service=MarketDataService(lambda symbol: {'chart':{'result':[]}})
    assert service.watchlist(['NVDA'])['results'][0]['status']=='unavailable'
    with pytest.raises(ValueError):service.get('NVDA?redirect=evil')
    with pytest.raises(ValueError):service.watchlist([])


def test_yahoo_transport_is_fixed_and_encoded(monkeypatch):
    captured=[]
    def fetch(request,timeout):
        captured.append(request.full_url);return io.BytesIO(json.dumps(chart()).encode())
    monkeypatch.setattr('Stratex.real_market_service.urlopen',fetch)
    assert MarketDataService().get('^NSEI').analysis['signal']=='STRONG BUY'
    assert '%5ENSEI' in captured[0] and captured[0].startswith('https://query1.finance.yahoo.com/')


def test_local_actions_approval_replay_and_audit(tmp_path):
    calls=[];now=[100]
    engine=LocalActionEngine(tmp_path,'secret',True,apps={'code':['/usr/bin/code']},clock=lambda:now[0],
        runner=lambda argv,**kw:calls.append(argv) or SimpleNamespace(returncode=0))
    plan=engine.parse('Jarvis, open VS Code')['action']
    assert not calls and plan['status']=='pending'
    with pytest.raises(PermissionError):engine.execute(plan['id'],'wrong')
    assert engine.execute(plan['id'],'secret')['status']=='completed'
    with pytest.raises(ValueError):engine.execute(plan['id'],'secret')
    assert calls==[['/usr/bin/code']]
    assert 'completed' in (tmp_path/'action_audit.jsonl').read_text()
    expired=engine.parse('open code')['action'];now[0]=1000
    with pytest.raises(ValueError):engine.execute(expired['id'],'secret')


def test_drafts_mail_and_search_preserve_case(tmp_path):
    engine=LocalActionEngine(tmp_path,contacts={'alice':'+91 9000000000'})
    message=engine.parse('send whatsapp to Alice saying Hello FROM Friday')['action']
    assert message['payload']['message']=='Hello FROM Friday'
    assert message['payload']['url'].startswith('https://wa.me/919000000000')
    assert message['status']=='ready'
    assert 'No mail cache' in engine.parse('read emails')['text']
    (tmp_path/'mail_cache.txt').write_text('Verified cache content')
    assert engine.parse('read emails')['text']=='Verified cache content'
    assert 'search_query=LoFi+Mix' in engine.parse('play LoFi Mix on youtube')['action']['payload']['url']
    assert engine.parse('open unknown')['source']=='local'
    assert engine.parse('what time is it')['text']


def test_room_service_is_configured_not_arbitrary(tmp_path):
    captured=[]
    class Response(io.BytesIO): status=200
    adapter=HomeAssistantRoomAdapter('http://home.internal','secret',lambda request,timeout:captured.append(request) or Response())
    engine=LocalActionEngine(tmp_path,'approval',True)
    engine.devices={'lights':{'on':{'service':'light.turn_on','data':{'entity_id':'light.room'}}}}
    engine.device_runner=adapter
    planned=engine.parse('turn on the lights')['action']
    assert not captured
    assert engine.execute(planned['id'],'approval')['status']=='completed'
    assert captured[0].full_url=='http://home.internal/api/services/light/turn_on'
    assert json.loads(captured[0].data)['entity_id']=='light.room'
    assert 'not configured' in engine.parse('turn on the geyser')['text']


def test_voice_gate_hysteresis_and_guard():
    gate=voice.AdaptiveVoiceGate()
    assert gate.feed([.04]*10,1).kind=='quiet'
    assert gate.feed([.04]*10,1.12).kind=='speech_start'
    assert gate.feed([.015]*10,1.2).kind=='speech'
    assert gate.feed([0]*10,2).kind=='speech_end'
    guarded=voice.AdaptiveVoiceGate()
    guarded.feed([.04]*10,1,True)
    assert guarded.feed([.04]*10,1.2,True).kind=='quiet'
    with pytest.raises(ValueError):gate.feed([float('nan')],3)


def test_utterance_assembly_wake_debounce_echo():
    assembler=voice.UtteranceAssembler()
    assert assembler.add('unaddressed',10)['status']=='asleep'
    assert assembler.add('Hey Friday',11)['status']=='awake'
    assert assembler.add('Friday',11.1)['status']=='debounced'
    assembler.add('what is the weather in',12)
    assert assembler.flush(12.3) is None
    assembler.add('Tirupati',12.4)
    assert assembler.flush(12.7)=='what is the weather in Tirupati'
    assembler.speaking('It is currently ten o clock',13)
    assert assembler.add('It is currently ten o clock',13.5)['status']=='echo'


def test_clap_shape_and_filter_reset():
    clap=voice.ClapDetector()
    for i in range(10):assert not clap.feed(.005,i*.02)
    assert not clap.feed(.2,.22)
    assert clap.feed(.01,.27)
    assert not clap.feed(.2,.3)
    smooth=voice.OneEuroFilter()
    assert smooth.filter(0,0)==0
    assert 0<smooth.filter(1,.02)<1
    smooth.reset();assert smooth.filter(5,1)==5
    with pytest.raises(ValueError):smooth.filter(3,0)


def test_speech_bridges_real_payloads():
    requests=[]
    def transport(request,timeout):
        requests.append(request)
        return io.BytesIO(b'{"text":"Hey Friday"}' if 'speech-to-text' in request.full_url else b'mpeg-bytes')
    bridge=speech.SpeechBridge('secret','voice-id',transport)
    assert bridge.transcribe(b'webm-data')=='Hey Friday'
    assert b'scribe_v1' in requests[0].data and b'webm-data' in requests[0].data
    assert bridge.synthesize('Hello')==b'mpeg-bytes'
    assert not speech.SpeechBridge().capabilities()['stt']
    with pytest.raises(RuntimeError):speech.SpeechBridge().transcribe(b'webm')


def test_workplace_voice_and_market_through_http(tmp_path):
    engine=CrossAgentEngine(str(tmp_path));runtime=engine.capability_runtime()
    runtime.market=MarketDataService(lambda symbol:chart())
    app=FastAPI();app.include_router(create_research_router(engine))
    with TestClient(app) as client:
        assert client.get('/assistant').status_code==200
        assert 'localhost' not in client.get('/assistant').text
        result=client.post('/api/assistant/respond',json={'query':'Nifty stock market'}).json()
        assert result['watchlist']['results'][0]['snapshot']['symbol']=='^NSEI'
        session=client.post('/api/voice/sessions',json={}).json()['session_id']
        reply=client.post(f'/api/voice/sessions/{session}/transcript',json={'text':'Hey Friday, open github','at':10}).json()
        assert reply['status']=='answered' and reply['reply']['action']['target']=='github'
        assert client.post('/api/assistant/actions/no/approve').status_code==403


def test_conversation_sessions_do_not_share_history(tmp_path):
    cross=CrossAgentEngine(str(tmp_path));runtime=cross.capability_runtime()
    first=runtime.new_chat();second=runtime.new_chat()
    runtime.chat_sessions[first]['brain'].models=('test',)
    runtime.chat_sessions[first]['brain'].provider=lambda model,messages:'answer to '+messages[-1]['content']
    assert runtime.chat(first,'explain testing')['source']=='cloud'
    assert len(runtime.chat_sessions[first]['brain'].history)==2
    assert runtime.chat_sessions[second]['brain'].history==[]
    status=runtime.actions.system_status()
    assert 0<=status['disk_used_percent']<=100
    assert status['disk_total_bytes']>=status['disk_free_bytes']


def test_motion_filter_is_available_through_voice_session_http(tmp_path):
    engine=CrossAgentEngine(str(tmp_path));app=FastAPI();app.include_router(create_research_router(engine))
    with TestClient(app) as client:
        identifier=client.post('/api/voice/sessions',json={}).json()['session_id']
        path='/api/voice/sessions/'+identifier+'/motion'
        assert client.post(path,json={'x':0,'y':0,'at':1}).json()['x']==0
        moved=client.post(path,json={'x':1,'y':1,'at':1.02}).json()
        assert 0<moved['x']<1 and 0<moved['y']<1
        assert client.post(path,json={'x':-1,'y':0,'at':2}).status_code==422
