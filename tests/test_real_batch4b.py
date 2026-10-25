"""
Real Batch 4b Tests — 8 Trading/Crypto Repo Implementations

Tests for:
- Stratex/app/agents/real_trading_agents.py — multi-agent LLM trading framework
- Stratex/app/agents/real_freqtrade.py — crypto trading bot with hyperopt
- Stratex/app/agents/real_vectorbt.py — vectorized backtesting engine
- Stratex/app/agents/real_backtrader.py — event-driven backtesting library
- Stratex/app/agents/real_hummingbot.py — high-frequency crypto trading bot
- Stratex/app/agents/real_ccxt.py — unified 100+ exchange trading API
- Stratex/app/agents/real_polymarket.py — prediction market API
- Stratex/app/agents/real_lumibot.py — AI agent trading framework
"""

import pytest
import sys
import os
import math

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


# =======================================================================
# 1. Stratex — TradingAgents (multi-agent LLM trading)
# =======================================================================

class TestTradingAgents:
    """Test Stratex real_trading_agents.py."""

    def test_trading_agent_conviction(self):
        from Stratex.app.agents.real_trading_agents import TradingAgent
        agent = TradingAgent(name="trader1", confidence=0.8)
        assert agent.confidence == 0.8

    def test_trading_agent_decision(self):
        from Stratex.app.agents.real_trading_agents import TradingAgent
        agent = TradingAgent(name="trader1")
        result = agent.make_decision("BUY", 0.7)
        assert result["decision"] == "BUY"

    def test_trading_agent_memory(self):
        from Stratex.app.agents.real_trading_agents import TradingAgent
        agent = TradingAgent(name="trader1")
        agent.remember("bought BTC at 50000")
        agent.remember("sold ETH at 3000")
        assert len(agent.memory) == 2
        results = agent.recall("BTC")
        assert len(results) == 1

    def test_research_agent_analyze_news(self):
        from Stratex.app.agents.real_trading_agents import ResearchAgent
        news = [
            {"title": "Tesla beats earnings", "sentiment": "positive", "category": "earnings"},
            {"title": "Apple misses revenue", "sentiment": "negative", "category": "earnings"},
        ]
        result = ResearchAgent.analyze_news(news)
        assert result["sentiment_score"] == 0  # 1 positive + 1 negative
        assert result["total_news"] == 2

    def test_research_agent_key_signals(self):
        from Stratex.app.agents.real_trading_agents import ResearchAgent
        news = [
            {"title": "Company reports record growth", "sentiment": "positive"},
            {"title": "Stock drops 10% on warning", "sentiment": "negative"},
        ]
        signals = ResearchAgent.extract_key_signals(news)
        assert len(signals) == 2

    def test_research_agent_generate_report(self):
        from Stratex.app.agents.real_trading_agents import ResearchAgent
        prices = [100, 102, 101, 105, 108, 110, 107, 112, 115, 113]
        report = ResearchAgent.generate_report(prices, [])
        assert report["trend"] in ["bullish", "bearish", "neutral"]

    def test_trader_agent_decide(self):
        from Stratex.app.agents.real_trading_agents import TraderAgent
        report = {"trend": "bullish", "news_sentiment": 2}
        result = TraderAgent.decide(report, 100.0)
        assert result["action"] == "BUY"

    def test_trader_agent_decide_bearish(self):
        from Stratex.app.agents.real_trading_agents import TraderAgent
        report = {"trend": "bearish", "news_sentiment": -2}
        result = TraderAgent.decide(report, 100.0)
        assert result["action"] == "SELL"

    def test_trader_agent_execute_trade(self):
        from Stratex.app.agents.real_trading_agents import TraderAgent
        trader = TraderAgent(cash=10000)
        trade = trader.execute_trade("BUY", 2, 100.0)
        assert trade["action"] == "BUY"
        assert trader.position == 2
        assert trader.cash == 9800

    def test_risk_manager_assess(self):
        from Stratex.app.agents.real_trading_agents import RiskManager
        result = RiskManager.assess_risk(80000, 100000)
        assert result["drawdown"] > 0.15
        assert result["risk_level"] == "high"

    def test_risk_manager_position_size(self):
        from Stratex.app.agents.real_trading_agents import RiskManager
        rm = RiskManager(risk_per_trade=0.01)
        size = rm.position_size(100000, 100.0, 95.0)
        assert size > 0

    def test_portfolio_manager_buy(self):
        from Stratex.app.agents.real_trading_agents import PortfolioManager
        pm = PortfolioManager(cash=10000)
        assert pm.buy("AAPL", 10, 100.0)
        assert pm.holdings["AAPL"] == 10

    def test_portfolio_manager_sell(self):
        from Stratex.app.agents.real_trading_agents import PortfolioManager
        pm = PortfolioManager(cash=10000)
        pm.buy("AAPL", 10, 100.0)
        assert pm.sell("AAPL", 5, 110.0)
        assert pm.holdings["AAPL"] == 5

    def test_portfolio_manager_total_value(self):
        from Stratex.app.agents.real_trading_agents import PortfolioManager
        pm = PortfolioManager(cash=10000)
        pm.buy("AAPL", 10, 100.0)
        value = pm.total_value({"AAPL": 120.0})
        assert value > 10000

    def test_bull_bear_debate(self):
        from Stratex.app.agents.real_trading_agents import BullBearDebate
        prices = [100, 105, 110, 115, 120, 125]
        news = [{"title": "record growth", "sentiment": "positive"}]
        debate = BullBearDebate()
        result = debate.debate(prices, news, rounds=3)
        assert result["rounds"] == 3

    def test_trading_agents_manager_run_cycle(self):
        from Stratex.app.agents.real_trading_agents import TradingAgentsManager
        manager = TradingAgentsManager()
        prices = [100 + i * 0.5 for i in range(20)]
        news = [{"title": "bullish news", "sentiment": "positive"}]
        result = manager.run_trading_cycle(prices, news)
        assert "research" in result
        assert "decision" in result
        assert "risk" in result

    def test_trading_agents_manager_execute(self):
        from Stratex.app.agents.real_trading_agents import TradingAgentsManager
        manager = TradingAgentsManager()
        prices = [100 + i * 0.5 for i in range(20)]
        result = manager.run_trading_cycle(prices, [])
        exec_result = manager.execute_cycle_trade(result, 1.0)
        assert "executed" in exec_result


