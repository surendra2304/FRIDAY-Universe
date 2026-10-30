"""Drive playbooks: real lead/ad/ops workflows, economics and scheduled skills."""
from __future__ import annotations

from datetime import datetime, timezone
import time
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from friday_core.real_cross_agent_engine import CrossAgentEngine
from friday_core.real_capability_api import create_capability_router as create_research_router
from friday_core.real_business_routines import BusinessRoutineEngine


@pytest.fixture
def runtime(tmp_path):
    return CrossAgentEngine(str(tmp_path)).capability_runtime()


def lead(**patch):
    now=2000000
    return {**dict(id='lead-1',name='Alice',source='crm:1',owner='Sales',email='alice@example.com',
        status='open',added_at=now-86400,updated_at=now-86400,last_interaction=now-6*86400,interest='a reviewed pilot'),**patch}


def test_leads_optout_duplicates_staleness_and_factual_drafts(runtime):
    result=runtime.business.review_leads([lead(),lead(id='duplicate'),lead(id='optout',email='no@example.com',opted_out=True),
        lead(id='won',email='customer@example.com',status='won'),lead(id='missing',email='missing@example.com',owner='')],now=2000000)
    assert result['leads'][0]['classification']=='Needs follow-up'
    assert 'reviewed pilot' in result['leads'][0]['draft']
    assert result['duplicates']==[{'id':'duplicate','duplicate_of':'lead-1'}]
    assert result['excluded']==[{'id':'optout','reason':'opted_out'}]
    assert result['leads'][1]['classification']=='Won' and not result['leads'][1]['draft']
    assert result['leads'][2]['classification']=='Unclear'
    assert result['mode']=='draft_only'


def test_contacted_today_respects_timezone(runtime):
    now=datetime(2026,10,26,1,tzinfo=timezone.utc).timestamp()
    prior=datetime(2026,10,25,23,tzinfo=timezone.utc).timestamp()
    result=runtime.business.review_leads([lead(updated_at=now,last_interaction=prior)],now,reporting_timezone='Asia/Kolkata')
    assert result['leads'][0]['classification']=='Waiting on customer'
    assert not result['leads'][0]['draft']


def ad(**patch):
    return {**dict(date='2026-10-25',timezone='Asia/Kolkata',attribution_window='7d_click',campaign='Campaign A',source='ads:1',
        spend=100,impressions=1000,clicks=50,leads=5,purchases=2,revenue=300,updated_at=123),**patch}


def test_ad_report_weighted_metrics_missing_data_and_windows(runtime):
    result=runtime.business.ad_report([ad(),ad(campaign='B',source='ads:2',spend=200,clicks=10,impressions=100,leads=0,purchases=0,revenue=None),
        ad(source='wrong-window',attribution_window='1d_click')],date='2026-10-25',reporting_timezone='Asia/Kolkata',attribution_window='7d_click',
        previous=[ad(date='2026-10-24',spend=100,leads=10)],budget=250)
    assert result['totals']['ctr_pct']==pytest.approx(60/1100*100)
    assert result['totals']['cpc']==5
    assert result['totals']['cpl']==60
    assert result['totals']['roas'] is None
    assert result['source_failures'][0]['reason']=='incomparable reporting window'
    assert 'Spend exceeds stated budget' in result['flags']
    assert result['campaigns'][1]['cpl'] is None
    assert result['mode']=='read_only'


def test_duplicate_rows_and_mixed_currencies(runtime):
    report=runtime.business.ad_report([ad(),ad()],date='2026-10-25',reporting_timezone='Asia/Kolkata',attribution_window='7d_click')
    assert report['totals']['spend']==100
    with pytest.raises(ValueError):runtime.business.ad_report([ad(currency='INR'),ad(source='other',currency='USD')],date='2026-10-25',reporting_timezone='Asia/Kolkata',attribution_window='7d_click')


def test_pilot_economics_is_math_not_100_crore_promise(runtime):
    result=runtime.business.pilot_economics(20000,5000,30000,30000,100,10,60,15,5)
    assert result['break_even_customers']==2
    assert result['capacity_customers']==10
    assert result['hours_saved_weekly']==3.75
    assert result['gross_margin']==.75
    assert result['setup_payback_months']==.25
    assert len(result['validation_steps'])==6


