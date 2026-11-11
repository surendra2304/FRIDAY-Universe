# ==============================================================================
# STRATEGY_SUPERTREND.PY - Trend Rider & Pullback Engine (honest-prior edition)
# ==============================================================================
# 2026-11-11 incident fix (see Stratex/docs/INCIDENT_2026-11-11_LOSSES.md):
#   * The old header claimed "_OOS_WIN_RATE_PRIOR = 0.80 (sniper mode)".
#     The realized testnet ledger measured 17 wins / 64 closed trades = 0.266.
#     The fabricated 0.80 let every signal clear the profitability gate with a
#     fantasy +0.6R expectancy while the account bled. The prior is now the
#     ledger-measured value; R:R now reflects the realized winner geometry
#     (avg win +4.18 vs avg loss -1.03 ~= 4:1, haircut to 3.0).
#   * Anti-churn brackets: SL distance is floored at MIN_BRACKET_PCT of price
#     so a stop can never sit inside one candle's noise (64/64 ledger trades
#     previously died in under 20 minutes, 9 of them at the exact entry price).
# ==============================================================================

from collections import namedtuple
import os


class SignalResult(namedtuple("SignalResult", ["side", "sl", "tp", "strategy_type", "win_rate_prior", "rr_ratio"])):
    @property
    def confidence(self):
        return self.win_rate_prior

_STRATEGY_TYPE = "RULE_BASED"

# Batch 2 (2026-11-11): shorts fighting the dominant trend were a ledger loss
# source. With this flag on (default), SELL entries require a FULL bear regime:
# close < EMA200 AND EMA50 < EMA200. A pullback that dips price under the
# EMA200 while the EMA50 still sits above it no longer counts as shortable.
BLOCK_SHORTS_IN_BULL_REGIME = os.getenv("BLOCK_SHORTS_IN_BULL_REGIME", "true").strip().lower() in ("1", "true", "yes", "on")

# Honest, evidence-based priors (2026-11-11):
#   win rate 0.266 — measured on the closed-trade testnet ledger (17/64)
#   R:R 3.0        — realized avg-win/avg-loss was ~4.06:1; 3.0 is the haircut
_OOS_WIN_RATE_PRIOR = 0.266
_RR_RATIO = 3.0

# Anti-churn floor: stop/tp distances below this fraction of price are noise
# (they were getting hit inside a single candle). 0.30% floor ~= 3x the ~8 bps
# one-way futures friction x 2 sides, and wide enough to sit outside 15m noise.
MIN_BRACKET_PCT = 0.0030


def _bracket_ok(entry: float, sl: float, tp: float, side: str) -> bool:
    """True when both bracket legs clear the anti-churn minimum distance."""
    if entry <= 0:
        return False
    floor_dist = entry * MIN_BRACKET_PCT
    if side == "BUY":
        return (entry - sl) >= floor_dist and (tp - entry) >= floor_dist
    return (sl - entry) >= floor_dist and (entry - tp) >= floor_dist