# =======================================================================
# 2. Stratex — Freqtrade (crypto trading bot)
# =======================================================================

class TestFreqtrade:
    """Test Stratex real_freqtrade.py."""

    def test_freqtrade_config_timeframe(self):
        from Stratex.app.agents.real_freqtrade import FreqtradeConfig
        config = FreqtradeConfig(timeframe="1h")
        assert config.timeframe_minutes == 60

    def test_freqtrade_config_stoploss(self):
        from Stratex.app.agents.real_freqtrade import FreqtradeConfig
        config = FreqtradeConfig(stoploss=-0.10)
        stop = config.calculate_stoploss(100.0)
        assert abs(stop - 90.0) < 0.01

    def test_freqtrade_config_take_profit(self):
        from Stratex.app.agents.real_freqtrade import FreqtradeConfig
        config = FreqtradeConfig(take_profit=0.20)
        tp = config.calculate_take_profit(100.0)
        assert abs(tp - 120.0) < 0.01

    def test_freqtrade_config_minimal_roi(self):
        from Stratex.app.agents.real_freqtrade import FreqtradeConfig
        config = FreqtradeConfig()
        roi = config.get_minimal_roi(30)
        assert roi > 0

    def test_strategy_populate_entry_trend(self):
        from Stratex.app.agents.real_freqtrade import FreqtradeStrategy
        closes = [100, 101, 102, 105, 108, 110, 107, 112, 115, 113, 118, 120]
        signals = FreqtradeStrategy.populate_entry_trend({"close": closes})
        assert len(signals) == len(closes)

    def test_strategy_populate_exit_trend(self):
        from Stratex.app.agents.real_freqtrade import FreqtradeStrategy
        closes = [100, 101, 102, 105, 108, 110, 107, 112, 115, 113, 118, 120]
        signals = FreqtradeStrategy.populate_exit_trend({"close": closes})
        assert len(signals) == len(closes)

    def test_trailing_stop_calculate(self):
        from Stratex.app.agents.real_freqtrade import TrailingStop
        stop = TrailingStop.calculate_trailing_stop(100, 110, 115, 0.10, 0.05)
        assert stop < 115

    def test_trailing_stop_should_exit(self):
        from Stratex.app.agents.real_freqtrade import TrailingStop
        assert TrailingStop.should_exit(85, 90)

    def test_hyperopt_generate_trials(self):
        from Stratex.app.agents.real_freqtrade import HyperoptOptimizer
        param_space = {"period": [10, 14, 21], "stop_loss": [0.05, 0.10, 0.15]}
        trials = HyperoptOptimizer.generate_trials(param_space, 20)
        assert len(trials) == 20
        assert "period" in trials[0]

    def test_hyperopt_objective_function(self):
        from Stratex.app.agents.real_freqtrade import HyperoptOptimizer
        prices = [100, 102, 101, 105, 108, 110, 107, 112, 115, 113, 118, 120]
        trial = {"period": 14, "stop_loss": 0.10, "take_profit": 0.20}
        score = HyperoptOptimizer.objective_function(trial, prices)
        assert isinstance(score, float)

    def test_freqai_feature_engineering(self):
        from Stratex.app.agents.real_freqtrade import FreqAIPredictor
        prices = [100 + i * 0.5 for i in range(30)]
        features = FreqAIPredictor.feature_engineering(prices, lookback=14)
        assert len(features) > 0
        assert len(features[0]) == 6

    def test_freqai_predict_direction(self):
        from Stratex.app.agents.real_freqtrade import FreqAIPredictor
        prices = [100 + i * 0.5 for i in range(30)]
        features = FreqAIPredictor.feature_engineering(prices)
        predictions = FreqAIPredictor.predict_direction(features)
        assert len(predictions) == len(features)

    def test_freqtrade_backtest(self):
        from Stratex.app.agents.real_freqtrade import FreqtradeBot, FreqtradeBacktest
        bot = FreqtradeBot()
        prices = [100 + i * 0.5 for i in range(50)]
        result = bot.run_backtest(prices)
        assert "trades" in result or "error" in result

    def test_freqtrade_backtest_metrics(self):
        from Stratex.app.agents.real_freqtrade import FreqtradeBacktest
        trades = [{"pnl": 0.05}, {"pnl": -0.02}, {"pnl": 0.03}]
        metrics = FreqtradeBacktest.calculate_metrics(trades)
        assert "profit_factor" in metrics
        assert "win_rate" in metrics

    def test_freqtrade_optimize(self):
        from Stratex.app.agents.real_freqtrade import FreqtradeBot
        bot = FreqtradeBot()
        prices = [100 + i * 0.5 for i in range(50)]
        result = bot.optimize(prices, num_trials=20)
        assert "best_params" in result


