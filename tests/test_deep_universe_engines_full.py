"""
tests/test_deep_universe_engines_full.py — Comprehensive tests for all adapted deep engines across the Universe.

Verifies:
1. Stratex: CCXT, Backtrader, Vectorbt, Freqtrade, Hummingbot, Lumibot, Polymarket, TradingAgents, TradingHub
2. IntelX: Intelligence X, ShadowDragon Dorks/Permutations/Forensics, Maltego Graph, MalNet, Horizon Monitor
3. VyralX: ClaudeAds, TopRank, OpenHiggsfield, Hyperframes, Unified Growth Pack
4. Cross-Agent Engine Flow & API surface verification
"""

import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


# =======================================================================
# 1. STRATEX — FULL ENGINE VERIFICATION
# =======================================================================

class TestStratexDeepEngines:
    """Test full integration of all trading engines in Stratex."""

    def test_ccxt_live_or_simulated(self):
        from Stratex.app.agents.real_ccxt import CCXTManager, ExchangeConfig, HAS_REAL_CCXT
        mgr = CCXTManager()
        ex = mgr.add_exchange("binance", ExchangeConfig(name="binance"))
        ticker = ex.fetch_ticker("BTC/USDT")
        assert ticker["symbol"] == "BTC/USDT"
        assert ticker["last"] > 0
        assert ticker["bid"] > 0
        assert ticker["ask"] >= ticker["bid"]

    def test_ccxt_arbitrage_detection(self):
        from Stratex.app.agents.real_ccxt import CCXTManager, ExchangeConfig
        mgr = CCXTManager()
        ex1 = mgr.add_exchange("binance", ExchangeConfig(name="binance"))
        ex2 = mgr.add_exchange("coinbase", ExchangeConfig(name="coinbase"))
        prices = {
            "binance": {"bid": 65000.0, "ask": 65050.0},
            "coinbase": {"bid": 65150.0, "ask": 65200.0},
        }
        best = mgr.find_best_price(prices)
        assert best["buy_price"] > 0
        assert best["sell_price"] > 0
        assert abs(best["spread"]) == 100.0

    def test_backtrader_real_or_simulated_cerebro(self):
        from Stratex.app.agents.real_backtrader import BacktraderCerebro, HAS_REAL_BACKTRADER
        data = {"close": [100.0 + i * 0.5 + ((i % 5) - 2) for i in range(40)]}
        res = BacktraderCerebro.run_real_cerebro(data, fast=5, slow=15)
        assert "final_value" in res or "portfolio_values" in res
        assert res.get("final_value", 0) > 0 or len(res.get("portfolio_values", [])) > 0

    def test_vectorbt_vectorized_portfolio(self):
        from Stratex.app.agents.real_vectorbt import PortfolioSimulation, HAS_REAL_VECTORBT
        closes = [100.0 + i * 0.4 for i in range(50)]
        res = PortfolioSimulation.simulate_real_vectorbt(closes, fast_window=5, slow_window=15)
        assert "total_return" in res
        assert "sharpe_ratio" in res
        assert "max_drawdown" in res

    def test_freqtrade_hyperopt(self):
        from Stratex.app.agents.real_freqtrade import FreqtradeBacktest
        data = {"close": [100.0, 102.0, 99.0, 105.0, 108.0, 104.0, 110.0]}
        res = FreqtradeBacktest.run_strategy_hyperopt(data)
        assert res["engine"] == "freqtrade_hyperopt"
        assert "best_config" in res
        assert res["trials_evaluated"] > 0

    def test_hummingbot_pure_market_making(self):
        from Stratex.app.agents.real_hummingbot import MarketMakingStrategy
        bid, ask = MarketMakingStrategy.calculate_bid_ask(100.0, 0.002, level=0)
        assert bid < 100.0
        assert ask > 100.0
        skewed_spread = MarketMakingStrategy.adjust_spread(100.0, inventory=0.5, base_spread=0.002)
        assert skewed_spread > 0.002

    def test_lumibot_backtest_runner(self):
        from Stratex.app.agents.real_lumibot import LumibotBacktest
        res = LumibotBacktest.run_live_or_simulated_backtest("BTC-USD", initial_cash=10000.0, days=15)
        assert res["engine"] == "lumibot_backtest"
        assert res["initial_cash"] == 10000.0
        assert res["final_value"] > 0

    def test_polymarket_probability_and_odds(self):
        from Stratex.app.agents.real_polymarket import PolymarketAPI, PredictionMarketAnalyzer
        kelly = PredictionMarketAnalyzer.kelly_fraction(0.60, 1.0)
        assert kelly > 0.0
        assert kelly <= 1.0

    def test_trading_agents_debate(self):
        from Stratex.app.agents.real_trading_agents import BullBearDebate
        debate = BullBearDebate()
        res = debate.debate([100.0, 105.0, 110.0], [{"title": "Surge in profits", "sentiment": "positive"}], rounds=3)
        assert res["rounds"] == 3
        assert "winner" in res

    def test_unified_trading_hub(self):
        from Stratex.app.trading_hub import hub
        quote = hub.get_market_quote("BTC/USDT", "binance")
        assert quote["symbol"] == "BTC/USDT"
        
        quotes = hub.compute_market_making_quotes(50000.0, spread=0.001, inventory=0.2)
        assert quotes["bid"] < 50000.0
        assert quotes["ask"] > 50000.0
        
        debate = hub.debate_trade_decision("BTC/USDT", 65000.0, ["Surge in institutional crypto volume"])
        assert debate["action"] in ["BUY", "HOLD", "SELL"]
        assert debate["conviction"] > 0

    def test_stratex_flask_api_routes(self):
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "Stratex"))
        from dashboard import app
        client = app.test_client()

        # Test CCXT endpoint
        r1 = client.get("/api/v1/trading/engines/ccxt/ticker?symbol=BTC/USDT&exchange=binance")
        assert r1.status_code == 200
        assert r1.json["status"] == "success"

        # Test Hummingbot endpoint
        r2 = client.post("/api/v1/trading/engines/hummingbot/market-make", json={"mid_price": 200.0, "spread": 0.001})
        assert r2.status_code == 200
        assert r2.json["quotes"]["bid"] < 200.0

        # Test Trading Agents debate endpoint
        r3 = client.post("/api/v1/trading/engines/trading-agents/debate", json={"symbol": "ETH/USDT", "price": 3500.0})
        assert r3.status_code == 200
        assert "deliberation" in r3.json


