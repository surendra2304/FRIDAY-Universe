"""
Real Batch 4a Tests — 10 Real-World Repo Implementations

Tests for:
- Stratex/app/agents/real_autohedge.py — swarm consensus, Kelly sizing, risk management
- Stratex/app/agents/real_vibe_trading.py — alpha factors, GTJA 191 library
- Stratex/app/agents/real_fincept_terminal.py — market analytics, technical indicators
- VyralX/app/services/real_claude_ads.py — 12-platform paid media ops
- VyralX/app/services/real_toprank.py — SEO/GEO ranking, analytics
- VyralX/app/services/real_open_higgsfield.py — generative video/image studio
- VyralX/app/services/real_hyperframes.py — HTML-to-video rendering
- Cortex/apps/api/src/cortex_api/real_agentic_inbox.py — AI agent email coordination
- Memora/core/memory/real_context_mode.py — context window optimization
- Forge/app/services/real_camofox_browser.py — stealth headless browser
"""

import pytest
import sys
import os
import math

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


# =======================================================================
# 1. Stratex — AutoHedge (swarm intelligence, Kelly sizing, risk)
# =======================================================================

class TestAutoHedge:
    """Test Stratex real_autohedge.py."""

    def test_swarm_agent_conviction(self):
        from Stratex.app.agents.real_autohedge import SwarmAgent
        agent = SwarmAgent(name="trader1", conviction=0.8, weight=1.0)
        assert agent.conviction == 0.8

    def test_swarm_agent_signal(self):
        from Stratex.app.agents.real_autohedge import SwarmAgent
        agent = SwarmAgent(name="trader1", conviction=0.9)
        signal = agent.conviction_weighted_signal(signal_strength=0.01)
        assert signal is not None

    def test_swarm_agent_risk_adjusted(self):
        from Stratex.app.agents.real_autohedge import SwarmAgent
        agent = SwarmAgent(name="trader1", risk_tolerance=0.7, conviction=0.8)
        signal = agent.risk_adjusted_signal(signal=0.01, volatility=0.15)
        assert signal is not None

    def test_swarm_consensus(self):
        from Stratex.app.agents.real_autohedge import SwarmAgent, SwarmConsensus
        agents = [
            SwarmAgent(name=f"a{i}", conviction=0.8 + i * 0.05)
            for i in range(5)
        ]
        consensus = SwarmConsensus(agents=agents)
        result = consensus.consensus_signal(signals=[0.01, 0.02, 0.015, 0.018, 0.022])
        assert result is not None

    def test_kelly_fraction(self):
        from Stratex.app.agents.real_autohedge import KellyPositionSizer
        sizer = KellyPositionSizer()
        fraction = sizer.kelly_fraction(win_prob=0.6, win_ratio=2.0)
        assert fraction > 0
        assert fraction <= 1.0

    def test_kelly_fraction_edge(self):
        from Stratex.app.agents.real_autohedge import KellyPositionSizer
        sizer = KellyPositionSizer()
        fraction = sizer.kelly_fraction(win_prob=0.5, win_ratio=1.5)
        assert fraction > 0

    def test_kelly_safe(self):
        from Stratex.app.agents.real_autohedge import KellyPositionSizer
        sizer = KellyPositionSizer()
        fraction = sizer.kelly_fraction(win_prob=0.3, win_ratio=0.5)
        assert fraction == 0.0

    def test_kelly_position_size(self):
        from Stratex.app.agents.real_autohedge import KellyPositionSizer
        sizer = KellyPositionSizer(bankroll=10000)
        size = sizer.position_size(win_prob=0.6, win_ratio=2.0, fraction=0.25)
        assert size > 0

    def test_kelly_fractional(self):
        from Stratex.app.agents.real_autohedge import KellyPositionSizer
        sizer = KellyPositionSizer(bankroll=10000)
        kelly = sizer.kelly_fraction(win_prob=0.6, win_ratio=2.0)
        frac = sizer.fractional_kelly(kelly_fraction=kelly, fraction=0.5)
        assert frac > 0

    def test_risk_manager(self):
        from Stratex.app.agents.real_autohedge import RiskManager
        rm = RiskManager(max_drawdown_pct=0.2, stop_loss_pct=0.05, take_profit_pct=0.15)
        assert rm.max_drawdown_pct == 0.2

    def test_risk_manager_stop_loss(self):
        from Stratex.app.agents.real_autohedge import RiskManager
        rm = RiskManager(stop_loss_pct=0.05)
        triggered = rm.stop_loss_triggered(current_price=95, entry_price=100)
        assert triggered

    def test_risk_manager_take_profit(self):
        from Stratex.app.agents.real_autohedge import RiskManager
        rm = RiskManager(take_profit_pct=0.10)
        triggered = rm.take_profit_triggered(current_price=110, entry_price=100)
        assert triggered

    def test_portfolio_rebalancer(self):
        from Stratex.app.agents.real_autohedge import PortfolioRebalancer
        pr = PortfolioRebalancer(target_weights={"AAPL": 0.5, "GOOG": 0.3, "MSFT": 0.2})
        result = pr.rebalance(prices={"AAPL": 150, "GOOG": 2800, "MSFT": 300})
        assert isinstance(result, dict)

    def test_portfolio_drift(self):
        from Stratex.app.agents.real_autohedge import PortfolioRebalancer
        pr = PortfolioRebalancer(target_weights={"AAPL": 0.5, "GOOG": 0.5})
        drift = pr.drift(asset="AAPL", total_value=100000)
        assert drift is not None

    def test_backtest_engine(self):
        from Stratex.app.agents.real_autohedge import BacktestEngine
        engine = BacktestEngine(initial_capital=100000)
        engine.buy("AAPL", price=150, shares=100)
        engine.sell("AAPL", price=160, shares=100)
        result = engine.total_value(prices={"AAPL": 160})
        assert result > 0

    def test_backtest_sharpe(self):
        from Stratex.app.agents.real_autohedge import BacktestEngine
        engine = BacktestEngine()
        sharpe = engine.sharpe_ratio(returns=[0.01, 0.02, 0.015, 0.018])
        assert isinstance(sharpe, float)

    def test_drawdown_controller(self):
        from Stratex.app.agents.real_autohedge import DrawdownController
        dc = DrawdownController(peak_value=100000, soft_limit=0.1, hard_limit=0.2)
        dc.update_peak(110000)
        mult = dc.position_multiplier(95000)
        assert 0 <= mult <= 1

    def test_volatility_targeter(self):
        from Stratex.app.agents.real_autohedge import VolatilityTargeter
        vt = VolatilityTargeter(target_vol=0.15, vol_window=5)
        mult = vt.scaled_position(base_position=1.0, prices=[100, 102, 101, 105, 108, 110, 107, 112])
        assert mult > 0

    def test_volatility_compute(self):
        from Stratex.app.agents.real_autohedge import VolatilityTargeter
        vt = VolatilityTargeter(vol_window=5)
        vol = vt.compute_volatility([100, 102, 101, 105, 108, 110])
        assert vol > 0

    def test_agent_coordinator(self):
        from Stratex.app.agents.real_autohedge import AgentCoordinator, SwarmAgent
        ac = AgentCoordinator()
        ac.register_agent(SwarmAgent(name="trader1", conviction=0.8))
        ac.register_agent(SwarmAgent(name="trader2", conviction=0.6))
        signal = ac.aggregate_signals({"trader1": 0.01, "trader2": 0.02})
        assert signal is not None


# =======================================================================
# 2. Stratex — Vibe-Trading (alpha factors, GTJA 191)
# =======================================================================