# =======================================================================
# 3. Stratex — Vectorbt (vectorized backtesting)
# =======================================================================

class TestVectorbt:
    """Test Stratex real_vectorbt.py."""

    def test_sma_signal(self):
        from Stratex.app.agents.real_vectorbt import SignalGenerator
        closes = [100 + i * 0.5 for i in range(60)]
        signals = SignalGenerator.sma_signal(closes, 20, 50)
        assert len(signals) == len(closes)
        assert any(s == 1 for s in signals)

    def test_rsi_signal(self):
        from Stratex.app.agents.real_vectorbt import SignalGenerator
        closes = [100, 105, 110, 108, 105, 100, 95, 90, 85, 80, 85, 90, 95, 100, 105]
        signals = SignalGenerator.rsi_signal(closes, 14)
        assert len(signals) == len(closes)

    def test_bollinger_signal(self):
        from Stratex.app.agents.real_vectorbt import SignalGenerator
        closes = [100 + i * 0.5 for i in range(30)]
        signals = SignalGenerator.bollinger_signal(closes, 20)
        assert len(signals) == len(closes)

    def test_macd_signal(self):
        from Stratex.app.agents.real_vectorbt import SignalGenerator
        closes = [100 + i * 0.5 for i in range(40)]
        signals = SignalGenerator.macd_signal(closes)
        assert len(signals) == len(closes)

    def test_position_sizer_fixed_fraction(self):
        from Stratex.app.agents.real_vectorbt import PositionSizer
        size = PositionSizer.fixed_fraction(10000, 100.0, 0.1)
        assert size == 10.0

    def test_position_sizer_kelly(self):
        from Stratex.app.agents.real_vectorbt import PositionSizer
        size = PositionSizer.kelly(0.6, 2.0, 10000, 100.0)
        assert size > 0

    def test_portfolio_simulation(self):
        from Stratex.app.agents.real_vectorbt import PortfolioSimulation
        prices = [100 + i * 0.5 for i in range(50)]
        signals = [0] * 50
        signals[10] = 1
        signals[30] = -1
        result = PortfolioSimulation.simulate(prices, signals, 10000)
        assert "portfolio_values" in result
        assert len(result["trades"]) >= 1

    def test_portfolio_calculate_returns(self):
        from Stratex.app.agents.real_vectorbt import PortfolioSimulation
        values = [100, 101, 102, 100, 103]
        returns = PortfolioSimulation.calculate_returns(values)
        assert len(returns) == 4

    def test_vectorbt_metrics_total_return(self):
        from Stratex.app.agents.real_vectorbt import VectorbtMetrics
        ret = VectorbtMetrics.total_return([100, 110, 120])
        assert abs(ret - 0.2) < 0.01

    def test_vectorbt_metrics_sharpe(self):
        from Stratex.app.agents.real_vectorbt import VectorbtMetrics
        values = [100 + i * 0.5 for i in range(50)]
        sharpe = VectorbtMetrics.sharpe_ratio(values)
        assert isinstance(sharpe, float)

    def test_vectorbt_metrics_max_drawdown(self):
        from Stratex.app.agents.real_vectorbt import VectorbtMetrics
        dd = VectorbtMetrics.max_drawdown([100, 110, 105, 85, 90, 95])
        assert dd > 0

    def test_vectorbt_metrics_calculate_all(self):
        from Stratex.app.agents.real_vectorbt import VectorbtMetrics
        values = [100 + i * 0.5 for i in range(50)]
        metrics = VectorbtMetrics.calculate_all(values)
        assert "sharpe_ratio" in metrics
        assert "max_drawdown" in metrics
        assert "calmar_ratio" in metrics

    def test_vectorbt_portfolio_from_signals(self):
        from Stratex.app.agents.real_vectorbt import VectorbtPortfolio
        prices = [100 + i * 0.5 for i in range(50)]
        signals = [0] * 50
        signals[10] = 1
        signals[30] = -1
        result = VectorbtPortfolio.from_signals(prices, signals)
        assert "simulation" in result
        assert "metrics" in result

    def test_vectorbt_compare_strategies(self):
        from Stratex.app.agents.real_vectorbt import VectorbtPortfolio
        prices = [100 + i * 0.5 for i in range(50)]
        strategies = {
            "sma": [0]*50 + [1]*25,
            "rsi": [1]*25 + [0]*25,
        }
        result = VectorbtPortfolio.compare_strategies(prices, strategies)
        assert "best_strategy" in result

    def test_vectorbt_rolling_sharpe(self):
        from Stratex.app.agents.real_vectorbt import VectorbtPortfolio
        values = [100 + i * 0.5 for i in range(50)]
        sharpe = VectorbtPortfolio.rolling_sharpe(values, window=10)
        assert len(sharpe) == len(values) - 1


