# ==============================================================================
# CONFIG_TEMPLATE.PY - Copy this file to config.py and fill in your own keys
# ==============================================================================

# --- Binance Demo Trading API Keys ---
# Get your Demo Trading API keys at: https://demo.binance.com
API_KEY = "YOUR_BINANCE_DEMO_API_KEY_HERE"
SECRET_KEY = "YOUR_BINANCE_DEMO_SECRET_KEY_HERE"

# --- Demo Trading Base URLs ---
BASE_URL = "https://demo-api.binance.com"
WS_URL = "wss://demo-api.binance.com/ws-api/v3"

# --- Dynamic Market Scanner ---
TOP_COINS_LIMIT = 5  # Number of top trending coins to scan
TIMEFRAME = "1m"            # Candle interval (1m, 5m, 15m, 1h)

# --- Risk Management ---
TRADE_QTY = 0.001           # BTC quantity per trade (small for safety)
MAX_OPEN_TRADES = 5         # Allow more trades to open concurrently

# --- Strategy to Run ---
# Options: "scalper", "swing", "ml", "aggressor", "multi"
ACTIVE_STRATEGY = "multi"

# --- Backtesting Engine ---
BACKTEST_FEE_RATE = 0.001          # 0.1% fee per trade
BACKTEST_SLIPPAGE_RATE = 0.0005    # 0.05% slippage
RISK_PER_TRADE = 0.01              # 1% risk of equity per trade
STARTING_BALANCE = 10000.0         # Initial balance
OOS_TRAIN_PCT = 0.60               # Walk-forward train %
OOS_VAL_PCT = 0.20                 # Walk-forward validation %