class TestVibeTrading:
    """Test Stratex real_vibe_trading.py."""

    def test_momentum_factor(self):
        from Stratex.app.agents.real_vibe_trading import MomentumFactor
        f = MomentumFactor(window=5)
        scores = f.compute([100, 102, 101, 105, 108, 110, 107, 112, 115, 113], [1000, 1100, 1200, 1300, 1400, 1500, 1600, 1700, 1800, 1900])
        assert len(scores) > 0

    def test_reversal_factor(self):
        from Stratex.app.agents.real_vibe_trading import ReversalFactor
        f = ReversalFactor(window=3)
        scores = f.compute([100, 105, 108, 103, 98, 95, 92, 90, 88, 85], [1000, 1100, 1200, 1300, 1400, 1500, 1600, 1700, 1800, 1900])
        assert len(scores) > 0

    def test_volatility_factor(self):
        from Stratex.app.agents.real_vibe_trading import VolatilityFactor
        f = VolatilityFactor(window=5)
        scores = f.compute([100, 110, 95, 120, 85, 130, 75, 140, 65, 150], [1000, 1100, 1200, 1300, 1400, 1500, 1600, 1700, 1800, 1900])
        assert len(scores) > 0

    def test_value_factor(self):
        from Stratex.app.agents.real_vibe_trading import ValueFactor
        f = ValueFactor(window=5)
        scores = f.compute([10.0, 12.0, 8.0, 15.0, 7.0, 20.0, 5.0, 25.0, 4.0, 30.0], [1000, 1100, 1200, 1300, 1400, 1500, 1600, 1700, 1800, 1900])
        assert len(scores) > 0

    def test_liquidity_factor(self):
        from Stratex.app.agents.real_vibe_trading import LiquidityFactor
        f = LiquidityFactor(window=5)
        scores = f.compute([1000, 2000, 500, 3000, 400, 5000, 300, 6000, 200, 7000], [1000, 1100, 1200, 1300, 1400, 1500, 1600, 1700, 1800, 1900])
        assert len(scores) > 0

    def test_gtja_alpha_001(self):
        from Stratex.app.agents.real_vibe_trading import GTJAFactorLibrary
        lib = GTJAFactorLibrary()
        result = lib.alpha_001(
            close=[100, 101, 102, 103, 104, 105, 106, 107, 108, 109],
            open_=[100, 101, 102, 103, 104, 105, 106, 107, 108, 109],
            high=[101, 102, 103, 104, 105, 106, 107, 108, 109, 110],
            low=[99, 100, 101, 102, 103, 104, 105, 106, 107, 108],
        )
        assert len(result) > 0

    def test_gtja_alpha_002(self):
        from Stratex.app.agents.real_vibe_trading import GTJAFactorLibrary
        lib = GTJAFactorLibrary()
        result = lib.alpha_002(
            close=[100, 101, 102, 103, 104, 105, 106, 107, 108, 109],
            volumes=[1000, 1100, 1200, 1300, 1400, 1500, 1600, 1700, 1800, 1900],
        )
        assert len(result) > 0

    def test_gtja_alpha_003(self):
        from Stratex.app.agents.real_vibe_trading import GTJAFactorLibrary
        lib = GTJAFactorLibrary()
        result = lib.alpha_003(
            close=[100, 102, 101, 105, 108, 110, 107, 112, 115, 113],
        )
        assert len(result) > 0

    def test_gtja_alpha_010(self):
        from Stratex.app.agents.real_vibe_trading import GTJAFactorLibrary
        lib = GTJAFactorLibrary()
        result = lib.alpha_010(
            close=[100, 101, 102, 103, 104, 105, 106, 107, 108, 109],
        )
        assert len(result) > 0

    def test_gtja_alpha_191(self):
        from Stratex.app.agents.real_vibe_trading import GTJAFactorLibrary
        lib = GTJAFactorLibrary()
        result = lib.alpha_191(
            close=[100, 101, 102, 103, 104, 105, 106, 107, 108, 109, 110],
            high=[101, 102, 103, 104, 105, 106, 107, 108, 109, 110, 111],
            low=[99, 100, 101, 102, 103, 104, 105, 106, 107, 108, 109],
            volumes=[1000, 1100, 1200, 1300, 1400, 1500, 1600, 1700, 1800, 1900, 2000],
        )
        assert len(result) > 0

    def test_factor_zscore(self):
        from Stratex.app.agents.real_vibe_trading import FactorZScore
        zs = FactorZScore(window=10)
        scores = zs.compute([0.01, 0.02, 0.015, 0.018, 0.022, 0.019, 0.021, 0.017, 0.02, 0.023])
        assert len(scores) > 0

    def test_factor_correlation(self):
        from Stratex.app.agents.real_vibe_trading import FactorCorrelation
        fc = FactorCorrelation()
        corr = fc.correlation([0.01, 0.02, 0.015, 0.018, 0.022], [0.011, 0.019, 0.016, 0.017, 0.021])
        assert -1.0 <= corr <= 1.0

    def test_factor_correlation_matrix(self):
        from Stratex.app.agents.real_vibe_trading import FactorCorrelation
        fc = FactorCorrelation()
        matrix = fc.correlation_matrix([[0.01, 0.02, 0.03], [0.01, 0.02, 0.03]])
        assert len(matrix) == 2

    def test_factor_ic(self):
        from Stratex.app.agents.real_vibe_trading import FactorIC
        ic = FactorIC()
        result = ic.compute_ic(
            factor=[0.01, 0.02, 0.015, 0.018, 0.022, 0.019, 0.021, 0.017, 0.02, 0.023],
            returns=[0.005, 0.01, 0.008, 0.009, 0.012, 0.01, 0.011, 0.0085, 0.01, 0.013]
        )
        assert -1.0 <= result <= 1.0

    def test_factor_ic_mean(self):
        from Stratex.app.agents.real_vibe_trading import FactorIC
        ic = FactorIC()
        ics = ic.rolling_ic([0.01, 0.02, 0.015, 0.018, 0.022], [0.005, 0.01, 0.008, 0.009, 0.012], window=5)
        mean = ic.ic_mean(ics)
        assert isinstance(mean, float)

    def test_factor_rotation(self):
        from Stratex.app.agents.real_vibe_trading import FactorRotation
        fr = FactorRotation()
        allocation = fr.rotate(
            current_weights={"momentum": 0.4, "reversal": 0.3, "value": 0.3},
            factor_returns={"momentum": 0.01, "reversal": 0.005, "value": 0.008},
            momentum=0.1
        )
        assert isinstance(allocation, dict)

    def test_factor_portfolio(self):
        from Stratex.app.agents.real_vibe_trading import FactorPortfolio
        fp = FactorPortfolio()
        combined = fp.combined_factor({
            "momentum": [0.01, 0.02, 0.015, 0.018, 0.022],
            "reversal": [0.005, 0.01, 0.008, 0.009, 0.012],
        })
        assert len(combined) > 0

    def test_factor_portfolio_top_n(self):
        from Stratex.app.agents.real_vibe_trading import FactorPortfolio
        fp = FactorPortfolio()
        selected = fp.top_n_selection([0.02, 0.015, 0.01, 0.018, 0.022, 0.012], n=3)
        assert len(selected) == 3

    def test_risk_decomposition(self):
        from Stratex.app.agents.real_vibe_trading import RiskDecomposition
        rd = RiskDecomposition()
        risk = rd.total_risk(
            factor_weights={"momentum": 0.5, "value": 0.5},
            factor_covariances={"momentum": {"momentum": 0.04, "value": 0.01}, "value": {"momentum": 0.01, "value": 0.03}}
        )
        assert risk > 0

    def test_risk_contribution(self):
        from Stratex.app.agents.real_vibe_trading import RiskDecomposition
        rd = RiskDecomposition()
        contrib = rd.factor_contribution(
            factor_weights={"momentum": 0.5, "value": 0.5},
            factor_covariances={"momentum": {"momentum": 0.04, "value": 0.01}, "value": {"momentum": 0.01, "value": 0.03}}
        )
        assert isinstance(contrib, dict)

    def test_backtest_metrics(self):
        from Stratex.app.agents.real_vibe_trading import BacktestMetrics
        bm = BacktestMetrics()
        total_ret = bm.total_return(initial=10000, final=11000)
        assert total_ret > 0

    def test_backtest_metrics_win_rate(self):
        from Stratex.app.agents.real_vibe_trading import BacktestMetrics
        bm = BacktestMetrics()
        win_rate = bm.win_rate([True, False, True, True, False, True])
        assert 0 <= win_rate <= 1

    def test_backtest_metrics_max_dd(self):
        from Stratex.app.agents.real_vibe_trading import BacktestMetrics
        bm = BacktestMetrics()
        dd = bm.max_drawdown([100, 110, 105, 85, 90, 95])
        assert dd > 0