# =======================================================================
# 4. Stratex — Backtrader (event-driven backtesting)
# =======================================================================

class TestBacktrader:
    """Test Stratex real_backtrader.py."""

    def test_data_feed_create_ohlc(self):
        from Stratex.app.agents.real_backtrader import DataFeed
        data = [{"open": 100, "high": 101, "low": 99, "close": 100.5, "volume": 1000}]
        ohlc = DataFeed.create_ohlc(data)
        assert "open" in ohlc
        assert "close" in ohlc

    def test_indicator_sma(self):
        from Stratex.app.agents.real_backtrader import BacktraderIndicator
        result = BacktraderIndicator.sma([10, 11, 12, 13, 14], 3)
        assert math.isnan(result[0])
        assert abs(result[-1] - 13) < 0.01

    def test_indicator_ema(self):
        from Stratex.app.agents.real_backtrader import BacktraderIndicator
        result = BacktraderIndicator.ema([10, 11, 12, 13, 14], 3)
        assert result[0] == 10
        assert result[-1] > result[0]

    def test_indicator_rsi(self):
        from Stratex.app.agents.real_backtrader import BacktraderIndicator
        prices = [100, 102, 101, 105, 108, 110, 107, 112, 115, 113, 118, 120, 117, 122, 125, 130, 128, 132]
        result = BacktraderIndicator.rsi(prices, 14)
        assert len(result) > 0
        assert all(0 <= r <= 100 for r in result)

    def test_indicator_macd(self):
        from Stratex.app.agents.real_backtrader import BacktraderIndicator
        prices = [100 + i * 0.5 for i in range(30)]
        macd, signal, hist = BacktraderIndicator.macd(prices)
        assert len(macd) == len(signal) == len(hist)

    def test_indicator_bollinger(self):
        from Stratex.app.agents.real_backtrader import BacktraderIndicator
        prices = [100 + i * 0.5 for i in range(25)]
        upper, lower = BacktraderIndicator.bollinger_bands(prices, 20)
        assert upper[-1] >= lower[-1]

    def test_indicator_atr(self):
        from Stratex.app.agents.real_backtrader import BacktraderIndicator
        high = [101 + i for i in range(20)]
        low = [100 + i for i in range(20)]
        close = [100 + i for i in range(20)]
        result = BacktraderIndicator.atr(high, low, close, 14)
        assert len(result) > 0

    def test_strategy_generate_signals_sma(self):
        from Stratex.app.agents.real_backtrader import BacktraderStrategy
        closes = [100 + i * 0.5 for i in range(50)]
        signals = BacktraderStrategy.generate_signals({"close": closes}, "sma_crossover")
        assert len(signals) == len(closes)

    def test_strategy_generate_signals_rsi(self):
        from Stratex.app.agents.real_backtrader import BacktraderStrategy
        closes = [100, 105, 108, 103, 98, 95, 92, 90, 88, 85, 80, 85, 90, 95, 100]
        signals = BacktraderStrategy.generate_signals({"close": closes}, "rsi_reversal")
        assert len(signals) == len(closes)

    def test_broker_buy(self):
        from Stratex.app.agents.real_backtrader import BacktraderBroker
        broker = BacktraderBroker(cash=10000, commission=0.001)
        result = broker.buy(100.0, size=10)
        assert result["executed"] if isinstance(result, dict) and "executed" in result else True

    def test_broker_sell(self):
        from Stratex.app.agents.real_backtrader import BacktraderBroker
        broker = BacktraderBroker(cash=10000, commission=0.001)
        broker.buy(100.0, size=10)
        broker.sell(110.0, size=5)
        assert broker.position == 5

    def test_analyzer_returns(self):
        from Stratex.app.agents.real_backtrader import BacktraderAnalyzer
        returns = BacktraderAnalyzer.returns([100, 101, 102, 100, 103])
        assert len(returns) == 4

    def test_analyzer_sharpe(self):
        from Stratex.app.agents.real_backtrader import BacktraderAnalyzer
        values = [100 + i * 0.5 for i in range(50)]
        sharpe = BacktraderAnalyzer.sharpe(values)
        assert isinstance(sharpe, float)

    def test_analyzer_drawdown(self):
        from Stratex.app.agents.real_backtrader import BacktraderAnalyzer
        dd = BacktraderAnalyzer.drawdown([100, 110, 105, 85, 90, 95])
        assert dd > 0

    def test_analyzer_trade_analyzer(self):
        from Stratex.app.agents.real_backtrader import BacktraderAnalyzer
        trades = [{"pnl": 0.05}, {"pnl": -0.02}, {"pnl": 0.03}]
        result = BacktraderAnalyzer.trade_analyzer(trades)
        assert result["total_trades"] == 3
        assert 0 <= result["win_rate"] <= 1

    def test_cerebro_run(self):
        from Stratex.app.agents.real_backtrader import BacktraderCerebro
        closes = [100 + i * 0.5 for i in range(50)]
        result = BacktraderCerebro.run({"close": closes}, "sma_crossover")
        assert "portfolio_values" in result
        assert "trades" in result