def get_signal(df):
    """
    Supertrend + 200 EMA + Value Pullback Strategy (honest-prior edition):
    1. Fresh Breakout: Supertrend flips Bullish + Price > 200 EMA + ADX >= 25
    2. Trend Pullback Continuation: Supertrend already Bullish + Pullback to EMA21/50
       + Bullish bounce + RSI in 40-65 zone + ADX >= 25
    Brackets: SL 2.0x ATR (floored at MIN_BRACKET_PCT of price), TP = 3R.
    Signals whose bracket sits inside the churn floor are suppressed (None).
    Returns: SignalResult
    """
    if df is None or len(df) < 50:
        return SignalResult(None, None, None, _STRATEGY_TYPE, _OOS_WIN_RATE_PRIOR, _RR_RATIO)

    # Required columns check
    if 'supertrend' not in df.columns or 'ema_200' not in df.columns:
        try:
            import features
            df = features.add_features(df)
        except Exception:
            return SignalResult(None, None, None, _STRATEGY_TYPE, _OOS_WIN_RATE_PRIOR, _RR_RATIO)

    if 'supertrend' not in df.columns:
        return SignalResult(None, None, None, _STRATEGY_TYPE, _OOS_WIN_RATE_PRIOR, _RR_RATIO)

    last = df.iloc[-1]
    prev = df.iloc[-2]

    # Chop filter: skip weak markets if ADX is present
    adx = float(last.get('adx', last.get('adx_14', 0.0)))
    if 0.0 < adx < 25.0:
        return SignalResult(None, None, None, _STRATEGY_TYPE, _OOS_WIN_RATE_PRIOR, _RR_RATIO)

    st_now = bool(last['supertrend'])
    st_prev = bool(prev['supertrend'])
    close = float(last['close'])
    open_p = float(last['open'])
    low = float(last['low'])
    high = float(last.get('high', close))
    prev_high = float(prev.get('high', prev['close']))

    ema_200 = float(last.get('ema_200', close))
    ema_50  = float(last.get('ema_50', close))
    ema_21  = float(last.get('ema_21', last.get('ema_20', close)))
    atr     = float(last.get('atr', last.get('atr_14', close * 0.01)))
    rsi     = float(last.get('rsi', last.get('rsi_14', 50.0)))
    st_lower = float(last.get('st_lower', close - 1.5 * atr))
    st_upper = float(last.get('st_upper', close + 1.5 * atr))

    # --- 1. Fresh Trend Flip (Breakout Entry) ---
    if st_now == True and st_prev == False and close > ema_200:
        sl = max(st_lower, close - (atr * 2.0))
        risk = max(close - sl, atr * 0.8)
        tp = close + (risk * _RR_RATIO)
        if _bracket_ok(close, sl, tp, "BUY"):
            return SignalResult("BUY", sl, tp, _STRATEGY_TYPE, _OOS_WIN_RATE_PRIOR, _RR_RATIO)
        return SignalResult(None, None, None, _STRATEGY_TYPE, _OOS_WIN_RATE_PRIOR, _RR_RATIO)

    # --- 2. Bullish Trend Continuation / Dynamic Pullback Entry ---
    # When established in an uptrend (Supertrend True for >1 bar, price above 200 EMA & EMA21 > EMA50)
    if st_now == True and st_prev == True and close > ema_200 and ema_21 >= ema_50:
        # Price dipped to touch EMA21 or EMA50 during this candle or prev candle
        pulled_back = (low <= ema_21 * 1.002 or prev['low'] <= ema_21 * 1.002)
        # Closed bullish (green candle bouncing back above EMA21)
        bullish_bounce = (close > open_p) and (close >= ema_21)
        # Healthy momentum (not overbought, resetting from support)
        rsi_healthy = (38 <= rsi <= 68)

        if pulled_back and bullish_bounce and rsi_healthy:
            sl = max(st_lower, close - (atr * 2.0))
            risk = max(close - sl, atr * 0.8)
            tp = close + (risk * _RR_RATIO)
            if _bracket_ok(close, sl, tp, "BUY"):
                return SignalResult("BUY", sl, tp, _STRATEGY_TYPE, _OOS_WIN_RATE_PRIOR, _RR_RATIO)
            return SignalResult(None, None, None, _STRATEGY_TYPE, _OOS_WIN_RATE_PRIOR, _RR_RATIO)

    # --- 3. Fresh Bearish Trend Flip (Breakout Entry) ---
    # Regime gate: a bearish flip inside a still-bull big-picture regime (EMA50
    # above EMA200) is a pullback, not a trend change — shorts stay blocked.
    if BLOCK_SHORTS_IN_BULL_REGIME and ema_50 > ema_200:
        return SignalResult(None, None, None, _STRATEGY_TYPE, _OOS_WIN_RATE_PRIOR, _RR_RATIO)
    if st_now == False and st_prev == True and close < ema_200:
        sl = min(st_upper, close + (atr * 2.0))
        risk = max(sl - close, atr * 0.8)
        tp = close - (risk * _RR_RATIO)
        if _bracket_ok(close, sl, tp, "SELL"):
            return SignalResult("SELL", sl, tp, _STRATEGY_TYPE, _OOS_WIN_RATE_PRIOR, _RR_RATIO)
        return SignalResult(None, None, None, _STRATEGY_TYPE, _OOS_WIN_RATE_PRIOR, _RR_RATIO)

    # --- 4. Bearish Trend Continuation / Dynamic Pullback Entry ---
    # Same regime gate as section 3: full bear regime required for shorts.
    if BLOCK_SHORTS_IN_BULL_REGIME and ema_50 > ema_200:
        return SignalResult(None, None, None, _STRATEGY_TYPE, _OOS_WIN_RATE_PRIOR, _RR_RATIO)
    # When established in a downtrend (Supertrend False for >1 bar, price below 200 EMA & EMA21 <= EMA50)
    if st_now == False and st_prev == False and close < ema_200 and ema_21 <= ema_50:
        # Price rallied to test EMA21 or EMA50 resistance during this candle or prev candle
        pulled_back = (high >= ema_21 * 0.998 or prev_high >= ema_21 * 0.998)
        # Closed bearish (red candle rejecting back down below EMA21)
        bearish_bounce = (close < open_p) and (close <= ema_21 * 1.002)
        # Healthy momentum (not oversold, resetting from resistance)
        rsi_healthy = (32 <= rsi <= 62)

        if pulled_back and bearish_bounce and rsi_healthy:
            sl = min(st_upper, close + (atr * 2.0))
            risk = max(sl - close, atr * 0.8)
            tp = close - (risk * _RR_RATIO)
            if _bracket_ok(close, sl, tp, "SELL"):
                return SignalResult("SELL", sl, tp, _STRATEGY_TYPE, _OOS_WIN_RATE_PRIOR, _RR_RATIO)
            return SignalResult(None, None, None, _STRATEGY_TYPE, _OOS_WIN_RATE_PRIOR, _RR_RATIO)

    return SignalResult(None, None, None, _STRATEGY_TYPE, _OOS_WIN_RATE_PRIOR, _RR_RATIO)