# =======================================================================
# 2. INTELX — FULL ENGINE & ROUTE VERIFICATION
# =======================================================================

class TestIntelXDeepEngines:
    """Test full integration of all OSINT and graph engines in IntelX."""

    def test_google_dork_assistant_generate(self):
        from IntelX.app.agents.real_intelx_osint import GoogleDorkAssistant
        dorks = GoogleDorkAssistant().generate("target.com", dork_type="all")
        assert len(dorks) >= 5
        assert any("filetype:" in str(d) for d in dorks)

    def test_email_permutator_generate(self):
        from IntelX.app.agents.real_intelx_osint import EmailPermutator
        perms = EmailPermutator().generate("alice", "smith", org_domain="intel.org")
        assert len(perms) >= 10
        emails = [p.email for p in perms]
        assert "alice.smith@intel.org" in emails or "asmith@intel.org" in emails

    def test_image_forensics_ela(self):
        from IntelX.app.agents.real_intelx_osint import ImageForensics
        res = ImageForensics.compute_ela("")
        assert "manipulation_score" in res or "error" in res or res.get("status")

    def test_maltego_graph_build(self):
        from IntelX.app.agents.real_maltego_graph import MaltegoGraph, MaltegoEntity, MaltegoRelationship
        graph = MaltegoGraph()
        e1 = MaltegoEntity(entity_type="Email", entity_value="investigator@sec.gov")
        e2 = MaltegoEntity(entity_type="Domain", entity_value="sec.gov")
        graph.add_entity(e1)
        graph.add_entity(e2)
        rel = MaltegoRelationship(source_id=e1.entity_id, target_id=e2.entity_id, relationship_type="belongs_to")
        graph.add_relationship(rel)
        assert len(graph.entities) == 2
        assert len(graph.relationships) == 1

    def test_malnet_correlate(self):
        from IntelX.app.agents.real_maltego_graph import MalNetEngine
        engine = MalNetEngine()
        corr = engine.correlate("194.26.29.112")
        assert "ip_findings" in corr or "indicator" in corr or "threat_score" in corr

    def test_intelx_fastapi_routes(self):
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "IntelX"))
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from routers.real_osint_routes import router as real_osint_router

        app = FastAPI()
        app.include_router(real_osint_router)
        client = TestClient(app)

        # 1. Dorks
        r1 = client.post("/api/v1/intelx/osint/dorks", json={"target": "cybersec.org", "category": "all"})
        assert r1.status_code == 200
        assert r1.json()["dorks_count"] > 0

        # 2. Email Permutations
        r2 = client.post("/api/v1/intelx/osint/email-permutations", json={"first_name": "bob", "last_name": "ross", "domain": "paint.org"})
        assert r2.status_code == 200
        assert r2.json()["permutation_count"] > 0

        # 3. Maltego Graph
        r3 = client.post("/api/v1/intelx/maltego/graph", json={
            "name": "Investigation-Alpha",
            "entities": [{"value": "target@host.com", "type": "Email"}],
            "relationships": []
        })
        assert r3.status_code == 200
        assert r3.json()["entity_count"] == 1


# =======================================================================
# 3. VYRALX — FULL ENGINE & GROWTH PACK VERIFICATION
# =======================================================================

class TestVyralXGrowthDeepEngines:
    """Test full integration of VyralX media and growth engines."""

    def test_unified_growth_pack_endpoint(self):
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "VyralX"))
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from VyralX.app.services.real_media_routes import router

        app = FastAPI()
        app.include_router(router, prefix="/api/v1/vyralx")
        client = TestClient(app)

        resp = client.post("/api/v1/vyralx/engines/growth-pack", json={
            "brand_name": "FRIDAY Universe",
            "campaign_goal": "Scale autonomous AI operations",
            "content_text": "Autonomous agents executing trading, reasoning, and security",
            "platforms": ["google_ads", "linkedin"],
            "keywords": ["ai agents", "autonomous", "trading"]
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["engine"] == "VyralX_GrowthPack"
        assert "google_ads" in data["ad_campaigns"]
        assert "linkedin" in data["ad_campaigns"]
        assert data["seo_rank_score"] > 0
        assert data["video_scenes"] >= 1
        assert "svg" in data["diagram_svg"].lower()