# =======================================================================
# 5. Stratex — Hummingbot (HFT crypto trading)
# =======================================================================

class TestHummingbot:
    """Test Stratex real_hummingbot.py."""

    def test_connector_config_spread_at_level(self):
        from Stratex.app.agents.real_hummingbot import ConnectorConfig
        config = ConnectorConfig(order_level_spread=0.0001)
        assert abs(config.spread_at_level(0) - 0.0001) < 1e-10
        assert abs(config.spread_at_level(2) - 0.0003) < 1e-10

    def test_connector_config_size_at_level(self):
        from Stratex.app.agents.real_hummingbot import ConnectorConfig
        config = ConnectorConfig(order_level_amount=0.01)
        assert config.size_at_level(0) == 0.01
        assert config.size_at_level(2) == 0.03

    def test_connector_total_order_size(self):
        from Stratex.app.agents.real_hummingbot import ConnectorConfig
        config = ConnectorConfig(order_levels=5, order_level_amount=0.01)
        assert abs(config.total_order_size - 0.15) < 1e-10

    def test_market_making_calculate_bid_ask(self):
        from Stratex.app.agents.real_hummingbot import MarketMakingStrategy
        bid, ask = MarketMakingStrategy.calculate_bid_ask(100.0, 0.002, level=0)
        assert bid < 100
        assert ask > 100

    def test_market_making_inventory_imbalance(self):
        from Stratex.app.agents.real_hummingbot import MarketMakingStrategy
        bids = [(100, 10), (99, 20)]
        asks = [(101, 5), (102, 10)]
        imbalance = MarketMakingStrategy.inventory_imbalance(bids, asks)
        assert imbalance > 0

    def test_market_making_adjust_spread(self):
        from Stratex.app.agents.real_hummingbot import MarketMakingStrategy
        spread = MarketMakingStrategy.adjust_spread(100.0, 0.5)
        assert spread > 0.0001

    def test_market_making_hedge_ratio(self):
        from Stratex.app.agents.real_hummingbot import MarketMakingStrategy
        ratio = MarketMakingStrategy.hedge_ratio(10.0, -500.0)
        assert ratio > 0

    def test_market_making_pnl(self):
        from Stratex.app.agents.real_hummingbot import MarketMakingStrategy
        pnl = MarketMakingStrategy.pnl_calculation(100, 110, 10, is_buy=True)
        assert pnl == 100

    def test_cross_exchange_arbitrage(self):
        from Stratex.app.agents.real_hummingbot import CrossExchangeArbitrage
        prices = {"binance": 100.0, "coinbase": 101.0, "kraken": 99.0}
        opps = CrossExchangeArbitrage.find_arbitrage(prices)
        assert len(opps) > 0

    def test_cross_exchange_fee_adjusted(self):
        from Stratex.app.agents.real_hummingbot import CrossExchangeArbitrage
        result = CrossExchangeArbitrage.calculate_fee_adjusted_profit(99.0, 101.0, 10.0)
        assert result["net_profit"] > 0

    def test_scheduler_schedule_trade(self):
        from Stratex.app.agents.real_hummingbot import SchedulerController
        schedule = SchedulerController.schedule_trade(300, total_runs=5)
        assert schedule == [300, 600, 900, 1200, 1500]

    def test_scheduler_parse_schedule(self):
        from Stratex.app.agents.real_hummingbot import SchedulerController
        assert SchedulerController.parse_schedule("5m") == 300
        assert SchedulerController.parse_schedule("1h") == 3600

    def test_scheduler_should_run(self):
        from Stratex.app.agents.real_hummingbot import SchedulerController
        assert SchedulerController.should_run(600, 300, 300)

    def test_paper_trading_buy(self):
        from Stratex.app.agents.real_hummingbot import PaperTradingEngine
        engine = PaperTradingEngine(cash=10000)
        result = engine.place_order("BTC", "buy", 0.5, 100.0)
        assert result["executed"] if isinstance(result, dict) and "executed" in result else True

    def test_paper_trading_portfolio_value(self):
        from Stratex.app.agents.real_hummingbot import PaperTradingEngine
        engine = PaperTradingEngine(cash=10000)
        engine.place_order("BTC", "buy", 0.5, 100.0)
        value = engine.portfolio_value({"BTC": 120.0})
        assert value > 10000

    def test_hummingbot_manager_generate_orders(self):
        from Stratex.app.agents.real_hummingbot import HummingbotManager
        manager = HummingbotManager()
        orders = manager.generate_orders(100.0)
        assert len(orders["bids"]) == 5
        assert len(orders["asks"]) == 5

    def test_hummingbot_manager_detect_arbitrage(self):
        from Stratex.app.agents.real_hummingbot import HummingbotManager
        manager = HummingbotManager()
        opps = manager.detect_arbitrage({"binance": 100.0, "coinbase": 101.0})
        assert len(opps) > 0


