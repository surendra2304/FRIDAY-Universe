from __future__ import annotations

import os
import sys
import pytest
from fastapi.testclient import TestClient

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)


# ═════════════════════════════════════════════════════════════════════════════
# 1. STRATEX E2E TESTS (AutoHedge, Vibe-Trading, FinceptTerminal)
# ═════════════════════════════════════════════════════════════════════════════

class TestStratexE2E:
    @classmethod
    def setup_class(cls):
        stratex_path = os.path.join(REPO_ROOT, "Stratex")
        if stratex_path in sys.path:
            sys.path.remove(stratex_path)
        sys.path.insert(0, stratex_path)

    @pytest.fixture(scope="class")
    def client(self):
        from Stratex.dashboard import app
        app.config["TESTING"] = True
        with app.test_client() as c:
            yield c

    def test_autohedge_consensus(self, client):
        resp = client.post("/api/v1/trading/engines/autohedge/consensus", json={
            "agents": [
                {"name": "trend", "conviction": 0.9, "weight": 1.5, "risk_tolerance": 0.4},
                {"name": "reversal", "conviction": 0.7, "weight": 1.0, "risk_tolerance": 0.6},
            ],
            "signals": {"trend": 0.8, "reversal": -0.2},
        })
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["status"] == "success"
        assert data["engine"] == "AutoHedge"
        assert "consensus_signal" in data
        assert "weighted_vote" in data
        assert data["agent_count"] == 2

    def test_autohedge_position_size(self, client):
        resp = client.post("/api/v1/trading/engines/autohedge/position-size", json={
            "win_prob": 0.6,
            "win_ratio": 2.0,
            "fraction": 0.5,
            "bankroll": 100000.0,
            "current_value": 95000.0,
        })
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["status"] == "success"
        assert data["kelly_fraction"] == pytest.approx(0.4, rel=1e-2)
        assert data["raw_position_size"] > 0
        assert data["recommended_position_size"] > 0
        assert data["drawdown_multiplier"] > 0

    def test_autohedge_rebalance(self, client):
        resp = client.post("/api/v1/trading/engines/autohedge/rebalance", json={
            "positions": {"BTC": 1.0, "ETH": 10.0},
            "prices": {"BTC": 60000.0, "ETH": 3000.0},
            "target_weights": {"BTC": 0.5, "ETH": 0.5},
            "cash": 10000.0,
        })
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["status"] == "success"
        assert data["total_value"] == 100000.0
        assert "BTC" in data["drift"]
        assert "orders" in data

    def test_autohedge_backtest(self, client):
        resp = client.post("/api/v1/trading/engines/autohedge/backtest", json={
            "initial_capital": 50000.0,
            "trades": [
                {"action": "buy", "asset": "SOL", "price": 100.0, "shares": 50.0},
                {"action": "sell", "asset": "SOL", "price": 120.0, "shares": 25.0},
            ],
            "prices": {"SOL": 130.0},
            "returns": [0.02, 0.015, -0.01, 0.03, 0.005],
        })
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["status"] == "success"
        assert data["final_value"] > 50000.0
        assert data["sharpe_ratio"] > 0

    def test_vibe_alphas(self, client):
        prices = [100.0 + i * 0.8 for i in range(25)]
        volumes = [1000.0 + (i % 4) * 150 for i in range(25)]
        resp = client.post("/api/v1/trading/engines/vibe/alphas", json={
            "prices": prices,
            "volumes": volumes,
        })
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["status"] == "success"
        assert "momentum" in data["core_factors"]
        assert "alpha_001" in data["gtja_alphas"]
        assert "alpha_191" in data["gtja_alphas"]

    def test_vibe_portfolio(self, client):
        resp = client.post("/api/v1/trading/engines/vibe/portfolio", json={
            "weights": {"momentum": 0.5, "value": 0.3, "volatility": 0.2},
            "values": {"momentum": [1.2]*10, "value": [0.6]*10, "volatility": [-0.5]*10},
            "top_n": 2,
        })
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["status"] == "success"
        assert len(data["combined_factor"]) == 10
        assert len(data["top_n_selection"]) == 2
        assert "total_risk" in data["risk_decomposition"]

    def test_fincept_technical(self, client):
        prices = [100.0, 101.5, 101.0, 103.0, 104.5, 104.0, 106.0, 107.5, 107.0, 109.0]
        resp = client.post("/api/v1/trading/engines/fincept/technical", json={
            "prices": prices,
        })
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["status"] == "success"
        assert "sma" in data["technical_indicators"]
        assert "rsi" in data["technical_indicators"]
        assert "bollinger_bands" in data["technical_indicators"]
        assert "bullish_engulfing" in data["candlestick_patterns"]

    def test_fincept_orderflow(self, client):
        resp = client.post("/api/v1/trading/engines/fincept/orderflow", json={
            "bids": [[100.0, 20.0], [99.5, 30.0]],
            "asks": [[100.5, 15.0], [101.0, 25.0]],
        })
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["status"] == "success"
        assert data["microprice"] > 0
        assert "bid_ask_imbalance" in data

    def test_fincept_regime(self, client):
        returns = [0.012, 0.008, 0.015, 0.02, 0.005, 0.011, 0.014]
        resp = client.post("/api/v1/trading/engines/fincept/regime", json={
            "returns": returns,
        })
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["status"] == "success"
        assert "detected_regime" in data
        assert data["detected_regime"] in ["bull_calm", "bull_volatile", "bear_calm", "bear_volatile", "neutral", "unknown"]

    def test_fincept_fundamentals(self, client):
        resp = client.post("/api/v1/trading/engines/fincept/fundamentals", json={
            "assets": 600000.0,
            "liabilities": 200000.0,
            "debt": 150000.0,
            "equity": 400000.0,
            "income": 60000.0,
            "revenue": 300000.0,
            "price": 180.0,
            "eps": 9.0,
            "bvps": 60.0,
        })
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["status"] == "success"
        assert data["metrics"]["current_ratio"] == 3.0
        assert data["metrics"]["return_on_equity"] == 0.15
        assert data["financial_health_score"] > 0