def test_weekly_ops_sweep_prioritizes_sources(runtime):
    leads=runtime.business.review_leads([lead()],2000000)
    result=runtime.business.weekly_sweep([dict(title='Overdue promise',due_at=100,owner='Ops',source='tasks:1',status='open')],
        leads,{'flags':['CPL increased'],'freshness':[{'source':'ads:1'}]},2000000)
    assert len(result['priorities'])==3
    assert result['priorities'][0]['source']=='tasks:1'


def test_routine_timezone_persistence_claim_and_stale_sources(tmp_path):
    calls=[]
    engine=BusinessRoutineEngine(tmp_path,lambda kind,sources,parameters:calls.append(kind) or {'draft':'review only'})
    engine.save_skill('leads','lead_review',['crm'],{},validated=False)
    now=datetime(2026,10,26,0,tzinfo=timezone.utc).timestamp()
    with pytest.raises(ValueError):engine.create('leads','Asia/Kolkata',9,15,[0,1,2,3,4],now)
    engine.save_skill('leads','lead_review',['crm'],{},validated=True)
    routine=engine.create('leads','Asia/Kolkata',9,15,[0,1,2,3,4],now)
    assert datetime.fromtimestamp(routine['next_run'],timezone.utc).hour==3
    assert datetime.fromtimestamp(routine['next_run'],timezone.utc).minute==45
    slot=routine['next_run']
    results=engine.tick(slot+1,lambda source:{'updated_at':slot,'data':[]})
    assert results[0]['status']=='completed' and calls==['lead_review']
    again=BusinessRoutineEngine(tmp_path,lambda *args:None)
    assert again.tick(slot+10,lambda source:{'updated_at':slot,'data':[]})==[]
    next_slot=again.routines[routine['id']].next_run
    failed=again.tick(next_slot+1,lambda source:{'updated_at':slot-86400,'data':[]})
    assert failed[0]['status']=='failed' and 'stale' in failed[0]['error']
    again.save_skill('leads','lead_review',['new_crm'],{},validated=False)
    assert again.routines[routine['id']].paused


def test_dst_nonexistent_time_is_skipped(tmp_path):
    engine=BusinessRoutineEngine(tmp_path,lambda *args:{})
    engine.save_skill('skill','lead_review',['crm'],{},validated=True)
    before=datetime(2026,3,7,23,tzinfo=timezone.utc).timestamp()
    routine=engine.create('skill','America/New_York',2,30,[6],before)
    assert datetime.fromtimestamp(routine['next_run'],timezone.utc).date().isoformat()=='2026-03-15'


def test_business_http_and_manual_validation_before_scheduling(tmp_path,monkeypatch):
    monkeypatch.setenv('FRIDAY_CONTROL_TOKEN','test-control')
    cross=CrossAgentEngine(str(tmp_path));app=FastAPI();app.include_router(create_research_router(cross))
    headers={'x-friday-control-token':'test-control'}
    with TestClient(app) as client:
        assert client.put('/api/business/sources/crm',json={'data':[],'updated_at':time.time()}).status_code==403
        assert client.put('/api/business/sources/crm',headers=headers,json={'data':[lead(updated_at=time.time(),last_interaction=None)],'updated_at':time.time()}).status_code==200
        saved=client.post('/api/business/skills',headers=headers,json={'arguments':dict(name='review',kind='lead_review',sources=['crm'],parameters={})})
        assert saved.status_code==200
        validated=client.post('/api/business/skills/review/validate',headers=headers)
        assert validated.status_code==200 and validated.json()['validated']
        scheduled=client.post('/api/business/routines',headers=headers,json={'arguments':dict(skill='review',timezone_='Asia/Kolkata',hour=9,minute=15,weekdays=[0,1,2,3,4],now=time.time())})
        assert scheduled.status_code==200
        assert client.get('/api/business/routines',headers=headers).json()[0]['skill']=='review'


def test_opportunity_rankings_require_buyer_access_and_realistic_budget(runtime):
    cards=[dict(id='1',title='Content repurposing',category='Creator operations',minimum_budget=5000,pilot_weeks=3,source='provided-playbook:1'),
           dict(id='2',title='Plant monitoring',category='Manufacturing',minimum_budget=200000,pilot_weeks=16,source='provided-playbook:2')]
    result=runtime.business.rank_opportunities(cards,20000,6,['content'],{'1':5,'2':0})
    assert result[0]['id']=='1' and result[0]['pilot_ready']
    assert not result[1]['pilot_ready'] and len(result[1]['reasons'])==3
    assert result[0]['human_review_required']