# =======================================================================
# 3. Stratex — FinceptTerminal (market analytics, technical indicators)
# =======================================================================

class TestFinceptTerminal:
    """Test Stratex real_fincept_terminal.py."""

    def test_candlestick_bullish_engulfing(self):
        from Stratex.app.agents.real_fincept_terminal import CandlestickPattern
        open_ = [100, 101, 102, 100, 98, 99]
        close = [101, 103, 100, 102, 99, 101]
        patterns = CandlestickPattern.bullish_engulfing(open_, close)
        assert len(patterns) == len(close)

    def test_candlestick_bearish_engulfing(self):
        from Stratex.app.agents.real_fincept_terminal import CandlestickPattern
        open_ = [100, 101, 102, 100, 98, 99]
        close = [101, 103, 100, 102, 99, 101]
        patterns = CandlestickPattern.bearish_engulfing(open_, close)
        assert len(patterns) == len(close)

    def test_candlestick_hammer(self):
        from Stratex.app.agents.real_fincept_terminal import CandlestickPattern
        low = [95, 94, 93, 92, 91, 90]
        high = [98, 97, 96, 95, 94, 93]
        close = [96, 95.5, 95, 94.5, 94, 93]
        patterns = CandlestickPattern.hammer(low, high, close)
        assert len(patterns) == len(close)

    def test_candlestick_doji(self):
        from Stratex.app.agents.real_fincept_terminal import CandlestickPattern
        open_ = [100, 100.01, 100, 100, 100]
        close = [100, 100.005, 100, 100, 100]
        patterns = CandlestickPattern.doji(open_, close)
        assert any(patterns)

    def test_sma(self):
        from Stratex.app.agents.real_fincept_terminal import TechnicalIndicators
        result = TechnicalIndicators.sma([10, 11, 12, 13, 14, 15], 3)
        assert math.isnan(result[0])
        assert abs(result[-1] - 14) < 0.01

    def test_ema(self):
        from Stratex.app.agents.real_fincept_terminal import TechnicalIndicators
        result = TechnicalIndicators.ema([10, 11, 12, 13, 14, 15], 3)
        assert result[0] == 10
        assert result[-1] > result[0]

    def test_rsi(self):
        from Stratex.app.agents.real_fincept_terminal import TechnicalIndicators
        prices = [100, 102, 101, 105, 108, 110, 107, 112, 115, 113, 118, 120, 117, 122, 125, 130, 128, 132]
        result = TechnicalIndicators.rsi(prices, window=14)
        assert len(result) > 0
        assert all(0 <= r <= 100 for r in result)

    def test_macd(self):
        from Stratex.app.agents.real_fincept_terminal import TechnicalIndicators
        prices = [100, 102, 101, 105, 108, 110, 107, 112, 115, 113, 118, 120, 122, 125, 128, 130, 128, 132, 130, 135]
        macd_line, signal_line, histogram = TechnicalIndicators.macd(prices)
        assert len(macd_line) == len(signal_line) == len(histogram)

    def test_bollinger_bands(self):
        from Stratex.app.agents.real_fincept_terminal import TechnicalIndicators
        prices = [100, 102, 101, 105, 108, 110, 107, 112, 115, 113, 118, 120, 117, 122, 125, 120, 125, 130, 128, 132]
        upper, mid, lower = TechnicalIndicators.bollinger_bands(prices, window=20)
        assert len(upper) == len(mid) == len(lower)
        assert upper[-1] >= mid[-1]
        assert lower[-1] <= mid[-1]

    def test_atr(self):
        from Stratex.app.agents.real_fincept_terminal import TechnicalIndicators
        high = [101 + i for i in range(20)]
        low = [100 + i for i in range(20)]
        close = [100 + i for i in range(20)]
        result = TechnicalIndicators.atr(high, low, close, window=14)
        assert len(result) > 0

    def test_stochastic(self):
        from Stratex.app.agents.real_fincept_terminal import TechnicalIndicators
        high = [101 + i for i in range(20)]
        low = [100 + i for i in range(20)]
        close = [100 + i for i in range(20)]
        k, d = TechnicalIndicators.stochastic(high, low, close, window=14)
        assert len(k) == len(d)

    def test_obv(self):
        from Stratex.app.agents.real_fincept_terminal import TechnicalIndicators
        result = TechnicalIndicators.obv([100, 101, 102, 101, 100, 101, 102, 103], [1000, 1100, 1200, 1100, 1000, 1100, 1200, 1300])
        assert result[0] == 0

    def test_vwap(self):
        from Stratex.app.agents.real_fincept_terminal import TechnicalIndicators
        result = TechnicalIndicators.vwap([101, 102, 103, 104, 105], [100, 101, 102, 103, 104], [100, 101, 102, 103, 104], [1000, 2000, 3000, 4000, 5000])
        assert len(result) == 5
        assert result[-1] > 0

    def test_ichimoku(self):
        from Stratex.app.agents.real_fincept_terminal import TechnicalIndicators
        high = [101 + i for i in range(30)]
        low = [100 + i for i in range(30)]
        result = TechnicalIndicators.ichimoku(high, low)
        assert "conversion" in result
        assert "span_a" in result

    def test_order_flow_imbalance(self):
        from Stratex.app.agents.real_fincept_terminal import OrderFlowAnalysis
        bids = [(100, 10), (99.5, 20), (99, 30)]
        asks = [(100.5, 10), (101, 15), (101.5, 20)]
        imbalance = OrderFlowAnalysis.bid_ask_imbalance(bids, asks)
        assert -1.0 <= imbalance <= 1.0

    def test_microprice(self):
        from Stratex.app.agents.real_fincept_terminal import OrderFlowAnalysis
        bids = [(100, 10), (99.5, 20)]
        asks = [(100.5, 10), (101, 15)]
        mp = OrderFlowAnalysis.microprice(bids, asks)
        assert 99.5 < mp < 101

    def test_correlation(self):
        from Stratex.app.agents.real_fincept_terminal import CrossAssetAnalysis
        corr = CrossAssetAnalysis.correlation([1, 2, 3, 4, 5], [2, 4, 6, 8, 10])
        assert abs(corr - 1.0) < 0.01

    def test_beta(self):
        from Stratex.app.agents.real_fincept_terminal import CrossAssetAnalysis
        beta = CrossAssetAnalysis.beta([0.01, 0.02, 0.015, 0.018], [0.005, 0.01, 0.008, 0.009])
        assert beta > 0

    def test_sharpe_ratio(self):
        from Stratex.app.agents.real_fincept_terminal import CrossAssetAnalysis
        sharpe = CrossAssetAnalysis.sharpe_ratio([0.01, 0.02, 0.015, 0.018, 0.022, 0.019, 0.021, 0.017])
        assert sharpe > 0

    def test_sortino_ratio(self):
        from Stratex.app.agents.real_fincept_terminal import CrossAssetAnalysis
        returns = [0.01, 0.02, -0.005, 0.015, 0.018, -0.008, 0.022, 0.019]
        sortino = CrossAssetAnalysis.sortino_ratio(returns)
        assert isinstance(sortino, float)

    def test_portfolio_volatility(self):
        from Stratex.app.agents.real_fincept_terminal import PortfolioAnalytics
        vol = PortfolioAnalytics.portfolio_volatility([0.4, 0.3, 0.3], [[0.04, 0.01, 0.01], [0.01, 0.03, 0.01], [0.01, 0.01, 0.02]])
        assert vol > 0

    def test_max_drawdown(self):
        from Stratex.app.agents.real_fincept_terminal import PortfolioAnalytics
        dd = PortfolioAnalytics.max_drawdown([100, 110, 105, 85, 90, 95])
        assert dd > 0

    def test_cagr(self):
        from Stratex.app.agents.real_fincept_terminal import PortfolioAnalytics
        cagr = PortfolioAnalytics.cagr(100, 150, 5)
        assert cagr > 0

    def test_var(self):
        from Stratex.app.agents.real_fincept_terminal import PortfolioAnalytics
        var = PortfolioAnalytics.value_at_risk([-0.02, -0.01, 0.01, 0.02, -0.005], confidence=0.9)
        assert var <= 0

    def test_market_regime(self):
        from Stratex.app.agents.real_fincept_terminal import MarketRegimeDetector
        prices = [100 + i * 0.5 for i in range(60)]
        regime = MarketRegimeDetector.detect_regime(prices, window=50)
        assert regime in ["bull_calm", "bull_volatile", "bear_calm", "bear_volatile", "neutral"]

    def test_current_ratio(self):
        from Stratex.app.agents.real_fincept_terminal import FinancialStatementAnalysis
        cr = FinancialStatementAnalysis.current_ratio(150000, 100000)
        assert abs(cr - 1.5) < 0.01

    def test_debt_to_equity(self):
        from Stratex.app.agents.real_fincept_terminal import FinancialStatementAnalysis
        de = FinancialStatementAnalysis.debt_to_equity(50000, 100000)
        assert abs(de - 0.5) < 0.01

    def test_roe(self):
        from Stratex.app.agents.real_fincept_terminal import FinancialStatementAnalysis
        roe = FinancialStatementAnalysis.return_on_equity(20000, 100000)
        assert abs(roe - 0.2) < 0.01

    def test_pe_ratio(self):
        from Stratex.app.agents.real_fincept_terminal import FinancialStatementAnalysis
        pe = FinancialStatementAnalysis.price_to_earnings(150, 5)
        assert abs(pe - 30) < 0.01

    def test_economic_calendar_summary(self):
        from Stratex.app.agents.real_fincept_terminal import EconomicCalendar
        summary = EconomicCalendar.calendar_summary([
            {"type": "gdp", "weight": 0.8},
            {"type": "inflation", "weight": 0.85},
            {"type": "employment", "weight": 0.6},
        ])
        assert summary["total_events"] == 3
        assert summary["high_impact"] == 2