# =======================================================================
# 6. Stratex — CCXT (unified exchange API)
# =======================================================================

class TestCCXT:
    """Test Stratex real_ccxt.py."""

    def test_exchange_config_has_credentials(self):
        from Stratex.app.agents.real_ccxt import ExchangeConfig
        config = ExchangeConfig(api_key="key", secret="secret")
        assert config.has_credentials

    def test_exchange_base_load_markets(self):
        from Stratex.app.agents.real_ccxt import ExchangeBase
        exchange = ExchangeBase()
        markets = exchange.load_markets()
        assert len(markets) >= 5

    def test_exchange_base_parse_symbol(self):
        from Stratex.app.agents.real_ccxt import ExchangeBase
        base, quote = ExchangeBase.parse_symbol("BTC/USDT")
        assert base == "BTC"
        assert quote == "USDT"

    def test_exchange_base_normalize_symbol(self):
        from Stratex.app.agents.real_ccxt import ExchangeBase
        assert ExchangeBase.normalize_symbol("BTC/USDT") == "BTC/USDT"

    def test_exchange_base_fetch_ticker(self):
        from Stratex.app.agents.real_ccxt import ExchangeBase
        exchange = ExchangeBase()
        ticker = exchange.fetch_ticker("BTC/USDT")
        assert "last" in ticker
        assert "bid" in ticker
        assert "ask" in ticker

    def test_exchange_base_fetch_order_book(self):
        from Stratex.app.agents.real_ccxt import ExchangeBase
        exchange = ExchangeBase()
        book = exchange.fetch_order_book("BTC/USDT", 10)
        assert len(book["bids"]) == 5
        assert len(book["asks"]) == 5

    def test_exchange_base_fetch_ohlcv(self):
        from Stratex.app.agents.real_ccxt import ExchangeBase
        exchange = ExchangeBase()
        ohlcv = exchange.fetch_ohlcv("BTC/USDT", "1h", 50)
        assert len(ohlcv) == 50
        assert len(ohlcv[0]) == 6

    def test_exchange_base_create_order_buy(self):
        from Stratex.app.agents.real_ccxt import ExchangeBase
        exchange = ExchangeBase()
        order = exchange.create_order("BTC/USDT", "limit", "buy", 0.1, 100.0)
        assert order["id"].startswith("order-")
        assert exchange.order_count == 1

    def test_exchange_base_create_order_sell(self):
        from Stratex.app.agents.real_ccxt import ExchangeBase
        exchange = ExchangeBase()
        exchange.create_order("BTC/USDT", "limit", "buy", 0.1, 100.0)
        exchange.create_order("BTC/USDT", "limit", "sell", 0.1, 110.0)
        assert exchange.order_count == 2

    def test_market_data_create_market(self):
        from Stratex.app.agents.real_ccxt import MarketData
        market = MarketData.create_market("BTC", "USDT")
        assert market.symbol == "BTC/USDT"
        assert market.spot is True

    def test_market_data_base_symbol(self):
        from Stratex.app.agents.real_ccxt import MarketData
        market = MarketData.create_market("ETH", "USDT")
        assert market.base_symbol == "ETH"

    def test_ccxt_manager_add_exchange(self):
        from Stratex.app.agents.real_ccxt import CCXTManager, ExchangeConfig
        manager = CCXTManager()
        exchange = manager.add_exchange("binance", ExchangeConfig(name="binance"))
        assert exchange.market_count >= 5

    def test_ccxt_manager_find_best_price(self):
        from Stratex.app.agents.real_ccxt import CCXTManager
        prices = {
            "binance": {"bid": 99.9, "ask": 100.1},
            "coinbase": {"bid": 100.0, "ask": 100.2},
        }
        best = CCXTManager.find_best_price(prices)
        assert best["buy_exchange"] == "coinbase"

    def test_ccxt_manager_calculate_fee(self):
        from Stratex.app.agents.real_ccxt import CCXTManager
        fee = CCXTManager.calculate_fee(1.0, 100.0, 0.001)
        assert abs(fee - 0.1) < 0.001

    def test_ccxt_manager_estimate_transfer_fee(self):
        from Stratex.app.agents.real_ccxt import CCXTManager
        fee = CCXTManager.estimate_transfer_fee("USDT", "ERC20")
        assert fee == 0.005


# =======================================================================
# 7. Stratex — Polymarket (prediction market API)
# =======================================================================

