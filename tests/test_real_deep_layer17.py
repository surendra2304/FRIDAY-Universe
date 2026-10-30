"""Cloud9 public-topic computations, position gates and persistent trade review."""
from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from friday_core.real_cross_agent_engine import CrossAgentEngine
from friday_core.real_capability_api import create_capability_router as create_research_router
from Stratex.real_trading_discipline import TradingDisciplineEngine, TradeJournal


def test_risk_first_sizing_fees_and_exposure():
    engine=TradingDisciplineEngine()
    plan=engine.plan(10000,100,95,120,risk_fraction=.01,fee_fraction=.001)
    assert plan.allowed
    assert plan.estimated_loss<=100
    assert plan.quantity*100<=10000
    assert plan.quantity==19
    assert plan.reward_risk==pytest.approx((20-.22)/(5+.195))
    low_rr=engine.plan(10000,100,95,102)
    assert not low_rr.allowed
    blocked=engine.plan(10000,100,95,120,existing_risk=500)
    assert blocked.quantity==0 and not blocked.allowed


def test_short_risk_plan_and_lot_rounding():
    plan=TradingDisciplineEngine().plan(10000,100,105,80,side='sell',lot_size=5)
    assert plan.allowed and plan.quantity%5==0
    with pytest.raises(ValueError):TradingDisciplineEngine().plan(10000,100,90,110,side='sell')


@pytest.mark.parametrize('patch',[{'equity':0},{'risk_fraction':.5},{'entry':float('nan')},{'stop':105},{'fee_fraction':-1}])
def test_invalid_risk_inputs(patch):
    with pytest.raises(ValueError):TradingDisciplineEngine().plan(**{**dict(equity=10000,entry=100,stop=95,target=120),**patch})


def test_r_multiples_can_be_profitable_below_half_wins():
    result=TradingDisciplineEngine.expectancy([3,3,-1,-1,-1])
    assert result['win_rate']==.4 and result['expectancy_r']==pytest.approx(.6)
    assert result['profit_factor']==2
    assert result['breakeven_win_rate']==.25


def test_market_structure_breakout_volume_and_regime():
    bars=[{'open':100+i,'high':101+i,'low':99+i,'close':100+i,'volume':100} for i in range(20)]
    bars.append({'open':121,'high':126,'low':120,'close':125,'volume':200})
    result=TradingDisciplineEngine.market_structure(bars)
    assert result['breakout']=='above' and result['volume_confirmed']
    assert result['relative_volume']==2 and result['regime']=='trend'
    assert result['atr14']>0 and result['support']<result['resistance']
    assert result['suggested_long_stop']<result['support']


def test_candlestick_patterns_are_computed_not_win_rate_claims():
    bars=[{'open':100,'high':102,'low':98,'close':100,'volume':10} for i in range(7)]
    result=TradingDisciplineEngine.market_structure(bars)
    assert 'doji' in result['patterns'] and result['regime']=='range'
    assert result['efficiency_ratio']==0
    assert result['relative_volume']==1


def test_correlation_concentration_and_hedge_direction():
    returns={'A':[.1,-.1,.2,.3],'B':[.2,-.2,.4,.6]}
    result=TradingDisciplineEngine.correlation_exposure(returns,{'A':.5,'B':.5})
    assert result['correlated_pairs'][0]['correlation']==pytest.approx(1)
    assert result['correlated_pairs'][0]['same_direction_risk']
    hedge=TradingDisciplineEngine.correlation_exposure(returns,{'A':.5,'B':-.5})
    assert not hedge['correlated_pairs'][0]['same_direction_risk']


def test_journal_persistence_expectancy_and_revenge_gate(tmp_path):
    path=tmp_path/'journal.jsonl';journal=TradeJournal(path)
    journal.record('t1','X',-100,100,False,timestamp=100)
    assert not journal.review(now=200)['allowed']
    assert journal.review(now=2000)['allowed']
    journal.record('t2','X',-200,100,True,timestamp=2100)
    assert 'Rolling daily loss limit reached' in TradeJournal(path).review(now=5000)['reasons']
    assert journal.review(now=5000)['plan_adherence']==.5
    with pytest.raises(ValueError):journal.record('t2','X',100,100,True)


def test_risk_gate_and_journal_are_http_capabilities(tmp_path,monkeypatch):
    monkeypatch.setenv('FRIDAY_CONTROL_TOKEN','test-control')
    cross=CrossAgentEngine(str(tmp_path));app=FastAPI();app.include_router(create_research_router(cross))
    with TestClient(app,headers={'x-friday-control-token':'test-control'}) as client:
        args=dict(equity=10000,entry=100,stop=95,target=120)
        assert client.post('/api/trading/risk-plan',json={'arguments':args}).json()['allowed']
        assert client.post('/api/trading/journal',json={'arguments':dict(trade_id='recent',symbol='X',pnl=-100,initial_risk=100,followed_plan=True)}).status_code==200
        gated=client.post('/api/trading/risk-plan',json={'arguments':args}).json()
        assert not gated['allowed'] and gated['plan']['allowed']


def test_trailing_stops_never_widen_and_losers_cannot_scale():
    engine=TradingDisciplineEngine()
    winning=engine.manage_position('buy',100,95,104,120,122,3)
    assert winning['stop']==116 and winning['scale_eligible']
    losing=engine.manage_position('buy',100,95,95,97,101,3)
    assert losing['stop']>=95 and not losing['scale_eligible']
    short=engine.manage_position('sell',100,105,95,80,78,3)
    assert short['stop']==84 and short['scale_eligible']