# =======================================================================
# 4. VyralX — claude-ads (12-platform paid media)
# =======================================================================

class TestClaudeAds:
    """Test VyralX real_claude_ads.py."""

    def test_platform_adapter_objectives(self):
        from VyralX.app.services.real_claude_ads import PlatformAdapter
        adapter = PlatformAdapter(platform="google_ads")
        assert "search" in adapter.supported_objectives

    def test_platform_adapter_formats(self):
        from VyralX.app.services.real_claude_ads import PlatformAdapter
        adapter = PlatformAdapter(platform="meta_ads")
        assert "video" in adapter.supported_formats

    def test_platform_adapter_can_target(self):
        from VyralX.app.services.real_claude_ads import PlatformAdapter
        adapter = PlatformAdapter(platform="youtube_ads")
        assert adapter.can_target("awareness")
        assert not adapter.can_target("search")

    def test_ad_account(self):
        from VyralX.app.services.real_claude_ads import AdAccount
        account = AdAccount(platform="google_ads", account_id="acc1", name="Test")
        assert account.is_active
        assert account.remaining_cap == 100000.0
        account.record_spend(5000)
        assert account.remaining_cap == 95000.0

    def test_campaign_metrics(self):
        from VyralX.app.services.real_claude_ads import Campaign
        c = Campaign(platform="meta_ads", account_id="acc1", campaign_id="c1", name="Test")
        for _ in range(100):
            c.record_impression()
        for _ in range(5):
            c.record_click()
        for _ in range(2):
            c.record_conversion()
        c.record_spend(100)
        assert abs(c.ctr - 0.05) < 0.001
        assert c.cpa == 50.0

    def test_ad_creative(self):
        from VyralX.app.services.real_claude_ads import AdCreative
        creative = AdCreative(creative_id="cr1", platform="google_ads", name="Test Ad")
        assert not creative.is_approved
        creative.approve()
        assert creative.is_approved

    def test_cta_label(self):
        from VyralX.app.services.real_claude_ads import AdCreative
        creative = AdCreative(creative_id="cr2", platform="google_ads", name="Test", cta="buy_now")
        assert creative.cta_label == "Buy Now"

    def test_capability_gate(self):
        from VyralX.app.services.real_claude_ads import CapabilityGate
        auth = CapabilityGate.authorize_action(["budget_modification"], "budget_change")
        assert auth["authorized"]
        auth2 = CapabilityGate.authorize_action([], "budget_change")
        assert not auth2["authorized"]

    def test_ad_audit(self):
        from VyralX.app.services.real_claude_ads import AdAudit
        audit = AdAudit(audit_id="a1", platform="google_ads", account_id="acc1", audited_at="")
        audit.add_finding("critical", "budget", "Exceeded")
        summary = audit.summary()
        assert summary["critical"] == 1
        assert summary["total_findings"] == 1

    def test_ad_report(self):
        from VyralX.app.services.real_claude_ads import AdReport
        report = AdReport(report_id="r1", platform="meta_ads", period_start="2024-01", period_end="2024-01-31")
        report.add_metric("spend", 1000)
        report.add_metric("clicks", 50)
        json_str = report.to_json()
        assert "spend" in json_str

    def test_multi_platform_manager(self):
        from VyralX.app.services.real_claude_ads import MultiPlatformAdManager, AdAccount, Campaign
        manager = MultiPlatformAdManager()
        manager.register_account(AdAccount(platform="google_ads", account_id="acc1", name="Test"))
        manager.register_account(AdAccount(platform="meta_ads", account_id="acc2", name="Test2"))
        manager.create_campaign(Campaign(platform="google_ads", account_id="acc1", campaign_id="c1", name="Campaign"))
        assert manager.account_count == 2
        assert manager.platform_count == 2

    def test_cross_platform_performance(self):
        from VyralX.app.services.real_claude_ads import CrossPlatformAnalyzer, Campaign
        campaigns = [
            Campaign(platform="google_ads", account_id="a1", campaign_id="c1", name="C1"),
            Campaign(platform="meta_ads", account_id="a2", campaign_id="c2", name="C2"),
        ]
        campaigns[0].record_spend(100)
        campaigns[0].record_impression()
        campaigns[1].record_spend(200)
        campaigns[1].record_impression()
        perf = CrossPlatformAnalyzer.platform_performance(campaigns)
        assert "google_ads" in perf
        assert "meta_ads" in perf


# =======================================================================
# 5. VyralX — toprank (SEO/GEO ranking, analytics)
# =======================================================================