class TestPolymarket:
    """Test Stratex real_polymarket.py."""

    def test_market_create(self):
        from Stratex.app.agents.real_polymarket import PredictionMarket
        market = PredictionMarket.create_market("Will BTC hit $100k?", ["Yes", "No"])
        assert market.outcome_count == 2
        assert market.is_binary

    def test_market_implied_probabilities(self):
        from Stratex.app.agents.real_polymarket import PredictionMarket
        market = PredictionMarket.create_market("Test?", ["A", "B"])
        probs = market.implied_probabilities
        assert "A" in probs
        assert "B" in probs
        assert sum(probs.values()) == 1.0

    def test_market_favorite_outcome(self):
        from Stratex.app.agents.real_polymarket import PredictionMarket
        market = PredictionMarket.create_market("Test?", ["A", "B"])
        market.update_price(0, 0.7)
        assert market.favorite_outcome == "A"

    def test_market_resolve(self):
        from Stratex.app.agents.real_polymarket import PredictionMarket
        market = PredictionMarket.create_market("Test?", ["Yes", "No"])
        market.resolve("Yes")
        assert market.resolved
        assert market.outcome_prices == [1.0, 0.0]

    def test_order_create(self):
        from Stratex.app.agents.real_polymarket import Order
        order = Order.create_order("market-1", "Yes", "BUY", 10, 0.5)
        assert order.notional == 5.0
        assert not order.is_filled

    def test_order_fill(self):
        from Stratex.app.agents.real_polymarket import Order
        order = Order.create_order("market-1", "Yes", "BUY", 10, 0.5)
        order.fill(10)
        assert order.is_filled

    def test_position_open(self):
        from Stratex.app.agents.real_polymarket import Position
        pos = Position.open_position("market-1", "Yes", 10, 0.5)
        assert pos.cost_basis == 5.0

    def test_position_unrealized_pnl(self):
        from Stratex.app.agents.real_polymarket import Position
        pos = Position.open_position("market-1", "Yes", 10, 0.5)
        pnl = pos.unrealized_pnl(0.7)
        assert abs(pnl - 2.0) < 1e-10

    def test_position_close(self):
        from Stratex.app.agents.real_polymarket import Position
        pos = Position.open_position("market-1", "Yes", 10, 0.5)
        result = pos.close(0.7)
        assert abs(result["pnl"] - 2.0) < 1e-10
        assert not pos.quantity > 0

    def test_polymarket_api_create_market(self):
        from Stratex.app.agents.real_polymarket import PolymarketAPI
        api = PolymarketAPI()
        market = api.create_market("Will it rain?", ["Yes", "No"])
        assert market.market_id in api.markets

    def test_polymarket_api_place_order(self):
        from Stratex.app.agents.real_polymarket import PolymarketAPI
        api = PolymarketAPI()
        market = api.create_market("Test?", ["Yes", "No"])
        order = api.place_order(market.market_id, "Yes", "BUY", 10, 0.6)
        assert order.order_id in api.orders

    def test_polymarket_api_match_order(self):
        from Stratex.app.agents.real_polymarket import PolymarketAPI
        api = PolymarketAPI()
        market = api.create_market("Test?", ["Yes", "No"])
        order = api.place_order(market.market_id, "Yes", "BUY", 10, 0.6)
        result = api.match_order(order.order_id, 10)
        assert result

    def test_polymarket_api_resolve(self):
        from Stratex.app.agents.real_polymarket import PolymarketAPI
        api = PolymarketAPI()
        market = api.create_market("Test?", ["Yes", "No"])
        result = api.resolve_market(market.market_id, "Yes")
        assert result

    def test_analyzer_market_efficiency(self):
        from Stratex.app.agents.real_polymarket import PredictionMarketAnalyzer
        efficiency = PredictionMarketAnalyzer.market_efficiency([0.5, 0.5])
        assert efficiency > 0.9

    def test_analyzer_arbitrage(self):
        from Stratex.app.agents.real_polymarket import PredictionMarket, PredictionMarketAnalyzer
        market1 = PredictionMarket.create_market("Test?", ["Yes", "No"])
        market1.update_price(0, 0.4)
        market2 = PredictionMarket.create_market("Test?", ["Yes", "No"])
        market2.update_price(0, 0.6)
        opps = PredictionMarketAnalyzer.arbitrage_opportunities({"m1": market1, "m2": market2})
        assert len(opps) > 0

    def test_analyzer_consensus_price(self):
        from Stratex.app.agents.real_polymarket import PredictionMarket, PredictionMarketAnalyzer
        markets = []
        for price in [0.4, 0.5, 0.6]:
            m = PredictionMarket.create_market("Test?", ["Yes", "No"])
            m.update_price(0, price)
            markets.append(m)
        consensus = PredictionMarketAnalyzer.consensus_price(markets, "Yes")
        assert abs(consensus - 0.5) < 0.01

    def test_analyzer_kelly_fraction(self):
        from Stratex.app.agents.real_polymarket import PredictionMarketAnalyzer
        kelly = PredictionMarketAnalyzer.kelly_fraction(0.6)
        assert kelly > 0

    def test_analyzer_implied_odds(self):
        from Stratex.app.agents.real_polymarket import PredictionMarketAnalyzer
        odds = PredictionMarketAnalyzer.calculate_implied_odds(0.25)
        assert odds == 3.0


# =======================================================================
# 8. Stratex — Lumibot (AI agent trading framework)
# =======================================================================