# ═════════════════════════════════════════════════════════════════════════════
# 2. VYRALX E2E TESTS (ClaudeAds, TopRank, OpenHiggsfield, Hyperframes)
# ═════════════════════════════════════════════════════════════════════════════

class TestVyralXE2E:
    @classmethod
    def setup_class(cls):
        os.environ["DATABASE_URL"] = "sqlite:///./data/vyralx_test.db"
        os.environ["ENVIRONMENT"] = "testing"
        for mod in list(sys.modules):
            if mod == "app" or mod.startswith("app."):
                sys.modules.pop(mod, None)
        vyralx_path = os.path.join(REPO_ROOT, "VyralX")
        if vyralx_path in sys.path:
            sys.path.remove(vyralx_path)
        sys.path.insert(0, vyralx_path)

    @classmethod
    def teardown_class(cls):
        os.environ.pop("DATABASE_URL", None)

    @pytest.fixture(scope="class")
    def client(self):
        from app.main import app
        return TestClient(app)

    def test_claude_ads_campaign(self, client):
        resp = client.post("/api/v1/vyralx/engines/ads/campaign", json={
            "account_id": "acc_enterprise_01",
            "name": "Global AI Video Launch",
            "platform": "google_ads",
            "objective": "conversions",
            "budget_daily": 250.0,
            "budget_total": 7500.0,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "success"
        assert data["platform"] == "google_ads"
        assert data["total_campaigns"] >= 1

    def test_claude_ads_compliance(self, client):
        resp = client.post("/api/v1/vyralx/engines/ads/compliance", json={
            "title": "Autonomous AI Video Marketing",
            "description": "Production-grade video synthesis for marketing teams #ad",
            "cta": "Get Started",
            "platform": "google_ads",
            "destination_url": "https://vyralx.ai/ad",
            "landing_url": "https://vyralx.ai/landing",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "success"
        assert data["compliant"] is True

    def test_claude_ads_report(self, client):
        resp = client.get("/api/v1/vyralx/engines/ads/report/google_ads")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "success"
        assert data["platform"] == "google_ads"
        assert "roas" in data

    def test_toprank_analyze(self, client):
        resp = client.post("/api/v1/vyralx/engines/toprank/analyze", json={
            "content": "AI agent architectures enable autonomous execution. Autonomous video generation empowers growth.",
            "keywords": ["ai agent", "video generation"],
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "success"
        assert data["word_count"] > 5
        assert "analysis" in data

    def test_toprank_geo_optimize(self, client):
        resp = client.post("/api/v1/vyralx/engines/toprank/geo-optimize", json={
            "content": "Autonomous video generation engine powered by FRIDAY Universe multi-agent architecture.",
            "query": "what is the leading video agent",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "success"
        assert data["ai_visibility_score"] >= 0

    def test_toprank_safety(self, client):
        resp = client.post("/api/v1/vyralx/engines/toprank/safety?text=High+quality+marketing+campaign")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "success"
        assert data["is_safe"] is True

    def test_higgsfield_generate(self, client):
        resp = client.post("/api/v1/vyralx/engines/studio/generate", json={
            "prompt": "Cinematic visual render of decentralized AI intelligence network",
            "model": "Flux.1-dev",
            "width": 1024,
            "height": 1024,
            "num_steps": 20,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "success"
        assert "Flux.1-dev" in data["model"]
        assert "output_path" in data
        assert data["total_studio_generations"] >= 1

    def test_higgsfield_capabilities(self, client):
        resp = client.get("/api/v1/vyralx/engines/studio/capabilities")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "success"
        assert "total_models" in data["capabilities"]

    def test_hyperframes_create_script(self, client):
        resp = client.post("/api/v1/vyralx/engines/hyperframes/create-script", json={
            "title": "FRIDAY Universe Launch",
            "text": "Ten autonomous engines coordinate seamlessly. Cross-agent peer calls provide unified execution.",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "success"
        assert data["scene_count"] >= 1
        assert "manifest" in data

    def test_hyperframes_aspect_ratios(self, client):
        resp = client.get("/api/v1/vyralx/engines/hyperframes/aspect-ratios")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "success"
        assert "16:9" in data["supported_aspect_ratios"]
        assert data["resolutions"]["16:9"] == [1920, 1080]


# ═════════════════════════════════════════════════════════════════════════════
# 3. CORTEX E2E TESTS (Agentic Inbox)
# ═════════════════════════════════════════════════════════════════════════════

class TestCortexE2E:
    @classmethod
    def setup_class(cls):
        os.environ.pop("DATABASE_URL", None)
        cortex_path = os.path.join(REPO_ROOT, "Cortex", "apps", "api", "src")
        if cortex_path in sys.path:
            sys.path.remove(cortex_path)
        sys.path.insert(0, cortex_path)

    @pytest.fixture(scope="class")
    def client(self):
        from cortex_api.main import app
        return TestClient(app)

    def test_inbox_classify_meeting(self, client):
        resp = client.post("/api/v1/cortex/inbox/classify", json={
            "sender": "partner@vc.com",
            "recipient": "cortex@universe.ai",
            "subject": "Executive Meeting Tomorrow",
            "body": "Let's schedule a meeting to review cross-agent KPIs tomorrow at 2 PM.",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "success"
        assert data["classification"] == "meeting"
        assert "meeting" in data["labels"]
        assert data["is_spam"] is False
        assert data["priority_score"] > 0

    def test_inbox_classify_finance(self, client):
        resp = client.post("/api/v1/cortex/inbox/classify", json={
            "sender": "billing@cloud.oracle.com",
            "recipient": "cortex@universe.ai",
            "subject": "Monthly Cloud Invoice #INV-98214",
            "body": "Please find attached invoice for server hosting and GPU compute payment.",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "success"
        assert data["classification"] == "finance"

    def test_inbox_actions(self, client):
        resp = client.post("/api/v1/cortex/inbox/actions", json={
            "text": "Please review the security audit. You must submit the SOC2 report by Thursday.",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "success"
        assert data["item_count"] >= 1

    def test_inbox_summarize(self, client):
        resp = client.post("/api/v1/cortex/inbox/summarize", json={
            "sender": "lead@dev.org",
            "recipient": "cortex@universe.ai",
            "subject": "Deployment Architecture",
            "body": "We have completed the deployment of all 10 specialized agent engines across the cluster.",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "success"
        assert len(data["summary"]) > 0

    def test_inbox_triage(self, client):
        resp = client.post("/api/v1/cortex/inbox/triage", json={
            "messages": [
                {"sender": "a@co.com", "recipient": "c@co.com", "subject": "Meeting", "body": "Let's meet."},
                {"sender": "b@co.com", "recipient": "c@co.com", "subject": "Invoice", "body": "Please pay."},
            ]
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "success"
        assert "meeting" in data["triage"]
        assert "finance" in data["triage"]

    def test_inbox_digest(self, client):
        resp = client.get("/api/v1/cortex/inbox/digest")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "success"
        assert "unread_count" in data["digest"]

    def test_inbox_coordinate(self, client):
        resp = client.post("/api/v1/cortex/inbox/coordinate", json={
            "messages": [
                {"sender": "client@corp.com", "recipient": "c@co.com", "subject": "Support help needed", "body": "Help me fix error."},
                {"sender": "cfo@corp.com", "recipient": "c@co.com", "subject": "Invoice approval", "body": "Approve this bill."},
            ]
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "success"
        assert len(data["routing"]) == 2
        assert len(data["coordination_plan"]) == 2


# ═════════════════════════════════════════════════════════════════════════════
# 4. MEMORA E2E TESTS (Context Mode)
# ═════════════════════════════════════════════════════════════════════════════

class TestMemoraE2E:
    @classmethod
    def setup_class(cls):
        memora_path = os.path.join(REPO_ROOT, "Memora")
        if memora_path in sys.path:
            sys.path.remove(memora_path)
        sys.path.insert(0, memora_path)

    @pytest.fixture(scope="class")
    def client(self):
        from apps.api.main import app
        return TestClient(app)

    def test_context_optimize(self, client):
        content = "Autonomous reasoning engine coordinates tasks across 10 specialized agent clusters. " * 30
        resp = client.post("/api/v1/memora/context-mode/optimize", json={
            "content": content,
            "platform": "claude_code",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "success"
        assert data["platform"] == "claude_code"
        assert data["platform_token_limit"] == 200000
        assert data["hooks_supported"] is True
        assert data["optimization"]["original_tokens"] > 0

    def test_context_sandbox_tool_git(self, client):
        git_diff = "\n".join(f"+ def function_{i}(): pass" for i in range(100))
        resp = client.post("/api/v1/memora/context-mode/sandbox-tool", json={
            "tool_type": "git",
            "output": git_diff,
            "max_lines": 15,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "success"
        assert "omitted" in data["sandboxed_output"]
        assert data["metrics"]["savings"] > 0

    def test_context_sandbox_tool_test(self, client):
        test_out = "PASSED test_1\nFAILED test_2\nError: assertion error at line 42\nPASSED test_3"
        resp = client.post("/api/v1/memora/context-mode/sandbox-tool", json={
            "tool_type": "test",
            "output": test_out,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "success"
        assert "Errors" in data["sandboxed_output"]

    def test_context_sandbox_batch(self, client):
        resp = client.post("/api/v1/memora/context-mode/sandbox-batch", json={
            "outputs": {
                "git_status": "\n".join(f"modified file_{i}.py" for i in range(50)),
                "pytest": "PASSED\nFAILED: test_auth\nError: 401 Unauthorized",
            }
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "success"
        assert "savings_percentage" in data["batch_savings"]

    def test_context_session_store_retrieve(self, client):
        resp_store = client.post("/api/v1/memora/context-mode/session/store", json={
            "key": "active_framework",
            "value": "FastAPI with async worker pool",
            "category": "architecture",
        })
        assert resp_store.status_code == 200
        assert resp_store.json()["stored"] is True

        resp_get = client.get("/api/v1/memora/context-mode/session/retrieve?key=active_framework")
        assert resp_get.status_code == 200
        assert resp_get.json()["value"] == "FastAPI with async worker pool"

    def test_context_platforms(self, client):
        resp = client.get("/api/v1/memora/context-mode/platforms")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "success"
        assert "claude_code" in data["platforms"]
        assert "copilot" in data["platforms"]
        assert "cursor" in data["platforms"]


# ═════════════════════════════════════════════════════════════════════════════
# 5. FORGE E2E TESTS (Camofox Stealth Browser)
# ═════════════════════════════════════════════════════════════════════════════

class TestForgeE2E:
    @classmethod
    def setup_class(cls):
        os.environ.pop("DATABASE_URL", None)
        for mod in list(sys.modules):
            if mod == "app" or mod.startswith("app."):
                sys.modules.pop(mod, None)
        forge_path = os.path.join(REPO_ROOT, "Forge")
        if forge_path in sys.path:
            sys.path.remove(forge_path)
        sys.path.insert(0, forge_path)

    @pytest.fixture(scope="class")
    def client(self):
        from app.main import app
        return TestClient(app)

    def test_browser_fingerprint(self, client):
        resp = client.post("/api/v1/forge/browser/fingerprint")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "success"
        assert "user_agent" in data["fingerprint"]
        assert len(data["fingerprint_hash"]) == 16

    def test_browser_stealth_assess_clean(self, client):
        resp = client.post("/api/v1/forge/browser/stealth-assess", json={
            "navigator_data": {"webdriver": False, "userAgent": "Mozilla/5.0", "plugins": [1, 2], "languages": ["en"]},
            "permission_data": {"notifications": "prompt"},
            "canvas_hash": "canvas_valid_hash_987",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "success"
        assert data["detection_results"]["risk_level"] == "low"

    def test_browser_stealth_assess_headless(self, client):
        resp = client.post("/api/v1/forge/browser/stealth-assess", json={
            "navigator_data": {"webdriver": True, "userAgent": "HeadlessChrome", "plugins": [], "languages": []},
            "permission_data": {"notifications": "denied"},
            "canvas_hash": "short",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "success"
        assert len(data["bypass_suggestions"]) > 0

    def test_browser_antibot_challenge(self, client):
        resp = client.post("/api/v1/forge/browser/antibot/challenge", json={
            "html_content": "<html><title>Just a moment...</title><body>Checking your connection</body></html>",
            "retry_attempt": 2,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "success"
        assert data["challenge_type"] == "cloudflare_interstitial"
        assert data["recommended_backoff_seconds"] > 0

    def test_browser_antibot_trajectory(self, client):
        resp = client.post("/api/v1/forge/browser/antibot/trajectory", json={
            "start_pos": [0, 0],
            "end_pos": [300, 450],
            "steps": 8,
            "scroll_direction": "down",
            "scroll_distance": 500,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "success"
        assert len(data["mouse_path"]) == 9
        assert len(data["scroll_pattern"]) > 0

    def test_browser_context(self, client):
        resp = client.post("/api/v1/forge/browser/context", json={
            "proxy": "residential-proxy-us.io:8080",
            "use_proxy": True,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "success"
        assert data["proxy"] == "residential-proxy-us.io:8080"
        assert "risk_level" in data["stealth_assessment"]

    def test_browser_health_report(self, client):
        resp = client.get("/api/v1/forge/browser/health-report")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "success"
        assert data["health_report"]["stealth_level"] == "high"
        assert len(data["stealth_checklist"]) >= 8