class TestTopRank:
    """Test VyralX real_toprank.py."""

    def test_keyword_density(self):
        from VyralX.app.services.real_toprank import SEORanker
        text = "SEO is important. SEO helps ranking. SEO is crucial for visibility."
        density = SEORanker.keyword_density(text, ["SEO"])
        assert density["SEO"] > 0

    def test_word_count(self):
        from VyralX.app.services.real_toprank import SEORanker
        assert SEORanker.word_count("This is a test sentence.") == 5

    def test_readability(self):
        from VyralX.app.services.real_toprank import SEORanker
        score = SEORanker.readability_score("The cat sat on the mat. The dog ran in the park.")
        assert 0 <= score <= 100

    def test_heading_structure(self):
        from VyralX.app.services.real_toprank import SEORanker
        html = "<h1>Title</h1><h2>Subtitle</h2><h3>Subsub</h3><h1>Another</h1>"
        structure = SEORanker.heading_structure(html)
        assert structure.get(1, 0) == 2
        assert structure.get(2, 0) == 1

    def test_internal_links(self):
        from VyralX.app.services.real_toprank import SEORanker
        html = '<a href="/about">About</a><a href="https://external.com">Ext</a><a href="/contact">Contact</a>'
        links = SEORanker.internal_link_structure(html)
        assert links["internal_count"] == 2
        assert links["external_count"] == 1

    def test_content_score(self):
        from VyralX.app.services.real_toprank import SEORanker
        text = "Machine learning is a subset of artificial intelligence. Machine learning enables computers to learn from data."
        score = SEORanker.content_score(text, ["machine learning", "artificial intelligence"])
        assert score > 0

    def test_url_score(self):
        from VyralX.app.services.real_toprank import SEORanker
        score = SEORanker.url_score("https://example.com/seo-tips")
        assert score > 0

    def test_schema_markup(self):
        from VyralX.app.services.real_toprank import SEORanker
        html = '<script type="application/ld+json">{"@type": "Article"}</script>'
        score = SEORanker.schema_markup_score(html)
        assert score > 0

    def test_ai_visibility(self):
        from VyralX.app.services.real_toprank import GEORanker
        text = "AI: Artificial intelligence transforms industries. AI: Machine learning enables automation."
        score = GEORanker.ai_visibility_score(text)
        assert score > 0

    def test_llm_friendliness(self):
        from VyralX.app.services.real_toprank import GEORanker
        result = GEORanker.llm_friendliness("Short answer. Another short answer. Third short answer.")
        assert "score" in result

    def test_analytics_tracker(self):
        from VyralX.app.services.real_toprank import AnalyticsTracker
        tracker = AnalyticsTracker()
        tracker.track_event("click", "user1")
        tracker.track_event("view", "user2")
        tracker.track_event("click", "user1")
        assert tracker.event_count == 3
        assert tracker.unique_users() == 2

    def test_conversion_rate(self):
        from VyralX.app.services.real_toprank import AnalyticsTracker
        tracker = AnalyticsTracker()
        rate = tracker.conversion_rate(100, 5)
        assert abs(rate - 0.05) < 0.001

    def test_funnel_analysis(self):
        from VyralX.app.services.real_toprank import AnalyticsTracker
        tracker = AnalyticsTracker()
        stages = {"visits": 1000, "signups": 200, "purchases": 50}
        rates = tracker.funnel_analysis(stages)
        assert rates["signups"] == 0.2

    def test_safety_rules(self):
        from VyralX.app.services.real_toprank import SafetyRuleEngine
        engine = SafetyRuleEngine()
        for rule in SafetyRuleEngine.default_rules():
            engine.add_rule(rule)
        assert not engine.is_safe("This product is guaranteed to work with no risk.")
        assert engine.is_safe("This is a normal sentence.")

    def test_risk_score(self):
        from VyralX.app.services.real_toprank import SafetyRuleEngine
        engine = SafetyRuleEngine()
        for rule in SafetyRuleEngine.default_rules():
            engine.add_rule(rule)
        score = engine.risk_score("Buy now, 100% sure, no obligation.")
        assert score > 0

    def test_mcp_surface(self):
        from VyralX.app.services.real_toprank import MCPSurface
        surface = MCPSurface.create_surface("marketing", "Marketing tools")
        surface.add_tool("analyze", "Analyze content")
        manifest = surface.to_manifest()
        assert manifest["name"] == "marketing"
        assert surface.tool_count == 1

    def test_marketing_skill(self):
        from VyralX.app.services.real_toprank import AgentMarketingSkill
        skill = AgentMarketingSkill.create_skill("seo_optimizer", "Optimize SEO")
        skill.add_input("url", "Target URL")
        skill.add_output("score", "SEO score")
        skill.add_step("Analyze")
        assert skill.input_count == 1
        assert skill.step_count == 1


# =======================================================================
# 6. VyralX — Open-Higgsfield-AI (generative studio)
# =======================================================================

class TestOpenHiggsfield:
    """Test VyralX real_open_higgsfield.py."""

    def test_generation_request(self):
        from VyralX.app.services.real_open_higgsfield import GenerationRequest
        req = GenerationRequest(request_id="g1", model="Flux.1-dev", prompt="test")
        assert req.resolution == "1024x1024"
        assert req.aspect_ratio == "1:1"

    def test_request_video_detection(self):
        from VyralX.app.services.real_open_higgsfield import GenerationRequest
        req = GenerationRequest(request_id="g2", model="Sora-2", prompt="test")
        assert req.is_video

    def test_model_router_image(self):
        from VyralX.app.services.real_open_higgsfield import ModelRouter
        router = ModelRouter()
        models = router.get_models_by_type("image")
        assert len(models) > 0

    def test_model_router_video(self):
        from VyralX.app.services.real_open_higgsfield import ModelRouter
        router = ModelRouter()
        models = router.get_models_by_type("video")
        assert len(models) > 0

    def test_model_recommend(self):
        from VyralX.app.services.real_open_higgsfield import ModelRouter
        model = ModelRouter.recommend_model("portrait of a person", "image")
        assert model == "Midjourney-niji-6"

    def test_model_capabilities(self):
        from VyralX.app.services.real_open_higgsfield import ModelRouter
        caps = ModelRouter.model_capabilities("Flux.1-dev")
        assert caps["type"] == "image"

    def test_prompt_enhancer(self):
        from VyralX.app.services.real_open_higgsfield import PromptEnhancer
        enhanced = PromptEnhancer.enhance("a cat", "photographic")
        assert "photorealistic" in enhanced

    def test_prompt_negative(self):
        from VyralX.app.services.real_open_higgsfield import PromptEnhancer
        negative = PromptEnhancer.negative_prompt("photographic")
        assert "blurry" in negative

    def test_generation_result(self):
        from VyralX.app.services.real_open_higgsfield import GenerationResult
        result = GenerationResult(
            request_id="r1", model="Flux.1-dev", prompt="test",
            output_path="/outputs/test.png", width=1024, height=1024,
            seed=42, elapsed=5.0,
        )
        assert result.megapixels > 1.0

    def test_local_inference_memory(self):
        from VyralX.app.services.real_open_higgsfield import LocalInferenceEngine
        mem = LocalInferenceEngine.memory_requirement_mb("Flux.1-dev", 1024)
        assert mem > 0

    def test_local_inference_gpu(self):
        from VyralX.app.services.real_open_higgsfield import LocalInferenceEngine
        gpu = LocalInferenceEngine.gpu_requirement("Flux.1-dev")
        assert gpu == "A100 40GB"

    def test_generation_pipeline(self):
        from VyralX.app.services.real_open_higgsfield import GenerationPipeline, GenerationResult
        result = GenerationResult(
            request_id="r1", model="Flux.1-dev", prompt="test",
            output_path="/outputs/test.png", width=1024, height=1024,
            seed=42, elapsed=5.0,
        )
        stats = GenerationPipeline.pipeline_stats([result])
        assert stats["total"] == 1

    def test_multi_model_studio(self):
        from VyralX.app.services.real_open_higgsfield import MultiModelStudio, GenerationRequest
        studio = MultiModelStudio()
        req = GenerationRequest(request_id="g1", model="Flux.1-dev", prompt="test")
        result = studio.generate(req)
        assert result.model in studio.router.available_models
        assert studio.total_generations == 1

    def test_studio_capabilities(self):
        from VyralX.app.services.real_open_higgsfield import MultiModelStudio
        studio = MultiModelStudio()
        caps = studio.studio_capabilities()
        assert caps["total_models"] > 10