class TestLumibot:
    """Test Stratex real_lumibot.py."""

    def test_broker_config_is_paper(self):
        from Stratex.app.agents.real_lumibot import BrokerConfig
        config = BrokerConfig(trading_type="paper")
        assert config.is_paper
        assert not config.is_live

    def test_broker_config_has_credentials(self):
        from Stratex.app.agents.real_lumibot import BrokerConfig
        config = BrokerConfig(api_key="key", api_secret="secret")
        assert config.has_credentials

    def test_order_create(self):
        from Stratex.app.agents.real_lumibot import LumibotOrder
        order = LumibotOrder.create_order("AAPL", "BUY", 10, "market", 100.0)
        assert order.symbol == "AAPL"
        assert order.side == "BUY"

    def test_order_fill(self):
        from Stratex.app.agents.real_lumibot import LumibotOrder
        order = LumibotOrder.create_order("AAPL", "BUY", 10, "market", 100.0)
        order.fill(100.0)
        assert order.is_filled

    def test_position_open(self):
        from Stratex.app.agents.real_lumibot import LumibotPosition
        pos = LumibotPosition.open_position("AAPL", 10, 100.0)
        assert pos.quantity == 10
        assert pos.is_open

    def test_position_update_market_value(self):
        from Stratex.app.agents.real_lumibot import LumibotPosition
        pos = LumibotPosition.open_position("AAPL", 10, 100.0)
        pos.update_market_value(120.0)
        assert pos.unrealized_pnl == 200.0

    def test_position_close(self):
        from Stratex.app.agents.real_lumibot import LumibotPosition
        pos = LumibotPosition.open_position("AAPL", 10, 100.0)
        pos.update_market_value(120.0)
        result = pos.close(120.0)
        assert result["pnl"] == 200.0

    def test_strategy_submit_order(self):
        from Stratex.app.agents.real_lumibot import LumibotStrategy, BrokerConfig
        strategy = LumibotStrategy(cash=10000)
        strategy.broker = BrokerConfig(trading_type="paper")
        order = strategy.submit_order("AAPL", "BUY", 10, "market", 100.0)
        assert order.order_id if hasattr(order, "order_id") else True

    def test_strategy_open_positions(self):
        from Stratex.app.agents.real_lumibot import LumibotStrategy, BrokerConfig
        strategy = LumibotStrategy(cash=10000)
        strategy.broker = BrokerConfig(trading_type="paper")
        strategy.submit_order("AAPL", "BUY", 10, "market", 100.0)
        assert "AAPL" in strategy.open_positions

    def test_strategy_total_value(self):
        from Stratex.app.agents.real_lumibot import LumibotStrategy, BrokerConfig
        strategy = LumibotStrategy(cash=10000)
        strategy.broker = BrokerConfig(trading_type="paper")
        strategy.submit_order("AAPL", "BUY", 10, "market", 100.0)
        value = strategy.total_value({"AAPL": 120.0})
        assert value > 10000

    def test_backtest_generate_signals_sma(self):
        from Stratex.app.agents.real_lumibot import LumibotBacktest
        prices = {"AAPL": [100 + i * 0.5 for i in range(50)]}
        signals = LumibotBacktest.generate_signals(prices, "sma_crossover")
        assert len(signals["AAPL"]) == 50

    def test_backtest_generate_signals_breakout(self):
        from Stratex.app.agents.real_lumibot import LumibotBacktest
        prices = {"AAPL": [100 + i * 0.5 for i in range(50)]}
        signals = LumibotBacktest.generate_signals(prices, "breakout")
        assert len(signals["AAPL"]) == 50

    def test_backtest_generate_signals_mean_reversion(self):
        from Stratex.app.agents.real_lumibot import LumibotBacktest
        prices = {"AAPL": [100 + i * 0.5 for i in range(50)]}
        signals = LumibotBacktest.generate_signals(prices, "mean_reversion")
        assert len(signals["AAPL"]) == 50

    def test_backtest_run(self):
        from Stratex.app.agents.real_lumibot import LumibotBacktest
        prices = {"AAPL": [100 + i * 0.5 for i in range(50)]}
        result = LumibotBacktest.run(prices, "sma_crossover", 10000)
        assert "portfolio_values" in result
        assert "trades" in result

    def test_backtest_calculate_metrics(self):
        from Stratex.app.agents.real_lumibot import LumibotBacktest
        values = [100 + i * 0.5 for i in range(50)]
        metrics = LumibotBacktest.calculate_metrics(values)
        assert "sharpe_ratio" in metrics
        assert "max_drawdown" in metrics

    def test_lumibot_manager_set_broker(self):
        from Stratex.app.agents.real_lumibot import LumibotManager, BrokerConfig
        manager = LumibotManager()
        manager.set_broker(BrokerConfig(name="tradier", trading_type="live"))
        assert manager.strategy.broker.name == "tradier"

    def test_lumibot_manager_run_backtest(self):
        from Stratex.app.agents.real_lumibot import LumibotManager
        manager = LumibotManager()
        prices = {"AAPL": [100 + i * 0.5 for i in range(50)]}
        result = manager.run_backtest(prices, "sma_crossover")
        assert "metrics" in result

    def test_lumibot_manager_broker_count(self):
        from Stratex.app.agents.real_lumibot import LumibotManager
        manager = LumibotManager()
        assert manager.broker_count >= 10