# =======================================================================
# 7. VyralX — hyperframes (HTML-to-video rendering)
# =======================================================================

class TestHyperframes:
    """Test VyralX real_hyperframes.py."""

    def test_html_scene(self):
        from VyralX.app.services.real_hyperframes import HTMLScene
        scene = HTMLScene.create_scene("<div>Hello</div>", title="Test", duration=5.0)
        assert scene.aspect_ratio == "16:9"
        assert scene.text_content == "Hello"

    def test_scene_frame_count(self):
        from VyralX.app.services.real_hyperframes import HTMLScene
        scene = HTMLScene.create_scene("<div>Hello</div>", duration=5.0)
        assert scene.to_frame_count(30) == 150

    def test_frame_compositor(self):
        from VyralX.app.services.real_hyperframes import HTMLScene, FrameCompositor
        scene = HTMLScene.create_scene("<div>Hello</div>", duration=3.0)
        frames = FrameCompositor.frames_for_scene(scene, fps=30)
        assert frames == 90

    def test_frame_compositor_transitions(self):
        from VyralX.app.services.real_hyperframes import FrameCompositor
        frames = FrameCompositor.transition_frames("fade", fps=30)
        assert frames == 15

    def test_scene_transition_fade(self):
        from VyralX.app.services.real_hyperframes import SceneTransition
        transition = SceneTransition.fade(0.5)
        css = transition.render_css()
        assert "opacity" in css

    def test_video_script(self):
        from VyralX.app.services.real_hyperframes import VideoScript
        script = VideoScript.from_text("This is a test. This is another test. Third test.", title="Test Video")
        assert script.scene_count() == 3
        assert script.total_duration() == 9.0

    def test_render_pipeline(self):
        from VyralX.app.services.real_hyperframes import RenderPipeline, VideoScript
        script = VideoScript.from_text("Test sentence one. Test sentence two.", title="T")
        estimate = RenderPipeline.estimate_render_time(script)
        assert estimate > 0

    def test_render_encoding_settings(self):
        from VyralX.app.services.real_hyperframes import RenderPipeline
        settings = RenderPipeline.encoding_settings((1920, 1080), 30, 8.0)
        assert settings["width"] == 1920
        assert settings["fps"] == 30

    def test_aspect_ratio_handler(self):
        from VyralX.app.services.real_hyperframes import AspectRatioHandler
        res = AspectRatioHandler.resolution_for("16:9")
        assert res == (1920, 1080)

    def test_aspect_ratio_crop(self):
        from VyralX.app.services.real_hyperframes import AspectRatioHandler
        crop = AspectRatioHandler.crop_region(1920, 1080, "1:1")
        assert crop[2] > 0
        assert crop[3] > 0

    def test_hyperframes_manager(self):
        from VyralX.app.services.real_hyperframes import HyperframesManager
        manager = HyperframesManager()
        script = manager.create_script("Test", "This is a test. Second sentence here.")
        result = manager.render_script("Test")
        assert result["scenes"] == 2
        assert result["total_duration"] > 0

    def test_hyperframes_manifest(self):
        from VyralX.app.services.real_hyperframes import HyperframesManager
        manager = HyperframesManager()
        manager.create_script("Test", "A sentence. Another sentence.")
        manifest = manager.export_manifest("Test")
        assert manifest["scene_count"] == 2

    def test_hyperframes_optimize(self):
        from VyralX.app.services.real_hyperframes import HyperframesManager
        manager = HyperframesManager()
        manager.create_script("Test", "One sentence. Two sentences.")
        pacing = manager.optimize_scenes("Test")
        assert "avg_scene_duration" in pacing


# =======================================================================
# 8. Cortex — agentic-inbox (AI agent email coordination)
# =======================================================================

class TestAgenticInbox:
    """Test Cortex real_agentic_inbox.py."""

    def test_email_message(self):
        from Cortex.apps.api.src.cortex_api.real_agentic_inbox import EmailMessage
        msg = EmailMessage.create_message("alice@example.com", "bob@example.com", "Meeting tomorrow", "Let's meet tomorrow at 10am.")
        assert msg.message_id.startswith("msg-")
        assert msg.word_count > 0

    def test_email_priority(self):
        from Cortex.apps.api.src.cortex_api.real_agentic_inbox import EmailMessage
        msg = EmailMessage.create_message("alice@example.com", "bob@example.com", "URGENT: Deadline approaching", "Please respond asap. This is critical.")
        assert msg.priority_score > 0.4

    def test_email_mark_read(self):
        from Cortex.apps.api.src.cortex_api.real_agentic_inbox import EmailMessage
        msg = EmailMessage.create_message("alice@example.com", "bob@example.com", "Test", "Body")
        assert not msg.is_read
        msg.mark_read()
        assert msg.is_read

    def test_email_thread(self):
        from Cortex.apps.api.src.cortex_api.real_agentic_inbox import EmailThread
        thread = EmailThread.create_thread("Test Subject")
        assert thread.message_count == 0

    def test_ai_classify_meeting(self):
        from Cortex.apps.api.src.cortex_api.real_agentic_inbox import EmailMessage, AIEmailAgent
        msg = EmailMessage.create_message("a@b.com", "c@d.com", "Meeting tomorrow", "Let's schedule a meeting.")
        assert AIEmailAgent.classify_email(msg) == "meeting"

    def test_ai_classify_invoice(self):
        from Cortex.apps.api.src.cortex_api.real_agentic_inbox import EmailMessage, AIEmailAgent
        msg = EmailMessage.create_message("a@b.com", "c@d.com", "Invoice #12345", "Please find the attached invoice for payment.")
        assert AIEmailAgent.classify_email(msg) == "finance"

    def test_ai_classify_support(self):
        from Cortex.apps.api.src.cortex_api.real_agentic_inbox import EmailMessage, AIEmailAgent
        msg = EmailMessage.create_message("a@b.com", "c@d.com", "Support issue with product", "I need help with a broken feature.")
        assert AIEmailAgent.classify_email(msg) == "support"

    def test_ai_extract_action_items(self):
        from Cortex.apps.api.src.cortex_api.real_agentic_inbox import AIEmailAgent
        items = AIEmailAgent.extract_action_items("Please review the document. You must send the report by Friday.")
        assert len(items) > 0

    def test_ai_summarize(self):
        from Cortex.apps.api.src.cortex_api.real_agentic_inbox import EmailMessage, AIEmailAgent
        msg = EmailMessage.create_message("a@b.com", "c@d.com", "Test", "This is a long email. It has multiple sentences. The summary should be short.")
        summary = AIEmailAgent.summarize_email(msg)
        assert len(summary) > 0

    def test_ai_sentiment(self):
        from Cortex.apps.api.src.cortex_api.real_agentic_inbox import AIEmailAgent
        assert AIEmailAgent.detect_sentiment("This is great and wonderful!") == "positive"
        assert AIEmailAgent.detect_sentiment("This is terrible and awful.") == "negative"
        assert AIEmailAgent.detect_sentiment("The meeting is at 3pm.") == "neutral"

    def test_ai_spam_detection(self):
        from Cortex.apps.api.src.cortex_api.real_agentic_inbox import EmailMessage, AIEmailAgent
        msg = EmailMessage.create_message("a@b.com", "c@d.com", "WINNER: You won a prize!", "Click here now! Limited time offer! No obligation! Guaranteed!")
        assert AIEmailAgent.detect_spam(msg)

    def test_ai_auto_label(self):
        from Cortex.apps.api.src.cortex_api.real_agentic_inbox import EmailMessage, AIEmailAgent
        msg = EmailMessage.create_message("a@b.com", "c@d.com", "Meeting tomorrow URGENT", "Let's meet. This is critical and important.")
        labels = AIEmailAgent.auto_label(msg)
        assert "meeting" in labels

    def test_inbox_state(self):
        from Cortex.apps.api.src.cortex_api.real_agentic_inbox import InboxState, EmailMessage
        inbox = InboxState()
        msg = EmailMessage.create_message("a@b.com", "c@d.com", "Test", "Body")
        msg.add_label("test")
        inbox.add_message(msg)
        assert inbox.message_count == 1
        assert inbox.unread_count == 1
        assert inbox.thread_count == 1

    def test_inbox_search(self):
        from Cortex.apps.api.src.cortex_api.real_agentic_inbox import InboxState, EmailMessage
        inbox = InboxState()
        msg = EmailMessage.create_message("a@b.com", "c@d.com", "Important meeting", "Let's discuss the project.")
        inbox.add_message(msg)
        results = inbox.search("meeting")
        assert len(results) == 1

    def test_async_worker_process(self):
        from Cortex.apps.api.src.cortex_api.real_agentic_inbox import InboxState, EmailMessage, AIEmailAgent, AsyncEmailWorker
        inbox = InboxState()
        for i in range(3):
            msg = EmailMessage.create_message(f"user{i}@b.com", "me@b.com", f"Meeting {i}", "Let's meet.")
            inbox.add_message(msg)
        result = AsyncEmailWorker.process_inbox(inbox, AIEmailAgent())
        assert result["processed"] == 3
        assert result["classified"] == 3

    def test_async_worker_triage(self):
        from Cortex.apps.api.src.cortex_api.real_agentic_inbox import InboxState, EmailMessage, AsyncEmailWorker
        inbox = InboxState()
        inbox.add_message(EmailMessage.create_message("a@b.com", "c@d.com", "Meeting tomorrow", "Meet."))
        inbox.add_message(EmailMessage.create_message("d@b.com", "c@d.com", "Invoice payment", "Pay."))
        triage = AsyncEmailWorker.triage_messages(inbox)
        assert "meeting" in triage
        assert "finance" in triage

    def test_async_worker_digest(self):
        from Cortex.apps.api.src.cortex_api.real_agentic_inbox import InboxState, EmailMessage, AsyncEmailWorker
        inbox = InboxState()
        for i in range(5):
            inbox.add_message(EmailMessage.create_message(f"user{i}@b.com", "me@b.com", f"Message {i}", "Body text."))
        digest = AsyncEmailWorker.generate_digest(inbox)
        assert digest["unread_count"] == 5
        assert len(digest["top_senders"]) > 0

    def test_agent_coordinator_route(self):
        from Cortex.apps.api.src.cortex_api.real_agentic_inbox import EmailMessage, AgentCoordinator
        msg = EmailMessage.create_message("a@b.com", "c@d.com", "Support issue", "Help me.")
        assert AgentCoordinator.route_message(msg) == "support_agent"

    def test_agent_coordination_plan(self):
        from Cortex.apps.api.src.cortex_api.real_agentic_inbox import EmailMessage, AgentCoordinator
        msgs = [
            EmailMessage.create_message("a@b.com", "c@d.com", "Meeting tomorrow", "Meet."),
            EmailMessage.create_message("d@b.com", "c@d.com", "Invoice", "Pay."),
            EmailMessage.create_message("e@b.com", "c@d.com", "Support", "Help."),
        ]
        plan = AgentCoordinator.coordination_plan(msgs)
        assert len(plan) == 3


# =======================================================================
# 9. Memora — context-mode (context window optimization)
# =======================================================================

class TestContextMode:
    """Test Memora real_context_mode.py."""

    def test_token_estimate(self):
        from Memora.core.memory.real_context_mode import ContextCompressor
        tokens = ContextCompressor.token_estimate("This is a test string.")
        assert tokens > 0

    def test_compress_text(self):
        from Memora.core.memory.real_context_mode import ContextCompressor
        text = "This is a test. " * 500
        compressed = ContextCompressor.compress_text(text, max_tokens=100)
        assert ContextCompressor.token_estimate(compressed) <= 100

    def test_summarize_conversation(self):
        from Memora.core.memory.real_context_mode import ContextCompressor
        msgs = [{"role": "user", "content": "Hello"}, {"role": "assistant", "content": "Hi there!"}]
        summary = ContextCompressor.summarize_conversation(msgs)
        assert "user" in summary

    def test_extract_key_points(self):
        from Memora.core.memory.real_context_mode import ContextCompressor
        text = "This is an important point. Another key detail here. More information follows."
        points = ContextCompressor.extract_key_points(text)
        assert len(points) > 0

    def test_deduplicate(self):
        from Memora.core.memory.real_context_mode import ContextCompressor
        text = "line one\nline two\nline one\nline three\nline two"
        result = ContextCompressor.deduplicate(text)
        lines = result.split("\n")
        assert len(lines) == 3

    def test_context_reduction(self):
        from Memora.core.memory.real_context_mode import ContextCompressor
        original = "word " * 1000
        compressed = ContextCompressor.compress_text(original, max_tokens=100)
        reduction = ContextCompressor.context_reduction_percentage(original, compressed)
        assert reduction > 0.5

    def test_sandbox_output(self):
        from Memora.core.memory.real_context_mode import ToolOutputSandbox
        output = "\n".join(f"line {i}" for i in range(100))
        sandboxed = ToolOutputSandbox.sandbox_output(output, max_lines=20)
        assert "omitted" in sandboxed

    def test_extract_errors(self):
        from Memora.core.memory.real_context_mode import ToolOutputSandbox
        output = "Error: file not found\nFAILED: test_case_1\nTraceback: AttributeError"
        errors = ToolOutputSandbox.extract_errors(output)
        assert len(errors) > 0

    def test_sandbox_by_type_test(self):
        from Memora.core.memory.real_context_mode import ToolOutputSandbox
        output = "PASSED\nFAILED: test_x\nError: assertion failed\nFAILED: test_y"
        result = ToolOutputSandbox.sandbox_by_type(output, "test")
        assert "Errors" in result

    def test_sandbox_by_type_git(self):
        from Memora.core.memory.real_context_mode import ToolOutputSandbox
        output = "\n".join(f"change {i}" for i in range(100))
        result = ToolOutputSandbox.sandbox_by_type(output, "git")
        assert "omitted" in result

    def test_session_memory(self):
        from Memora.core.memory.real_context_mode import SessionMemory
        session = SessionMemory.create_session("test")
        session.store("key1", "value1", "general")
        session.store("key2", "value2", "code")
        assert session.entry_count == 2
        assert session.retrieve("key1") == "value1"

    def test_session_search(self):
        from Memora.core.memory.real_context_mode import SessionMemory
        session = SessionMemory.create_session("test")
        session.store("python", "Python is a language", "code")
        session.store("java", "Java is a language", "code")
        results = session.search("python")
        assert len(results) == 1

    def test_session_summary(self):
        from Memora.core.memory.real_context_mode import SessionMemory
        session = SessionMemory.create_session("test")
        session.store("k1", "v1", "general")
        session.store("k2", "v2", "code")
        summary = session.session_summary()
        assert "general" in summary
        assert "code" in summary

    def test_context_router(self):
        from Memora.core.memory.real_context_mode import ContextRouter
        limit = ContextRouter.platform_context_limit("claude_code")
        assert limit == 200000

    def test_context_router_route(self):
        from Memora.core.memory.real_context_mode import ContextRouter, ContextCompressor
        content = "word " * 50000
        routed = ContextRouter.route_context(content, "copilot")
        assert ContextCompressor.token_estimate(routed) < ContextCompressor.token_estimate(content)

    def test_context_router_hooks(self):
        from Memora.core.memory.real_context_mode import ContextRouter
        assert ContextRouter.platform_supports_hooks("claude_code")
        assert not ContextRouter.platform_supports_hooks("chatgpt")

    def test_routing_decision(self):
        from Memora.core.memory.real_context_mode import ContextRouter
        decision = ContextRouter.routing_decision("short text", "cursor")
        assert "utilization" in decision
        assert "needs_compression" in decision

    def test_mcp_hook_pre_tool(self):
        from Memora.core.memory.real_context_mode import MCPHookEngine
        output = "\n".join(f"line {i}" for i in range(100))
        sandboxed = MCPHookEngine.pre_tool_hook("git_diff", output)
        assert "omitted" in sandboxed

    def test_mcp_hook_post_tool(self):
        from Memora.core.memory.real_context_mode import MCPHookEngine
        output = "\n".join(f"line {i}" for i in range(100))
        result = MCPHookEngine.post_tool_hook("git_diff", output)
        assert result["savings_percentage"] > 0

    def test_context_mode_manager(self):
        from Memora.core.memory.real_context_mode import ContextModeManager
        manager = ContextModeManager()
        result = manager.optimize_context("This is a test. " * 100, "claude_code")
        assert "original_tokens" in result
        assert "reduction_percentage" in result

    def test_context_mode_process_tool(self):
        from Memora.core.memory.real_context_mode import ContextModeManager
        manager = ContextModeManager()
        result = manager.process_tool_output("git_diff", "\n".join(f"l{i}" for i in range(100)))
        assert "sandboxed_output" in result
        assert result["savings"] > 0

    def test_context_mode_session(self):
        from Memora.core.memory.real_context_mode import ContextModeManager
        manager = ContextModeManager()
        manager.persist_session_memory("test_key", "test_value", "code")
        assert manager.retrieve_session_memory("test_key") == "test_value"

    def test_context_mode_sandbox_all(self):
        from Memora.core.memory.real_context_mode import ContextModeManager
        manager = ContextModeManager()
        result = manager.sandbox_all_outputs({
            "git_diff": "\n".join(f"l{i}" for i in range(100)),
            "pytest": "PASSED\nFAILED: test_x\nError: bad",
        })
        assert "savings_percentage" in result


# =======================================================================
# 10. Forge — camofox-browser (stealth headless browser)
# =======================================================================

class TestCamofoxBrowser:
    """Test Forge real_camofox_browser.py."""

    def test_fingerprint_generate(self):
        from Forge.app.services.real_camofox_browser import BrowserFingerprint
        fp = BrowserFingerprint.generate()
        assert fp.user_agent.startswith("Mozilla")
        assert fp.screen_width > 0
        assert fp.hardware_concurrency > 0

    def test_fingerprint_hash(self):
        from Forge.app.services.real_camofox_browser import BrowserFingerprint
        fp = BrowserFingerprint.generate()
        assert len(fp.fingerprint_hash()) == 16

    def test_fingerprint_to_dict(self):
        from Forge.app.services.real_camofox_browser import BrowserFingerprint
        fp = BrowserFingerprint.generate()
        d = fp.to_dict()
        assert "user_agent" in d
        assert "platform" in d

    def test_stealth_webdriver_detection(self):
        from Forge.app.services.real_camofox_browser import StealthDetector
        assert StealthDetector.webdriver_detection({"webdriver": True})
        assert not StealthDetector.webdriver_detection({"webdriver": False})

    def test_stealth_headless_detection(self):
        from Forge.app.services.real_camofox_browser import StealthDetector
        assert StealthDetector.headless_detection({"userAgent": "HeadlessChrome", "plugins": [], "languages": []})

    def test_stealth_detect_all(self):
        from Forge.app.services.real_camofox_browser import StealthDetector
        results = StealthDetector.detect_all(
            {"webdriver": False, "userAgent": "Mozilla", "plugins": [1], "languages": ["en"]},
            {"notifications": "prompt"},
            "abc123def456",
        )
        assert "risk_level" in results
        assert results["risk_level"] == "low"

    def test_stealth_bypass_suggestions(self):
        from Forge.app.services.real_camofox_browser import StealthDetector
        results = StealthDetector.detect_all(
            {"webdriver": True, "userAgent": "HeadlessChrome", "plugins": [], "languages": []},
            {"notifications": "denied"},
            "short",
        )
        suggestions = StealthDetector.bypass_suggestions(results)
        assert len(suggestions) > 0

    def test_antibot_cloudflare_detection(self):
        from Forge.app.services.real_camofox_browser import AntiBotBypass
        assert AntiBotBypass.cloudflare_challenge_type("<html>Just a moment...</html>") == "cloudflare_interstitial"
        assert AntiBotBypass.cloudflare_challenge_type("<html>Normal page</html>") == "none"

    def test_antibot_challenge_response(self):
        from Forge.app.services.real_camofox_browser import AntiBotBypass
        response = AntiBotBypass.challenge_response("cloudflare_js_challenge")
        assert response["action"] == "execute_js"

    def test_antibot_backoff(self):
        from Forge.app.services.real_camofox_browser import AntiBotBypass
        delay = AntiBotBypass.backoff_strategy(2)
        assert delay > 0

    def test_antibot_mouse_path(self):
        from Forge.app.services.real_camofox_browser import AntiBotBypass
        path = AntiBotBypass.mouse_movement_path((0, 0), (100, 100), steps=5)
        assert len(path) == 6

    def test_antibot_scroll_pattern(self):
        from Forge.app.services.real_camofox_browser import AntiBotBypass
        steps = AntiBotBypass.scroll_pattern("down", 500)
        assert len(steps) > 0

    def test_proxy_manager(self):
        from Forge.app.services.real_camofox_browser import ProxyManager
        pm = ProxyManager()
        pm.add_proxy("proxy1:8080")
        pm.add_proxy("proxy2:8080")
        assert pm.available_count == 2
        proxy = pm.get_next()
        assert proxy in ["proxy1:8080", "proxy2:8080"]

    def test_proxy_manager_failure(self):
        from Forge.app.services.real_camofox_browser import ProxyManager
        pm = ProxyManager()
        pm.add_proxy("p1")
        pm.mark_failed("p1")
        assert pm.available_count == 0
        assert pm.failure_rate == 1.0

    def test_browser_context(self):
        from Forge.app.services.real_camofox_browser import BrowserContext
        context = BrowserContext.create_context()
        assert len(context.session_id) == 16
        assert context.fingerprint.user_agent.startswith("Mozilla")

    def test_browser_context_cookies(self):
        from Forge.app.services.real_camofox_browser import BrowserContext
        context = BrowserContext.create_context()
        context.add_cookie("session", "abc123", domain="example.com")
        assert context.cookie_count == 1

    def test_camofox_manager(self):
        from Forge.app.services.real_camofox_browser import CamofoxManager
        manager = CamofoxManager()
        manager.add_proxy("proxy1:8080")
        context = manager.create_context(use_proxy=True)
        assert context.proxy == "proxy1:8080"
        assert manager.context_count == 1

    def test_camofox_stealth_assess(self):
        from Forge.app.services.real_camofox_browser import CamofoxManager
        manager = CamofoxManager()
        context = manager.create_context()
        assessment = manager.assess_stealth(context)
        assert "risk_level" in assessment

    def test_camofox_challenge_handler(self):
        from Forge.app.services.real_camofox_browser import CamofoxManager
        manager = CamofoxManager()
        result = manager.challenge_handler("<html>Just a moment...</html>")
        assert result["needs_retry"]
        assert result["challenge_type"] == "cloudflare_interstitial"

    def test_camofox_checklist(self):
        from Forge.app.services.real_camofox_browser import CamofoxManager
        manager = CamofoxManager()
        checklist = manager.stealth_checklist()
        assert len(checklist) >= 8

    def test_camofox_health_report(self):
        from Forge.app.services.real_camofox_browser import CamofoxManager
        manager = CamofoxManager()
        manager.add_proxy("proxy1:8080")
        manager.create_context()
        report = manager.health_report()
        assert report["contexts"] == 1
        assert report["stealth_level"] == "high"
